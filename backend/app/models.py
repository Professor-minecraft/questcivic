from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Date,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Work(Base):
    __tablename__ = "works"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(10), nullable=False)  # "LS" or "RS"
    sr_no = Column(Integer, nullable=False)
    work_code = Column(String(255), nullable=True)
    work_type = Column(String(500), nullable=False)
    category = Column(String(255), nullable=True)
    state = Column(String(255), nullable=False)
    district = Column(String(255), nullable=False)
    constituency = Column(String(255), nullable=True)  # null for RS
    state_norm = Column(String(255), nullable=False, index=True)
    district_norm = Column(String(255), nullable=False, index=True)
    constituency_norm = Column(String(255), nullable=True, index=True)  # null for RS
    mp_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=True)
    completion_date = Column(Date, nullable=True)

    submissions = relationship("Submission", back_populates="work", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_works_location_match", "state_norm", "district_norm", "constituency_norm"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    otp_secret = Column(String(64), nullable=False)
    state = Column(String(255), nullable=True)
    district = Column(String(255), nullable=True)
    constituency = Column(String(255), nullable=True)
    xp = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")
    xp_logs = relationship("XPLog", back_populates="user", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    work_id = Column(Integer, ForeignKey("works.id"), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # "pending" | "approved" | "rejected"
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    reject_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="submissions")
    work = relationship("Work", back_populates="submissions")
    xp_logs = relationship("XPLog", back_populates="submission")


class XPLog(Base):
    __tablename__ = "xp_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True, index=True)
    points = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="xp_logs")
    submission = relationship("Submission", back_populates="xp_logs")
