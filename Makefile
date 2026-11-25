.SILENT:

API_CONTAINER = bank-account-mngt-api
TEST_SETTINGS = --settings=bankAccountManager.settings_test

all: help

up:
	docker compose up -d

reload:
	docker compose up -d --build
	@if [ "$(logs)" = "1" ]; then \
		docker logs -f $(API_CONTAINER); \
	fi

down:
	docker compose down

migrations:
	python manage.py makemigrations app $(TEST_SETTINGS)

migrate:
	docker exec -it $(API_CONTAINER) python manage.py migrate

test:
	python manage.py test app $(TEST_SETTINGS)

check:
	pylint $$(git ls-files '*.py')

audit:
	pip-audit -r requirements.txt
	bandit -q -ll -r app bankAccountManager -x app/tests

run:
ifndef cmd
	$(error cmd must be set, make run cmd=createsuperuser)
else
	docker exec -it $(API_CONTAINER) python manage.py $(cmd)
endif

help:
	echo "Usage: make <target>"
	echo ""
	echo "    up          Start docker compose in detached mode"
	echo "    reload      Rebuild and restart (logs=1 to follow the API logs)"
	echo "    down        Stop docker compose"
	echo "    migrations  Generate migrations locally (commit the result)"
	echo "    migrate     Apply migrations inside the API container"
	echo "    test        Run the test suite (SQLite, no services needed)"
	echo "    check       Run pylint"
	echo "    audit       Run pip-audit and bandit"
	echo "    run         Run a manage.py command in the container (ex: make run cmd=createsuperuser)"
	echo "    help        Show this help message"
	echo ""
