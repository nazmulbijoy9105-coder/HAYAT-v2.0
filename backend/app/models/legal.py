"""
HAYAT v2.0 — SQLAlchemy Models
Structured legal entities for PostgreSQL.
"""

from datetime import datetime, date
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Date,
    Integer,
    Boolean,
    ForeignKey,
    Table,
    Index,
    UniqueConstraint,
    JSON,
    Enum,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB

from app.db.postgres import Base


# ─── Enums ───
class DocumentType(str, PyEnum):
    CONSTITUTION = "constitution"
    ACT = "act"
    RULE = "rule"
    REGULATION = "regulation"
    PRACTICE_DIRECTION = "practice_direction"
    CIRCULAR = "circular"
    SUPREME_COURT_JUDGMENT = "supreme_court_judgment"
    HIGH_COURT_JUDGMENT = "high_court_judgment"
    TRIBUNAL_DECISION = "tribunal_decision"
    LAW_COMMISSION_REPORT = "law_commission_report"
    PARLIAMENT_DEBATE = "parliament_debate"
    OFFICIAL_FORM = "official_form"
    SCHEDULE = "schedule"
    GAZETTE = "gazette"
    TREATY = "treaty"
    OTHER = "other"


class DocumentStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    OCR = "ocr"
    PARSING = "parsing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class CourtLevel(str, PyEnum):
    SUPREME_COURT_APPELLATE = "supreme_court_appellate"
    SUPREME_COURT_HIGH_COURT_DIVISION = "supreme_court_high_court_division"
    DISTRICT_COURT = "district_court"
    SESSIONS_COURT = "sessions_court"
    SPECIAL_TRIBUNAL = "special_tribunal"
    ADMINISTRATIVE_TRIBUNAL = "administrative_tribunal"
    INTERNATIONAL = "international"


class CaseStatus(str, PyEnum):
    PENDING = "pending"
    DISPOSED = "disposed"
    DISMISSED = "dismissed"
    ALLOWED = "allowed"
    REMANDED = "remanded"
    SETTLED = "settled"
    WITHDRAWN = "withdrawn"
    APPEALED = "appealed"


class UserRole(str, PyEnum):
    SUPER_ADMIN = "super_admin"
    LEGAL_EDITOR = "legal_editor"
    RESEARCHER = "researcher"
    PRACTITIONER = "practitioner"
    PUBLIC = "public"
    INSTITUTION = "institution"


