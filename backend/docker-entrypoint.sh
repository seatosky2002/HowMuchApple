#!/bin/sh
set -e

echo "[entrypoint] running alembic migrations..."
alembic upgrade head

echo "[entrypoint] starting uvicorn..."
# workers=1 고정: APScheduler가 앱 내에서 돌아서 워커를 늘리면 크롤링/알림이 중복 실행됨
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
