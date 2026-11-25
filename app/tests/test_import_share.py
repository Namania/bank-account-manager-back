import datetime

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from app.models import Transaction
from app.services import imports
from app.tests.base import ApiTestCase

D = datetime.date

CSV_FR = """Date;Libellé;Montant
15/01/2026;CB CARREFOUR;-45,90
16/01/2026;VIR SALAIRE;2 100,00
16/01/2026;CB BOULANGERIE;-3,20
16/01/2026;CB BOULANGERIE;-3,20
"""

CSV_DEBIT_CREDIT = """date,label,debit,credit
2026-01-15,Loyer,800.00,
2026-01-16,Remboursement,,25.5
"""

OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260115120000
<TRNAMT>-45.90
<FITID>A1
<NAME>CB CARREFOUR
<MEMO>PARIS
</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260116<TRNAMT>2100.00<FITID>A2<NAME>VIR SALAIRE</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


class ImportParsingTests(ApiTestCase):
    def test_french_csv(self):
        rows, errors = imports.parse(CSV_FR.encode())
        self.assertEqual(errors, [])
        self.assertEqual([(r.date, r.cents, r.label) for r in rows], [
            (D(2026, 1, 15), -4590, "CB CARREFOUR"), (D(2026, 1, 16), 210000, "VIR SALAIRE"),
            (D(2026, 1, 16), -320, "CB BOULANGERIE"), (D(2026, 1, 16), -320, "CB BOULANGERIE"),
        ])
        self.assertEqual(len({r.import_id for r in rows}), 4)  # identical lines stay distinct

    def test_debit_and_credit_columns(self):
        rows, _ = imports.parse(CSV_DEBIT_CREDIT.encode())
        self.assertEqual([(r.cents, r.label) for r in rows], [(-80000, "Loyer"), (2550, "Remboursement")])

    def test_ofx(self):
        rows, errors = imports.parse(OFX.encode())
        self.assertEqual(errors, [])
        self.assertEqual([(r.date, r.cents, r.label, r.import_id) for r in rows], [
            (D(2026, 1, 15), -4590, "CB CARREFOUR PARIS", "A1"), (D(2026, 1, 16), 210000, "VIR SALAIRE", "A2"),
        ])

    def test_latin1_file_is_decoded(self):
        rows, _ = imports.parse("Date;Libellé;Montant\n15/01/2026;Café;-2,00\n".encode("latin-1"))
        self.assertEqual(rows[0].label, "Café")

    def test_bad_lines_are_reported_with_their_number(self):
        rows, errors = imports.parse(b"date,label,amount\n2026-01-15,ok,1.00\nhier,ko,1.00\n2026-01-17,ko,abc\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual([e["line"] for e in errors], [3, 4])

    def test_unknown_columns_are_refused(self):
        with self.assertRaises(imports.ImportFormatError):
            imports.parse(b"a,b,c\n1,2,3\n")


class ImportApiTests(ApiTestCase):
    def upload(self, content, user=None, account=None, name="releve.csv"):
        file = SimpleUploadedFile(name, content if isinstance(content, bytes) else content.encode())
        account = account or self.alice_acc
        return self.as_user(user or self.alice).post(f"/accounts/{account.id}/import/", {"file": file}, format="multipart")

    def test_import_creates_transactions_against_the_bank(self):
        response = self.upload(CSV_FR)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"created": 4, "skipped": 0, "errors": []})
        self.assertEqual(self.balance(self.alice_acc), 100000 - 4590 + 210000 - 640)
        debit = Transaction.objects.get(comment="CB CARREFOUR")
        self.assertEqual((debit.sender, debit.receiver, debit.amount, debit.date),
                         (self.alice_acc, self.bank, 4590, D(2026, 1, 15)))
        credit = Transaction.objects.get(comment="VIR SALAIRE")
        self.assertEqual((credit.sender, credit.receiver), (self.bank, self.alice_acc))

    def test_importing_the_same_file_twice_creates_nothing_new(self):
        self.upload(CSV_FR)
        before = self.balance(self.alice_acc)
        response = self.upload(CSV_FR)
        self.assertEqual(response.data, {"created": 0, "skipped": 4, "errors": []})
        self.assertEqual(self.balance(self.alice_acc), before)

    def test_ofx_import_is_deduplicated_by_bank_id(self):
        self.assertEqual(self.upload(OFX, name="releve.ofx").data["created"], 2)
        self.assertEqual(self.upload(OFX, name="releve.ofx").data, {"created": 0, "skipped": 2, "errors": []})

    def test_same_file_can_be_imported_into_another_account(self):
        self.upload(CSV_FR)
        other = self.make_account(self.alice, "Autre")
        self.assertEqual(self.upload(CSV_FR, account=other).data["created"], 4)

    def test_cannot_import_into_foreign_account(self):
        self.assertEqual(self.upload(CSV_FR, user=self.mallory).status_code, 404)
        self.assertEqual(self.balance(self.alice_acc), 100000)

    def test_unreadable_file_is_400(self):
        self.assertEqual(self.upload(b"a,b,c\n1,2,3\n").status_code, 400)
        self.assertEqual(self.as_user(self.alice).post(f"/accounts/{self.alice_acc.id}/import/", {}, format="multipart").status_code, 400)

    def test_oversized_file_is_400(self):
        self.assertEqual(self.upload(b"date,label,amount\n" + b"x" * (1024 * 1024 + 1)).status_code, 400)

    def test_partial_file_imports_good_lines_and_reports_bad_ones(self):
        response = self.upload("date,label,amount\n2026-01-15,ok,-1.00\nhier,ko,1.00\n")
        self.assertEqual((response.data["created"], [e["line"] for e in response.data["errors"]]), (1, [3]))


class AccountSharingTests(ApiTestCase):
    def setUp(self):
        cache.clear()

    def share(self, username, user=None, account=None, action="share"):
        account = account or self.alice_acc
        return self.as_user(user or self.alice).post(f"/accounts/{account.id}/{action}/", {"username": username}, format="json")

    def test_owner_can_share_with_another_user(self):
        response = self.share("mallory")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owners_details"],
                         [{"id": self.alice.id, "username": "alice"}, {"id": self.mallory.id, "username": "mallory"}])
        self.assertEqual(self.as_user(self.mallory).get(f"/accounts/{self.alice_acc.id}/").status_code, 200)

    def test_only_an_owner_can_share(self):
        self.assertEqual(self.share("mallory", user=self.mallory).status_code, 404)
        self.assertEqual(list(self.alice_acc.owners.all()), [self.alice])

    def test_unknown_user_and_duplicates_are_refused(self):
        self.assertEqual(self.share("nobody").status_code, 404)
        self.assertEqual(self.share("alice").status_code, 400)

    def test_bank_account_cannot_be_shared(self):
        self.bank.owners.add(self.alice)
        self.assertEqual(self.share("mallory", account=self.bank).status_code, 403)

    def test_unshare_removes_an_owner(self):
        self.share("mallory")
        self.assertEqual(self.share("mallory", action="unshare").status_code, 204)
        self.assertEqual(list(self.alice_acc.owners.all()), [self.alice])

    def test_an_owner_can_leave_but_the_last_one_cannot(self):
        self.share("mallory")
        self.assertEqual(self.share("alice", action="unshare").status_code, 204)
        self.assertEqual(self.share("mallory", user=self.mallory, action="unshare").status_code, 400)
        self.assertEqual(list(self.alice_acc.owners.all()), [self.mallory])

    def test_username_guessing_is_throttled(self):
        codes = [self.share(f"guess{i}").status_code for i in range(11)]
        self.assertEqual(codes, [404] * 10 + [429])
