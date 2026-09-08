"""감시 알림 상태 테이블 추가

중복 알림 억제와 회복 알림 판단에 쓴다. 메모리에 두면 배포마다 초기화돼 같은
장애로 다시 알림이 오고 회복 여부도 알 수 없다.

행 하나짜리 키/값 테이블이다 (현재 키: crawler_health).

주의: 초기 마이그레이션 20260616_0001이 Base.metadata.create_all()을 쓰기 때문에
**빈 DB에서는 0001이 이 테이블까지 이미 만든다**. 그래서 존재 여부를 보고
건너뛴다. 이 구조상 앞으로 테이블을 추가하는 마이그레이션은 모두 같은 가드가
필요하다 (0001을 명시적 DDL로 바꾸는 게 근본 해결이지만 별개 작업이다).

Revision ID: 20260909_0004
Revises: 20260908_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0004"
down_revision = "20260908_0003"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("monitor_state"):
        # 빈 DB에서 0001의 create_all()이 이미 만든 경우
        return
    op.create_table(
        "monitor_state",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "notified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    if _has_table("monitor_state"):
        op.drop_table("monitor_state")
