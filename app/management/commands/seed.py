"""Fill a development database with fictional but coherent data.

Two people, Alice and Bruno, with their own accounts and a joint one, six months
of history (salaries, rent, subscriptions, groceries, outings), recurring rules
and budgets. The same command on the same day always produces the same data.
"""
import calendar
import datetime
import random
from typing import NamedTuple

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Account, Budget, Category, RecurringTransaction, Transaction
from app.money import to_euros
from app.services import recurring

DEMO_PASSWORD = "demo-password"
DEMO_USERS = ("alice", "bruno")
HISTORY_MONTHS = 6
MONTHLY = RecurringTransaction.Frequency.MONTHLY

CATEGORIES = {
    "Salaire": "#2bb58a",
    "Logement": "#0f2a47",
    "Courses": "#f59e0b",
    "Restaurants": "#ef4444",
    "Transport": "#3b82f6",
    "Loisirs": "#a855f7",
    "Santé": "#14b8a6",
    "Abonnements": "#64748b",
    "Épargne": "#84cc16",
}

GROCERY_SHOPS = ["Marché des Halles", "Épicerie du Canal", "Supermarché Bellevue", "Primeur Saint-Jean"]
RESTAURANTS = ["Bistrot des Tilleuls", "Chez Lucette", "Pizzeria Napoli", "Le Petit Wok", "Crêperie du Port"]
OUTINGS = ["Cinéma Le Rex", "Librairie Papyrus", "Concert au Zénith", "Musée des Beaux-Arts", "Escalade Bloc & Co"]
HEALTH = ["Pharmacie du Centre", "Médecin généraliste", "Dentiste"]


class Rule(NamedTuple):
    """A fixed monthly operation."""
    owner: str
    sender: str
    receiver: str
    cents: int
    label: str
    category: str
    day: int


class Habit(NamedTuple):
    """Day-to-day spending: a few purchases a month, in a price range."""
    account: str
    shops: list
    category: str
    per_month: tuple
    min_cents: int
    max_cents: int


# Account keys: "bank", "alice", "savings", "bruno", "joint".
RULES = [
    Rule("alice", "bank", "alice", 235000, "Salaire Atelier Lumen", "Salaire", 1),
    Rule("alice", "alice", "bank", 8640, "Abonnement transports", "Transport", 2),
    Rule("alice", "alice", "savings", 20000, "Épargne mensuelle", "Épargne", 3),
    Rule("alice", "alice", "joint", 60000, "Part du compte joint", "Logement", 4),
    Rule("alice", "alice", "bank", 1349, "Streaming vidéo", "Abonnements", 12),
    Rule("alice", "alice", "bank", 1999, "Forfait mobile", "Abonnements", 15),
    Rule("bruno", "bank", "bruno", 198000, "Salaire Menuiserie Roux", "Salaire", 1),
    Rule("bruno", "bruno", "joint", 60000, "Part du compte joint", "Logement", 4),
    Rule("bruno", "bruno", "bank", 1599, "Forfait mobile", "Abonnements", 15),
    Rule("bruno", "bruno", "bank", 2990, "Salle de sport", "Loisirs", 20),
    Rule("alice", "joint", "bank", 98000, "Loyer", "Logement", 5),
    Rule("alice", "joint", "bank", 2850, "Assurance habitation", "Logement", 8),
    Rule("alice", "joint", "bank", 9500, "Électricité et gaz", "Logement", 10),
    Rule("bruno", "joint", "bank", 3499, "Box internet", "Abonnements", 12),
]

HABITS = [
    Habit("alice", GROCERY_SHOPS, "Courses", (3, 5), 3200, 8900),
    Habit("alice", RESTAURANTS, "Restaurants", (2, 4), 1600, 4800),
    Habit("alice", OUTINGS, "Loisirs", (1, 3), 900, 6500),
    Habit("alice", HEALTH, "Santé", (0, 1), 800, 6000),
    Habit("bruno", GROCERY_SHOPS, "Courses", (2, 4), 2500, 7000),
    Habit("bruno", RESTAURANTS, "Restaurants", (1, 3), 1400, 4200),
    Habit("bruno", OUTINGS, "Loisirs", (0, 2), 1000, 5500),
    Habit("joint", GROCERY_SHOPS, "Courses", (0, 1), 2000, 5000),
]

# Monthly budgets in euros, per user.
BUDGETS = {
    "alice": {"Courses": 400, "Restaurants": 150, "Loisirs": 120, "Transport": 100},
    "bruno": {"Courses": 300},
}


