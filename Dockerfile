FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user; it only needs to write the collected static files.
RUN useradd --system --no-create-home app && mkdir -p /app/staticfiles && chown -R app /app/staticfiles
USER app

# Migrations are generated in development and committed: never run makemigrations here.
# Threaded worker: a browser that opens a connection without sending a request
# (preconnect, keep-alive) would otherwise block the only sync worker until it
# is killed by the timeout. One process keeps the login throttle counters, which
# live in per-process memory, exact.
# The control socket is unused and its default path needs a home directory.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn bankAccountManager.wsgi:application --bind 0.0.0.0:5555 --worker-class gthread --workers 1 --threads 8 --no-control-socket"]
