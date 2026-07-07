#!/bin/bash
# 최초 1회 Let's Encrypt 인증서 발급 스크립트.
#
# 문제: nginx는 인증서가 없으면 443 설정 때문에 기동 실패 → certbot은 nginx(80)가
#       떠 있어야 발급 가능 (닭-달걀). 임시 자체서명 인증서로 nginx를 먼저 띄우고
#       실제 인증서 발급 후 교체한다.
#
# 사용: 저장소 루트에서  DOMAIN/CERTBOT_EMAIL이 .env에 있는 상태로
#       ./deploy/init-letsencrypt.sh

set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"

# .env에서 DOMAIN, CERTBOT_EMAIL 로드
if [ -f .env ]; then
  export "$(grep -E '^(DOMAIN|CERTBOT_EMAIL)=' .env | xargs)"
fi
: "${DOMAIN:?.env에 DOMAIN이 필요합니다}"
: "${CERTBOT_EMAIL:?.env에 CERTBOT_EMAIL이 필요합니다}"

echo "### 1/4 임시 자체서명 인증서 생성 ($DOMAIN)"
$COMPOSE run --rm --entrypoint sh certbot -c "
  mkdir -p /etc/letsencrypt/live/$DOMAIN &&
  apk add --no-cache openssl >/dev/null 2>&1 || true &&
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
    -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
    -subj '/CN=$DOMAIN'
"

echo "### 2/4 nginx 기동"
$COMPOSE up -d --build nginx

echo "### 3/4 임시 인증서 삭제 후 실제 인증서 발급"
$COMPOSE run --rm --entrypoint sh certbot -c "
  rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf
"
$COMPOSE run --rm certbot certonly --webroot -w /var/www/certbot \
  --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email \
  -d "$DOMAIN"

echo "### 4/4 nginx 리로드"
$COMPOSE exec nginx nginx -s reload

echo "완료. 이후 갱신은 certbot 컨테이너가 자동 처리합니다."
