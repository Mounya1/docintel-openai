# ─────────────────────────────────────────────────
# DocIntel — Production Dockerfile
# ─────────────────────────────────────────────────
FROM python:3.12-slim

# Security: run as non-root
RUN groupadd -r docintel && useradd -r -g docintel docintel

WORKDIR /app

# System deps (tesseract optional — uncomment to enable OCR on scanned PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # tesseract-ocr \
    # poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Create dirs and fix ownership
RUN mkdir -p /app/uploads /app/logs /app/data \
    && chown -R docintel:docintel /app

USER docintel

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
