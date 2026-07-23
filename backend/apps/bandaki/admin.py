from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BandakiCustomer, BandakiLoan


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
