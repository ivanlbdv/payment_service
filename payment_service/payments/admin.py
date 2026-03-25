from django.contrib import admin

from .models import Order, Payment


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'status', 'get_status_display')
    list_filter = ('status',)
    search_fields = ('id',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('amount', 'status')
        }),
    )

    @admin.display(description='Статус')
    def get_status_display(self, obj):
        return obj.get_status_display()


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'amount', 'type', 'status',
        'bank_payment_id', 'created_at', 'last_synced_at'
    )
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('id', 'bank_payment_id', 'order__id')
    readonly_fields = (
        'created_at', 'updated_at',
        'bank_status', 'bank_amount', 'bank_paid_at', 'last_synced_at'
    )
    raw_id_fields = ('order',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('order', 'amount', 'type', 'status')
        }),
        ('Информация от банка', {
            'fields': (
                'bank_payment_id', 'bank_status',
                'bank_amount', 'bank_paid_at', 'last_synced_at'
            ),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
