# Bank Account Manager — API

REST API to track personal expenses: accounts, transactions, categories, recurring operations, budgets and bank statement import. Built with Django and Django REST Framework. The web front-end lives in its own repository.

## Installation

1. Copy `.env.example` to `.env` and fill it in. `SECRET_KEY` must be a random value of at least 50 characters:

   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(60))"
   ```

2. Build and start the stack:

   ```sh
   make reload
   ```

3. Create the bank account and an administrator:

   ```sh
   make run cmd=create_bank
   make run cmd=createsuperuser
   ```

4. Create the regular users in the back-office at `/admin/`. Users cannot be created through the API.

The stack has three containers: the API (port 5555, reachable from the host only), PostgreSQL, and a scheduler that creates the recurring transactions that are due, once an hour. In production the API must sit behind a TLS reverse proxy that forwards `X-Forwarded-Proto` (see [Security](#security)).

After a code change, use `make reload`: `make up` does not rebuild the image.

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
make test            # test suite on SQLite, no service needed
make test-postgres   # same suite on the compose PostgreSQL, including the concurrency test
make check           # pylint
make audit           # pip-audit and bandit
```

Migrations are generated locally with `make migrations` and committed. The container only applies them.

The OpenAPI schema is served at `/schema/` (signed-in users). With `DEBUG` on, an interactive version is at `/docs/`.

## Concepts

- **Accounts** belong to one or more users. The creator is the first owner and can share the account with another user by username.
- **The bank account** (`is_bank`) is the counterparty for anything external: a credit is a transaction from the bank to your account, a debit goes from your account to the bank. Its own balance is never tracked. Get its id from `GET /accounts/bank/`.
- **Transactions** move an amount from a sender to a receiver on a `date`. Creating, editing or deleting one updates the balances of both accounts.
- **Categories** are either shared (no owner, managed by staff) or private to the user who created them. A transaction may have none.
- **Recurring transactions** are rules (weekly, monthly, yearly) that create a real transaction each time they fall due.
- **Budgets** are monthly spending limits per category, reported with what is spent and what is left.

### Money

Amounts are stored as integer cents and exchanged as decimal euros with two decimals, always as strings:

| Stored | Sent and received |
|---|---|
| `1050` | `"10.50"` |

A transaction amount is always strictly positive: the direction is given by `sender` and `receiver`.

### Income and expense

Statistics and budgets look at a set of accounts (all of yours, or one). An **expense** is money leaving the set, an **income** is money entering it. A transfer between two of your own accounts is neither, and the opening transaction of an account is not an income.

## Authentication

Tokens are carried by `HttpOnly` cookies and never appear in a response body. Browser clients must send requests with credentials (`credentials: "include"`).

Every write request (`POST`, `PUT`, `PATCH`, `DELETE`) must carry the CSRF token in the `X-CSRFToken` header. The token is returned by `/token/`, `/token/refresh/` and `/csrf/`.

| Endpoint | Purpose |
|---|---|
| `POST /token/` | Log in with `username` and `password`, as JSON. Sets the cookies, returns `{"csrfToken"}`. Limited to 5 attempts per minute. |
| `POST /token/refresh/` | Renew the access token (15 minutes) and rotate the refresh token (1 day). Returns 401 when the session is over. |
| `POST /token/logout/` | Revoke the refresh token and clear the cookies. |
| `GET /csrf/` | Get a CSRF token, for example after a page reload. |
| `POST /users/me/password/` | Change the password with `current_password` and `new_password`. Signs every other session out. |

## Endpoints

