from django.db import models
from rest_framework import serializers

from .models import Order, Payment


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    type_display = serializers.CharField(
        source='get_type_display',
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'amount', 'type', 'type_display',
            'status', 'status_display', 'bank_payment_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'status',
            'bank_payment_id',
            'created_at',
            'updated_at'
        ]

    def validate(self, data):
        order = data['order']
        amount = data['amount']

        total_paid = order.payments.filter(
            status__in=[Payment.Status.COMPLETED, Payment.Status.REFUNDED]
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        if total_paid + amount > order.amount:
            raise serializers.ValidationError(
                'Общая сумма платежей превысит сумму заказа'
            )
        return data


class OrderSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    total_paid = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'amount', 'status', 'status_display',
            'total_paid', 'remaining_amount', 'payments'
        ]
        read_only_fields = [
            'status',
            'payments',
            'status_display',
            'total_paid',
            'remaining_amount'
        ]

    def get_total_paid(self, obj):
        """Возвращает общую сумму оплаченных платежей"""
        total_paid = obj.payments.filter(
            status=Payment.Status.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        return total_paid

    def get_remaining_amount(self, obj):
        """Возвращает оставшуюся к оплате сумму"""
        return obj.amount - self.get_total_paid(obj)


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01
    )
    type = serializers.ChoiceField(choices=Payment.Type.choices)

    def validate_amount(self, value):
        order = self.context['order']
        total_paid = order.payments.filter(
            status__in=[Payment.Status.COMPLETED, Payment.Status.REFUNDED]
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        remaining = order.amount - total_paid
        if value > remaining:
            raise serializers.ValidationError(
                f'Сумма платежа превышает доступную для оплаты. Осталось оплатить: {remaining}'
            )
        return value

    def create(self, validated_data):
        order = self.context['order']
        payment = Payment.objects.create(
            order=order,
            amount=validated_data['amount'],
            type=validated_data['type']
        )
        try:
            payment.deposit()
        except Exception as e:
            payment.delete()
            raise serializers.ValidationError(
                f'Ошибка при создании платежа: {str(e)}'
            )
        return payment


class PaymentRefundSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()

    def validate_payment_id(self, value):
        try:
            payment = Payment.objects.get(id=value)
        except Payment.DoesNotExist:
            raise serializers.ValidationError('Платеж не найден')

        if payment.status != Payment.Status.COMPLETED:
            raise serializers.ValidationError(
                'Возврат возможен только для завершенных платежей'
            )

        return value

    def save(self, **kwargs):
        payment_id = self.validated_data['payment_id']
        payment = Payment.objects.get(id=payment_id)
        payment.refund()
        return payment
