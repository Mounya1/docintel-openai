"""
SQLAlchemy ORM models for DocIntel.

Tables:
  users          — platform users with RBAC roles
  documents      — uploaded files and their processing state
  extractions    — versioned AI extraction results per document
  validations    — per-rule validation results per extraction
  schemas        — extraction schema definitions per doc type
  reviews        — human-in-the-loop review tasks
  audit_logs     — immutable tamper-proof audit trail
"""

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, Boolean, Index, func,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    name            = Column(String, nullable=False)
    password_hash   = Column(String, nullable=False)
    role            = Column(String, default="viewer")      # admin | editor | reviewer | viewer
    department      = Column(String, nullable=True)
    avatar_initials = Column(String(3), nullable=True)
    mfa_enabled     = Column(Boolean, default=False)
    is_active       = Column(Boolean, default=True)
    last_login      = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=utcnow)

    documents   = relationship("Document", back_populates="uploader", foreign_keys="Document.uploaded_by")
    audit_logs  = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.user_id")


# ──────────────────────────────────────────────
# Documents
# ──────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id            = Column(String, primary_key=True)
    name          = Column(String, nullable=False)           # display name (editable)
    original_name = Column(String, nullable=False)           # original upload filename
    doc_type      = Column(String, nullable=True)            # contract | invoice | report | medical
    file_path     = Column(String, nullable=False)           # stored filename in upload dir
    file_size     = Column(Integer, nullable=True)
    page_count    = Column(Integer, nullable=True)
    mime_type     = Column(String, nullable=True)
    status        = Column(String, default="uploaded")       # uploaded|processing|extracted|needs_review|approved|rejected|error
    risk_level    = Column(String, default="low")            # low | medium | high
    schema_id     = Column(String, ForeignKey("schemas.id"), nullable=True)
    uploaded_by   = Column(String, ForeignKey("users.id"), nullable=False)
    created_at    = Column(DateTime(timezone=True), default=utcnow)
    updated_at    = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    uploader    = relationship("User", back_populates="documents", foreign_keys=[uploaded_by])
    schema      = relationship("Schema", back_populates="documents")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan", order_by="Extraction.version.desc()")
    reviews     = relationship("Review", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_status", "status"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
    )


# ──────────────────────────────────────────────
# Extractions  (versioned)
# ──────────────────────────────────────────────
class Extraction(Base):
    __tablename__ = "extractions"

    id                  = Column(String, primary_key=True)
    document_id         = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version             = Column(Integer, default=1)
    schema_id           = Column(String, ForeignKey("schemas.id"), nullable=True)
    fields              = Column(Text, nullable=True)           # JSON string
    raw_text            = Column(Text, nullable=True)           # First 5k chars of OCR output
    confidence_overall  = Column(Float, nullable=True)
    confidence_per_field = Column(Text, nullable=True)          # JSON string: {field: score}
    model_used          = Column(String, nullable=True)
    processing_time_ms  = Column(Integer, nullable=True)
    status              = Column(String, default="pending")     # pending|completed|failed
    error               = Column(Text, nullable=True)
    created_by          = Column(String, ForeignKey("users.id"), nullable=True)
    created_at          = Column(DateTime(timezone=True), default=utcnow)

    document    = relationship("Document", back_populates="extractions")
    validations = relationship("Validation", back_populates="extraction", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Validations  (per extraction, per rule)
# ──────────────────────────────────────────────
class Validation(Base):
    __tablename__ = "validations"

    id               = Column(String, primary_key=True)
    extraction_id    = Column(String, ForeignKey("extractions.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_name        = Column(String, nullable=False)
    rule_description = Column(String, nullable=True)
    passed           = Column(Boolean, nullable=False)
    severity         = Column(String, default="error")   # error | warning | info
    message          = Column(Text, nullable=True)
    created_at       = Column(DateTime(timezone=True), default=utcnow)

    extraction = relationship("Extraction", back_populates="validations")


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────
class Schema(Base):
    __tablename__ = "schemas"

    id               = Column(String, primary_key=True)
    name             = Column(String, nullable=False)
    doc_type         = Column(String, nullable=False)
    version          = Column(String, default="1.0")
    status           = Column(String, default="active")     # active | draft | deprecated
    definition       = Column(Text, nullable=False)          # JSON: {fields: {...}}
    validation_rules = Column(Text, nullable=True)           # JSON: ["rule1", ...]
    created_by       = Column(String, ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime(timezone=True), default=utcnow)
    updated_at       = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    documents  = relationship("Document", back_populates="schema")


# ──────────────────────────────────────────────
# Reviews  (human-in-the-loop)
# ──────────────────────────────────────────────
class Review(Base):
    __tablename__ = "reviews"

    id            = Column(String, primary_key=True)
    document_id   = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    extraction_id = Column(String, nullable=False)
    assigned_to   = Column(String, ForeignKey("users.id"), nullable=True)
    status        = Column(String, default="pending")     # pending | in_progress | completed
    decision      = Column(String, nullable=True)         # approved | rejected
    notes         = Column(Text, nullable=True)
    reviewed_at   = Column(DateTime(timezone=True), nullable=True)
    reviewed_by   = Column(String, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime(timezone=True), default=utcnow)

    document     = relationship("Document", back_populates="reviews")
    reviewer     = relationship("User", foreign_keys=[reviewed_by])
    assignee     = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (Index("ix_reviews_status", "status"),)


# ──────────────────────────────────────────────
# Audit Logs  (immutable — never deleted)
# ──────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id            = Column(String, primary_key=True)
    user_id       = Column(String, ForeignKey("users.id"), nullable=True)
    user_name     = Column(String, nullable=True)
    action        = Column(String, nullable=False)        # e.g. DOCUMENT_UPLOADED
    resource_type = Column(String, nullable=True)         # document | schema | user | extraction
    resource_id   = Column(String, nullable=True)
    resource_name = Column(String, nullable=True)
    details       = Column(Text, nullable=True)           # JSON: extra context
    ip_address    = Column(String, nullable=True)
    user_agent    = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), default=utcnow, index=True)

    user = relationship("User", back_populates="audit_logs", foreign_keys=[user_id])