def _months_back(day: datetime.date, months: int) -> datetime.date:
    index = day.year * 12 + day.month - 1 - months
    return datetime.date(index // 12, index % 12 + 1, 1)


def _day_in_month(month_start: datetime.date, day: int) -> datetime.date:
    return month_start.replace(day=min(day, calendar.monthrange(month_start.year, month_start.month)[1]))


class Command(BaseCommand):
    help = "Fill a development database with fictional data (needs DEBUG, or --force)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete every account, transaction, category, rule and budget first")
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("seed is for development: DEBUG is off. Use --force if you really mean it.")

        has_data = Account.objects.filter(is_bank=False).exists() or User.objects.filter(username__in=DEMO_USERS).exists()
        if has_data and not options["reset"]:
            raise CommandError("The database already has data. Use --reset to delete it and start again.")

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            _Seeder(datetime.date.today()).run()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Account.objects.filter(is_bank=False).count()} accounts and "
            f"{Transaction.objects.count()} transactions."
        ))
        for account in Account.objects.filter(is_bank=False).order_by("id"):
            owners = ", ".join(account.owners.values_list("username", flat=True))
            self.stdout.write(f"  {account.label:<22} {to_euros(account.balance):>10} €  ({owners})")
        self.stdout.write(f"Sign in as {' or '.join(DEMO_USERS)} with the password: {DEMO_PASSWORD}")

    @staticmethod
    def _reset():
        """Remove the application data. Other users (your admin) and the bank account are kept."""
        Budget.objects.all().delete()
        RecurringTransaction.objects.all().delete()
        Transaction.objects.all().delete()
        Account.objects.filter(is_bank=False).delete()
        Category.objects.all().delete()
        User.objects.filter(username__in=DEMO_USERS).delete()


class _Seeder:
    def __init__(self, today: datetime.date):
        self.today = today
        self.start = _months_back(today, HISTORY_MONTHS)
        self.rng = random.Random(20260101)  # nosec B311
        self.users = {}
        self.accounts = {}
        self.categories = {}

    def run(self):
        self.categories = {
            label: Category.objects.create(label=label, color=color) for label, color in CATEGORIES.items()
        }
        self._create_people_and_accounts()
        self._run_rules()
        self._spend_day_to_day()
        for username, budgets in BUDGETS.items():
            for label, euros in budgets.items():
                Budget.objects.create(owner=self.users[username], category=self.categories[label], amount=euros * 100)

    def _create_people_and_accounts(self):
        for username in DEMO_USERS:
            self.users[username] = User.objects.create_user(
                username, email=f"{username}@example.org", password=DEMO_PASSWORD
            )
        alice, bruno = self.users["alice"], self.users["bruno"]
        self.accounts = {
            "bank": Account.objects.get_or_create(is_bank=True, defaults={"label": "Bank"})[0],
            "alice": self._account("Compte courant Alice", 120000, alice),
            "savings": self._account("Livret A", 450000, alice),
            "bruno": self._account("Compte courant Bruno", 65000, bruno),
            "joint": self._account("Compte joint", 30000, alice, bruno),
        }

    def _account(self, label, opening_cents, *owners):
        account = Account.objects.create(label=label, balance=opening_cents)
        account.owners.set(owners)
        # The opening balance predates the history, so that the balance curve starts from it.
        Transaction.objects.filter(receiver=account, is_opening=True).update(
            date=self.start - datetime.timedelta(days=1)
        )
        return account

    def _run_rules(self):
        """Create each rule six months back and let it generate its own history."""
        for rule in RULES:
            first = _day_in_month(self.start, rule.day)
            created = RecurringTransaction.objects.create(
                owner=self.users[rule.owner], sender=self.accounts[rule.sender],
                receiver=self.accounts[rule.receiver], amount=rule.cents, comment=rule.label,
                category=self.categories[rule.category], frequency=MONTHLY, start_date=first, next_date=first,
            )
            recurring.run_rule(created.pk, self.today)

    def _spend_day_to_day(self):
        for back in range(HISTORY_MONTHS, -1, -1):
            month = _months_back(self.today, back)
            for habit in HABITS:
                for _ in range(self.rng.randint(*habit.per_month)):
                    date = _day_in_month(month, self.rng.randint(1, 28))
                    if date > self.today:
                        continue
                    Transaction.objects.create(
                        sender=self.accounts[habit.account], receiver=self.accounts["bank"],
                        amount=self.rng.randint(habit.min_cents, habit.max_cents),
                        comment=self.rng.choice(habit.shops), category=self.categories[habit.category], date=date,
                    )
