import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class Order(models.Model):
    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Не оплачен'
        PARTIALLY_PAID = 'partially_paid', 'Частично оплачен'
        PAID = 'paid', 'Оплачен'

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID
    )

    def update_status(self):
        total_paid = self.payments.filter(
            status=Payment.Status.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        if total_paid >= self.amount:
            self.status = self.PaymentStatus.PAID
        elif total_paid > 0:
            self.status = self.PaymentStatus.PARTIALLY_PAID
        else:
            self.status = self.PaymentStatus.UNPAID

        self.save()

    def __str__(self):
        return f'Order {self.id} - {self.get_status_display()}'


class Payment(models.Model):
    class Type(models.TextChoices):
        CASH = 'cash', 'Наличные'
        ACQUIRING = 'acquiring', 'Эквайринг'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает подтверждения'
        COMPLETED = 'completed', 'Завершен'
        REFUNDED = 'refunded', 'Возвращен'
        FAILED = 'failed', 'Ошибка'

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    bank_payment_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bank_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Статус платежа в системе банка"
    )
    last_synced_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Последняя синхронизация статуса с банком"
    )
    bank_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Сумма платежа в системе банка"
    )
    bank_paid_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Дата и время оплаты в системе банка"
    )

    def clean(self):
        super().clean()
        if self.amount > self.order.amount:
            raise ValidationError(
                'Сумма платежа не может превышать сумму заказа'
            )

        total_paid = self.order.payments.filter(
            status__in=[Payment.Status.COMPLETED, Payment.Status.REFUNDED]
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        if total_paid + self.amount > self.order.amount:
            raise ValidationError(
                'Общая сумма платежей превышает сумму заказа'
            )

    def _call_bank_api_acquiring_start(self):
        try:
            response = requests.post(
                'http://bank.api/acquiring_start',
                json={
                    'order_id': self.order.id,
                    'amount': float(self.amount)
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self.bank_payment_id = data['payment_id']
            self.bank_status = 'pending'
            self.last_synced_at = timezone.now()
            self.save(update_fields=['bank_payment_id', 'bank_status', 'last_synced_at'])
            return {'success': True, 'payment_id': data['payment_id']}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def _call_bank_api_refund(self):
        """Вызов API банка для возврата платежа"""
        if not self.bank_payment_id:
            return {'success': False, 'error': 'Нет ID платежа в банке'}

        try:
            response = requests.post(
                'http://bank.api/acquiring_refund',
                json={'payment_id': self.bank_payment_id},
                timeout=30
            )
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def _check_bank_payment_status(self):
        """Проверка статуса платежа в банке через acquiring_check"""
        if not self.bank_payment_id:
            return {
                'success': False,
                'error': 'Нет ID платежа в банке',
                'bank_error_type': 'missing_payment_id'
            }

        try:
            response = requests.get(
                f'http://bank.api/acquiring_check?payment_id={self.bank_payment_id}',
                timeout=30
            )

            if response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Платеж не найден в системе банка',
                    'bank_error_type': 'payment_not_found'
                }

            response.raise_for_status()
            data = response.json()

            self.bank_status = data.get('status')
            self.bank_amount = data.get('amount')

            bank_paid_at_str = data.get('paid_at')
            if bank_paid_at_str:
                self.bank_paid_at = parse_datetime(bank_paid_at_str)

            self.last_synced_at = timezone.now()

            self.save(update_fields=[
                'bank_status',
                'bank_amount',
                'bank_paid_at',
                'last_synced_at'
            ])

            return {
                'success': True,
                'data': data
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Ошибка связи с банком: {str(e)}',
                'bank_error_type': 'connection_error'
            }
        except (KeyError, ValueError, TypeError) as e:
            return {
                'success': False,
                'error': f'Ошибка парсинга ответа банка: {str(e)}',
                'bank_error_type': 'parsing_error'
            }

    def sync_with_bank(self):
        """Синхронизация статуса с банком и обновление локального статуса"""
        bank_data = self._check_bank_payment_status()

        if not bank_data['success']:
            error_message = bank_data['error']

            self.bank_status = 'error'
            self.last_synced_at = timezone.now()
            self.save(update_fields=['bank_status', 'last_synced_at'])

            if self.status not in [self.Status.FAILED, self.Status.REFUNDED]:
                self.status = self.Status.FAILED
                self.save()
                self.order.update_status()

            return {
                'synced': False,
                'error': error_message,
                'bank_error_type': bank_data.get('bank_error_type')
            }

        data = bank_data['data']
        status_changed = False

        if data['status'] == 'completed' and self.status != self.Status.COMPLETED:
            self.status = self.Status.COMPLETED
            status_changed = True
        elif data['status'] == 'failed' and self.status not in [self.Status.FAILED, self.Status.REFUNDED]:
            self.status = self.Status.FAILED
            status_changed = True

        if status_changed:
            self.save()
            self.order.update_status()

        if self.bank_amount is not None and self.bank_amount != self.amount:
            print(f'Предупреждение: расхождение сумм для платежа {self.id}. '
                f'Локальная: {self.amount}, в банке: {self.bank_amount}')

        return {
            'synced': True,
            'data': data
        }

    def deposit(self):
        if self.status != self.Status.PENDING:
            raise ValueError('Платеж уже обработан')

        if self.type == self.Type.ACQUIRING:
            bank_response = self._call_bank_api_acquiring_start()
            if not bank_response['success']:
                self.status = self.Status.FAILED
                self.save()
                raise Exception(
                    f'Ошибка создания платежа в банке: {bank_response["error"]}'
                )
        elif self.type == self.Type.CASH:
            self.status = self.Status.COMPLETED
            self.bank_status = 'completed'
            self.bank_amount = self.amount
            self.bank_paid_at = timezone.now()
            self.last_synced_at = timezone.now()
            self.save(update_fields=[
                'status', 'bank_status', 'bank_amount',
                'bank_paid_at', 'last_synced_at'
            ])
        else:
            raise ValueError(f'Неподдерживаемый тип платежа: {self.type}')

        self.order.update_status()

    def refund(self):
        if self.status != self.Status.COMPLETED:
            raise ValueError('Можно вернуть только завершенные платежи')

        if self.type == self.Type.ACQUIRING and self.bank_payment_id:
            bank_response = self._call_bank_api_refund()
            if not bank_response['success']:
                raise Exception(
                    f'Ошибка возврата платежа в банке: {bank_response["error"]}'
                )

        self.status = self.Status.REFUNDED
        self.save()
        self.order.update_status()

    def __str__(self):
        return f'Payment {self.id} - {self.amount} - {self.get_status_display()}'
