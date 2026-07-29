"""Seed idempotent demo data.

Seeds: one Shop, its AppSetting, an owner, a manager, two karigar accounts with
profiles + opening balances, a few ornaments, gold/cash ledger entries, and
bandaki (gold-loan) customers with loans.

Run:  python manage.py seed_demo
"""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AppSetting, CalendarPreference, Role, Shop, User
from apps.bandaki.models import BandakiCustomer, BandakiLoan, InterestPeriod
from apps.ledger.models import (
    CashEntry,
    Direction,
    GoldEntry,
    KarigarProfile,
    Ornament,
)

DEMO_PASSWORD = "Karigar@123"

DEMO_USERS = [
    {"username": "owner", "full_name": "Shop Owner", "email": "owner@karigar.local", "role": Role.OWNER, "is_staff": True, "is_superuser": True},
    {"username": "manager", "full_name": "Shop Manager", "email": "manager@karigar.local", "role": Role.MANAGER},
    {"username": "karigar1", "full_name": "Ram Bahadur", "email": "karigar1@karigar.local", "role": Role.KARIGAR},
    {"username": "karigar2", "full_name": "Sita Devi", "email": "karigar2@karigar.local", "role": Role.KARIGAR},
]

# Bandaki (gold-loan) customers. Keyed by name — the seed is idempotent on name,
# so re-running never duplicates a customer.
BANDAKI_CUSTOMERS = [
    {"name": "Hari Prasad Sharma", "phone": "+977-9841000001", "location": "Ason, Kathmandu"},
    {"name": "Kamala Shrestha", "phone": "+977-9841000002", "location": "Patan, Lalitpur"},
    {"name": "Bikash Tamang", "phone": "+977-9841000003", "location": "Bhaktapur"},
    {"name": "Sunita Maharjan", "phone": "+977-9841000004", "location": "Kirtipur"},
    {"name": "Rajesh Gurung", "phone": "+977-9841000005", "location": "Thamel, Kathmandu"},
    {"name": "Gita Adhikari", "phone": "+977-9841000006", "location": "Baneshwor, Kathmandu"},
    {"name": "Nabin Karki", "phone": "+977-9841000007", "location": "Chabahil, Kathmandu"},
    {"name": "Laxmi Bhandari", "phone": "+977-9841000008", "location": "Pulchowk, Lalitpur"},
    {"name": "Deepak Thapa", "phone": "+977-9841000009", "location": "Balaju, Kathmandu"},
    {"name": "Sarita Rai", "phone": "+977-9841000010", "location": "Boudha, Kathmandu"},
    # Two inactive customers so the UI's active/inactive filter has something
    # to show on both sides.
    {"name": "Mohan Lal Newar", "phone": "+977-9841000011", "location": "Jhamsikhel, Lalitpur", "is_active": False},
    {"name": "Bishnu Kumari Dangol", "phone": "+977-9841000012", "location": "Sanepa, Lalitpur", "is_active": False},
]

BANDAKI_REMARKS = [
    "", "", "Gold chain pledged.", "Bangles pledged (2 pcs).",
    "Earrings + ring pledged.", "Renewed from an older loan.",
    "Necklace pledged, 22kt.", "Partial repayment expected next month.",
]


