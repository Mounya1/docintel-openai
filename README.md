#  DocIntel — AI-Document Intelligence Platform

> **Extract structured data from any document in seconds using GPT-4o.**

**[Live Demo](https://docintel-openai.vercel.app)** · **[API Docs](https://docintel-api-wnb5.onrender.com/docs)** · **Demo: admin@docintel.ai / Admin123!**

DocIntel is a full-stack document intelligence platform that automates document classification, field extraction, and validation using OpenAI's GPT-4o. Upload contracts, invoices, medical records, or reports — DocIntel extracts structured JSON fields with confidence scores, flags anomalies, and stores everything in a searchable database.

---

##  Key Features

| Feature | Description |
|---|---|
|  **AI Extraction** | GPT-4o classifies documents and extracts structured fields with 90–95% confidence |
|  **Multi-Format Support** | PDF, images (PNG, JPG via GPT-4o vision), DOCX, XLSX, TXT, CSV |
|  **Auth & RBAC** | JWT-based authentication with role-based access control (Admin, Reviewer, Viewer) |
|  **Async Processing** | Optional Celery + Redis queue (`USE_CELERY=true`); otherwise processed in-process |
|  **Cloud Storage** | AWS S3 integration for secure file storage |
|  **Confidence Scoring** | Per-field and overall confidence with risk-level classification |
|  **Validation Engine** | Schema-driven rules + business logic (invoice totals, date checks, required fields) |
|  **Audit Logging** | Immutable audit trail for every action |
|  **MCP Server** | 9-tool Model Context Protocol server for Copilot / Claude integration |
|  **Dockerized** | One-command local stack with Docker Compose (5 containers) |
|  **Cloud Deployed** | Frontend on Vercel, API + Postgres on Render, files on AWS S3 |

---

##  Architecture

```
┌─────────────────────────────────────────────────────────┐
│              React + Vite Frontend (Vercel)             │
│                docintel-openai.vercel.app               │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Render)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Auth    │ │Documents │ │Schemas   │ │ Analytics │  │
│  │  Routes  │ │  Routes  │ │  Routes  │ │  Routes   │  │
│  └──────────┘ └────┬─────┘ └──────────┘ └───────────┘  │
│                    │                                    │
│  ┌─────────────────▼────────────────────────────────┐   │
│  │           Processing Pipeline                     │   │
│  │  OCR → Classification → Extraction → Validation   │   │
│  └─────────────────┬────────────────────────────────┘   │
└────────────────────┼────────────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
  ┌──────────┐ ┌──────────┐    ┌──────────┐
  │PostgreSQL│ │  Redis   │    │  AWS S3  │
  │ (Render) │ │(optional)│    │ (Files)  │
  └──────────┘ └──────────┘    └──────────┘
```

---

##  Live Demo

| | URL |
|---|---|
| **Frontend** | [docintel-openai.vercel.app](https://docintel-openai.vercel.app) |
| **API Docs** | [docintel-api-wnb5.onrender.com/docs](https://docintel-api-wnb5.onrender.com/docs) |
| **Health Check** | [docintel-api-wnb5.onrender.com/api/health](https://docintel-api-wnb5.onrender.com/api/health) |

**Demo Credentials:**
- Admin: `admin@docintel.ai` / `Admin123!`
- Reviewer: `reviewer@docintel.ai` / `Review123!`

> Note: The API runs on Render's free tier and may take ~50s to wake after inactivity.

---

##  Quick Start (Local)

### Prerequisites

- Docker & Docker Compose
- OpenAI API key
- AWS S3 bucket (for file storage)

### 1. Clone & Configure

```bash
git clone https://github.com/Mounya1/docintel-openai.git
cd docintel-openai
cp .env.example .env
```

Edit `.env` and set at least `OPENAI_API_KEY`. Fill in the `AWS_*` and `S3_BUCKET_NAME`
values to store uploads in S3; leave them blank to keep files on local disk.

### 2. Launch

```bash
docker compose up --build -d
```

### 3. Open

- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs

---

##  Docker Services

| Container | Image | Port | Purpose |
|---|---|---|---|
| `api` | Python 3.12 + FastAPI | 8000 | REST API server |
| `frontend` | Node 20 + React/Vite | 5173 | Web UI |
| `worker` | Python 3.12 + Celery | — | Background task processing |
| `postgres` | PostgreSQL 16 | 5432 | Primary database |
| `redis` | Redis 7 | 6379 | Task queue broker |

---

##  Deployment

| Part | Platform | Config |
|---|---|---|
| Frontend | Vercel | `frontend/vercel.json` — project root `frontend`, env `VITE_API_BASE_URL=https://docintel-api-wnb5.onrender.com` |
| API + Postgres | Render (Blueprint) | `render.yaml` — Docker web service + free Postgres |
| Files | AWS S3 | `S3_BUCKET_NAME` + AWS keys set in Render |

Pushing to `main` redeploys both Vercel and Render automatically.

> Render's free Postgres expires after 30 days. For a permanent free setup (Oracle Cloud
> Always Free VM + Neon Postgres + Caddy HTTPS), see [`deploy/README.md`](deploy/README.md).

---

##  Processing Pipeline

When a document is uploaded:

1. **Upload** → File stored in AWS S3
2. **Text Extraction** → pypdf for PDFs (optional Tesseract OCR for scans), GPT-4o vision for images
3. **Classification** → GPT-4o identifies document type (invoice, contract, report, medical)
4. **Extraction** → GPT-4o extracts structured fields as JSON with confidence scores
5. **Validation** → Schema rules + business logic checks
6. **Storage** → Results persisted to PostgreSQL
7. **Audit** → Immutable log entry created

---

##  API Endpoints

All routes are under `/api`. Interactive reference: [`/docs`](https://docintel-api-wnb5.onrender.com/docs).

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT |
| GET | `/api/auth/me` | Get current user |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/` | Upload one or more documents for processing |
| GET | `/api/documents/` | List documents (filter by `status`, `type`, `search`) |
| GET | `/api/documents/{id}` | Get document details |
| GET | `/api/documents/{id}/download` | Download the original file |
| POST | `/api/documents/{id}/review` | Approve or reject a document |
| DELETE | `/api/documents/{id}` | Delete document |

### Extractions
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/extractions/document/{doc_id}` | All extraction versions for a document |
| GET | `/api/extractions/{id}/validations` | Validation results for an extraction |
| PATCH | `/api/extractions/{id}/fields` | Edit fields (creates a new version) |

### Schemas, Analytics, Audit & Users
| Method | Endpoint | Description |
|---|---|---|
| GET / POST | `/api/schemas/` | List or create extraction schemas |
| GET / PUT / DELETE | `/api/schemas/{id}` | Get, update or delete a schema |
| GET | `/api/analytics/overview` | Dashboard stats |
| GET | `/api/audit/` | Audit log (paginated) |
| GET | `/api/audit/export` | Export audit log as CSV |
| GET / POST | `/api/users/` | List or create users (admin) |
| PATCH / DELETE | `/api/users/{id}` | Update or deactivate a user (admin) |

---

##  MCP Server

`app/mcp_server.py` is a Model Context Protocol server that lets AI assistants
(GitHub Copilot in VS Code, Claude Code, Claude Desktop) query DocIntel data directly.

| Tool | Description |
|---|---|
| `health` | Server status and connected database (host only) |
| `list_documents` | List documents with filters |
| `get_document` | Document details with latest extraction |
| `list_schemas` | List extraction schemas |
| `list_extractions` | Extraction versions for a document |
| `list_audit_logs` | Recent audit log entries |
| `analytics_overview` | Dashboard statistics |
| `summarize_document` | AI summary of a document |
| `ask_document` | Ask a question about a document |

### Setup

1. Create `.env.mcp` in the project root (git-ignored) with the database to query:
   ```env
   # Local docker-compose database
   DATABASE_URL=postgresql+asyncpg://docintel:docintel_secret@127.0.0.1:5432/docintel
   # Or the live Render database (External Database URL, pasted as-is)
   # DATABASE_URL=postgresql://docintel:...@dpg-xxxx.oregon-postgres.render.com/docintel
   ```
2. **VS Code:** `.vscode/mcp.json` already registers `docintel-mcp`. Run
   **MCP: List Servers → docintel-mcp → Start Server**, then use Copilot Chat in **Agent** mode.
3. **Claude Code:**
   ```bash
   claude mcp add docintel -- .venv/bin/python3 -m app.mcp_server
   ```

Example prompts: *"Give me an analytics overview"*, *"List documents that need review"*,
*"Summarize document `<id>`"*.

---

##  Tech Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Celery, Pydantic

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4

**AI/ML:** OpenAI GPT-4o / GPT-4o-mini, JSON mode extraction, vision input for images

**Database:** PostgreSQL 16 (asyncpg), SQLite for quick local dev, Redis 7 (optional)

**Infrastructure:** Docker, Docker Compose, Vercel, Render, AWS S3

**Auth:** JWT (python-jose), bcrypt, RBAC

---

##  Project Structure

```
docintel-openai/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings & environment
│   ├── render_config.py        # Normalizes hosted Postgres URLs for asyncpg
│   ├── mcp_server.py           # MCP server (9 tools)
│   ├── database.py             # Async SQLAlchemy engine
│   ├── models.py               # ORM models
│   ├── worker.py               # Celery task definitions
│   ├── routes/
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── documents.py        # Document CRUD + upload
│   │   ├── extractions.py      # Extraction results
│   │   ├── schemas.py          # Schema management
│   │   ├── analytics.py        # Dashboard analytics
│   │   ├── audit.py            # Audit log viewer
│   │   └── users.py            # User management
│   ├── services/
│   │   ├── llm.py              # OpenAI GPT-4o integration
│   │   ├── ocr.py              # Text extraction (PDF, DOCX)
│   │   ├── pipeline.py         # Processing orchestrator
│   │   ├── storage.py          # AWS S3 file storage
│   │   ├── validation.py       # Business rule validation
│   │   └── auth.py             # Auth service
│   └── utils/
│       └── audit.py            # Audit log writer
├── frontend/                   # React + Vite app (vercel.json for Vercel)
├── deploy/                     # Optional self-hosted setup (Caddy, Oracle/EC2, Neon)
├── docker-compose.yml
├── Dockerfile
├── render.yaml                 # Render deployment config
├── requirements.txt
└── .env.example                # Copy to .env
```

---

##  Sample Extraction Output

```json
{
  "doc_type": "invoice",
  "summary": "Invoice #INV-3337 from Sliced Invoices for web design services",
  "fields": {
    "invoice_number": { "value": "INV-3337", "confidence": 98 },
    "order_number": { "value": "12345", "confidence": 95 },
    "invoice_date": { "value": "2016-01-25", "confidence": 97 },
    "due_date": { "value": "2016-01-31", "confidence": 97 },
    "total_due": { "value": "$93.50", "confidence": 99 },
    "service_description": { "value": "Web Design", "confidence": 95 },
    "tax": { "value": "$8.50", "confidence": 94 },
    "payment_status": { "value": "Paid", "confidence": 90 }
  },
  "anomalies": [],
  "overall_confidence": 95
}
```

---

##  Security

- JWT-based authentication with configurable expiration
- Role-based access control (Admin, Reviewer, Viewer)
- Password hashing with bcrypt
- CORS middleware (currently allows all origins; restrict before handling sensitive data)
- Input validation with Pydantic
- Immutable audit log for compliance
- Secrets kept in git-ignored `.env` / `.env.mcp` and platform environment variables

---
