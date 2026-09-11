"""item.status에 reserved 추가 + 잘못 sold로 묶인 예약중 매물 재분류

SOLD_RE가 `거래완료|판매완료|예약\\s*중|예약\\s*완료`를 모두 잡아 **예약중까지
sold로 묶고** 있었다. 예약중은 아직 팔리지 않은 상태이고 예약이 깨지면 다시
판매되는데도 시세에서 빠져 있었다.

당근만 이 영향을 받는다. 당근 검색 카드에는 플랫폼이 붙인 상태 배지가 있고
_parse_listing_text()가 카드 텍스트를 통째로 제목으로 가져오면서 배지가 제목에
섞여 들어오기 때문이다. 번개·중고나라는 검색 API가 판매완료 매물을 주지 않거나
별도 필드로 주는데 그 필드를 읽지 않아 sold 판정이 거의 0이다.

재분류 규칙: 현재 sold이고 제목에 예약 표기가 있으며 거래완료/판매완료 표기가
**없는** 매물 → reserved. 둘 다 있으면 판매완료가 이긴다.

Revision ID: 20260909_0005
Revises: 20260909_0004
"""

from alembic import op

revision = "20260909_0005"
down_revision = "20260909_0004"
branch_labels = None
depends_on = None

_RESERVED_RE = "예약 ?중|예약 ?완료"
_SOLD_RE = "거래 ?완료|판매 ?완료|나눔 ?완료"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE item MODIFY COLUMN status "
        "ENUM('active','reserved','sold','deleted') NOT NULL"
    )
    op.execute(
        f"""
        UPDATE item
           SET status = 'reserved'
         WHERE status = 'sold'
           AND title REGEXP '{_RESERVED_RE}'
           AND title NOT REGEXP '{_SOLD_RE}'
        """
    )


def downgrade() -> None:
    # reserved를 없애기 전에 sold로 되돌려야 ENUM 축소가 가능하다
    op.execute("UPDATE item SET status = 'sold' WHERE status = 'reserved'")
    op.execute(
        "ALTER TABLE item MODIFY COLUMN status "
        "ENUM('active','sold','deleted') NOT NULL"
    )