class Command(BaseCommand):
    help = "Seed idempotent demo data (shop, users, settings)."

    @transaction.atomic
    def handle(self, *args, **options):
        shop, created = Shop.objects.get_or_create(
            name="Kanchan Jewellers",
            defaults={
                "address": "New Road, Kathmandu",
                "contact": "+977-1-4000000",
            },
        )
        self.stdout.write(f"Shop: {shop.name} ({'created' if created else 'exists'})")

        AppSetting.objects.get_or_create(
            shop=shop,
            defaults={"calendar_preference": CalendarPreference.BS},
        )

        for spec in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "full_name": spec["full_name"],
                    "email": spec["email"],
                    "role": spec["role"],
                    "shop": shop,
                    "is_staff": spec.get("is_staff", False),
                    "is_superuser": spec.get("is_superuser", False),
                    "is_active": True,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"  + {user.username} ({user.role})")
                )
            else:
                self.stdout.write(f"  = {user.username} exists")

        owner = User.objects.get(username="owner")

        # --- Ornaments ---
        ornaments = {}
        for name in ["Gold", "Ring", "Chain", "Bangle", "Earring", "Necklace"]:
            orn, _ = Ornament.objects.get_or_create(shop=shop, name=name)
            ornaments[name] = orn
        self.stdout.write(f"Ornaments: {', '.join(ornaments)}")

        # --- Karigar profiles with opening balances ---
        profiles = {}
        profile_specs = {
            "karigar1": {
                "phone": "+977-9800000001",
                "location": "Ason, Kathmandu",
                # Opening: karigar already holds 5.000 g (Dr) and owes nothing in cash.
                "opening_gold_g": Decimal("5.000"),
                "opening_cash_npr": Decimal("0.00"),
            },
            "karigar2": {
                "phone": "+977-9800000002",
                "location": "Patan, Lalitpur",
                # Opening: shop owes 2000 cash (Cr) -> negative.
                "opening_gold_g": Decimal("0.000"),
                "opening_cash_npr": Decimal("-2000.00"),
            },
        }
        for username, spec in profile_specs.items():
            user = User.objects.get(username=username)
            profile, _ = KarigarProfile.objects.get_or_create(
                user=user,
                defaults={
                    "shop": shop,
                    "full_name": user.full_name,
                    "phone": spec["phone"],
                    "location": spec["location"],
                    "opening_gold_g": spec["opening_gold_g"],
                    "opening_cash_npr": spec["opening_cash_npr"],
                    "joined_date": datetime.date(2024, 1, 15),
                    "plain_password": DEMO_PASSWORD,
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
            profiles[username] = profile
        self.stdout.write(f"Karigar profiles: {', '.join(profiles)}")

        # --- Sample gold/cash entries (only if none exist yet) ---
        if not GoldEntry.objects.filter(shop=shop).exists():
            k1 = profiles["karigar1"]
            # Issue 24kt 20g (Dr), receive a 22kt 18g chain (Cr), both tagged
            # with the same job number written on the shop's paperwork.
            GoldEntry.objects.create(
                shop=shop, order_number="ORD-1001", karigar=k1, direction=Direction.DR,
                gross_weight_g=Decimal("20.000"), carat=24,
                remarks="Issued for chain.", entry_date=datetime.date(2024, 2, 1),
                created_by=owner, updated_by=owner,
            )
            GoldEntry.objects.create(
                shop=shop, order_number="ORD-1001", karigar=k1, direction=Direction.CR,
                gross_weight_g=Decimal("18.000"), carat=22,
                ornament=ornaments["Chain"], remarks="Chain received.",
                entry_date=datetime.date(2024, 2, 10),
                created_by=owner, updated_by=owner,
            )
            # Cash advance of 5000 (Dr) to karigar2.
            CashEntry.objects.create(
                shop=shop, karigar=profiles["karigar2"], direction=Direction.DR,
                amount_npr=Decimal("5000.00"), remarks="Advance.",
                entry_date=datetime.date(2024, 2, 5),
                created_by=owner, updated_by=owner,
            )
            self.stdout.write("Sample gold/cash entries created.")

        # --- Bulk demo data: >=100 gold and >=100 cash entries ---
        self._bulk_entries(shop, owner, profiles, ornaments)

        # --- Bandaki: gold-loan customers and their loans ---
        self._bandaki(shop, owner)

        self.stdout.write(self.style.SUCCESS("\nSeed complete."))
        self.stdout.write(f"All demo users share the password: {DEMO_PASSWORD}")
        self.stdout.write("Logins: owner / manager / karigar1 / karigar2")

    def _bulk_entries(self, shop, owner, profiles, ornaments, gold_target=100, cash_target=100):
        """Generate demo volume: >= gold_target gold and cash_target cash
        entries spread across karigars and a year of dates. Idempotent — only
        tops up to the target so re-running doesn't keep piling on."""
        rng = random.Random(42)  # deterministic
        base = datetime.date(2024, 1, 1)
        karigars = list(profiles.values())
        ornament_list = list(ornaments.values())
        carats = [22, 24]

        # A pool of job numbers to tag some entries with. Just labels — there
        # is no order record behind them.
        order_numbers = [f"ORD-{2000 + n}" for n in range(1, 11)]

        gold_needed = max(0, gold_target - GoldEntry.objects.filter(shop=shop).count())
        for i in range(gold_needed):
            direction = Direction.DR if i % 2 == 0 else Direction.CR
            is_cr = direction == Direction.CR
            GoldEntry.objects.create(
                shop=shop,
                karigar=rng.choice(karigars),
                order_number=rng.choice(order_numbers) if rng.random() < 0.6 else "",
                direction=direction,
                gross_weight_g=Decimal(f"{rng.uniform(2, 60):.3f}"),
                carat=rng.choice(carats),
                ornament=rng.choice(ornament_list) if is_cr else None,
                remarks=rng.choice(["", "", "Repair", "New order", "Adjustment", "Return"]),
                entry_date=base + datetime.timedelta(days=rng.randint(0, 364)),
                created_by=owner, updated_by=owner,
            )
        if gold_needed:
            self.stdout.write(f"Bulk gold entries added: {gold_needed}")

        cash_needed = max(0, cash_target - CashEntry.objects.filter(shop=shop).count())
        for i in range(cash_needed):
            direction = Direction.DR if i % 2 == 0 else Direction.CR
            CashEntry.objects.create(
                shop=shop,
                karigar=rng.choice(karigars),
                order_number=rng.choice(order_numbers) if rng.random() < 0.3 else "",
                direction=direction,
                amount_npr=Decimal(f"{rng.randint(5, 400) * 50}.00"),
                remarks=rng.choice(["", "", "Advance", "Payment", "Settlement", "Wages"]),
                entry_date=base + datetime.timedelta(days=rng.randint(0, 364)),
                created_by=owner, updated_by=owner,
            )
        if cash_needed:
            self.stdout.write(f"Bulk cash entries added: {cash_needed}")

    def _bandaki(self, shop, owner, loan_target=40):
        """Seed bandaki customers and loans.

        Loan dates are relative to **today**, not fixed calendar dates: interest
        accrues from ``loan_date`` on every read, so anchoring to today keeps the
        demo showing a realistic spread of accrued amounts however long after
        seeding the data is looked at.

        Idempotent — customers are matched on name, and loans only top up to
        ``loan_target`` so re-running doesn't keep piling on.
        """
        rng = random.Random(7)  # deterministic
        today = timezone.localdate()

        customers = []
        created_count = 0
        for spec in BANDAKI_CUSTOMERS:
            customer, created = BandakiCustomer.objects.get_or_create(
                shop=shop,
                name=spec["name"],
                defaults={
                    "phone": spec["phone"],
                    "location": spec["location"],
                    "remarks": spec.get("remarks", ""),
                    "is_active": spec.get("is_active", True),
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
            customers.append(customer)
            created_count += int(created)
        self.stdout.write(
            f"Bandaki customers: {len(customers)} ({created_count} created)"
        )

        loans_needed = max(0, loan_target - BandakiLoan.objects.filter(shop=shop).count())
        for i in range(loans_needed):
            customer = customers[i % len(customers)] if i < len(customers) else rng.choice(customers)
            period = (
                InterestPeriod.MONTHLY if rng.random() < 0.75 else InterestPeriod.YEARLY
            )
            # Monthly loans quote ~1-3% per month; yearly ones ~12-24% per year.
            if period == InterestPeriod.MONTHLY:
                rate = Decimal(f"{rng.uniform(1.0, 3.0):.3f}")
            else:
                rate = Decimal(f"{rng.uniform(12.0, 24.0):.3f}")
            BandakiLoan.objects.create(
                shop=shop,
                customer=customer,
                # Spread over the last two years so accrued interest varies from
                # a few days' worth up to a couple of years'.
                loan_date=today - datetime.timedelta(days=rng.randint(3, 730)),
                gross_amount=Decimal(f"{rng.randint(10, 600) * 500}.00"),
                interest_rate=rate,
                interest_period=period,
                remarks=rng.choice(BANDAKI_REMARKS),
                # A fifth are already repaid/closed, so the active filter and the
                # history view both have material.
                is_active=rng.random() >= 0.2,
                created_by=owner,
                updated_by=owner,
            )
        if loans_needed:
            self.stdout.write(f"Bandaki loans added: {loans_needed}")
        else:
            self.stdout.write("Bandaki loans already at target.")
