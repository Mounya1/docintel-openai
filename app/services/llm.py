"""
LLM Service — uses OpenAI GPT-4o to classify documents and extract structured fields.

Two-step pipeline:
  1. classify_document()  → detect doc_type if not provided by schema
  2. extract_fields()     → extract structured JSON fields per schema definition

Uses OpenAI's JSON mode (response_format={"type": "json_object"}) for reliable
structured output, and vision input for image-based documents.
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
import os
import re



logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in environment")
        _client = OpenAI(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a document intelligence AI specializing in extracting structured data from business documents.

Your task: Extract all relevant fields from the provided document text according to the given schema.

Rules:
1. Return ONLY valid JSON — no markdown fences, no explanation, no preamble
2. For each field, provide: value, confidence (0-100), and optional notes
3. Detect the document type from content if not specified
4. Flag anomalies or concerns in the "anomalies" array
5. If a required field is missing, set value to null and confidence to 0
6. For currency values, include the currency symbol (e.g., "$12,500.00")
7. For dates, use ISO 8601 format (YYYY-MM-DD)
8. overall_confidence is the weighted average across all fields

Response format (strict JSON):
{
  "doc_type": "contract|invoice|report|medical|document",
  "summary": "One sentence summary of the document",
  "fields": {
    "field_name": {
      "value": "<extracted value — string, number, array, or null>",
      "confidence": 95,
      "notes": "<optional note about extraction uncertainty>"
    }
  },
  "anomalies": ["list of concerns, mismatches, or missing required items"],
  "overall_confidence": 90,
  "page_count_estimate": 1
}"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_fields(
    text: str,
    schema_definition: Optional[Dict] = None,
    doc_type_hint: Optional[str] = None,
) -> Tuple[Dict[str, Any], int, float]:
    """
    Call OpenAI GPT-4o to extract structured fields.

    Returns:
        (result_dict, processing_time_ms, overall_confidence)
    """
    client = get_client()
    start = time.monotonic()

    schema_str = ""
    if schema_definition:
        schema_str = f"\n\nSchema to extract (extract ALL these fields):\n{json.dumps(schema_definition, indent=2)}"
    if doc_type_hint:
        schema_str += f"\n\nDocument type hint: {doc_type_hint}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if text.startswith("__IMAGE_BASE64__:"):
        # Vision input
        b64_data = text.replace("__IMAGE_BASE64__:", "")
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_data}",
                        "detail": "high",
                    },
                },
                {
                    "type": "text",
                    "text": f"Extract all data fields from this document image.{schema_str}",
                },
            ],
        })
        # Vision + json_object mode: not all models support both — parse carefully
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=2048,
            temperature=0,
        )
    else:
        # Text input with JSON mode
        capped = text[:15_000]
        messages.append({
            "role": "user",
            "content": f"Document text:\n\n{capped}\n\nExtract all data fields from this document.{schema_str}",
        })
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=2048,
            temperature=0,
            response_format={"type": "json_object"},
        )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    raw = response.choices[0].message.content or ""

    try:
        clean = raw.strip()
        clean = re.sub(r"^```json\s*", "", clean)
        clean = re.sub(r"^```\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean).strip()
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        logger.error(f"OpenAI JSON parse error: {e} | Raw: {raw[:300]}")
        result = {
            "doc_type": doc_type_hint or "document",
            "summary": "Extraction partially failed",
            "fields": {},
            "anomalies": ["AI response was not valid JSON"],
            "overall_confidence": 30,
            "page_count_estimate": 1,
        }

    tokens = response.usage.total_tokens if response.usage else "?"
    logger.info(
        f"OpenAI extraction: model={settings.openai_model} "
        f"confidence={result.get('overall_confidence')}% "
        f"time={elapsed_ms}ms tokens={tokens}"
    )
    return result, elapsed_ms, float(result.get("overall_confidence", 50))


def classify_document(text: str) -> str:
    """Quick classification — keyword heuristics first, OpenAI fallback."""
    t = text.lower()[:3000]

    if any(k in t for k in ["invoice", "bill to", "invoice number", "inv-", "amount due"]):
        return "invoice"
    if any(k in t for k in ["agreement", "contract", "parties", "whereas", "governing law"]):
        return "contract"
    if any(k in t for k in ["patient", "mrn", "diagnosis", "physician", "consent", "hipaa"]):
        return "medical"
    if any(k in t for k in ["revenue", "ebitda", "quarterly", "balance sheet", "profit"]):
        return "report"

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Classify documents. Reply with exactly ONE word from: contract, invoice, report, medical, document"
                },
                {"role": "user", "content": f"Classify:\n\n{text[:2000]}"},
            ],
            max_tokens=10,
            temperature=0,
        )
        return response.choices[0].message.content.strip().lower().split()[0]
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return "document"


def summarize_document(text: str, fields: Dict[str, Any]) -> str:
    """Generate a 2-3 sentence human-readable summary after extraction."""
    try:
        client = get_client()
        fields_str = json.dumps({k: v for k, v in fields.items() if v is not None}, indent=2)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You write concise 2-3 sentence document summaries for business users."
                },
                {
                    "role": "user",
                    "content": f"Summarize based on extracted fields:\n\n{fields_str}\n\nExcerpt:\n{text[:800]}"
                },
            ],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return ""
