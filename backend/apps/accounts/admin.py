from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import AppSetting, Shop, Subscription, User


# ---------------------------------------------------------------------------
# Shared display helper for subscription status
# ---------------------------------------------------------------------------
def _status_label(sub):
    if not sub:
        return "No subscription"
    return f"Active ({sub.days_remaining} days left)" if sub.is_active else "Expired"


# ---------------------------------------------------------------------------
# Inlines on the Shop page (single-screen provisioning overview)
# ---------------------------------------------------------------------------
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0
    fields = ("start_date", "end_date", "plan", "notes", "status_readonly")
    readonly_fields = ("status_readonly",)

    @admin.display(description="Computed status")
    def status_readonly(self, obj):
        return _status_label(obj)


class ShopUserInline(admin.TabularInline):
    """Read-only roster of the shop's users. User creation stays in the User
    admin (password handling), but this gives a single-screen overview."""

    model = User
    extra = 0
    can_delete = False
    fields = ("username", "full_name", "role", "is_active")
    readonly_fields = ("username", "full_name", "role", "is_active")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "email", "role", "shop", "is_active")
    list_filter = ("role", "is_active", "shop")
    search_fields = ("username", "email", "full_name")
    ordering = ("username",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("full_name", "email")}),
        ("Role & shop", {"fields": ("role", "shop")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "description": (
                "Provision a shop user: pick the <b>role</b> (owner/manager/karigar), "
                "the <b>shop</b> they belong to, and set a <b>password</b> to share "
                "with them out-of-band. A shop is required for every non-superuser. "
                "The password is stored hashed — you cannot read it back later, so "
                "note it before saving."
            ),
            "fields": ("username", "full_name", "role", "shop", "password1", "password2"),
        }),
    )


# ---------------------------------------------------------------------------
# Shop
# ---------------------------------------------------------------------------
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "contact", "sub_status", "sub_end_date", "user_count", "created_at")
    search_fields = ("name", "contact")
    ordering = ("name",)
    inlines = [SubscriptionInline, ShopUserInline]

    @admin.display(description="Subscription")
    def sub_status(self, obj):
        return _status_label(getattr(obj, "subscription", None))

    @admin.display(description="Ends")
    def sub_end_date(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.end_date if sub else "—"

    @admin.display(description="Users")
    def user_count(self, obj):
        return obj.users.count()


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("shop", "plan", "start_date", "end_date", "status", "days_left")
    list_filter = ("plan",)
    search_fields = ("shop__name",)
    autocomplete_fields = ("shop",)
    readonly_fields = ("status", "days_left", "created_at", "updated_at")
    fields = ("shop", "plan", "start_date", "end_date", "status", "days_left", "notes", "created_at", "updated_at")
    actions = ("extend_30", "extend_90", "extend_365")

    @admin.display(description="Status")
    def status(self, obj):
        return _status_label(obj)

    @admin.display(description="Days remaining")
    def days_left(self, obj):
        return obj.days_remaining

    # --- Extend actions: reactivate from today if already expired ----------
    def _extend(self, request, queryset, days):
        today = timezone.localdate()
        count = 0
        for sub in queryset:
            base = sub.end_date if sub.end_date >= today else today
            sub.end_date = base + timedelta(days=days)
            sub.save(update_fields=["end_date", "updated_at"])
            count += 1
        self.message_user(request, f"Extended {count} subscription(s) by {days} days.")

    @admin.action(description="Extend by 30 days")
    def extend_30(self, request, queryset):
        self._extend(request, queryset, 30)

    @admin.action(description="Extend by 90 days")
    def extend_90(self, request, queryset):
        self._extend(request, queryset, 90)

    @admin.action(description="Extend by 365 days")
    def extend_365(self, request, queryset):
        self._extend(request, queryset, 365)


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("shop", "calendar_preference")
