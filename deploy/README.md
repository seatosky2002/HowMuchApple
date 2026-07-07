# 배포 가이드

서버 1대(Oracle A1 / EC2 등, Ubuntu + Docker 기준)에 전체 스택을 올린다.

```
[VM]
├── nginx    : HTTPS 종료, 프론트 정적 서빙, /api → backend 프록시
├── backend  : FastAPI + APScheduler(크롤링 06:00/15:00) + Playwright
├── mysql    : 데이터 (호스트 포트 미노출)
└── certbot  : 인증서 자동 갱신 (12시간 주기)
```

## 최초 배포

### 0. 서버 준비

- Docker + Docker Compose 설치, 80/443 포트 개방 (Oracle은 Security List도 확인)
- 도메인 A 레코드를 서버 IP로 연결
- ARM(Oracle A1)/x86 모두 지원 — 이미지가 양쪽 아키텍처에서 빌드됨

### 1. 코드 및 환경변수

```bash
git clone https://github.com/seatosky2002/HowMuchApple.git && cd HowMuchApple
git checkout main
```

**저장소 루트 `.env`** (compose가 읽음):

```env
DOMAIN=howmuchapple.example.com
CERTBOT_EMAIL=you@example.com
MYSQL_PASSWORD=<강력한 비밀번호>
MYSQL_ROOT_PASSWORD=<강력한 비밀번호>
```

**`backend/.env`** (앱 설정):

```env
SECRET_KEY=<openssl rand -hex 32 로 생성>
COOKIE_SECURE=true
FRONTEND_URL=https://howmuchapple.example.com
# MYSQL_HOST/PORT/PASSWORD는 compose가 주입하므로 생략 가능
# SMTP_USER/SMTP_PASSWORD 등 메일 설정은 필요 시 추가
```

### 2. 인증서 발급 (최초 1회)

```bash
chmod +x deploy/*.sh
./deploy/init-letsencrypt.sh
```

### 3. 전체 기동

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # 상태 확인
curl -s https://$DOMAIN/health                       # {"status":"ok",...}
```

마이그레이션(alembic)은 backend 컨테이너 시작 시 자동 실행된다.

### 4. 백업 cron 등록

```bash
crontab -e
# 매일 04:30 (첫 크롤링 전)
30 4 * * * /home/ubuntu/HowMuchApple/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
```

백업 파일(`deploy/backups/`)은 반드시 주기적으로 서버 밖으로 복사할 것.

## 평소 배포 (업데이트)

```bash
cd HowMuchApple
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

## 운영 명령어

| 작업 | 명령 |
|---|---|
| 로그 확인 | `docker compose -f docker-compose.prod.yml logs -f backend` |
| 헬스체크 | `curl https://$DOMAIN/health` |
| 크롤링 이력 | `docker compose -f docker-compose.prod.yml exec mysql mysql -uhowmuch -p howmuch -e "SELECT * FROM crawler_log ORDER BY log_id DESC LIMIT 10;"` |
| 수동 크롤링 | `docker compose -f docker-compose.prod.yml exec backend python -m app.crawlers.run --platform daangn --limit-targets 2` |
| DB 접속 | `docker compose -f docker-compose.prod.yml exec mysql mysql -uhowmuch -p howmuch` |
| 재시작 | `docker compose -f docker-compose.prod.yml restart backend` |

## 주의사항

- **backend 워커는 1개 고정** (`docker-entrypoint.sh`): APScheduler가 앱 안에서 돌아서 워커를 늘리면 크롤링/알림이 중복 실행된다. 트래픽 때문에 스케일이 필요해지면 크롤러를 별도 프로세스로 분리하는 게 선행 조건.
- `/docs`(Swagger)는 nginx에서 프록시하지 않으므로 외부 비노출. 필요하면 SSH 터널로: `ssh -L 8000:localhost:8000 server` 후 backend 포트 직접 접근.
- 크롤링 스케줄 변경은 `backend/.env`에 `CRAWLER_SCHEDULE="0 6,15 * * *"` 형식으로 오버라이드 후 backend 재시작.
- 로컬 개발은 기존 방식 유지 (`docker-compose.yml`의 MySQL + `make dev`). 이 파일들은 프로덕션 전용.
