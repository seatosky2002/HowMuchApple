"""KST로 저장된 기존 타임스탬프를 UTC로 보정한다

배경: mysql 컨테이너가 `TZ=Asia/Seoul`이라 `NOW()`가 KST를 반환했다. 컬럼 기본값이
`NOW()`인 곳(created_at 계열)은 KST로 저장되고, 애플리케이션이 직접 쓰는 곳
(`datetime.now(timezone.utc)`)은 UTC로 저장돼 9시간 어긋났다.

실측: `item` 74,758건 중 17,907건(24.0%)이 `updated_at < created_at`이었다.
`crawler_log`는 한 행 안에서 `started_at`(UTC)과 `created_at`(KST)이 9시간 달랐다.

이 마이그레이션은 KST로 저장된 값에서 9시간을 뺀다. 한국은 서머타임이 없어
오프셋이 +9로 고정이므로 단순 감산이 정확하다.

## 컬럼 분류

UTC로 이미 저장된 값 — **건드리지 않는다**
  crawler_log.started_at / finished_at, refresh_token.expires_at / revoked_at,
  verification.expires_at / verified_at, users.deleted_at, price_stats.bucket_ts

KST로 저장된 값 — 9시간 뺀다
  alert.triggered_at, crawler_log.created_at, item.created_at,
  refresh_token.created_at, users.created_at, verification.created_at,
  watchlist.created_at

INSERT는 KST, UPDATE는 UTC로 섞인 값 — 조건부로 뺀다
  item.updated_at, users.updated_at, watchlist.updated_at
  INSERT 직후에는 `updated_at = created_at`(둘 다 NOW())이고, 한 번이라도 UPDATE된
  행은 `onupdate`가 UTC를 넣어 `updated_at < created_at`이 된다. 따라서
  `updated_at >= created_at`인 행만 아직 KST로 보고 감산한다.
  (같은 초에 갱신된 극소수는 구분이 불가능해 KST로 취급된다 — 최대 9시간 오차가
  남지만 갱신 직후 행이라 영향이 없다.)

Revision ID: 20260908_0003
Revises: 20260907_0002
"""

from alembic import op

revision = "20260908_0003"
down_revision = "20260907_0002"
branch_labels = None
depends_on = None

KST_OFFSET_HOURS = 9

# (테이블, 컬럼) — 전부 KST로 저장된 것
PLAIN_KST_COLUMNS = [
    ("alert", "triggered_at"),
    ("crawler_log", "created_at"),
    ("item", "created_at"),
    ("refresh_token", "created_at"),
    ("users", "created_at"),
    ("verification", "created_at"),
    ("watchlist", "created_at"),
]

# (테이블) — updated_at이 created_at과 같을 때만 KST
MIXED_UPDATED_TABLES = ["item", "users", "watchlist"]


def upgrade() -> None:
    for table, column in PLAIN_KST_COLUMNS:
        op.execute(
            f"UPDATE {table} SET {column} = {column} - INTERVAL {KST_OFFSET_HOURS} HOUR "
            f"WHERE {column} IS NOT NULL"
        )
    for table in MIXED_UPDATED_TABLES:
        # created_at은 위에서 이미 UTC로 옮겨졌으므로, 아직 KST인 updated_at은
        # 보정된 created_at보다 9시간 앞서 있다 → `>=` 대신 그 관계로 판별한다.
        op.execute(
            f"UPDATE {table} SET updated_at = updated_at - INTERVAL {KST_OFFSET_HOURS} HOUR "
            f"WHERE updated_at IS NOT NULL AND created_at IS NOT NULL "
            f"AND updated_at = created_at + INTERVAL {KST_OFFSET_HOURS} HOUR"
        )


def downgrade() -> None:
    for table in MIXED_UPDATED_TABLES:
        op.execute(
            f"UPDATE {table} SET updated_at = updated_at + INTERVAL {KST_OFFSET_HOURS} HOUR "
            f"WHERE updated_at IS NOT NULL AND created_at IS NOT NULL "
            f"AND updated_at = created_at"
        )
    for table, column in PLAIN_KST_COLUMNS:
        op.execute(
            f"UPDATE {table} SET {column} = {column} + INTERVAL {KST_OFFSET_HOURS} HOUR "
            f"WHERE {column} IS NOT NULL"
        )
