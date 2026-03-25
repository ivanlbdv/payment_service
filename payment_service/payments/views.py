from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (OpenApiParameter, OpenApiResponse,
                                   extend_schema, inline_serializer)
from rest_framework import status
from rest_framework.decorators import api_view, schema
from rest_framework.response import Response

from .models import Order, Payment
from .serializers import (OrderSerializer, PaymentCreateSerializer,
                          PaymentRefundSerializer, PaymentSerializer)


@extend_schema(
    summary="Получить информацию о заказе",
    description="Возвращает детали заказа с информацией обо всех связанных платежах и статусами синхронизации с банком",
    responses={
        200: OrderSerializer,
        404: OpenApiResponse(
            response=None,
            description="Заказ не найден"
        )
    },
    parameters=[
        OpenApiParameter(
            name="order_id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID заказа"
        )
    ]
)
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


@extend_schema(
    summary="Создать новый платеж",
    description="Создает новый платеж для указанного заказа. Поддерживаются наличные и эквайринговые платежи",
    request=PaymentCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=inline_serializer(
                name='CreatePaymentResponse',
                fields={
                    'payment': PaymentSerializer,
                    'order': OrderSerializer
                }
            ),
            description="Платеж успешно создан"
        ),
        400: OpenApiResponse(
            response=None,
            description="Ошибка валидации данных"
        )
    },
    parameters=[
        OpenApiParameter(
            name="order_id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID заказа для создания платежа"
        )
    ]
)
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


@extend_schema(
    summary="Выполнить возврат платежа",
    description="Инициирует возврат завершенного платежа. Возврат возможен только для платежей со статусом 'completed'",
    request=PaymentRefundSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name='RefundPaymentResponse',
                fields={
                    'message': str,
                    'order': OrderSerializer
                }
            ),
            description="Возврат успешно выполнен"
        ),
        400: OpenApiResponse(
            response=None,
            description="Ошибка валидации или бизнес-логики"
        )
    }
)
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
