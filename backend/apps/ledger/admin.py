from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import CashEntry, GoldEntry, KarigarProfile, Order, Ornament


@admin.register(Ornament)
class OrnamentAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("name",)


@admin.register(KarigarProfile)
class KarigarProfileAdmin(SimpleHistoryAdmin):
    list_display = ("full_name", "phone", "shop", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("full_name", "phone", "user__username")


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ("__str__", "karigar", "status", "created_at")
    list_filter = ("status", "shop")
    search_fields = ("order_number",)


@admin.register(GoldEntry)
class GoldEntryAdmin(SimpleHistoryAdmin):
    list_display = ("__str__", "karigar", "direction", "gross_weight_g", "carat", "net_weight_g", "entry_date")
    list_filter = ("direction", "carat", "shop")
    search_fields = ("remarks", "order__order_number")


@admin.register(CashEntry)
class CashEntryAdmin(SimpleHistoryAdmin):
    list_display = ("__str__", "karigar", "direction", "amount_npr", "entry_date")
    list_filter = ("direction", "shop")
    search_fields = ("remarks",)
