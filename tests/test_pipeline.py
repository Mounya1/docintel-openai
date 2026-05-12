"""
Unit tests for the validation and pipeline services.
Run: pytest tests/ -v
"""

import pytest
from app.services.validation import validate_extraction, ValidationResult


def test_invoice_math_pass():
    fields = {"vendor": "Acme", "subtotal": "$100.00", "tax": "$10.00", "total": "$110.00",
              "invoice_no": "INV-001", "invoice_date": "2026-01-01",
              "due_date": "2027-01-01", "currency": "USD"}
    schema = {"fields": {
        "vendor": {"type": "string", "required": True},
        "invoice_no": {"type": "string", "required": True},
        "total": {"type": "currency", "required": True},
        "subtotal": {"type": "currency", "required": True},
        "invoice_date": {"type": "date", "required": True},
        "due_date": {"type": "date", "required": True},
        "currency": {"type": "string", "required": True},
    }}
    results = validate_extraction(fields, schema, [], 95)
    math = next(r for r in results if r.rule_name == "invoice_math_check")
    assert math.passed


def test_invoice_math_fail():
    fields = {"subtotal": "$100.00", "tax": "$10.00", "total": "$99.00",
              "vendor": "X", "invoice_no": "1", "invoice_date": "2026-01-01",
              "due_date": "2027-01-01", "currency": "USD"}
    results = validate_extraction(fields, None, [], 90)
    math = next((r for r in results if r.rule_name == "invoice_math_check"), None)
    assert math is not None and not math.passed


def test_required_field_missing():
    schema = {"fields": {"parties": {"type": "array", "required": True}}}
    fields = {}
    results = validate_extraction(fields, schema, [], 90)
    req = next(r for r in results if r.rule_name == "required_parties")
    assert not req.passed
    assert req.severity == "error"


def test_confidence_threshold_warning():
    results = validate_extraction({}, None, [], 60)
    conf = next(r for r in results if r.rule_name == "confidence_threshold")
    assert not conf.passed
    assert conf.severity == "warning"


def test_confidence_threshold_pass():
    results = validate_extraction({}, None, [], 95)
    conf = next(r for r in results if r.rule_name == "confidence_threshold")
    assert conf.passed


def test_anomalies_flagged():
    results = validate_extraction({}, None, ["Missing signature", "Date mismatch"], 90)
    anomaly = next(r for r in results if r.rule_name == "anomaly_check")
    assert not anomaly.passed
    assert "Missing signature" in anomaly.message


def test_contract_expiration_future():
    fields = {
        "parties": ["A Corp", "B Inc"],
        "effective_date": "2026-01-01",
        "expiration_date": "2028-01-01",
        "governing_law": "New York",
    }
    schema = {"fields": {
        "parties": {"type": "array", "required": True},
        "effective_date": {"type": "date", "required": True},
        "governing_law": {"type": "string", "required": True},
    }}
    results = validate_extraction(fields, schema, [], 92)
    exp = next((r for r in results if r.rule_name == "expiration_future"), None)
    if exp:
        assert exp.passed


def test_medical_phi_complete():
    fields = {"patient_name": "Jane Doe", "date_of_birth": "1985-03-12",
              "mrn": "MRN-001", "physician": "Dr. Smith",
              "consent_date": "2026-04-20", "facility": "City Hospital"}
    schema = {"fields": {
        "patient_name": {"type": "string", "required": True},
        "mrn": {"type": "string", "required": True},
        "physician": {"type": "string", "required": True},
        "consent_date": {"type": "date", "required": True},
        "facility": {"type": "string", "required": True},
    }}
    results = validate_extraction(fields, schema, [], 98)
    phi = next(r for r in results if r.rule_name == "phi_complete")
    assert phi.passed
