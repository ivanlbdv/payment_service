from django.urls import path

from . import views

urlpatterns = [
    path(
        'orders/<int:order_id>/',
        views.order_detail,
        name='order-detail'
    ),
    path(
        'orders/<int:order_id>/sync/',
        views.sync_order_payments,
        name='sync-order-payments'
    ),
    path(
        'orders/<int:order_id>/payments/',
        views.create_payment,
        name='create-payment'
    ),
    path(
        'payments/refund/',
        views.refund_payment,
        name='refund-payment'
    ),
]
