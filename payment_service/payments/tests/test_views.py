import json
from decimal import Decimal

from django.test import Client
from django.urls import reverse
from payments.models import Order, Payment
from rest_framework.test import APITestCase


class OrderViewsTest(APITestCase):
    def setUp(self):
        self.client = Client()
        self.order = Order.objects.create(amount=1000)
        Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        self.order.update_status()

    def test_order_detail_success(self):
        """Успешный запрос детализации заказа"""
        url = reverse('order-detail', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.order.id)
        self.assertEqual(response.data['amount'], '1000.00')
        self.assertEqual(response.data['status'], 'partially_paid')
        self.assertEqual(len(response.data['payments']), 1)

    def test_order_detail_not_found(self):
        """Заказ не найден"""
        url = reverse('order-detail', kwargs={'order_id': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class PaymentViewsTest(APITestCase):
    def setUp(self):
        self.client = Client()
        self.order = Order.objects.create(amount=1000)

    def test_create_payment_success(self):
        """Успешное создание платежа"""
        url = reverse('create-payment', kwargs={'order_id': self.order.id})
        data = {
            'amount': 500,
            'type': Payment.Type.CASH
        }
        response = self.client.generic(
            'POST',
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data['payment']['amount']), Decimal('500.00'))
        self.assertEqual(response.data['order']['status'], 'partially_paid')

    def test_create_payment_invalid_amount(self):
        """Ошибка создания платежа: сумма превышает оставшуюся"""
        Payment.objects.create(
            order=self.order,
            amount=800,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        self.order.update_status()

        url = reverse('create-payment', kwargs={'order_id': self.order.id})
        data = {
            'amount': 300,
            'type': Payment.Type.CASH
        }
        response = self.client.generic(
            'POST',
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        error_messages = str(response.data)
        self.assertIn('превышает доступную', error_messages)

    def test_refund_payment_success(self):
        """Успешный возврат платежа"""
        payment = Payment.objects.create(
            order=self.order,
            amount=500,
            type=Payment.Type.CASH,
            status=Payment.Status.COMPLETED
        )
        url = reverse('refund-payment')
        data = {'payment_id': payment.id}
        response = self.client.generic(
            'POST',
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Платеж успешно возвращен')
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

    def test_refund_payment_invalid(self):
        """Ошибка возврата: платеж не завершен"""
        pending_payment = Payment.objects.create(
            order=self.order,
            amount=200,
            type=Payment.Type.ACQUIRING,
            status=Payment.Status.PENDING
        )
        url = reverse('refund-payment')
        data = {'payment_id': pending_payment.id}
        response = self.client.generic(
            'POST',
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        error_messages = str(response.data)
        self.assertIn('только для завершенных', error_messages)
