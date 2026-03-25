from decimal import Decimal

from django.test import TestCase
from payments.models import Order, Payment
from payments.serializers import (OrderSerializer, PaymentCreateSerializer,
                                  PaymentRefundSerializer)


class OrderSerializerTest(TestCase):
    def setUp(self):
        self.order = Order.objects.create(amount=1000)
        Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        self.order.update_status()

    def test_order_serializer_data(self):
        """Проверка данных сериализатора заказа"""
        serializer = OrderSerializer(self.order)
        data = serializer.data
        self.assertEqual(Decimal(data['amount']), Decimal('1000.00'))
        self.assertEqual(data['status'], 'partially_paid')
        self.assertEqual(Decimal(data['total_paid']), Decimal('500.00'))
        self.assertEqual(Decimal(data['remaining_amount']), Decimal('500.00'))
        self.assertEqual(len(data['payments']), 1)


class PaymentCreateSerializerTest(TestCase):
    def setUp(self):
        self.order = Order.objects.create(amount=1000)

    def test_valid_payment_creation(self):
        """Валидные данные для создания платежа"""
        data = {'amount': 500, 'type': Payment.Type.CASH}
        serializer = PaymentCreateSerializer(data=data, context={'order': self.order})
        self.assertTrue(serializer.is_valid())

    def test_invalid_amount_exceeds_remaining(self):
        """Ошибка: сумма платежа превышает оставшуюся сумму"""
        Payment.objects.create(
            order=self.order,
            amount=800,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        data = {'amount': 300, 'type': Payment.Type.CASH}
        serializer = PaymentCreateSerializer(data=data, context={'order': self.order})
        self.assertFalse(serializer.is_valid())
        self.assertIn('превышает доступную', str(serializer.errors['amount']))

    def test_create_payment(self):
        """Создание платежа через сериализатор"""
        data = {'amount': 500, 'type': Payment.Type.CASH}
        serializer = PaymentCreateSerializer(data=data, context={'order': self.order})
        self.assertTrue(serializer.is_valid())
        payment = serializer.save()
        self.assertEqual(payment.amount, 500)
        self.assertEqual(payment.status, Payment.Status.COMPLETED)


class PaymentRefundSerializerTest(TestCase):
    def setUp(self):
        self.order = Order.objects.create(amount=1000)
        self.payment = Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )

    def test_valid_refund(self):
        """Валидный запрос на возврат"""
        data = {'payment_id': self.payment.id}
        serializer = PaymentRefundSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_refund_not_completed(self):
        """Ошибка: возврат для незавершенного платежа"""
        incomplete_payment = Payment.objects.create(
            order=self.order,
            amount=200,
            type=Payment.Type.ACQUIRING,
            status=Payment.Status.PENDING
        )
        data = {'payment_id': incomplete_payment.id}
        serializer = PaymentRefundSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('Возврат возможен только для завершенных платежей', str(serializer.errors['payment_id']))

    def test_invalid_refund_payment_not_found(self):
        """Ошибка: платеж не найден"""
        data = {'payment_id': 9999}
        serializer = PaymentRefundSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('Платеж не найден', str(serializer.errors['payment_id']))
