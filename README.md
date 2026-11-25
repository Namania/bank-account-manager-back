# Bank Account Manager — API

REST API to track personal expenses: accounts, transactions between accounts and categories. Built with Django and Django REST Framework. The web front-end lives in its own repository.

## Installation

1. Copy `.env.example` to `.env` and fill it in. `SECRET_KEY` must be a random value of at least 50 characters:

   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(60))"
   ```

2. Start the stack:

   ```sh
   make up
   ```

3. Create the bank account and an administrator:

   ```sh
   make run cmd=create_bank
   make run cmd=createsuperuser
   ```

4. Create the regular users in the back-office at `/admin/`. Users cannot be created through the API.

The API listens on port 5555. In production it must sit behind a TLS reverse proxy that forwards `X-Forwarded-Proto` (see [Security](#security)).

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
make test     # test suite, on SQLite, no service needed
make check    # pylint
make audit    # pip-audit and bandit
```

Migrations are generated locally with `make migrations` and committed. The container only applies them.

## Concepts

- **Accounts** belong to one or more users. The user who creates an account is its owner; sharing an account with someone else is done in the back-office.
- **The bank account** (`is_bank`) is the counterparty for anything external: a credit is a transaction from the bank to your account, a debit goes from your account to the bank. Its own balance is never tracked. Get its id from `GET /accounts/bank/`.
- **Transactions** move an amount from a sender to a receiver. Creating, editing or deleting a transaction updates the balances of both accounts.
- **Categories** are either shared (no owner, managed by staff) or private to the user who created them.

### Money

Amounts are stored as integer cents and exchanged as decimal euros with two decimals, always as strings:

| Stored | Sent and received |
|---|---|
| `1050` | `"10.50"` |

A transaction amount is always strictly positive: the direction is given by `sender` and `receiver`.

## Authentication

Tokens are carried by `HttpOnly` cookies and never appear in a response body. Browser clients must send requests with credentials (`credentials: "include"`).

Every write request (`POST`, `PUT`, `PATCH`, `DELETE`) must carry the CSRF token in the `X-CSRFToken` header. The token is returned by `/token/`, `/token/refresh/` and `/csrf/`.

| Endpoint | Purpose |
|---|---|
| `POST /token/` | Log in with `username` and `password`. Sets the cookies, returns `{"csrfToken"}`. Limited to 5 attempts per minute. |
| `POST /token/refresh/` | Renew the access token (15 minutes) and rotate the refresh token (1 day). Returns 401 when the session is over. |
| `POST /token/logout/` | Revoke the refresh token and clear the cookies. |
| `GET /csrf/` | Get a CSRF token, for example after a page reload. |

## Endpoints

| Endpoint | Methods | Notes |
|---|---|---|
| `/users/` | `GET`, `PUT`, `PATCH` | Yourself only, unless staff. `is_staff` is read-only. |
| `/users/me/` | `GET`, `PATCH` | The current user. |
| `/accounts/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Your active accounts. `balance` is set at creation and ignored afterwards. `DELETE` deactivates the account. |
| `/accounts/bank/` | `GET` | Id and label of the bank account. |
| `/transactions/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Both sides must be one of your active accounts or the bank. |
| `/transactions/by_account/<id>/` | `GET` | Transactions of one of your accounts. |
| `/categories/` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | Shared categories are read-only for non-staff users. |

Lists are paginated, 100 items per page. Dates are ISO 8601 with a UTC offset.

## Back-office

`/admin/` gives staff full access. Balances and amounts are typed in euros there. Editing a balance directly does not create a transaction; transactions created or edited there update balances as they do through the API.

## Security

| Variable | Effect |
|---|---|
| `DEBUG` | Only `1`, `true`, `yes` or `on` enable it. Enables the browsable API and session login; never use it in production. |
| `HTTPS_ONLY` | HTTPS redirect, HSTS and `Secure` cookies. On by default when `DEBUG` is off. |
| `SECURE_HSTS_SECONDS` | HSTS duration, one year by default. |
| `AUTH_COOKIE_SAMESITE` | `Lax` by default. Set `None` when the front-end is served from another site than the API. |
| `NUM_PROXIES` | Number of trusted reverse proxies, used to find the client address for login throttling. `1` by default. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Exact origin of the front-end, for example `https://app.example.org`. |

With `DEBUG` off, the application refuses to start with a `SECRET_KEY` shorter than 50 characters or with `*` in `ALLOWED_HOSTS`.

API responses carry a strict `Content-Security-Policy`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`. The policy for the front-end pages is set by whatever serves them.
