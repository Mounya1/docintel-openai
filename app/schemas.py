"""
Pydantic v2 schemas for request validation and response serialization.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum



# ── Enums ──────────────────────────────────────────────────────────────────────
class UserRole(str, Enum):
    admin    = "admin"
    editor   = "editor"
    reviewer = "reviewer"
    viewer   = "viewer"

class DocStatus(str, Enum):
    uploaded     = "uploaded"
    processing   = "processing"
    extracted    = "extracted"
    needs_review = "needs_review"
    approved     = "approved"
    rejected     = "rejected"
    error        = "error"

class DocType(str, Enum):
    contract = "contract"
    invoice  = "invoice"
    report   = "report"
    medical  = "medical"
    document = "document"

class RiskLevel(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"

class ReviewDecision(str, Enum):
    approved = "approved"
    rejected = "rejected"


# ── Auth ───────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(min_length=1)

class RegisterRequest(BaseModel):
    email:      EmailStr
    password:   str = Field(min_length=8)
    name:       str = Field(min_length=1)
    role:       UserRole = UserRole.viewer
    department: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         "UserOut"

class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id:              str
    email:           str
    name:            str
    role:            str
    department:      Optional[str]
    avatar_initials: Optional[str]
    last_login:      Optional[datetime]
    created_at:      datetime

class UserCreate(BaseModel):
    email:      EmailStr
    name:       str
    password:   str = Field(default="TempPass123!", min_length=8)
    role:       UserRole = UserRole.viewer
    department: Optional[str] = None

class UserUpdate(BaseModel):
    name:        Optional[str] = None
    role:        Optional[UserRole] = None
    department:  Optional[str] = None
    mfa_enabled: Optional[bool] = None


# ── Documents ──────────────────────────────────────────────────────────────────
class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}
    id:               str
    name:             str
    original_name:    str
    doc_type:         Optional[str]
    file_size:        Optional[int]
    page_count:       Optional[int]
    mime_type:        Optional[str]
    status:           str
    risk_level:       Optional[str] = None
    schema_id:        Optional[str]
    uploaded_by:      str
    uploaded_by_name: Optional[str] = None
    confidence:       Optional[float] = 0.0
    current_version:  Optional[int] = 1
    created_at:       datetime
    updated_at:       datetime


class DocumentDetail(DocumentOut):
    extractions: List["ExtractionOut"] = Field(default_factory=list)
    reviews:     List["ReviewOut"] = Field(default_factory=list)

class DocumentUpdate(BaseModel):
    name:      Optional[str] = None
    doc_type:  Optional[DocType] = None
    schema_id: Optional[str] = None

class ReviewRequest(BaseModel):
    decision:      ReviewDecision
    notes:         Optional[str] = None
    extraction_id: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentOut]
    total:     int
    limit:     int
    offset:    int


# ── Extractions ────────────────────────────────────────────────────────────────
class ExtractionOut(BaseModel):
    model_config = {
    "from_attributes": True,
    "protected_namespaces": ()}
    id:                  str
    document_id:         str
    version:             int
    schema_id:           Optional[str]
    fields:              Optional[Dict[str, Any]]
    confidence_overall:  Optional[float]
    confidence_per_field: Optional[Dict[str, float]]
    llm_model:          Optional[str]
    processing_time_ms:  Optional[int]
    status:              str
    error:               Optional[str]
    created_at:          datetime

class FieldsUpdateRequest(BaseModel):
    fields: Dict[str, Any] = Field(description="Partial or full field overrides")


# ── Validations ────────────────────────────────────────────────────────────────
class ValidationOut(BaseModel):
    model_config = {"from_attributes": True}
    id:               str
    extraction_id:    str
    rule_name:        str
    rule_description: Optional[str]
    passed:           bool
    severity:         str
    message:          Optional[str]
    created_at:       datetime


# ── Schemas ────────────────────────────────────────────────────────────────────
class SchemaOut(BaseModel):
    model_config = {"from_attributes": True}
    id:               str
    name:             str
    doc_type:         str
    version:          str
    status:           str
    definition:       Dict[str, Any]
    validation_rules: List[str] = []
    created_by:       Optional[str]
    created_at:       datetime
    updated_at:       datetime
    doc_count:        int = 0

class SchemaCreate(BaseModel):
    name:             str
    doc_type:         str
    version:          str = "1.0"
    definition:       Dict[str, Any]
    validation_rules: List[str] = []

class SchemaUpdate(BaseModel):
    name:             Optional[str] = None
    version:          Optional[str] = None
    definition:       Optional[Dict[str, Any]] = None
    validation_rules: Optional[List[str]] = None
    status:           Optional[str] = None


# ── Reviews ────────────────────────────────────────────────────────────────────
class ReviewOut(BaseModel):
    model_config = {"from_attributes": True}
    id:              str
    document_id:     str
    extraction_id:   str
    status:          str
    decision:        Optional[str]
    notes:           Optional[str]
    reviewed_at:     Optional[datetime]
    reviewed_by:     Optional[str]
    reviewed_by_name: Optional[str] = None
    created_at:      datetime


# ── Audit Logs ─────────────────────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    model_config = {"from_attributes": True}
    id:            str
    user_id:       Optional[str]
    user_name:     Optional[str]
    action:        str
    resource_type: Optional[str]
    resource_id:   Optional[str]
    resource_name: Optional[str]
    details:       Optional[Dict[str, Any]]
    ip_address:    Optional[str]
    created_at:    datetime

class AuditLogListResponse(BaseModel):
    logs:   List[AuditLogOut]
    total:  int
    limit:  int
    offset: int


# ── Analytics ──────────────────────────────────────────────────────────────────
class DailyCount(BaseModel):
    day:   str
    count: int

class ConfidenceDistribution(BaseModel):
    high:   int
    medium: int
    low:    int

class AnalyticsOverview(BaseModel):
    total_documents:        int
    by_status:              Dict[str, int]
    by_type:                Dict[str, int]
    avg_confidence:         float
    pending_review:         int
    avg_processing_seconds: float
    last_7_days:            List[DailyCount]
    confidence_distribution: ConfidenceDistribution


# ── Misc ───────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status:    str = "ok"
    timestamp: datetime
    version:   str = "1.0.0"

class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


# Forward references
TokenResponse.model_rebuild()
DocumentDetail.model_rebuild()
