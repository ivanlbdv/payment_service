from django.db import models
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (OpenApiParameter, OpenApiResponse,
                                   extend_schema, inline_serializer)
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Order, Payment
from .serializers import (OrderSerializer, PaymentCreateSerializer,
                          PaymentRefundSerializer, PaymentSerializer)


@extend_schema(
    summary="Получить информацию о заказе",
    description="Возвращает детали заказа с информацией обо всех связанных платежах. "
                "Для актуальной синхронизации статусов используйте эндпоинт синхронизации.",
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
    """Получение информации о заказе с платежами"""
    order = get_object_or_404(
        Order.objects
        .prefetch_related(
            'payments'
        )
        .annotate(
            total_paid=models.Sum(
                'payments__amount',
                filter=models.Q(
                    payments__status=Payment.Status.COMPLETED
                )
            )
        ),
        id=order_id
    )
    serializer = OrderSerializer(order)
    return Response(serializer.data)


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


@extend_schema(
    summary="Синхронизировать платежи заказа с банком",
    description="Принудительно синхронизирует статусы всех платежей заказа с банком. "
                "Возвращает результаты синхронизации для каждого платежа.",
    responses={
        200: inline_serializer(
            name='SyncResult',
            fields={
                'results': serializers.ListField(child=serializers.DictField()),
                'synced_count': serializers.IntegerField(),
                'error_count': serializers.IntegerField()
            }
        ),
        404: OpenApiResponse(description="Заказ не найден")
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
@api_view(['POST'])
def sync_order_payments(request, order_id):
    """
    Принудительная синхронизация всех платежей заказа с банком.
    Обновляет статусы, суммы и даты оплаты из банковской системы.
    """
    order = get_object_or_404(Order, id=order_id)
    payments = order.payments.all()
    results = []
    synced_count = 0
    error_count = 0

    for payment in payments:
        sync_result = payment.sync_with_bank()
        results.append({
            'payment_id': payment.id,
            'synced': sync_result['synced'],
            'error': sync_result.get('error'),
            'bank_error_type': sync_result.get('bank_error_type'),
            'current_status': payment.status,
            'bank_status': payment.bank_status
        })

        if sync_result['synced']:
            synced_count += 1
        else:
            error_count += 1

    order.update_status()

    return Response({
        'results': results,
        'synced_count': synced_count,
        'error_count': error_count
    })
