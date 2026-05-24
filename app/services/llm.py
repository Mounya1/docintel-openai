import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
import os
import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)

SYSTEM_PROMPT = """You are a document intelligence AI. Extract all relevant fields from the document.
Return your response as valid JSON with this structure:
{
  "doc_type": "contract|invoice|report|medical|document",
  "summary": "One sentence summary",
  "fields": { "field_name": { "value": "...", "confidence": 95, "notes": "" } },
  "anomalies": [],
  "overall_confidence": 90,
  "page_count_estimate": 1
}"""

CLASSIFICATION_PROMPT = """Classify the document into one of: contract, invoice, report, medical, or document.
Return your response as valid JSON with this structure:
{
  "doc_type": "<category>",
  "confidence": <0-100>,
  "reasoning": "<brief explanation>"
}"""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def classify_document(text: str) -> Tuple[str, float]:
    try:
        logger.info("Classifying...")
        client = get_client()
        start = time.monotonic()
        capped = text[:5000]
        
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": f"Classify the following document text and respond in JSON format:\n{capped}"}
            ],
            max_tokens=200,
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content or ""
        result = json.loads(raw.strip()) if raw else {"doc_type": "document", "confidence": 0}
        doc_type = result.get("doc_type", "document")
        confidence = float(result.get("confidence", 0))
        
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"✓ {doc_type} ({confidence}%) in {elapsed_ms}ms")
        return doc_type, confidence
        
    except Exception as e:
        logger.error(f"❌ Classification: {type(e).__name__}: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_fields(
    text: str,
    schema_definition: Optional[Dict] = None,
    doc_type_hint: Optional[str] = None,
) -> Tuple[Dict[str, Any], int, float]:
    try:
        logger.info("Extracting...")
        client = get_client()
        start = time.monotonic()
        schema_str = ""
        
        if schema_definition:
            schema_str = f"\n\nSchema:\n{json.dumps(schema_definition, indent=2)}"
        if doc_type_hint:
            schema_str += f"\n\nDocument type hint: {doc_type_hint}"
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if text.startswith("__IMAGE_BASE64__:"):
            b64_data = text.replace("__IMAGE_BASE64__:", "")
            messages.append({"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}", "detail": "high"}},
                {"type": "text", "text": f"Extract all data fields and respond in JSON format.{schema_str}"},
            ]})
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=2048,
                temperature=0
            )
        else:
            capped = text[:15000]
            messages.append({"role": "user", "content": f"Extract all fields from this document and respond in JSON format:\n\n{capped}{schema_str}"})
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=2048,
                temperature=0,
                response_format={"type": "json_object"}
            )
        
        elapsed_ms = int((time.monotonic() - start) * 1000)
        raw = response.choices[0].message.content or ""
        try:
            result = json.loads(raw.strip())
        except json.JSONDecodeError:
            result = {"doc_type": doc_type_hint or "document", "summary": "Failed", "fields": {}, "anomalies": ["JSON error"], "overall_confidence": 0, "page_count_estimate": 1}
        
        confidence = float(result.get("overall_confidence", 0))
        tokens = response.usage.total_tokens if response.usage else "?"
        logger.info(f"✓ Extracted {confidence}% confidence, {tokens} tokens in {elapsed_ms}ms")
        return result, elapsed_ms, confidence
        
    except Exception as e:
        logger.error(f"❌ Extraction: {type(e).__name__}: {e}")
        raise

def summarize_text(text: str, max_length: int = 500) -> str:
    client = get_client()
    capped = text[:5000]
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Summarize the document concisely."},
            {"role": "user", "content": f"Summarize:\n{capped}"}
        ],
        max_tokens=min(max_length // 4, 500),
        temperature=0.3
    )
    return (response.choices[0].message.content or "").strip()
