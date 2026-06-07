import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttributeDatatype(str, enum.Enum):
    option = "option"
    text = "text"
    int = "int"
    decimal = "decimal"
    bool = "bool"


class Category(Base):
    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    attributes: Mapped[list["CategoryAttribute"]] = relationship(back_populates="category")
    skus: Mapped[list["SKU"]] = relationship(back_populates="category")
    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Attribute(Base):
    __tablename__ = "attribute"

    attribute_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    datatype: Mapped[AttributeDatatype] = mapped_column(Enum(AttributeDatatype), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)

    options: Mapped[list["AttributeOption"]] = relationship(
        back_populates="attribute", order_by="AttributeOption.sort_order"
    )
    category_attrs: Mapped[list["CategoryAttribute"]] = relationship(back_populates="attribute")


class AttributeOption(Base):
    __tablename__ = "attribute_option"

    option_id: Mapped[int] = mapped_column(primary_key=True)
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.attribute_id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    attribute: Mapped["Attribute"] = relationship(back_populates="options")


class CategoryAttribute(Base):
    __tablename__ = "category_attribute"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.category_id", ondelete="CASCADE"), primary_key=True
    )
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.attribute_id", ondelete="CASCADE"), primary_key=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    display_group: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped["Category"] = relationship(back_populates="attributes")
    attribute: Mapped["Attribute"] = relationship(back_populates="category_attrs")