| Endpoint | Methods | Notes |
|---|---|---|
| `/users/` | `GET`, `PUT`, `PATCH` | Yourself only, unless staff. `is_staff` is read-only. |
| `/users/me/` | `GET`, `PATCH` | The current user. |
| `/accounts/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Your active accounts, as a plain list. `balance` is set at creation and ignored afterwards. `DELETE` deactivates the account. |
| `/accounts/bank/` | `GET` | Id and label of the bank account. |
| `/accounts/<id>/share/`, `/unshare/` | `POST` | Add or remove an owner, with `{"username"}`. An account always keeps one owner. |
| `/accounts/<id>/import/` | `POST` | Import a CSV or OFX statement, as a multipart field named `file`. |
| `/transactions/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Paginated, 100 per page. Both sides must be one of your active accounts or the bank. |
| `/transactions/by_account/<id>/` | `GET` | Transactions of one of your accounts. |
| `/categories/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Plain list. Shared categories are read-only for non-staff users. |
| `/recurring-transactions/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Plain list. `frequency` and `start_date` cannot change after creation. |
| `/budgets/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Plain list. `?month=YYYY-MM` picks the month reported in `spent` and `remaining`. |
| `/stats/by_category/` | `GET` | Expense and income per category. |
| `/stats/monthly/` | `GET` | Income, expense, net and end-of-month balance per month. |
| `/health/` | `GET`, `PATCH` | Public status. `PATCH` is for staff, see [Maintenance](#maintenance). |
| `/schema/` | `GET` | OpenAPI description. |

Dates are `YYYY-MM-DD`; timestamps are ISO 8601 with a UTC offset.

### Transaction filters

`/transactions/` and `/transactions/by_account/<id>/` accept:

| Parameter | Meaning |
|---|---|
| `date_from`, `date_to` | Operation date range, inclusive. |
| `category` | A category id, or `none` for transactions without category. |
| `account` | An account id, on either side. |
| `amount_min`, `amount_max` | In euros. |
| `search` | Text contained in the comment. |
| `ordering` | `date`, `amount` or `created_at`, with a leading `-` for descending. Default `-date`. |

The statistics endpoints accept `date_from`, `date_to` and `account`.

### Statement import

CSV files need a header line with a date column, a label column (`label`, `libellé`, `description`) and either an amount column (`amount`, `montant`) or `debit` and `credit` columns. Separators `;`, `,` and tab, French or English number formats and the usual date formats are recognised. OFX files are read as exported by banks.

A negative line becomes a debit to the bank, a positive one a credit. Importing the same statement twice creates nothing new. The answer is `{"created", "skipped", "errors"}`, where `errors` lists the lines that could not be read. Files are limited to 1 MB and 5000 lines.

## Maintenance

`GET /health/` is public and answers `{"status": "ok", "maintenance": false, "message": ""}`, or 503 with `"status": "error"` when the database does not answer.

While maintenance is on, every other API endpoint answers 503 with `{"maintenance": true, "message": "..."}`. The login, `/health/` and the back-office stay reachable. Switch it:

- from the back-office, in **Site settings**;
- with `make maintenance state=on message="Back at 2pm"` (and `state=off`);
- as a staff user, with `PATCH /health/ {"maintenance": true, "message": "..."}`.

## Back-office

`/admin/` gives staff full access. Balances and amounts are typed in euros there. Editing a balance directly does not create a transaction; transactions created or edited there update balances as they do through the API. The balance history of `/stats/monthly/` is rebuilt from the current balance, so a balance edited by hand shifts the whole curve.

## Security

| Variable | Effect |
|---|---|
| `DEBUG` | Only `1`, `true`, `yes` or `on` enable it. Enables the browsable API, `/docs/` and session login; never use it in production. |
| `HTTPS_ONLY` | HTTPS redirect, HSTS and `Secure` cookies. On by default when `DEBUG` is off. |
| `SECURE_HSTS_SECONDS` | HSTS duration, one year by default. |
| `AUTH_COOKIE_SAMESITE` | `Lax` by default. Set `None` when the front-end is served from another site than the API. |
| `NUM_PROXIES` | Number of trusted reverse proxies, used to find the client address for login throttling. `1` by default. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Exact origin of the front-end, for example `https://app.example.org`. |

With `DEBUG` off, the application refuses to start with a `SECRET_KEY` shorter than 50 characters or with `*` in `ALLOWED_HOSTS`.

API responses carry a strict `Content-Security-Policy`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`. The policy for the front-end pages is set by whatever serves them.

Login, password change and account sharing are rate-limited. The counters live in the memory of the single gunicorn process: running several processes needs a shared cache first.
