from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Order, Payment
from .serializers import (OrderSerializer, PaymentCreateSerializer,
                          PaymentRefundSerializer, PaymentSerializer)


@api_view(['GET'])
def order_detail(request, order_id):
    """Получение информации о заказе с платежами и статусами синхронизации"""
    order = get_object_or_404(Order, id=order_id)
    serializer = OrderSerializer(order)

    response_data = serializer.data

    for payment_data in response_data['payments']:
        payment = Payment.objects.get(id=payment_data['id'])
        sync_result = payment.sync_with_bank()

        if not sync_result['synced']:
            payment_data['sync_error'] = sync_result['error']
            payment_data['bank_error_type'] = sync_result.get('bank_error_type')

    return Response(response_data)


@api_view(['POST'])
def create_payment(request, order_id):
    """Создание нового платежа по заказу"""
    order = get_object_or_404(Order, id=order_id)

    serializer = PaymentCreateSerializer(
        data=request.data,
        context={'order': order}
    )
    if serializer.is_valid():
        payment = serializer.save()
        payment_serializer = PaymentSerializer(payment)
        order_serializer = OrderSerializer(order)

        return Response({
            'payment': payment_serializer.data,
            'order': order_serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def refund_payment(request):
    """Возврат платежа"""
    serializer = PaymentRefundSerializer(data=request.data)
    if serializer.is_valid():
        payment = serializer.save()
        order_serializer = OrderSerializer(payment.order)

        return Response({
            'message': 'Платеж успешно возвращен',
            'order': order_serializer.data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
