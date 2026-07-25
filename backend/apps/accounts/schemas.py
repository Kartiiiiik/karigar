from datetime import datetime

from ninja import Schema


class UserOut(Schema):
    id: int
    username: str
    email: str | None = None
    full_name: str = ""
    role: str
    shop: int | None = None
    is_active: bool
    date_joined: datetime

    @staticmethod
    def resolve_shop(obj):
        return obj.shop_id


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    access: str
    refresh: str
    user: UserOut


class RefreshIn(Schema):
    refresh: str


class AccessOut(Schema):
    access: str
    refresh: str


class ChangePasswordIn(Schema):
    old_password: str
    new_password: str


class ManagerCreateIn(Schema):
    username: str
    password: str
    full_name: str = ""
    email: str | None = None


class ManagerUpdateIn(Schema):
    full_name: str | None = None
    email: str | None = None
    is_active: bool | None = None


class AppSettingSchema(Schema):
    calendar_preference: str
    date_format: str = "DMY_TEXT"


class AppSettingPatch(Schema):
    calendar_preference: str | None = None
    date_format: str | None = None


class DetailOut(Schema):
    detail: str


class SubscriptionStatusOut(Schema):
    active: bool
    end_date: str | None = None  # AD ISO date; frontend converts for BS display
    days_remaining: int = 0
    message: str = ""
