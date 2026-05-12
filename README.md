# DocIntel — AI Document Intelligence Platform

> Upload contracts, invoices, medical records, or reports → extract, classify, summarize, and validate data with Claude AI.

---

## Architecture

```
┌──────────────┐    ┌────────────────────────────────────────────────────┐
│   React UI   │───▶│              FastAPI Backend                        │
│  (Vite/TS)   │    │                                                    │
└──────────────┘    │  /api/auth         JWT login / register            │
                    │  /api/documents    Upload, list, detail, review     │
                    │  /api/extractions  AI results + field editing       │
                    │  /api/schemas      Extraction schema CRUD           │
                    │  /api/audit        Tamper-proof audit logs          │
                    │  /api/analytics    Stats and dashboards             │
                    │  /api/users        RBAC user management             │
                    └───────────────┬────────────────────────────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
       ┌────────────┐       ┌──────────────┐       ┌──────────────┐
       │  SQLite /  │       │  Claude API  │       │  Celery +    │
       │ PostgreSQL │       │ (Extraction) │       │  Redis Queue │
       └────────────┘       └──────────────┘       └──────────────┘
```

### Processing Pipeline

```
Upload → OCR (pypdf / Tesseract) → Claude LLM Extraction →
Schema Validation → Business Rules → Human Review (if needed) →
Versioned Storage → Audit Log
```

---

## Quick Start (Development)

### 1. Clone and install

```bash
git clone <repo>
cd docintel-py

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs  
Redoc:    http://localhost:8000/redoc

### 4. Default credentials

| Email | Password | Role |
|---|---|---|
| admin@docintel.ai | Admin123! | admin |
| reviewer@docintel.ai | Review123! | reviewer |

---

## Production (Docker)

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, JWT_SECRET_KEY, APP_SECRET_KEY

docker-compose up --build -d
```

Add Flower monitoring:
```bash
docker-compose --profile monitoring up -d
# Flower UI: http://localhost:5555
```

---

## API Reference

### Auth
```
POST /api/auth/login          { email, password } → { access_token, user }
POST /api/auth/register       { email, password, name, role?, department? }
GET  /api/auth/me             → current user
```

### Documents
```
POST /api/documents/          multipart: files[], schema_id? → [{ id, name, status }]
GET  /api/documents/          ?status=&type=&search=&limit=&offset=
GET  /api/documents/{id}      → DocumentDetail (with extractions + reviews)
PATCH /api/documents/{id}     { name?, doc_type?, schema_id? }
DELETE /api/documents/{id}    (admin/editor)
POST /api/documents/{id}/review  { decision: approved|rejected, notes? }
GET  /api/documents/{id}/download
POST /api/documents/{id}/retry
```

### Extractions
```
GET  /api/extractions/document/{doc_id}    → [ExtractionOut]  (all versions)
GET  /api/extractions/{id}/validations     → [ValidationOut]
PATCH /api/extractions/{id}/fields         { fields: {...} }   → new version
```

### Schemas
```
GET    /api/schemas/          → [SchemaOut]
POST   /api/schemas/          { name, doc_type, version, definition, validation_rules }
GET    /api/schemas/{id}
PUT    /api/schemas/{id}      partial update
DELETE /api/schemas/{id}      (admin)
```

### Audit
```
GET /api/audit/               ?user_id=&action=&search=&limit=&offset=
GET /api/audit/export         → CSV download (admin)
GET /api/audit/actions        → distinct action types
```

### Analytics
```
GET /api/analytics/overview   → totals, by_status, by_type, confidence, last 7 days
```

### Users
```
GET    /api/users/            (admin)
POST   /api/users/            { email, name, role, department }
PATCH  /api/users/{id}        { role?, department?, mfa_enabled? }
DELETE /api/users/{id}        soft delete (admin)
```

---

## Project Structure

```
docintel-py/
├── app/
│   ├── main.py              # FastAPI app, middleware, router registration
│   ├── config.py            # Pydantic settings (reads .env)
│   ├── database.py          # Async SQLAlchemy engine + session + seeding
│   ├── models.py            # ORM models: User, Document, Extraction, ...
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── worker.py            # Celery task definitions
│   ├── routes/
│   │   ├── auth.py          # Login, register, /me
│   │   ├── documents.py     # Upload, list, detail, review, download
│   │   ├── extractions.py   # Extraction versions + field edits
│   │   ├── schemas.py       # Schema CRUD
│   │   ├── audit.py         # Audit log list + CSV export
│   │   ├── analytics.py     # Stats dashboard
│   │   └── users.py         # User management
│   ├── services/
│   │   ├── auth.py          # JWT + password hashing
│   │   ├── ocr.py           # PDF/image/DOCX text extraction
│   │   ├── llm.py           # Claude API: classify + extract fields
│   │   ├── validation.py    # Business rule engine
│   │   └── pipeline.py      # Full async processing pipeline
│   ├── middleware/
│   │   └── auth.py          # get_current_user, require_role deps
│   └── utils/
│       └── audit.py         # write_audit_log helper
├── tests/
│   └── test_pipeline.py     # Validation unit tests
├── uploads/                 # File storage (use S3 in production)
├── logs/                    # Application logs
├── data/                    # SQLite DB (dev)
├── Dockerfile
├── docker-compose.yml
├── alembic.ini              # DB migration config
├── requirements.txt
└── .env.example
```

---

## Extending the Platform

### Add a new document type
1. Add schema via `POST /api/schemas/` with your field definitions
2. Add validation rules in `app/services/validation.py`
3. Schema auto-applies to all uploaded documents of that `doc_type`

### Swap OCR provider
Edit `app/services/ocr.py` — replace `_extract_pdf()` with AWS Textract:
```python
import boto3
textract = boto3.client("textract", region_name=settings.aws_region)
response = textract.analyze_document(Document={"S3Object": {...}}, FeatureTypes=["TABLES","FORMS"])
```

### Use S3 for file storage
In `app/routes/documents.py`, replace local file write with:
```python
s3 = boto3.client("s3")
s3.upload_fileobj(file.file, settings.s3_bucket_name, saved_name)
```

### Run tests
```bash
pytest tests/ -v
```

---

## Security Notes

- All endpoints require JWT Bearer token (except `/api/auth/login` and `/api/auth/register`)
- RBAC roles: `admin > editor > reviewer > viewer`
- Audit logs are append-only (no delete endpoint)
- PHI fields in medical documents log access but mask values in non-admin responses (extend as needed)
- Production: enable HTTPS, set strong `JWT_SECRET_KEY` and `APP_SECRET_KEY`
- HIPAA, SOC 2, GDPR compliance requires additional controls (encryption at rest, BAA with cloud provider, etc.)
