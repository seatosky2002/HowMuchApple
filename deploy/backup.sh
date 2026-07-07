#!/bin/bash
# MySQL 백업 스크립트 — cron 등록용
#   crontab 예시 (매일 04:30, 크롤링 시작 전):
#   30 4 * * * /home/ubuntu/HowMuchApple/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
#
# 주의: 백업 파일을 서버 밖(로컬 scp, Object Storage 등)으로 주기적으로 복사할 것.
#       특히 Oracle Free Tier는 계정/인스턴스 회수 리스크가 있음.

set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="deploy/backups"
KEEP_DAYS=14
STAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

docker compose -f docker-compose.prod.yml exec -T mysql \
  sh -c 'exec mysqldump -uhowmuch -p"$MYSQL_PASSWORD" --single-transaction --routines howmuch' \
  | gzip > "$BACKUP_DIR/howmuch_$STAMP.sql.gz"

# 보존 기간 지난 백업 삭제
find "$BACKUP_DIR" -name "howmuch_*.sql.gz" -mtime +$KEEP_DAYS -delete

echo "[backup] done: $BACKUP_DIR/howmuch_$STAMP.sql.gz ($(du -h "$BACKUP_DIR/howmuch_$STAMP.sql.gz" | cut -f1))"
