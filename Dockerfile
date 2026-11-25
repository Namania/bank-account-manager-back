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
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn bankAccountManager.wsgi:application --bind 0.0.0.0:5555"]
