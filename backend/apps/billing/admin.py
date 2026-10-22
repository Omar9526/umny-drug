from django.contrib import admin

from .models import Payment, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("family", "plan", "status", "started_at", "current_period_end")
    list_filter = ("plan", "status")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("subscription", "amount", "currency", "status", "provider", "paid_at")
    list_filter = ("status", "provider")
    readonly_fields = ("idempotency_key",)