# ─── Association Tables ───
case_statutes = Table(
    "case_statutes",
    Base.metadata,
    Column("case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("statute_id", UUID(as_uuid=True), ForeignKey("statutes.id", ondelete="CASCADE"), primary_key=True),
    Column("interpretation_type", String(50)),  # interprets, distinguishes, overrules
    Column("paragraphs", ARRAY(String)),
    Column("created_at", DateTime, default=datetime.utcnow),
)

case_cases = Table(
    "case_cases",
    Base.metadata,
    Column("from_case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("to_case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
    Column("citation_type", String(50)),  # followed, distinguished, overruled, referred
    Column("context", Text),
    Column("paragraph", String(100)),
    Column("created_at", DateTime, default=datetime.utcnow),
)


# ─── Core Models ───
class User(Base):
    """Platform users with role-based access."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PUBLIC)
    institution_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    institution = relationship("Institution", back_populates="users")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Institution(Base):
    """Law firms, courts, universities, government bodies."""
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50))  # law_firm, court, university, government, ngo
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    api_quota_daily: Mapped[int] = mapped_column(Integer, default=1000)
    api_quota_used: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="institution")


class ApiKey(Base):
    """API keys for institution access."""
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scopes: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    last_used_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")


class Document(Base):
    """Raw legal documents from official sources."""
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_document_source_hash", "source_hash", unique=True),
        Index("idx_document_status", "status"),
        Index("idx_document_type_date", "document_type", "source_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.PENDING)

    # Source metadata
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # bangladesh_code, supreme_court, gazette, etc.
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    source_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # Storage
    object_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # MinIO path
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Processing metadata
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_version_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    case = relationship("Case", back_populates="document", uselist=False)
    statute = relationship("Statute", back_populates="document", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="document")


class Case(Base):
    """Judicial cases with full legal analysis."""
    __tablename__ = "cases"
    __table_args__ = (
        Index("idx_case_citation", "citation", unique=True),
        Index("idx_case_date", "date"),
        Index("idx_case_court", "court"),
        Index("idx_case_area_of_law", "area_of_law"),
        Index("idx_case_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    # Identifiers
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    citation: Mapped[str] = mapped_column(String(255), nullable=False)
    case_number: Mapped[str] = mapped_column(String(100), nullable=False)

    # Court info
    court: Mapped[str] = mapped_column(String(255), nullable=False)
    court_level: Mapped[CourtLevel] = mapped_column(Enum(CourtLevel), nullable=False)
    bench: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Dates
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    date_hearing: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    date_judgment: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # Classification
    area_of_law: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    case_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # civil, criminal, constitutional, etc.

    # Status
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.DISPOSED)

    # Parties
    petitioner: Mapped[str] = mapped_column(Text, nullable=False)
    respondent: Mapped[str] = mapped_column(Text, nullable=False)
    petitioner_counsel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    respondent_counsel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Content
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    facts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    arguments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ratio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    obiter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    held: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    directions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    orders: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Judges
    judges: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)

    # References (stored as JSON for flexibility)
    statutes_cited: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cases_cited: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    foreign_cases_cited: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    constitution_articles_cited: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # AI-generated
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_key_points: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    ai_sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Editorial
    editorial_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plain_language_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    practical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    common_mistakes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    faqs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    indexed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="case")
    statutes = relationship("Statute", secondary=case_statutes, back_populates="cases")

    def __repr__(self):
        return f"<Case {self.citation}>"


class Statute(Base):
    """Acts, rules, regulations — structured legislation."""
    __tablename__ = "statutes"
    __table_args__ = (
        Index("idx_statute_act_number", "act_number", unique=True),
        Index("idx_statute_year", "year"),
        Index("idx_statute_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    act_number: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dates
    assent_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    coming_into_force: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    repeal_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # Content
    preamble: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="in_force")  # in_force, amended, repealed, draft

    # Classification
    area_of_law: Mapped[str] = mapped_column(String(100), nullable=False)
    ministry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Editorial
    plain_language_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    practical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    common_mistakes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    faqs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="statute")
    sections = relationship("Section", back_populates="statute", cascade="all, delete-orphan")
    cases = relationship("Case", secondary=case_statutes, back_populates="statutes")


class Section(Base):
    """Individual sections of statutes."""
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("statute_id", "number", name="uq_section_statute_number"),
        Index("idx_section_number", "number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    statute_id: Mapped[str] = mapped_column(String(36), ForeignKey("statutes.id", ondelete="CASCADE"))

    number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Editorial
    plain_language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingredients: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    checklist: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    leading_cases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    latest_cases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    drafting_tips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    common_mistakes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    faqs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    statute = relationship("Statute", back_populates="sections")


class AuditLog(Base):
    """Immutable audit trail for compliance."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_document", "document_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, read, update, delete, search, download, export
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # case, statute, document, user, etc.
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    timestamp: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")
    document = relationship("Document", back_populates="audit_logs")


class ProcessingJob(Base):
    """Background job tracking for document pipeline."""
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("idx_job_status", "status"),
        Index("idx_job_document", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"))

    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ocr, parse, index, embed, ai_analysis
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed, retrying

    queue_name: Mapped[str] = mapped_column(String(50), nullable=False)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Progress
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=1)
    current_step: Mapped[int] = mapped_column(Integer, default=0)

    # Results
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
