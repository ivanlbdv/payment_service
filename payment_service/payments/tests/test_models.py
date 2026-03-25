from django.core.exceptions import ValidationError
from django.test import TestCase
from payments.models import Order, Payment


class OrderModelTest(TestCase):
    def setUp(self):
        self.order = Order.objects.create(amount=1000)

    def test_order_creation(self):
        """Проверка создания заказа"""
        self.assertEqual(self.order.amount, 1000)
        self.assertEqual(self.order.status, Order.PaymentStatus.UNPAID)

    def test_update_status_unpaid(self):
        """Статус 'не оплачен' при отсутствии платежей"""
        self.order.update_status()
        self.assertEqual(self.order.status, Order.PaymentStatus.UNPAID)

    def test_update_status_partially_paid(self):
        """Статус 'частично оплачен' при частичном платеже"""
        Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        self.order.update_status()
        self.assertEqual(self.order.status, Order.PaymentStatus.PARTIALLY_PAID)

    def test_update_status_paid(self):
        """Статус 'оплачен' при полной оплате"""
        Payment.objects.create(
            order=self.order,
            amount=1000,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        self.order.update_status()
        self.assertEqual(self.order.status, Order.PaymentStatus.PAID)


class PaymentModelTest(TestCase):
    def setUp(self):
        self.order = Order.objects.create(amount=1000)

    def test_payment_creation(self):
        """Проверка создания платежа"""
        payment = Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH
        )
        self.assertEqual(payment.amount, 500)
        self.assertEqual(payment.type, Payment.Type.CASH)
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_clean_amount_exceeds_order(self):
        """Валидация: сумма платежа не может превышать сумму заказа"""
        with self.assertRaises(ValidationError):
            payment = Payment(
                order=self.order,
                amount=1500,
                type=Payment.Type.CASH
            )
            payment.clean()

    def test_clean_total_exceeds_order(self):
        """Валидация: общая сумма платежей не может превышать сумму заказа"""
        Payment.objects.create(
            order=self.order,
            amount=800,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        with self.assertRaises(ValidationError):
            payment = Payment(
                order=self.order,
                amount=300,
                type=Payment.Type.CASH
            )
            payment.clean()

    def test_deposit_cash(self):
        """Депозит для наличных платежей"""
        payment = Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH
        )
        payment.deposit()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(payment.bank_status, 'completed')

    def test_refund_completed_payment(self):
        """Возврат завершенного платежа"""
        payment = Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        payment.refund()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
