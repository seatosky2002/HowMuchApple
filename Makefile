.PHONY: run dev migrate revision install playwright mysql-up mysql-down mysql-logs mysql-reset

install:
	pip install -r requirements.txt

playwright:
	playwright install chromium

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(msg)"

downgrade:
	alembic downgrade -1

mysql-up:
	docker compose up -d mysql

mysql-down:
	docker compose down

mysql-logs:
	docker compose logs -f mysql

mysql-reset:
	docker compose down -v
	docker compose up -d mysql
