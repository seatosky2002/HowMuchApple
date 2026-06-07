from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    watch_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.sku_id", ondelete="CASCADE"), nullable=False)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("emd.region_id", ondelete="SET NULL"))
    max_price: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    alert_email: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="watchlists")
    sku: Mapped["SKU"] = relationship(back_populates="watchlists")
    region: Mapped["EMD | None"] = relationship()
    alerts: Mapped[list["Alert"]] = relationship(back_populates="watchlist", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    watch_id: Mapped[int] = mapped_column(ForeignKey("watchlist.watch_id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item.item_id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_email: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    user: Mapped["User"] = relationship(back_populates="alerts")
    watchlist: Mapped["Watchlist"] = relationship(back_populates="alerts")
    item: Mapped["Item | None"] = relationship(back_populates="alerts")
