"""Turn recurring rules into real transactions when they fall due."""
import calendar
import datetime
import logging

from django.db import transaction

from app.models import RecurringTransaction, Transaction

audit = logging.getLogger("app.audit")

# A rule may start in the past, but not far enough to flood the ledger.
MAX_BACKDATE_DAYS = 366
_MONTHS = {RecurringTransaction.Frequency.MONTHLY: 1, RecurringTransaction.Frequency.YEARLY: 12}


def _add_months(start: datetime.date, months: int) -> datetime.date:
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return datetime.date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def occurrence_date(rule: RecurringTransaction, number: int) -> datetime.date:
    """Date of the occurrence `number` (0 is the start date)."""
    if rule.frequency == RecurringTransaction.Frequency.WEEKLY:
        return rule.start_date + datetime.timedelta(weeks=number)
    return _add_months(rule.start_date, _MONTHS[rule.frequency] * number)


def run_rule(rule_id: int, today: datetime.date) -> int:
    """Create every occurrence of one rule that is due. Returns how many were created."""
    created = 0
    with transaction.atomic():
        rule = RecurringTransaction.objects.select_for_update().select_related("sender", "receiver").get(pk=rule_id)
        while rule.is_active and rule.next_date is not None and rule.next_date <= today:
            if not (rule.sender.is_active and rule.receiver.is_active):
                audit.warning("recurring rule paused id=%s: one of its accounts is deactivated", rule.pk)
                rule.is_active = False
                break
            Transaction.objects.create(
                sender=rule.sender, receiver=rule.receiver, category=rule.category, amount=rule.amount,
                comment=rule.comment, date=rule.next_date, recurring=rule,
            )
            created += 1
            rule.occurrences += 1
            rule.next_date = occurrence_date(rule, rule.occurrences)
            if rule.end_date is not None and rule.next_date > rule.end_date:
                rule.next_date = None
                rule.is_active = False
        rule.save(update_fields=["occurrences", "next_date", "is_active"])
    return created


def run_due(today: datetime.date | None = None) -> int:
    """Run every rule that is due. Safe to call as often as wanted."""
    today = today or datetime.date.today()
    due = RecurringTransaction.objects.filter(is_active=True, next_date__lte=today).values_list("pk", flat=True)
    return sum(run_rule(rule_id, today) for rule_id in list(due))
