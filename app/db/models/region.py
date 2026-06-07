from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SD(Base):
    __tablename__ = "sd"

    sd_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    sggs: Mapped[list["SGG"]] = relationship(back_populates="sd")


class SGG(Base):
    __tablename__ = "sgg"

    sgg_id: Mapped[int] = mapped_column(primary_key=True)
    sd_id: Mapped[int] = mapped_column(ForeignKey("sd.sd_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    sd: Mapped["SD"] = relationship(back_populates="sggs")
    emds: Mapped[list["EMD"]] = relationship(back_populates="sgg")


class EMD(Base):
    __tablename__ = "emd"

    region_id: Mapped[int] = mapped_column(primary_key=True)
    sgg_id: Mapped[int] = mapped_column(ForeignKey("sgg.sgg_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    sgg: Mapped["SGG"] = relationship(back_populates="emds")
