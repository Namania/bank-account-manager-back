# Remédiation sécurité et bugs — Bank Account Manager (back) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger toutes les failles et tous les bugs relevés par l'audit du 25/11/2026 (C1-C4, E1-E6, M1-M6, F1-F3), passer les montants en centimes entiers, et livrer ce que le front attend de l'API (jetons en cookie HttpOnly, `/users/me/`, en-têtes de sécurité), chaque point étant verrouillé par un test.

**Architecture:** Structure actuelle conservée (ViewSets dans `app/serializers/`, signaux comme déclencheurs). Règles d'accès dans `app/permissions.py`, écriture des soldes dans `app/services/ledger.py` (atomique, verrouillée), conversion euros ↔ centimes dans `app/money.py`, authentification par cookie dans `app/auth.py`, lecture de l'environnement dans `bankAccountManager/env.py`. Tests sur SQLite via `bankAccountManager/settings_test.py`.

**Tech Stack:** Python 3.12, Django 5.2, DRF 3.18, simplejwt 5.5 (+ `token_blacklist`), PostgreSQL 16, Docker Compose, GitHub Actions. `django-money` est retiré.

**Spec:** note n° 151 du journal (Lab › Bank Account Manager, 2026-11-25), complétée par les arbitrages du propriétaire ci-dessous.

## Décisions actées (v2)

- Base neuve : les migrations 0001-0016 sont supprimées et remplacées par un `0001_initial` unique. `USE_TZ = True`.
- Solde et montant stockés en **centimes entiers** (`BigIntegerField`). L'API reçoit et renvoie des **euros en chaîne décimale à 2 décimales** (`"10.50"` ⇄ `1050`). Devise unique : EUR, plus de champ devise.
- Solde : fixé à la création par l'API, ignoré en modification par l'API, **modifiable dans le backoffice** (saisi en euros).
- Propriétaires d'un compte : le créateur ; partage par le backoffice.
- Transactions **modifiables** (montant, comptes, commentaire, catégorie) : toute modification recalcule les soldes.
- Détail des comptes dans une transaction réduit à `id`, `label`, `isActive`, `is_bank`.
- Catégories : globales (sans propriétaire, écriture staff) ou personnelles.
- JWT en **cookies HttpOnly** uniquement (plus de jeton dans le corps des réponses), accès 15 min, refresh 1 jour avec rotation et liste noire, CSRF exigé sur les requêtes d'écriture.
- HTTPS forcé hors debug (`HTTPS_ONLY`), reverse proxy TLS requis.

## Global Constraints

