"""
HAYAT v2.0 — Pydantic Schemas
Request/response models with strict validation.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ─── Base Schemas ───
class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    total: int
    page: int
    size: int
    pages: int


# ─── Document Schemas ───
class DocumentType(str, Enum):
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


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    OCR = "ocr"
    PARSING = "parsing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    document_type: DocumentType
    source: str = Field(..., min_length=1, max_length=100)
    source_url: Optional[str] = Field(None, max_length=1000)
    source_date: Optional[date] = None
    language: Optional[str] = Field(None, max_length=10)


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[DocumentStatus] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    language: Optional[str] = Field(None, max_length=10)
    page_count: Optional[int] = Field(None, ge=1)
    error_message: Optional[str] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    document_type: DocumentType
    status: DocumentStatus
    source: str
    source_url: Optional[str]
    source_date: Optional[date]
    source_hash: str
    file_size: Optional[int]
    mime_type: Optional[str]
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    language: Optional[str]
    page_count: Optional[int]
    version: int
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]


class DocumentListResponse(PaginatedResponse):
    results: List[DocumentResponse]


# ─── Case Schemas ───
class CourtLevel(str, Enum):
    SUPREME_COURT_APPELLATE = "supreme_court_appellate"
    SUPREME_COURT_HIGH_COURT_DIVISION = "supreme_court_high_court_division"
    DISTRICT_COURT = "district_court"
    SESSIONS_COURT = "sessions_court"
    SPECIAL_TRIBUNAL = "special_tribunal"
    ADMINISTRATIVE_TRIBUNAL = "administrative_tribunal"
    INTERNATIONAL = "international"


class CaseStatus(str, Enum):
    PENDING = "pending"
    DISPOSED = "disposed"
    DISMISSED = "dismissed"
    ALLOWED = "allowed"
    REMANDED = "remanded"
    SETTLED = "settled"
    WITHDRAWN = "withdrawn"
    APPEALED = "appealed"


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    citation: str = Field(..., min_length=1, max_length=255)
    case_number: str = Field(..., min_length=1, max_length=100)
    court: str = Field(..., min_length=1, max_length=255)
    court_level: CourtLevel
    bench: Optional[str] = Field(None, max_length=100)
    date: date
    date_hearing: Optional[date] = None
    date_judgment: Optional[date] = None
    area_of_law: str = Field(..., min_length=1, max_length=100)
    sub_area: Optional[str] = Field(None, max_length=100)
    case_type: Optional[str] = Field(None, max_length=50)
    status: CaseStatus = CaseStatus.DISPOSED
    petitioner: str
    respondent: str
    petitioner_counsel: Optional[str] = None
    respondent_counsel: Optional[str] = None
    judges: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    facts: Optional[str] = None
    issues: Optional[str] = None
    arguments: Optional[str] = None
    reasoning: Optional[str] = None
    ratio: Optional[str] = None
    obiter: Optional[str] = None
    held: Optional[str] = None
    directions: Optional[str] = None
    orders: Optional[str] = None
    relief: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    citation: Optional[str] = Field(None, max_length=255)
    case_number: Optional[str] = Field(None, max_length=100)
    court: Optional[str] = Field(None, max_length=255)
    court_level: Optional[CourtLevel] = None
    bench: Optional[str] = Field(None, max_length=100)
    date: Optional[date] = None
    area_of_law: Optional[str] = Field(None, max_length=100)
    status: Optional[CaseStatus] = None
    petitioner: Optional[str] = None
    respondent: Optional[str] = None
    judges: Optional[List[str]] = None
    summary: Optional[str] = None
    facts: Optional[str] = None
    issues: Optional[str] = None
    arguments: Optional[str] = None
    reasoning: Optional[str] = None
    ratio: Optional[str] = None
    obiter: Optional[str] = None
    held: Optional[str] = None
    directions: Optional[str] = None
    orders: Optional[str] = None
    relief: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_key_points: Optional[List[str]] = None
    editorial_notes: Optional[str] = None
    plain_language_summary: Optional[str] = None
    practical_notes: Optional[str] = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: Optional[str]
    title: str
    citation: str
    case_number: str
    court: str
    court_level: CourtLevel
    bench: Optional[str]
    date: date
    date_hearing: Optional[date]
    date_judgment: Optional[date]
    area_of_law: str
    sub_area: Optional[str]
    case_type: Optional[str]
    status: CaseStatus
    petitioner: str
    respondent: str
    petitioner_counsel: Optional[str]
    respondent_counsel: Optional[str]
    judges: List[str]
    summary: Optional[str]
    facts: Optional[str]
    issues: Optional[str]
    arguments: Optional[str]
    reasoning: Optional[str]
    ratio: Optional[str]
    obiter: Optional[str]
    held: Optional[str]
    directions: Optional[str]
    orders: Optional[str]
    relief: Optional[str]
    statutes_cited: Optional[Dict[str, Any]]
    cases_cited: Optional[Dict[str, Any]]
    ai_summary: Optional[str]
    ai_key_points: Optional[List[str]]
    plain_language_summary: Optional[str]
    practical_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(CaseResponse):
    document: Optional[DocumentResponse]
    related_cases: List[Dict[str, Any]] = Field(default_factory=list)
    cited_statutes: List[Dict[str, Any]] = Field(default_factory=list)
    citation_network: List[Dict[str, Any]] = Field(default_factory=list)


class CaseListResponse(PaginatedResponse):
    results: List[CaseResponse]


# ─── Statute Schemas ───
class StatuteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    act_number: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1800, le=2100)
    assent_date: Optional[date] = None
    coming_into_force: Optional[date] = None
    repeal_date: Optional[date] = None
    preamble: Optional[str] = None
    full_text: Optional[str] = None
    status: str = "in_force"
    area_of_law: str = Field(..., min_length=1, max_length=100)
    ministry: Optional[str] = Field(None, max_length=100)


class StatuteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    act_number: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1800, le=2100)
    assent_date: Optional[date] = None
    coming_into_force: Optional[date] = None
    repeal_date: Optional[date] = None
    preamble: Optional[str] = None
    full_text: Optional[str] = None
    status: Optional[str] = None
    area_of_law: Optional[str] = Field(None, max_length=100)
    ministry: Optional[str] = Field(None, max_length=100)
    plain_language_summary: Optional[str] = None
    practical_notes: Optional[str] = None


class SectionCreate(BaseModel):
    number: str = Field(..., min_length=1, max_length=50)
    title: Optional[str] = Field(None, max_length=500)
    text: str
    plain_language: Optional[str] = None
    ingredients: Optional[List[str]] = None
    checklist: Optional[List[str]] = None


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    statute_id: str
    number: str
    title: Optional[str]
    text: str
    plain_language: Optional[str]
    ingredients: Optional[List[str]]
    checklist: Optional[List[str]]
    leading_cases: Optional[List[str]]
    latest_cases: Optional[List[str]]
    drafting_tips: Optional[str]
    common_mistakes: Optional[List[str]]
    faqs: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class StatuteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: Optional[str]
    title: str
    act_number: str
    year: int
    assent_date: Optional[date]
    coming_into_force: Optional[date]
    repeal_date: Optional[date]
    preamble: Optional[str]
    full_text: Optional[str]
    status: str
    area_of_law: str
    ministry: Optional[str]
    plain_language_summary: Optional[str]
    practical_notes: Optional[str]
    sections: List[SectionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StatuteListResponse(PaginatedResponse):
    results: List[StatuteResponse]


# ─── Search Schemas ───
class SearchType(str, Enum):
    NATURAL_LANGUAGE = "natural_language"
    CITATION = "citation"
    JUDGE = "judge"
    SECTION = "section"
    TOPIC = "topic"
    ACT = "act"
    YEAR = "year"
    BENCH = "bench"
    RELIEF = "relief"
    RATIO = "ratio"
    KEYWORDS = "keywords"
    BOOLEAN = "boolean"
    SEMANTIC = "semantic"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    search_type: SearchType = SearchType.NATURAL_LANGUAGE
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sort: Optional[List[Dict[str, str]]] = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    highlight: bool = True
    semantic: bool = False

    @field_validator("size")
    @classmethod
    def validate_size(cls, v):
        if v > 100:
            return 100
        return v


class SearchResult(BaseModel):
    id: str
    type: str  # case, statute, document
    score: float
    title: str
    snippet: Optional[str]
    highlights: Optional[Dict[str, List[str]]]
    source: Dict[str, Any]


class SearchResponse(PaginatedResponse):
    results: List[SearchResult]
    semantic_results: Optional[List[SearchResult]] = None
    suggestions: Optional[List[str]] = None
    facets: Optional[Dict[str, Any]] = None


# ─── AI Schemas ───
class AISummarizeRequest(BaseModel):
    document_id: str
    style: Literal["brief", "detailed", "practitioner", "academic"] = "detailed"
    max_length: int = Field(500, ge=100, le=2000)


class AISummarizeResponse(BaseModel):
    document_id: str
    summary: str
    key_points: List[str]
    word_count: int
    processing_time: float


class AIExplainRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = None
    jurisdiction: Optional[str] = "bangladesh"
    include_statutes: bool = True
    include_cases: bool = True


class AIExplainResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    statutes_referenced: List[str]
    cases_referenced: List[str]
    disclaimer: str = "This AI-generated response is for informational purposes only and does not constitute legal advice. Always verify against official sources."


class AICompareRequest(BaseModel):
    case_ids: List[str] = Field(..., min_length=2, max_length=5)
    comparison_type: Literal["facts", "issues", "reasoning", "ratio", "full"] = "full"


class AICompareResponse(BaseModel):
    comparison: str
    similarities: List[str]
    differences: List[str]
    cases: List[str]


class AIRAGRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    context_documents: Optional[List[str]] = None
    temperature: float = Field(0.1, ge=0.0, le=1.0)


class AIRAGResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    source_documents: List[str]
    confidence: float
    processing_time: float


# ─── Analytics Schemas ───
class CaseTrendsRequest(BaseModel):
    area_of_law: Optional[str] = None
    court_level: Optional[CourtLevel] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    granularity: Literal["month", "quarter", "year"] = "year"


class CaseTrendsResponse(BaseModel):
    labels: List[str]
    data: List[int]
    area_of_law: Optional[str]
    court_level: Optional[str]


class CitationAnalyticsResponse(BaseModel):
    most_cited_cases: List[Dict[str, Any]]
    most_cited_statutes: List[Dict[str, Any]]
    citation_network_density: float
    average_citations_per_case: float


class JudgeAnalyticsResponse(BaseModel):
    judge_name: str
    total_cases: int
    cases_by_area: Dict[str, int]
    cases_by_year: Dict[str, int]
    average_case_length: float
    most_cited_by: List[str]


# ─── User Schemas ───
class UserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = "public"
    institution_id: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    institution_id: Optional[str]
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LoginRequest(BaseModel):
    email: str
    password: str


# ─── Practice Tools Schemas ───
class DeadlineTrackerCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    due_date: date
    case_id: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    assigned_to: Optional[str] = None


class DeadlineTrackerResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    due_date: date
    case_id: Optional[str]
    priority: str
    status: str
    created_at: datetime


class DocumentGeneratorRequest(BaseModel):
    template_type: Literal["petition", "affidavit", "notice", "agreement", "memo"]
    jurisdiction: str = "bangladesh"
    variables: Dict[str, Any]
    language: Literal["english", "bengali"] = "english"
