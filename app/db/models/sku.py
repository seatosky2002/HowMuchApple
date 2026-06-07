from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Decimal, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SKU(Base):
    __tablename__ = "sku"

    sku_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.category_id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    search_count: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped["Category"] = relationship(back_populates="skus")
    attributes: Mapped[list["SKUAttribute"]] = relationship(back_populates="sku")
    price_stats: Mapped[list["PriceStats"]] = relationship(back_populates="sku")
    items: Mapped[list["Item"]] = relationship(back_populates="sku")
    watchlists: Mapped[list["Watchlist"]] = relationship(back_populates="sku")


class SKUAttribute(Base):
    __tablename__ = "sku_attribute"

    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.sku_id", ondelete="CASCADE"), primary_key=True)
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.attribute_id", ondelete="CASCADE"), primary_key=True
    )
    option_id: Mapped[int | None] = mapped_column(ForeignKey("attribute_option.option_id", ondelete="SET NULL"))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_int: Mapped[int | None] = mapped_column(Integer)
    value_decimal: Mapped[float | None] = mapped_column(Decimal(12, 2))
    value_bool: Mapped[bool | None] = mapped_column()

    sku: Mapped["SKU"] = relationship(back_populates="attributes")
    attribute: Mapped["Attribute"] = relationship()
    option: Mapped["AttributeOption | None"] = relationship()


class PriceStats(Base):
    __tablename__ = "price_stats"

    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.sku_id", ondelete="CASCADE"), primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("emd.region_id", ondelete="CASCADE"), primary_key=True)
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    items_num: Mapped[int] = mapped_column(Integer, default=0)
    sum_price: Mapped[int] = mapped_column(BigInteger, default=0)
    avg_price: Mapped[float] = mapped_column(Decimal(12, 2), default=0)
    min_price: Mapped[int] = mapped_column(Integer, default=0)
    max_price: Mapped[int] = mapped_column(Integer, default=0)

    sku: Mapped["SKU"] = relationship(back_populates="price_stats")
    region: Mapped["EMD"] = relationship()
