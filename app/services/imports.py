"""Import bank statements (CSV or OFX) as transactions between an account and the bank.

A negative line is a debit (account to bank), a positive one a credit. Parsing is
text-only: OFX is read with regular expressions, never with an XML parser.
"""
import csv
import datetime
import hashlib
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from app.models import Account, Transaction
from app.money import to_cents

MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 5000
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y%m%d")
_LABEL_NAMES = ("label", "libelle", "description", "comment", "commentaire", "intitule")
_AMOUNT_NAMES = ("amount", "montant")


class ImportFormatError(ValueError):
    """The file as a whole cannot be read."""


@dataclass(frozen=True)
class Row:
    date: datetime.date
    cents: int  # signed: negative is a debit
    label: str
    import_id: str


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # usual encoding of French bank exports


def _normalize(header: str) -> str:
    text = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode()
    return text.strip().lower()


def _parse_date(raw: str) -> datetime.date:
    raw = raw.strip()
    for date_format in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"unreadable date: {raw!r}")


def _parse_cents(raw: str) -> int:
    text = re.sub(r"[\s\u00a0\u202f€]", "", raw)
    if "," in text and "." in text:
        # The last separator is the decimal one: 1.234,56 or 1,234.56
        thousands = "." if text.rfind(",") > text.rfind(".") else ","
        text = text.replace(thousands, "")
    text = text.replace(",", ".")
    try:
        return to_cents(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"unreadable amount: {raw!r}") from exc


def _with_ids(lines):
    """Give each line a stable id; identical lines in one file get distinct ids."""
    seen = Counter()
    rows = []
    for date, cents, label, given_id in lines:
        key = (date, cents, label)
        seen[key] += 1
        digest = hashlib.sha256(f"{date.isoformat()}|{cents}|{label}|{seen[key]}".encode()).hexdigest()[:40]
        rows.append(Row(date, cents, label, given_id or digest))
    return rows


def _find(headers, *names):
    for index, header in enumerate(headers):
        if any(header.startswith(name) for name in names):
            return index
    return None


@dataclass(frozen=True)
class _Columns:
    """Where each piece of a CSV line is, found from the header."""
    date: int
    label: int
    amount: int | None
    debit: int | None
    credit: int | None

    @classmethod
    def from_headers(cls, headers):
        columns = cls(
            date=_find(headers, "date"), label=_find(headers, *_LABEL_NAMES), amount=_find(headers, *_AMOUNT_NAMES),
            debit=_find(headers, "debit"), credit=_find(headers, "credit"),
        )
        has_amount = columns.amount is not None or None not in (columns.debit, columns.credit)
        if columns.date is None or columns.label is None or not has_amount:
            raise ImportFormatError(
                "Expected a CSV with a header line naming a date column, a label column "
                "(label, libellé, description) and an amount column (amount, montant) or debit and credit columns."
            )
        return columns

    def read(self, record):
        """One CSV record as (date, signed cents, label, no bank id)."""
        def cell(index):
            return record[index].strip() if index is not None and index < len(record) else ""

        if self.amount is not None:
            cents = _parse_cents(cell(self.amount))
        else:
            debit, credit = cell(self.debit), cell(self.credit)
            cents = (_parse_cents(credit) if credit else 0) - (abs(_parse_cents(debit)) if debit else 0)
        return _parse_date(cell(self.date)), cents, cell(self.label), None


def _parse_csv(text: str):
    first_line = text.splitlines()[0] if text.strip() else ""
    reader = csv.reader(io.StringIO(text), delimiter=max(";,\t", key=first_line.count))
    columns = _Columns.from_headers([_normalize(cell) for cell in next(reader, [])])

    lines, errors = [], []
    for number, record in enumerate(reader, start=2):
        if not any(value.strip() for value in record):
            continue
        if len(lines) >= MAX_ROWS:
            raise ImportFormatError(f"The file has more than {MAX_ROWS} lines.")
        try:
            lines.append(columns.read(record))
        except ValueError as exc:
            errors.append({"line": number, "error": str(exc)})
    return _with_ids(lines), errors


def _ofx_field(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}>([^<\r\n]*)", block, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_ofx(text: str):
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.IGNORECASE | re.DOTALL)
    if len(blocks) > MAX_ROWS:
        raise ImportFormatError(f"The file has more than {MAX_ROWS} lines.")
    lines, errors = [], []
    for number, block in enumerate(blocks, start=1):
        try:
            label = " ".join(part for part in (_ofx_field(block, "NAME"), _ofx_field(block, "MEMO")) if part)
            lines.append((
                _parse_date(_ofx_field(block, "DTPOSTED")[:8]),
                _parse_cents(_ofx_field(block, "TRNAMT")),
                label,
                _ofx_field(block, "FITID")[:64] or None,
            ))
        except ValueError as exc:
            errors.append({"line": number, "error": str(exc)})
    return _with_ids(lines), errors


def parse(data: bytes):
    """Return (rows, errors). Raises ImportFormatError when nothing can be read."""
    text = _decode(data)
    if "<OFX>" in text.upper() or "OFXHEADER" in text.upper():
        return _parse_ofx(text)
    return _parse_csv(text)


def import_rows(account: Account, rows) -> dict:
    """Create the transactions that are not already there. Returns created and skipped counts."""
    bank = Account.objects.filter(is_bank=True).first()
    if bank is None:
        raise ImportFormatError("No bank account exists yet: ask an administrator to create it.")
    with transaction.atomic():
        known = set(
            Transaction.objects.filter(Q(sender=account) | Q(receiver=account), import_id__isnull=False)
            .values_list("import_id", flat=True)
        )
        created = skipped = 0
        for row in rows:
            if row.import_id in known or row.cents == 0:
                skipped += 1
                continue
            sender, receiver = (bank, account) if row.cents > 0 else (account, bank)
            Transaction.objects.create(
                sender=sender, receiver=receiver, amount=abs(row.cents), comment=row.label[:200] or None,
                date=row.date, import_id=row.import_id,
            )
            known.add(row.import_id)
            created += 1
    return {"created": created, "skipped": skipped}
