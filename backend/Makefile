COMPOSE_FILE ?= ../docker-compose.yml

.PHONY: run dev migrate revision install playwright mysql-up mysql-down mysql-logs mysql-reset

install:
	python -m pip install -r requirements.txt

playwright:
	python -m playwright install chromium

dev:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate:
	python -m alembic upgrade head

revision:
	python -m alembic revision --autogenerate -m "$(msg)"

downgrade:
	python -m alembic downgrade -1

mysql-up:
	docker compose -f $(COMPOSE_FILE) up -d mysql

mysql-down:
	docker compose -f $(COMPOSE_FILE) down

mysql-logs:
	docker compose -f $(COMPOSE_FILE) logs -f mysql

mysql-reset:
	docker compose -f $(COMPOSE_FILE) down -v
	docker compose -f $(COMPOSE_FILE) up -d mysql
