import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ItemStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    deleted = "deleted"


class Item(Base):
    __tablename__ = "item"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.sku_id", ondelete="SET NULL"), nullable=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("emd.region_id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.category_id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.active)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow
    )

    sku: Mapped["SKU"] = relationship(back_populates="items")
    region: Mapped["EMD"] = relationship()
    category: Mapped["Category"] = relationship(back_populates="items")
    attribute_values: Mapped[list["ItemAttributeValue"]] = relationship(back_populates="item")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="item")


class ItemAttributeValue(Base):
    __tablename__ = "item_attribute_value"

    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item.item_id", ondelete="CASCADE"), primary_key=True)
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.attribute_id", ondelete="CASCADE"), primary_key=True
    )
    option_id: Mapped[int | None] = mapped_column(ForeignKey("attribute_option.option_id", ondelete="SET NULL"))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_int: Mapped[int | None] = mapped_column(Integer)
    value_decimal: Mapped[float | None] = mapped_column(Numeric(12, 2))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)

    item: Mapped["Item"] = relationship(back_populates="attribute_values")
    attribute: Mapped["Attribute"] = relationship()
    option: Mapped["AttributeOption | None"] = relationship()
