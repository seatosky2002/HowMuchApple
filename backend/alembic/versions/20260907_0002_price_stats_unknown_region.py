"""price_stats에 지역 미상(emd_id=0) 집계를 허용한다

지역을 못 알아낸 매물이 전국 시세 추이에서 통째로 빠지고 있었다. price_stats의
PK가 (sku_id, emd_id, bucket_ts)라 emd_id가 필요한데, snapshot_price_stats()가
emd_id IS NULL 매물을 그냥 버렸기 때문이다(운영 실측 6,986건 — SKU는 확정됐는데
판매자가 지역을 안 적은 매물).

전국 조회 경로는 이미 emd를 무시하고 합산하도록 되어 있어서(get_price_trend의
emd_id=None 분기, get_sku_with_price의 stats 분기), 스냅샷에 "지역 미상" 몫만
넣어주면 그대로 반영된다.

emd_id=0을 예약값으로 쓰고 emd FK를 제거한다. 대안으로 emd/sgg/sd에 가상 "미상"
행을 넣는 방법이 있었지만, /api/v1/regions가 지역 목록을 그대로 내려주므로 UI
드롭다운에 "미상"이 노출되고 region_matcher·dedupe_regions 등 지역 로직 전반에
가상 행이 새어들 위험이 있어 택하지 않았다.

FK를 제거하므로 emd 행을 삭제할 때 price_stats에 고아 행이 남을 수 있다.
현재 emd를 삭제하는 유일한 경로인 dedupe_regions.py는 price_stats를 직접
remap/삭제하므로 문제되지 않는다.

Revision ID: 20260907_0002
Revises: 20260616_0001
"""

from alembic import op

revision = "20260907_0002"
down_revision = "20260616_0001"
branch_labels = None
depends_on = None

UNKNOWN_EMD_ID = 0


def upgrade() -> None:
    op.drop_constraint("price_stats_ibfk_2", "price_stats", type_="foreignkey")


def downgrade() -> None:
    # FK를 되살리려면 예약값 행이 먼저 사라져야 한다
    op.execute(f"DELETE FROM price_stats WHERE emd_id = {UNKNOWN_EMD_ID}")
    op.create_foreign_key(
        "price_stats_ibfk_2",
        "price_stats",
        "emd",
        ["emd_id"],
        ["emd_id"],
        ondelete="CASCADE",
    )
