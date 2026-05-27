#  DocIntel — AI-Document Intelligence Platform

> **Extract structured data from any document in seconds using GPT-4o.**

** [Live Demo](https://docintel-frontend-h454.onrender.com)** · ** [API Docs](https://docintel-api-wnb5.onrender.com/docs)** · **Demo: admin@docintel.ai / Admin123!**

DocIntel is a full-stack document intelligence platform that automates document classification, field extraction, and validation using OpenAI's GPT-4o. Upload contracts, invoices, medical records, or reports — DocIntel extracts structured JSON fields with confidence scores, flags anomalies, and stores everything in a searchable database.

---

##  Key Features

| Feature | Description |
|---|---|
|  **AI Extraction** | GPT-4o classifies documents and extracts structured fields with 90–95% confidence |
|  **Multi-Format Support** | PDF, DOCX, images (PNG, JPG), and plain text |
|  **Auth & RBAC** | JWT-based authentication with role-based access control (Admin, Reviewer, Viewer) |
|  **Async Processing** | Celery + Redis task queue for background document processing |
|  **Cloud Storage** | AWS S3 integration for secure file storage |
|  **Confidence Scoring** | Per-field and overall confidence with risk-level classification |
|  **Validation Engine** | Schema-driven rules + business logic (invoice totals, date checks, required fields) |
|  **Audit Logging** | Immutable audit trail for every action |
|  **MCP Server** | 7-tool Model Context Protocol server for AI agent integration |
|  **Dockerized** | One-command deployment with Docker Compose (5 containers) |

---

##  Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                 │
│              docintel-frontend-h454.onrender.com        │
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
  │  (Data)  │ │ (Queue)  │    │ (Files)  │
  └──────────┘ └──────────┘    └──────────┘
```

---

##  Live Demo

| | URL |
|---|---|
| **Frontend** | [docintel-frontend-h454.onrender.com](https://docintel-frontend-h454.onrender.com) |
| **API Docs** | [docintel-api-wnb5.onrender.com/docs](https://docintel-api-wnb5.onrender.com/docs) |
| **Health Check** | [docintel-api-wnb5.onrender.com/api/health](https://docintel-api-wnb5.onrender.com/api/health) |

**Demo Credentials:**
- Admin: `admin@docintel.ai` / `Admin123!`
- Reviewer: `reviewer@docintel.ai` / `Review123!`

> Note: Free tier — API may take ~30s to wake after inactivity.

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

Edit `.env` with your credentials:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket-name
```

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

##  Processing Pipeline

When a document is uploaded:

1. **Upload** → File stored in AWS S3
2. **OCR** → Text extracted via PyPDF2 (PDFs) or python-docx (DOCX)
3. **Classification** → GPT-4o identifies document type (invoice, contract, report, medical)
4. **Extraction** → GPT-4o extracts structured fields as JSON with confidence scores
5. **Validation** → Schema rules + business logic checks
6. **Storage** → Results persisted to PostgreSQL
7. **Audit** → Immutable log entry created

---

##  API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT |
| GET | `/api/auth/me` | Get current user |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload document for processing |
| GET | `/api/documents/` | List all documents |
| GET | `/api/documents/{id}` | Get document details |
| DELETE | `/api/documents/{id}` | Delete document |

### Extractions
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/extractions/{doc_id}` | Get extraction results |
| GET | `/api/extractions/{id}/fields` | Get extracted fields |

### Schemas & Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/schemas/` | List extraction schemas |
| POST | `/api/schemas/` | Create custom schema |
| GET | `/api/analytics/dashboard` | Dashboard stats |

---

##  MCP Server

DocIntel includes a Model Context Protocol (MCP) server with 7 tools for AI agent integration:

| Tool | Description |
|---|---|
| `upload_document` | Upload and process a document |
| `get_document` | Retrieve document details |
| `list_documents` | List documents with filters |
| `get_extraction` | Get extraction results |
| `create_schema` | Create extraction schema |
| `get_analytics` | Fetch dashboard analytics |
| `search_documents` | Search across documents |

---

##  Tech Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Celery, Pydantic

**Frontend:** React 18, Vite, TailwindCSS

**AI/ML:** OpenAI GPT-4o, JSON mode extraction, Vision API

**Database:** PostgreSQL 16 (asyncpg), Redis 7

**Infrastructure:** Docker, Docker Compose, AWS S3, Render

**Auth:** JWT (PyJWT), bcrypt, RBAC

---

##  Project Structure

```
docintel-openai/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings & environment
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
├── frontend/                   # React + Vite app
├── mcp_server/                 # MCP server (7 tools)
├── docker-compose.yml
├── Dockerfile
├── render.yaml                 # Render deployment config
├── requirements.txt
└── .env
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
- CORS configured for frontend origin
- Input validation with Pydantic
- Immutable audit log for compliance

---



