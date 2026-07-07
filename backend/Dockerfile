FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 의존성 레이어 (requirements 변경 시에만 재빌드)
# build-essential: asyncmy가 arm64 wheel이 없어 소스 빌드 필요 (설치 후 제거)
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install -r requirements.txt \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Playwright chromium + 시스템 의존성 (pip 버전과 항상 일치하는 브라우저 설치)
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# 주의: APScheduler(크롤링/알림)가 프로세스 내에서 돌므로 워커는 반드시 1개
ENTRYPOINT ["./docker-entrypoint.sh"]
