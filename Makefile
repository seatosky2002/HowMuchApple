.PHONY: run dev migrate revision install playwright

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
