"""
Validation Service — runs business rules against extracted fields.

Each rule returns a ValidationResult with passed/severity/message.
Rules are evaluated after LLM extraction and stored per extraction.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    rule_name:        str
    rule_description: str
    passed:           bool
    severity:         str = "error"    # error | warning | info
    message:          Optional[str] = None


def validate_extraction(
    extracted_fields: Dict[str, Any],
    schema_definition: Optional[Dict],
    anomalies: List[str],
    overall_confidence: float,
) -> List[ValidationResult]:
    """
    Run all applicable validation rules and return results list.
    """
    results: List[ValidationResult] = []

    # 1. Schema-driven field validation
    if schema_definition:
        results.extend(_validate_schema_fields(extracted_fields, schema_definition))

    # 2. Type-specific business rules
    doc_type = _infer_doc_type(schema_definition)
    if doc_type == "invoice":
        results.extend(_validate_invoice(extracted_fields))
    elif doc_type == "contract":
        results.extend(_validate_contract(extracted_fields))
    elif doc_type == "medical":
        results.extend(_validate_medical(extracted_fields))

    # 3. Confidence threshold
    results.append(ValidationResult(
        rule_name="confidence_threshold",
        rule_description="Overall confidence must be ≥ 70%",
        passed=overall_confidence >= 70,
        severity="warning",
        message=f"Low confidence: {overall_confidence:.0f}%" if overall_confidence < 70 else None,
    ))

    # 4. AI-flagged anomalies
    if anomalies:
        results.append(ValidationResult(
            rule_name="anomaly_check",
            rule_description="No AI-flagged anomalies",
            passed=False,
            severity="warning",
            message="; ".join(anomalies[:5]),
        ))

    return results


# ── Schema field validation ────────────────────────────────────────────────────
def _validate_schema_fields(fields: Dict[str, Any], schema_def: Dict) -> List[ValidationResult]:
    results = []
    schema_fields = schema_def.get("fields", {})

    for field_name, field_def in schema_fields.items():
        value = _get_value(fields, field_name)

        if field_def.get("required"):
            missing = value is None or value == "" or value == []
            results.append(ValidationResult(
                rule_name=f"required_{field_name}",
                rule_description=f'Required field "{field_name}" must be present',
                passed=not missing,
                severity="error",
                message=f'Required field "{field_name}" is missing or empty' if missing else None,
            ))

        if value and field_def.get("type") == "date":
            valid_date = _is_valid_date(str(value))
            results.append(ValidationResult(
                rule_name=f"date_format_{field_name}",
                rule_description=f'"{field_name}" must be a valid YYYY-MM-DD date',
                passed=valid_date,
                severity="warning",
                message=f'Invalid date format in "{field_name}": {value}' if not valid_date else None,
            ))

        if value and field_def.get("type") == "currency":
            valid_curr = _is_valid_currency(str(value))
            results.append(ValidationResult(
                rule_name=f"currency_format_{field_name}",
                rule_description=f'"{field_name}" must be a valid currency value',
                passed=valid_curr,
                severity="warning",
                message=f'Unexpected currency format in "{field_name}": {value}' if not valid_curr else None,
            ))

    return results


# ── Invoice-specific rules ─────────────────────────────────────────────────────
def _validate_invoice(fields: Dict[str, Any]) -> List[ValidationResult]:
    results = []

    subtotal = _parse_amount(_get_value(fields, "subtotal"))
    tax      = _parse_amount(_get_value(fields, "tax")) or 0.0
    total    = _parse_amount(_get_value(fields, "total"))

    if subtotal is not None and total is not None:
        expected = round(subtotal + tax, 2)
        actual   = round(total, 2)
        results.append(ValidationResult(
            rule_name="invoice_math_check",
            rule_description="subtotal + tax must equal total",
            passed=abs(expected - actual) < 0.02,
            severity="error",
            message=f"Math mismatch: {subtotal} + {tax} = {expected}, but total is {actual}" if abs(expected - actual) >= 0.02 else None,
        ))

    due = _parse_date(_get_value(fields, "due_date"))
    if due:
        results.append(ValidationResult(
            rule_name="due_date_not_past",
            rule_description="Invoice due date must not be in the past",
            passed=due >= date.today(),
            severity="warning",
            message=f"Invoice is overdue — due date was {due}" if due < date.today() else None,
        ))

    return results


# ── Contract-specific rules ────────────────────────────────────────────────────
def _validate_contract(fields: Dict[str, Any]) -> List[ValidationResult]:
    results = []

    exp = _parse_date(_get_value(fields, "expiration_date"))
    if exp:
        results.append(ValidationResult(
            rule_name="expiration_future",
            rule_description="Contract expiration date must be in the future",
            passed=exp > date.today(),
            severity="error",
            message=f"Contract expired on {exp}" if exp <= date.today() else None,
        ))

    eff = _parse_date(_get_value(fields, "effective_date"))
    if eff and exp:
        results.append(ValidationResult(
            rule_name="date_range_valid",
            rule_description="Effective date must be before expiration date",
            passed=eff < exp,
            severity="error",
            message=f"Effective date ({eff}) is not before expiration ({exp})" if eff >= exp else None,
        ))

    parties = _get_value(fields, "parties")
    if parties is not None:
        count = len(parties) if isinstance(parties, list) else (1 if parties else 0)
        results.append(ValidationResult(
            rule_name="parties_count",
            rule_description="Contract must have at least 2 parties",
            passed=count >= 2,
            severity="error",
            message=f"Only {count} party found — expected at least 2" if count < 2 else None,
        ))

    return results


# ── Medical-specific rules ─────────────────────────────────────────────────────
def _validate_medical(fields: Dict[str, Any]) -> List[ValidationResult]:
    results = []

    consent_date = _parse_date(_get_value(fields, "consent_date"))
    if consent_date:
        days_ago = (date.today() - consent_date).days
        results.append(ValidationResult(
            rule_name="consent_within_30_days",
            rule_description="Consent date must be within 30 days of today",
            passed=days_ago <= 30,
            severity="warning",
            message=f"Consent is {days_ago} days old — may need renewal" if days_ago > 30 else None,
        ))

    phi_fields = ["patient_name", "date_of_birth", "mrn"]
    phi_complete = all(_get_value(fields, f) for f in phi_fields)
    results.append(ValidationResult(
        rule_name="phi_complete",
        rule_description="All PHI fields must be present (patient_name, dob, mrn)",
        passed=phi_complete,
        severity="error",
        message="One or more required PHI fields are missing" if not phi_complete else None,
    ))

    return results


# ── Helpers ────────────────────────────────────────────────────────────────────
def _get_value(fields: Dict[str, Any], key: str) -> Any:
    val = fields.get(key)
    if isinstance(val, dict):
        return val.get("value")
    return val


def _parse_date(val: Any) -> Optional[date]:
    if not val:
        return None
    try:
        s = str(val)[:10]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_amount(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _is_valid_date(val: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", val))


def _is_valid_currency(val: str) -> bool:
    return bool(re.match(r"^[\$€£¥]?[\d,]+\.?\d*$", val.replace(",", "")))


def _infer_doc_type(schema_def: Optional[Dict]) -> str:
    if not schema_def:
        return "document"
    # Schema definitions contain field names that hint at doc type
    fields = list((schema_def.get("fields") or {}).keys())
    if "invoice_no" in fields or "vendor" in fields:
        return "invoice"
    if "parties" in fields or "governing_law" in fields:
        return "contract"
    if "mrn" in fields or "patient_name" in fields:
        return "medical"
    return "document"
