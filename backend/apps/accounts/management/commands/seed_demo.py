"""Seed idempotent demo data.

Seeds: one Shop, its AppSetting, an owner, a manager, two karigar accounts with
profiles + opening balances, a few ornaments, and gold/cash ledger entries.

Run:  python manage.py seed_demo
"""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import AppSetting, CalendarPreference, Role, Shop, User
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
