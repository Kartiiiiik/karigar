import datetime
from decimal import Decimal

import pytest

from apps.accounts.models import AppSetting, CalendarPreference, Role, Shop, User
from apps.common.dates import format_date
from apps.ledger.models import CashEntry, Direction, GoldEntry, KarigarProfile
from apps.reports.services import build_cash_report, build_gold_report


@pytest.fixture
def setup(db):
    shop = Shop.objects.create(name="Report Shop")
    AppSetting.objects.create(shop=shop, calendar_preference=CalendarPreference.AD)
    owner = User(username="o", role=Role.OWNER, shop=shop, is_staff=True, is_superuser=True)
    owner.set_password("Karigar@123")
    owner.save()
    ku = User(username="k", role=Role.KARIGAR, shop=shop)
    ku.set_password("Karigar@123")
    ku.save()
    profile = KarigarProfile.objects.create(
        user=ku, shop=shop, full_name="Ram",
        opening_gold_g=Decimal("5.000"), opening_cash_npr=Decimal("0.00"),
    )
    GoldEntry.objects.create(shop=shop, karigar=profile, direction=Direction.DR,
                             gross_weight_g=Decimal("20.000"), carat=24,
                             entry_date=datetime.date(2024, 2, 1), created_by=owner)
    GoldEntry.objects.create(shop=shop, karigar=profile, direction=Direction.CR,
                             gross_weight_g=Decimal("18.000"), carat=24,
                             entry_date=datetime.date(2024, 2, 10), created_by=owner)
    CashEntry.objects.create(shop=shop, karigar=profile, direction=Direction.DR,
                             amount_npr=Decimal("5000.00"),
                             entry_date=datetime.date(2024, 2, 5), created_by=owner)
    return {"shop": shop, "owner": owner, "profile": profile}


@pytest.mark.django_db
def test_gold_report_net_dr_cr_columns(setup):
    # Columns: Date, Karigar, Order, Gross, Carat, Net Dr (5), Net Cr (6), Ornament, Remarks
    report = build_gold_report(setup["shop"], karigar_id=setup["profile"].id)
    assert len(report["rows"]) == 2
    assert report["rows"][0][5] == "20.000" and report["rows"][0][6] == ""  # Dr entry
    assert report["rows"][1][6] == "18.000" and report["rows"][1][5] == ""  # Cr entry
    # Opening 5.000 Dr folded into the Net Dr column.
    assert report["opening_row"][5] == "5.000"
    # Totals: Net Dr = 5 opening + 20 = 25; Net Cr = 18.
    assert report["total_row"][5] == "25.000"
    assert report["total_row"][6] == "18.000"
    # Closing = 25 - 18 = 7 Dr.
    assert report["closing_row"][0] == "Closing (Dr)"
    assert report["closing_row"][5] == "7.000"


@pytest.mark.django_db
def test_cash_report_debit_credit_columns(setup):
    # Columns: Date, Karigar, Debit (2), Credit (3), Remarks
    report = build_cash_report(setup["shop"], karigar_id=setup["profile"].id)
    assert report["rows"][0][2] == "5000.00" and report["rows"][0][3] == ""
    assert report["total_row"][2] == "5000.00"   # opening 0 + 5000 debit
    assert report["closing_row"][0] == "Closing (Dr)"
    assert report["totals"]["dr"] == Decimal("5000.00")


@pytest.mark.django_db
def test_gold_report_date_filter(setup):
    report = build_gold_report(setup["shop"], date_from=datetime.date(2024, 2, 5))
    assert len(report["rows"]) == 1  # only the Feb 10 Cr entry


@pytest.mark.django_db
def test_excel_export_endpoint(api, setup):
    resp = api(setup["owner"]).get("/api/v1/reports/gold/", {"fmt": "excel"})
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/vnd.openxmlformats")
    assert resp.content[:2] == b"PK"  # xlsx is a zip


@pytest.mark.django_db
def test_report_requires_staff(api, setup):
    # A karigar cannot pull shop-wide reports.
    from apps.accounts.models import Role, User
    k = User(username="kk", role=Role.KARIGAR, shop=setup["shop"])
    k.set_password("Karigar@123")
    k.save()
    assert api(k).get("/api/v1/reports/gold/").status_code == 403


def test_bs_date_conversion_roundtrip():
    # 2024-02-10 AD → BS "28 Magh 2080" (format: "<day> <Month> <year>", no suffix).
    ad = datetime.date(2024, 2, 10)
    bs = format_date(ad, "BS")
    assert "Magh" in bs and bs.endswith("2080")
    assert not bs.endswith("BS")
    # AD in each configurable format.
    assert format_date(ad, "AD", "YMD") == "2024-02-10"
    assert format_date(ad, "AD", "DMY") == "10/02/2024"
    assert format_date(ad, "AD", "MDY") == "02/10/2024"
    assert format_date(ad, "AD", "DMY_TEXT") == "10 Feb 2024"