- Branche `fix/security-remediation`, jamais `main`.
- Commits gitmoji (`:lock:`, `:bug:`, `:recycle:`, `:white_check_mark:`, `:wrench:`, `:memo:`), terminés par `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- `pylint $(git ls-files '*.py')` à 10.00/10 après chaque tâche.
- Commande de test : `python manage.py test app --settings=bankAccountManager.settings_test`.
- Environnement local : `.venv` (ignoré par git).
- Aucun `float` dans le calcul des montants ; aucun `makemigrations` au démarrage du conteneur ; aucun secret dans le dépôt ni dans l'image.

## Review Focus

1. Supprimer ou modifier une transaction dont un compte a été supprimé (`None`) : réussit et annule l'effet sur le compte restant. → Tâche 5.
2. Transaction sur un compte désactivé ou avec `sender == receiver` : 400, aucun solde modifié. → Tâche 6.
3. Montant mal formé (`"abc"`, `0`, négatif, 3 décimales) : 400, jamais 500. → Tâches 3 et 6.
4. Requête d'écriture authentifiée par cookie sans en-tête `X-CSRFToken` : 403. → Tâche 8.
5. Réutilisation d'un refresh token après rotation ou après déconnexion : 401. → Tâche 8.

Non testable ici : la concurrence réelle sous PostgreSQL (`select_for_update()` est sans effet sur SQLite). À vérifier à la main sur l'environnement Docker.

---

### Task 1: Socle de test et signal Token retiré (E1)

**Files:** Create `bankAccountManager/settings_test.py`, `app/tests/__init__.py`, `app/tests/test_smoke.py` · Modify `app/signals.py`, `bankAccountManager/settings.py` (DATABASES)

- [ ] **Step 1:** `settings_test.py` : `os.environ.setdefault` pour les variables exigées (`DEBUG="False"`, `ALLOWED_HOSTS="testserver"`, `SECRET_KEY` de 60 caractères, `HTTPS_ONLY="False"`), `from .settings import *`, `DATABASES["default"].update(ENGINE=sqlite3, NAME=":memory:")`, hasher MD5.
- [ ] **Step 2: Tests** (`test_smoke.py`) :
  - `test_user_creation_does_not_crash` : `User.objects.create_user("zoe", …)` existe en base.
  - `test_no_pending_migration` : `call_command("makemigrations", "app", check=True, dry_run=True)` ne lève rien.
- [ ] **Step 3:** Vérifier l'échec (`AttributeError: … 'Token' has no attribute 'objects'`).
- [ ] **Step 4:** Retirer de `signals.py` l'import `Token`, l'import `settings` et `create_auth_token`. Ajouter `'ATOMIC_REQUESTS': True` à `DATABASES['default']`.
- [ ] **Step 5:** `test_user_creation…` passe (`test_no_pending_migration` passera en tâche 3).
- [ ] **Step 6:** Commit — `:white_check_mark: test harness, drop broken token signal`

---

### Task 2: Réglages et en-têtes (C4, F1, M1, M4, S7)

**Files:** Create `bankAccountManager/env.py`, `app/middleware.py`, `app/tests/test_env.py`, `app/tests/test_settings.py` · Modify `bankAccountManager/settings.py`, `bankAccountManager/urls.py`, `.env.example`

**Interfaces — Produces:**
- `env_bool(name: str, default: bool = False) -> bool` (vrai pour `1`, `true`, `yes`, `on`), `env_list(name: str) -> list[str]`, `check_production_settings(secret_key: str, allowed_hosts: list[str]) -> None` (lève `ImproperlyConfigured` si clé préfixée `django-insecure-` ou < 50 caractères, ou si `*` dans les hôtes).
- `app.middleware.SecurityHeadersMiddleware` : ajoute `Permissions-Policy: geolocation=(), camera=(), microphone=()` partout ; hors `DEBUG` et hors chemins `/admin/` et `/static/`, ajoute `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`.

- [ ] **Step 1: Tests**
  - `test_env_bool` : `"False"`, `"false"`, `"0"`, `""` → `False` ; `"True"`, `"true"`, `"1"`, `"on"` → `True` ; défaut respecté si absente.
  - `test_env_list_strips_and_drops_empty` : `" a.fr , b.fr,, "` → `["a.fr", "b.fr"]`.
  - `test_production_rejects_weak_secret`, `test_production_rejects_wildcard_host`, `test_production_accepts_strong_config`.
  - `test_debug_is_a_real_boolean` : `settings.DEBUG is False`.
  - `test_use_tz_enabled`.
  - `test_renderers_are_json_only` : `DEFAULT_RENDERER_CLASSES == ["rest_framework.renderers.JSONRenderer"]`.
  - `test_session_login_route_absent` : `GET /auth/login/` → 404.
  - `test_404_does_not_leak_urlconf` : `b"URLconf"` absent de la réponse.
  - `test_api_response_has_security_headers` : sur `GET /accounts/`, CSP `default-src 'none'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Permissions-Policy` présent.
  - `test_admin_has_no_api_csp` : `GET /admin/login/` sans en-tête CSP.
- [ ] **Step 2:** Vérifier l'échec (`ImportError` sur `bankAccountManager.env`).
- [ ] **Step 3:** Implémenter `env.py` et le middleware (ajouté en fin de `MIDDLEWARE`).
- [ ] **Step 4:** `settings.py` : `DEBUG = env_bool('DEBUG')` ; listes via `env_list` ; `check_production_settings` hors debug ; `HTTPS_ONLY = env_bool('HTTPS_ONLY', default=not DEBUG)` qui active `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`, cookies `Secure`, `SECURE_HSTS_SECONDS` (env, défaut `31536000`) et sous-domaines ; `X_FRAME_OPTIONS = 'DENY'` ; `USE_TZ = True` ; rendu JSON seul hors debug ; `SessionAuthentication` et route `auth/` seulement en debug.
- [ ] **Step 5:** `.env.example` : `DEBUG=False`, `HTTPS_ONLY=`, `SECURE_HSTS_SECONDS=`, `AUTH_COOKIE_SAMESITE=`.
- [ ] **Step 6:** Tests `OK` ; `check --deploy` avec `HTTPS_ONLY=True` sans W004, W008, W012, W016, W018.
- [ ] **Step 7:** Commit — `:lock: parse DEBUG as boolean, validate env, harden production settings and headers`

---

### Task 3: Montants en centimes entiers, drapeau banque, migrations neuves (S10, E2)

**Files:** Create `app/money.py`, `app/serializers/fields.py`, `app/admin/forms.py`, `app/tests/base.py`, `app/tests/test_money.py`, `app/tests/test_bank.py`, `app/migrations/0001_initial.py` (régénérée) · Delete `app/migrations/0001…0016` · Modify `app/models/account.py`, `app/models/transaction.py`, `app/models/category.py`, `app/admin/*.py`, `app/management/commands/create_bank.py`, `bankAccountManager/settings.py` (retirer `djmoney`), serializers (champs montant)

**Interfaces — Produces:**
- `app.money.to_cents(value: Decimal) -> int` (lève `ValueError` au-delà de 2 décimales), `app.money.to_euros(cents: int) -> Decimal` (quantifié à `0.01`).
- `app.serializers.fields.CentsField` (sous-classe de `serializers.DecimalField`, `max_digits=14`, `decimal_places=2`) : entrée `"10.50"` → `1050`, sortie `1050` → `"10.50"`.
- `app.admin.forms.EuroFormField` (formulaire admin : affiche des euros, enregistre des centimes), utilisé par `AccountAdminForm.balance` et `TransactionAdminForm.amount`.
- Modèles : `Account.balance: BigIntegerField(default=0)` (centimes), `Account.is_bank: BooleanField(default=False)` + contrainte `unique_bank_account` (`UniqueConstraint(fields=['is_bank'], condition=Q(is_bank=True))`), `Transaction.amount: BigIntegerField(default=0)` (centimes), `Category.owner: ForeignKey(User, null=True, blank=True, on_delete=CASCADE, related_name="categories")`.
- `app.tests.base.ApiTestCase` : attributs `bank` (`is_bank=True`, créé en premier), `alice`, `mallory`, `staff` (`is_staff=True`), `alice_acc` (solde `100000`), `mallory_acc` (solde `0`), `category` (globale) ; méthodes `as_user(user) -> APIClient` (`force_authenticate`), `balance(account) -> int` (relit la base).

- [ ] **Step 1: Tests**
  - `test_to_cents` : `Decimal("10.50")` → `1050`, `Decimal("0.01")` → `1`, `Decimal("-3")` → `-300` ; `Decimal("1.234")` lève `ValueError`.
  - `test_to_euros` : `1050` → `Decimal("10.50")`, `5` → `Decimal("0.05")`.
  - `test_cents_field_round_trip` : `CentsField().to_internal_value("10.50") == 1050` ; `to_representation(1050) == "10.50"` ; `"1.234"` et `"abc"` lèvent `ValidationError`.
  - `test_only_one_bank_account` : second `is_bank=True` → `IntegrityError`.
  - `test_label_bank_does_not_make_a_bank`.
  - `test_create_bank_command_is_idempotent` : deux appels, un seul compte `is_bank`.
  - `test_account_api_speaks_euros` : `GET /accounts/<alice_acc>/` renvoie `balance == "1000.00"`.
- [ ] **Step 2:** Vérifier l'échec (`ImportError` sur `app.money`).
- [ ] **Step 3:** Implémenter `money.py`, `CentsField`, les modèles, supprimer les anciennes migrations et générer `0001_initial`. Retirer `djmoney` de `INSTALLED_APPS`. Supprimer les méthodes mortes `add`, `remove`, `set`, `getBalance` de `Account`.
- [ ] **Step 4:** `create_bank` : `Account.objects.get_or_create(is_bank=True, defaults={"label": "Bank"})`. Admin : formulaires en euros, `is_bank` et `owner` affichés. Serializers : `balance` et `amount` en `CentsField`.
- [ ] **Step 5:** Tests `OK`, y compris `test_no_pending_migration`.
- [ ] **Step 6:** Commit — `:recycle: store money as integer cents, flag the bank account, reset migrations`

---

### Task 4: Utilisateurs (C1, S3, S5)

**Files:** Modify `app/serializers/user.py` · Test `app/tests/test_users.py`

**Interfaces — Produces:** `/users/` en `GET`, `PUT`, `PATCH` seulement ; `GET` et `PATCH /users/me/` ; champs modifiables : `username`, `email`.

- [ ] **Step 1: Tests**
  - `test_cannot_promote_self_to_staff` : `PATCH {"is_staff": true}` → 200, `is_staff` reste `False`.
  - `test_non_staff_sees_only_self` ; `test_cannot_read_other_user` (404).
  - `test_create_and_delete_are_disabled_even_for_staff` : 405 et 405.
  - `test_me_returns_current_user` : `GET /users/me/` → `id` de l'appelant.
  - `test_me_patch_updates_email_but_not_is_staff`.
- [ ] **Step 2:** Vérifier l'échec.
- [ ] **Step 3:** `read_only_fields = ['id', 'is_staff']` ; ViewSet = `ListModelMixin, RetrieveModelMixin, UpdateModelMixin, GenericViewSet` ; action `me` (`detail=False`, `methods=["get", "patch"]`).
- [ ] **Step 4:** Tests `OK`.
- [ ] **Step 5:** Commit — `:lock: make is_staff read-only, drop user create/delete, add /users/me/`

---

### Task 5: Service de solde atomique, transactions modifiables (E3)

**Files:** Create `app/services/__init__.py`, `app/services/ledger.py` · Modify `app/signals.py` · Test `app/tests/test_ledger.py`

**Interfaces — Produces (`app.services.ledger`) :**
- `apply_transaction(tx: Transaction) -> None` : `receiver.balance += tx.amount`, `sender.balance -= tx.amount`.
- `revert_transaction(tx: Transaction) -> None` : l'inverse exact.
- `open_account(account: Account) -> None` : ne fait rien si `account.is_bank` ; sans compte banque, laisse le solde tel quel et journalise un WARNING ; sinon remet le solde à `0` et crée la transaction « Création du compte » (banque → compte si solde ≥ 0, compte → banque du montant opposé sinon).
- Règle commune : un côté `None` ou `is_bank` est ignoré. Chaque fonction s'exécute dans `transaction.atomic()` et relit le compte par `select_for_update()` avant `save(update_fields=["balance"])`.
- Journal `app.audit` : une ligne INFO par opération (`transaction applied id=… sender=… receiver=… amount=…`).
- Signaux : `pre_save(Transaction)` annule l'ancienne version si la ligne existe déjà ; `post_save(Transaction)` applique toujours ; `pre_delete(Transaction)` annule ; `post_save(Account, created)` appelle `open_account`.

- [ ] **Step 1: Tests** (montants en centimes)
  - `test_create_moves_balance` : transfert `50000` alice → mallory : `50000` / `50000`.
  - `test_delete_restores_both_balances`.
  - `test_update_amount_adjusts_balances` : `50000` puis montant modifié à `20000` : alice `80000`, mallory `20000`.
  - `test_update_accounts_moves_effect` : le receveur passe de mallory à un autre compte : mallory `0`, l'autre `50000`.
  - `test_bank_balance_never_moves` (création puis suppression).
  - `test_delete_with_deleted_account_reverts_remaining_side`.
  - `test_update_with_deleted_account_does_not_crash`.
  - `test_bank_account_gets_no_opening_transaction`.
  - `test_opening_balance_creates_bank_transaction` : montant `100000`, solde `100000`.
  - `test_negative_opening_balance` : compte créé à `-5000` → transaction compte → banque de `5000`, solde `-5000`.
  - `test_opening_without_bank_keeps_balance`.
  - `test_stale_instance_does_not_overwrite_balance` : deux crédits de `10000` dont un via une instance périmée → `20000`.
  - `test_apply_is_audited` (`assertLogs("app.audit")`).
- [ ] **Step 2:** Vérifier l'échec.
- [ ] **Step 3:** Implémenter `ledger.py`, réduire `signals.py` aux quatre déclencheurs.
- [ ] **Step 4:** Tests `OK`.
- [ ] **Step 5:** Commit — `:bug: atomic ledger service, balances follow transaction edits`

---

### Task 6: Comptes et transactions — autorisation et validation (C2, C3, E6, F2, F3)

**Files:** Create `app/permissions.py` · Modify `app/serializers/account.py`, `app/serializers/transaction.py` · Test `app/tests/test_accounts.py`, `app/tests/test_transactions.py`

**Interfaces — Produces:**
- `app.permissions.usable_accounts(user) -> QuerySet[Account]` : tout pour un staff ; sinon comptes actifs dont il est propriétaire, plus le compte banque.
- `AccountSerializer` : champs `id, owners, label, balance, create_at, isActive, is_bank` ; lecture seule : `owners`, `create_at`, `isActive`, `is_bank` ; `balance` accepté à la création, retiré en modification.
- `AccountSummarySerializer` : `id, label, isActive, is_bank`, utilisé pour `sender_details` et `receiver_details`.

- [ ] **Step 1: Tests comptes**
  - `test_balance_is_ignored_on_update` : `PATCH {"balance": "999999.00"}` → 200, solde inchangé.
  - `test_owners_are_ignored_on_update`.
  - `test_creator_becomes_sole_owner` : `POST {"label", "balance": "200.00", "owners": [alice]}` par mallory → propriétaire mallory, solde `20000`, réponse `balance == "200.00"`.
  - `test_cannot_read_or_update_foreign_account` (404).
  - `test_delete_is_soft` : 204, `isActive` à `False`, ligne conservée.
  - `test_non_staff_owner_cannot_modify_bank` : 403 en `PATCH` et `DELETE`.
  - `test_rename_is_allowed`.
- [ ] **Step 2: Tests transactions** (charge utile par défaut : alice_acc → bank, `"10.00"`)
  - `test_owner_can_debit_own_account` : 201, solde `99000`, réponse `amount == "10.00"`.
  - `test_cannot_debit_foreign_account`, `test_cannot_credit_foreign_account` : 400, soldes inchangés.
  - `test_invalid_amounts_are_rejected` : `"-200.00"`, `"0"`, `"abc"`, `"1.234"` → 400.
  - `test_same_sender_and_receiver_is_rejected`, `test_inactive_account_is_rejected` : 400.
  - `test_update_amount_adjusts_balance` : `PATCH {"amount": "25.00"}` → 200, solde `97500`.
  - `test_update_cannot_point_to_foreign_account` : `PATCH {"sender": mallory_acc}` par alice → 400.
  - `test_comment_is_editable`.
  - `test_details_do_not_leak_balance_or_owners` : clés `{"id", "label", "isActive", "is_bank"}`.
  - `test_foreign_transaction_is_invisible` : 404 en lecture et suppression.
  - `test_delete_restores_balance`.
  - `test_by_account_rejects_non_numeric_id` (404) ; `test_by_account_lists_own_transactions`.
  - `test_staff_can_use_any_account`.
- [ ] **Step 3:** Vérifier l'échec.
- [ ] **Step 4:** Implémenter : querysets de `sender`/`receiver` fixés dans `get_fields()` à `usable_accounts(user)` ; `validate_amount` refuse ≤ 0 ; `validate` refuse `sender == receiver` (valeurs de l'instance en repli lors d'un `PATCH`) ; `perform_create` du compte fixe `owners` au créateur ; `perform_destroy` désactive ; `PermissionDenied` sur le compte banque pour un non-staff ; route `by_account/(?P<account_id>\d+)`.
- [ ] **Step 5:** Tests `OK`.
- [ ] **Step 6:** Commit — `:lock: restrict accounts and transactions to their owner, validate amounts`

---

### Task 7: Catégories à propriétaire (E5)

**Files:** Modify `app/serializers/category.py`, `app/serializers/transaction.py`, `app/permissions.py` · Test `app/tests/test_categories.py`

**Interfaces — Produces:** `visible_categories(user) -> QuerySet[Category]` (tout pour un staff ; sinon globales + les siennes) ; `IsOwnerOrStaffOrReadOnly` ; `CategorySerializer` : `id, label, color, owner` (`owner` en lecture seule).

- [ ] **Step 1: Tests**
  - `test_non_staff_cannot_modify_or_delete_global_category` (403).
  - `test_created_category_belongs_to_creator` ; `test_staff_creates_global_category`.
  - `test_private_category_is_hidden_from_others`.
  - `test_owner_can_edit_and_delete_own_category`.
  - `test_transaction_cannot_use_foreign_private_category` (400).
- [ ] **Step 2:** Vérifier l'échec.
- [ ] **Step 3:** Implémenter (ViewSet : queryset visible, permission, `perform_create` fixe `owner` à `None` pour un staff, à l'utilisateur sinon ; queryset de `category` dans le serializer de transaction).
- [ ] **Step 4:** Tests `OK`.
- [ ] **Step 5:** Commit — `:lock: scope category writes to their owner`

---

### Task 8: Authentification par cookie HttpOnly (E4, M6, S1, S8)

**Files:** Create `app/auth.py` · Modify `bankAccountManager/settings.py`, `bankAccountManager/urls.py`, `app/apps.py` · Test `app/tests/test_auth.py`

**Interfaces — Produces:**
- Cookies : `access_token` (chemin `/`) et `refresh_token` (chemin `/token/`), `HttpOnly`, `Secure` si `HTTPS_ONLY`, `SameSite` = `AUTH_COOKIE_SAMESITE` (env, défaut `Lax`).
- `POST /token/` `{username, password}` → 200 `{"csrfToken": "…"}`, pose les deux cookies. Scope de throttling `token` : `5/min`.
- `POST /token/refresh/` (cookie refresh + CSRF) → 200 `{"csrfToken": "…"}`, pose les nouveaux cookies ; 401 et cookies effacés si le refresh est absent, expiré ou révoqué. Scope `token_refresh` : `30/min`.
- `POST /token/logout/` (CSRF) → 204, révoque le refresh et efface les cookies.
- `GET /csrf/` → 200 `{"csrfToken": "…"}` et pose le cookie `csrftoken`.
- `app.auth.CookieJWTAuthentication` : lit le cookie d'accès, exige un CSRF valide sur les méthodes d'écriture. Aucun jeton dans le corps d'une réponse ; plus d'en-tête `Authorization`.
- Récepteur `log_failed_login` sur `user_login_failed` : WARNING sur `app.security`, `login failed username=<u> ip=<REMOTE_ADDR>`, jamais le mot de passe.
- Réglages : `token_blacklist` installé ; accès 15 min, refresh 1 jour, `ROTATE_REFRESH_TOKENS` et `BLACKLIST_AFTER_ROTATION` à `True` ; `CORS_ALLOW_CREDENTIALS = True` ; `CSRF_COOKIE_SAMESITE` aligné ; `ImproperlyConfigured` si `AUTH_COOKIE_SAMESITE=None` sans `HTTPS_ONLY` ; `LOGGING` console pour `app.security`, `app.audit`, `django.security`.

- [ ] **Step 1: Tests** (`cache.clear()` en `setUp`)
  - `test_login_sets_httponly_cookies_and_hides_tokens` : cookies présents avec `httponly`, corps sans `access` ni `refresh`.
  - `test_cookie_authenticates_requests` : `GET /users/me/` → 200 après login.
  - `test_login_is_throttled_after_5_attempts_per_minute` : `[401]*5 + [429]`.
  - `test_write_without_csrf_header_is_rejected` : client `enforce_csrf_checks=True`, `POST /categories/` sans en-tête → 403 ; avec `X-CSRFToken` reçu au login → 201.
  - `test_refresh_rotates_and_old_token_is_rejected` : rejouer l'ancien cookie refresh → 401.
  - `test_logout_revokes_refresh_and_clears_cookies` : 204 puis refresh avec l'ancien cookie → 401.
  - `test_refresh_without_cookie_is_401`.
  - `test_failed_login_is_logged_without_password`.
  - `test_api_requires_authentication` : 401 sur `/accounts/`, `/transactions/`, `/categories/`, `/users/`.
  - `test_authorization_header_is_ignored` : un jeton d'accès valide en `Authorization: Bearer` seul → 401.
- [ ] **Step 2:** Vérifier l'échec.
- [ ] **Step 3:** Implémenter `app/auth.py`, les réglages, les routes, l'import dans `BankAppConfig.ready()`.
- [ ] **Step 4:** Tests `OK`.
- [ ] **Step 5:** Commit — `:lock: HttpOnly cookie auth with CSRF, throttled login, token rotation and revocation`

---

### Task 9: Conteneurs et dépendances (M2, M3)

**Files:** Create `.dockerignore`, `requirements-dev.txt` · Modify `Dockerfile`, `compose.yml`, `requirements.txt`, `.gitignore`

- [ ] **Step 1:** `requirements.txt` épinglé : `Django==5.2.19`, `django-colorfield==0.14.0`, `django-cors-headers==4.9.0`, `django-jazzmin==3.0.5`, `djangorestframework==3.18.3`, `djangorestframework-simplejwt==5.5.1`, `drf-redesign==0.6.0`, `gunicorn==27.0.1`, `Markdown==3.11.3`, `psycopg2-binary==2.9.13`, `python-dotenv==1.2.4`, `whitenoise==6.12.0`. `django-money` et `django-filter` disparaissent. `requirements-dev.txt` : `-r requirements.txt`, `pylint==4.1.4`, `pip-audit` et `bandit` épinglés à la version résolue le jour de l'exécution.
- [ ] **Step 2:** `.dockerignore` : `.env`, `.env.*`, `!.env.example`, `.git`, `.github`, `.venv`, `__pycache__`, `*.sqlite3`, `git-image`, `docs`, `staticfiles`. Ajouter `staticfiles` et `*.sqlite3` au `.gitignore`.
- [ ] **Step 3:** `Dockerfile` : utilisateur système `app`, `chown` de `/app`, `USER app` ; `CMD` = `migrate`, `collectstatic`, `gunicorn` (plus de `makemigrations`).
- [ ] **Step 4:** `compose.yml` : port de la base lié à `127.0.0.1` ; `healthcheck` `pg_isready` ; `depends_on.db.condition: service_healthy`.
- [ ] **Step 5:** Vérifier : `pip-audit -r requirements.txt` sans vulnérabilité ; tests `OK` ; si Docker tourne, `docker build` puis `docker run --rm <image> id -u` ≠ `0` et `ls -a /app` sans `.env` ni `.git`. Sinon le signaler.
- [ ] **Step 6:** Commit — `:wrench: pin dependencies, non-root container, no secrets in the image`

---

### Task 10: CI, Makefile, documentation (M6, dette)

**Files:** Create `.github/workflows/ci.yml` · Delete `.github/workflows/pylint.yml` · Modify `Makefile`, `README.md`

- [ ] **Step 1:** `ci.yml` : `push` et `pull_request` ; `permissions: contents: read` ; Python `3.12` ; étapes pylint, tests, `pip-audit -r requirements.txt`, `bandit -r app bankAccountManager -x app/tests` ; actions épinglées par SHA (obtenus par `git ls-remote`).
- [ ] **Step 2:** `Makefile` : conteneur `bank-account-mngt-api` ; cibles `test`, `migrate`, `audit` ; aide à jour.
- [ ] **Step 3:** `README.md` : API REST seule ; installation Docker Compose ; `create_bank` puis `createsuperuser` ; tableau des endpoints ; authentification par cookie et CSRF ; montants en euros côté API, centimes en base ; règles d'accès ; variables de sécurité ; reverse proxy TLS requis. Retirer l'URL GitLab et les captures du front.
- [ ] **Step 4:** Vérifier : `make check`, `make test`, `make audit`.
- [ ] **Step 5:** Commit — `:memo: CI with tests and security scans, fix Makefile, rewrite README`

---

## Actions manuelles hors dépôt

1. Recréer la base : `docker compose down -v` puis `make up` (les migrations ont été réinitialisées), `make run cmd=create_bank`, `make run cmd=createsuperuser`.
2. Générer une nouvelle `SECRET_KEY` : l'ancienne valeur `django-insecure-…` est dans l'historique git.
3. Reverse proxy TLS devant le port 5555, transmettant `X-Forwarded-Proto`.
4. Renseigner `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` avec l'origine exacte du front ; si le front et l'API ne partagent pas le même site, `AUTH_COOKIE_SAMESITE=None`.
5. Tester sous PostgreSQL deux transactions simultanées sur le même compte.
