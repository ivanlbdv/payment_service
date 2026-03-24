import requests
from django.core.exceptions import ValidationError
from django.db import models


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

    def deposit(self):
        if self.status != self.Status.PENDING:
            raise ValueError('Платеж уже обработан')

        if self.type == self.Type.ACQUIRING:
            bank_response = self._call_bank_api_acquiring_start()
            if not bank_response['success']:
                self.status = self.Status.FAILED
                self.save()
                raise Exception(f'Ошибка создания платежа в банке: {bank_response["error"]}')
            self.bank_payment_id = bank_response['payment_id']

        self.status = self.Status.COMPLETED
        self.save()
        self.order.update_status()

    def refund(self):
        if self.status != self.Status.COMPLETED:
            raise ValueError('Можно вернуть только завершенные платежи')

        self.status = self.Status.REFUNDED
        self.save()
        self.order.update_status()

    def _call_bank_api_acquiring_start(self):
        try:
            response = requests.post(
                'https://bank.api/acquiring_start',
                json={
                    'order_id': self.order.id,
                    'amount': float(self.amount)
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'payment_id': data['payment_id']}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def __str__(self):
        return f'Payment {self.id} - {self.amount} - {self.get_status_display()}'
