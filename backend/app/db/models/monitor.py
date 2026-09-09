"""감시 알림 상태 저장 — 중복 알림 억제와 회복 알림 판단에 쓴다.

메모리에 두면 배포마다 초기화돼 같은 장애로 다시 알림이 오고, 회복 여부도
판단할 수 없다. 행 하나짜리 키/값 테이블로 최소하게 둔다.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class MonitorState(Base):
    __tablename__ = "monitor_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 마지막으로 알린 상태 (ok / warn / down)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # 같은 장애가 이어지는 동안 억제하기 위한 지문 (플랫폼별 상태 조합)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=utc_now
    )
