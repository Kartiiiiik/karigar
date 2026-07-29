from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BandakiCustomer, BandakiItem, BandakiLoan, BandakiPayment


@admin.register(BandakiCustomer)
class BandakiCustomerAdmin(SimpleHistoryAdmin):
    list_display = ("name", "phone", "location", "shop", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("name", "phone", "location")


@admin.register(BandakiLoan)
class BandakiLoanAdmin(SimpleHistoryAdmin):
    list_display = (
        "__str__", "customer", "loan_date", "gross_amount",
        "interest_rate", "interest_period", "is_active",
    )
    list_filter = ("interest_period", "is_active", "shop")
    search_fields = ("customer__name", "remarks")


@admin.register(BandakiItem)
class BandakiItemAdmin(SimpleHistoryAdmin):
    list_display = (
        "loan", "ornament", "quantity", "gross_weight_g", "carat",
        "net_weight_g", "returned_on",
    )
    list_filter = ("shop", "carat", "returned_on")
    search_fields = ("loan__customer__name", "description", "ornament__name")
    readonly_fields = ("net_weight_g",)


@admin.register(BandakiPayment)
class BandakiPaymentAdmin(SimpleHistoryAdmin):
    list_display = ("loan", "payment_date", "amount", "shop")
    list_filter = ("shop", "payment_date")
    search_fields = ("loan__customer__name", "remarks")
    date_hierarchy = "payment_date"
