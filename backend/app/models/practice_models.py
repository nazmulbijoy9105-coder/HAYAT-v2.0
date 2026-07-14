"""
HAYAT v2.0 — Practice Management Models
Phase 13: Client management, diary, deadlines, billing.
"""

from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, Date, Integer, Boolean, ForeignKey, Enum, Numeric, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB

from app.db.postgres import Base


class Client(Base):
    """Legal clients managed by practitioners."""
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="individual")  # individual, company, government, ngo
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Identification
    nid_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trade_license: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Emergency contact
    emergency_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matters = relationship("Matter", back_populates="client")


class Matter(Base):
    """A legal matter/case file in practice management."""
    __tablename__ = "matters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    matter_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Classification
    area_of_law: Mapped[str] = mapped_column(String(100), nullable=False)
    case_type: Mapped[str] = mapped_column(String(50), nullable=False)  # civil, criminal, constitutional, etc.
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, pending, closed, archived
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, critical

    # Court info
    court: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    court_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    case_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Linked HAYAT case/statute
    hayat_case_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("cases.id"), nullable=True)

    # Financial
    fee_type: Mapped[str] = mapped_column(String(50), default="hourly")  # hourly, fixed, contingency, pro_bono
    fee_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    retainer_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    total_billed: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    total_paid: Mapped[float] = mapped_column(Numeric(15, 2), default=0)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="matters")
    deadlines = relationship("Deadline", back_populates="matter", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="matter", cascade="all, delete-orphan")
    documents = relationship("MatterDocument", back_populates="matter", cascade="all, delete-orphan")


class Deadline(Base):
    """Critical deadlines and court dates."""
    __tablename__ = "deadlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    matter_id: Mapped[str] = mapped_column(String(36), ForeignKey("matters.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline_type: Mapped[str] = mapped_column(String(50), nullable=False)  # hearing, filing, appeal, limitation, payment
    due_date: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    due_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Reminders
    reminder_7d: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_3d: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_1d: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_1h: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, overdue, cancelled
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    matter = relationship("Matter", back_populates="deadlines")


class TimeEntry(Base):
    """Billable time tracking."""
    __tablename__ = "time_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    matter_id: Mapped[str] = mapped_column(String(36), ForeignKey("matters.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

    is_billable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    matter = relationship("Matter", back_populates="time_entries")


class MatterDocument(Base):
    """Documents attached to a matter."""
    __tablename__ = "matter_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    matter_id: Mapped[str] = mapped_column(String(36), ForeignKey("matters.id", ondelete="CASCADE"))
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # petition, affidavit, notice, agreement, evidence, correspondence
    object_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    matter = relationship("Matter", back_populates="documents")


class CourtCalendar(Base):
    """Court cause lists and hearing schedules."""
    __tablename__ = "court_calendars"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    court: Mapped[str] = mapped_column(String(255), nullable=False)
    court_level: Mapped[str] = mapped_column(String(50), nullable=False)
    bench: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    date: Mapped[Date] = mapped_column(Date, nullable=False)
    case_number: Mapped[str] = mapped_column(String(100), nullable=False)
    matter_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("matters.id"), nullable=True)

    hearing_type: Mapped[str] = mapped_column(String(50), nullable=False)  # admission, arguments, judgment, cross-examination
    time_slot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled, adjourned, completed, cancelled
    adjourned_to: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
