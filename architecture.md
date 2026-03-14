# WebPilot AI — Architecture & Design Documentation

## 1. System Architecture (ASCII Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            WebPilot AI System                               │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │                  BROWSER (localhost:3000)             │
  │                                                      │
  │  ┌────────────┐  ┌───────────────┐  ┌──────────────┐│
  │  │  TaskForm  │  │ ResultViewer  │  │ TaskHistory  ││
  │  │            │  │               │  │              ││
  │  │ URL input  │  │ SSE live log  │  │  Task list   ││
  │  │ Goal input │  │ Progress bar  │  │  Status tags ││
  │  │ Category   │  │ Result card   │  │  Delete btn  ││
  │  └─────┬──────┘  └───────┬───────┘  └──────┬───────┘│
  │        │POST /api/tasks  │SSE stream        │GET/DEL │
  └────────┼─────────────────┼──────────────────┼────────┘
           │                 │                  │
           ▼                 ▼                  ▼
  ┌─────────────────────────────────────────────────────────┐
  │               FastAPI Backend  (localhost:8000)          │
  │                                                         │
  │  ┌──────────────────────────────────────────────────┐  │
  │  │                   main.py                         │  │
  │  │                                                   │  │
  │  │  POST /api/tasks ─────→ create Task (PENDING)    │  │
  │  │  GET  /api/tasks ─────→ list tasks (paginated)   │  │
  │  │  GET  /api/tasks/{id} → task + logs + result     │  │
  │  │  DEL  /api/tasks/{id} → delete task              │  │
  │  │  GET  /api/tasks/{id}/stream → SSE stream        │  │
  │  │  GET  /api/health ────→ health check             │  │
  │  └──────────────────────────┬───────────────────────┘  │
  │                             │                          │
  │  ┌──────────────────────────▼───────────────────────┐  │
  │  │              agent_service.py                     │  │
  │  │                                                   │  │
  │  │  execute_task_stream()                            │  │
  │  │    1. Set task status → RUNNING                   │  │
  │  │    2. POST to TinyFish SSE endpoint               │  │
  │  │    3. For each SSE event:                         │  │
  │  │       - Save TaskLog row                          │  │
  │  │       - Yield SSEEvent to FastAPI route           │  │
  │  │    4. On COMPLETE: Save TaskResult, status=DONE   │  │
  │  │    5. On ERROR: Save error, status=FAILED         │  │
  │  └──────────────────────────┬───────────────────────┘  │
  │                             │ httpx AsyncClient         │
  └─────────────────────────────┼──────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────┐
  │         TinyFish Cloud  (https://agent.tinyfish.ai)     │
  │                                                         │
  │  POST /v1/automation/run-sse                            │
  │                                                         │
  │  ┌──────────────────────────────────────────────────┐  │
  │  │  Browser Automation Engine                        │  │
  │  │                                                   │  │
  │  │  • Launches real Chromium browser                 │  │
  │  │  • Navigates to target URL                        │  │
  │  │  • Interprets goal → browser actions              │  │
  │  │  • Streams: STARTED, PROGRESS…, COMPLETE/ERROR    │  │
  │  └──────────────────────────────────────────────────┘  │
  │                                                         │
  │  Supports:  Amazon, LinkedIn, Best Buy, Google,         │
  │             and virtually any public website            │
  └─────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │                Database (SQLite / PostgreSQL)            │
  │                                                         │
  │  ┌────────────┐    ┌────────────┐    ┌───────────────┐ │
  │  │   tasks    │    │ task_logs  │    │ task_results  │ │
  │  │            │1   │            │*   │               │ │
  │  │ id (UUID)  │───▶│ task_id    │    │ task_id (1:1) │ │
  │  │ title      │    │ event_type │    │ data (JSON)   │ │
  │  │ target_url │    │ message    │    │ raw_text      │ │
  │  │ goal       │    │ level      │    │ screenshot_url│ │
  │  │ status     │    │ timestamp  │    │ created_at    │ │
  │  │ category   │    │ metadata   │    └───────────────┘ │
  │  │ created_at │    └────────────┘                      │
  │  │ duration_s │                                        │
  │  └────────────┘                                        │
  └─────────────────────────────────────────────────────────┘
```

---

## 2. Sequence Diagram

```
User          React Frontend    FastAPI Backend    TinyFish API    Database
 │                  │                   │                │             │
 │  Fill form       │                   │                │             │
 │─────────────────▶│                   │                │             │
 │  Click Run Agent │                   │                │             │
 │─────────────────▶│                   │                │             │
 │                  │ POST /api/tasks   │                │             │
 │                  │──────────────────▶│                │             │
 │                  │                   │ INSERT Task     │             │
 │                  │                   │(status=PENDING)│             │
 │                  │                   │────────────────────────────▶│
 │                  │                   │     task.id ◀──────────────│
 │                  │ {id, status:      │                │             │
 │                  │  "pending"} ◀─────│                │             │
 │                  │ Open SSE stream   │                │             │
 │                  │ GET /tasks/{id}   │                │             │
 │                  │  /stream ────────▶│                │             │
 │                  │                   │ UPDATE status  │             │
 │                  │                   │ → RUNNING ─────────────────▶│
 │                  │                   │ POST /run-sse  │             │
 │                  │                   │───────────────▶│             │
 │                  │                   │                │ Open browser│
 │                  │                   │                │ Navigate URL│
 │                  │ data: STARTED ◀─ │ ◀── STARTED ── │             │
 │  "Agent started" │                   │ INSERT log row │             │
 │  ◀───────────────│                   │────────────────────────────▶│
 │                  │                   │                │ Click/Type/ │
 │                  │ data: PROGRESS ◀─│ ◀── PROGRESS ──│ Scroll...   │
 │  "Typed search"  │                   │ INSERT log row │             │
 │  ◀───────────────│                   │────────────────────────────▶│
 │                  │       ...more PROGRESS events...   │             │
 │                  │                   │                │ Extract data│
 │                  │ data: COMPLETE ◀─│ ◀── COMPLETE ──│             │
 │                  │                   │ INSERT result  │             │
 │                  │                   │ UPDATE status  │             │
 │                  │                   │ → COMPLETED ───────────────▶│
 │                  │ GET /tasks/{id}   │                │             │
 │                  │──────────────────▶│                │             │
 │                  │                   │ SELECT task +  │             │
 │                  │                   │ logs + result ─────────────▶│
 │                  │                   │                │ ◀──────────│
 │                  │ {task, logs,      │                │             │
 │  View result     │  result} ◀────────│                │             │
 │  ◀───────────────│                   │                │             │
```

---

## 3. Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Flow                                 │
│                                                                 │
│  INPUT                                                          │
│  ─────                                                          │
│  User types:                                                    │
│    URL:  "https://amazon.com"                                   │
│    Goal: "Find the price of AirPods Pro"                        │
│                                                                 │
│         ┌──────────┐                                            │
│         │ TaskCreate│  ← Pydantic validates input               │
│         │  schema   │    (URL format, min length, etc.)         │
│         └────┬─────┘                                            │
│              │                                                  │
│         ┌────▼─────┐                                            │
│         │  Task ORM│  ← SQLAlchemy saves to DB                  │
│         │  model   │    id=UUID, status=PENDING                 │
│         └────┬─────┘                                            │
│              │                                                  │
│  PROCESSING  │                                                  │
│  ──────────  │                                                  │
│         ┌────▼─────────────────────────────────────────┐       │
│         │  TinyFish Request                             │       │
│         │  {                                            │       │
│         │    "url": "https://amazon.com",               │       │
│         │    "goal": "Find the price of AirPods Pro"   │       │
│         │  }                                            │       │
│         └────┬─────────────────────────────────────────┘       │
│              │                                                  │
│         ┌────▼─────────────────────────────────────────┐       │
│         │  TinyFish SSE Response (streamed)             │       │
│         │  data: {"event":"STARTED","message":"..."}   │       │
│         │  data: {"event":"PROGRESS","message":"..."}  │       │
│         │  data: {"event":"COMPLETE","data":{          │       │
│         │           "price":"$249","title":"..."}}     │       │
│         └────┬─────────────────────────────────────────┘       │
│              │                                                  │
│  OUTPUT      │                                                  │
│  ──────      │                                                  │
│         ┌────▼──────────────────────────────────────┐          │
│         │  TaskResult saved to DB                    │          │
│         │  {                                         │          │
│         │    "data": {"price": "$249.00",            │          │
│         │             "title": "AirPods Pro"},       │          │
│         │    "raw_text": "The current price is...",  │          │
│         │    "screenshot_url": "https://..."         │          │
│         │  }                                         │          │
│         └────┬──────────────────────────────────────┘          │
│              │                                                  │
│         ┌────▼──────────────────────────────────────┐          │
│         │  Displayed in ResultViewer component       │          │
│         │  (React renders JSON + raw text card)      │          │
│         └───────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Schema

```
┌──────────────────────────────────────────────────────────────────────┐
│  TABLE: tasks                                                         │
├─────────────────┬──────────────────┬─────────────────────────────────┤
│ Column          │ Type             │ Notes                            │
├─────────────────┼──────────────────┼─────────────────────────────────┤
│ id              │ VARCHAR(36)  PK  │ UUID v4                          │
│ title           │ VARCHAR(200)     │ NOT NULL                         │
│ target_url      │ VARCHAR(500)     │ NOT NULL                         │
│ goal            │ TEXT             │ NOT NULL                         │
│ status          │ ENUM             │ pending|running|completed|failed │
│ category        │ VARCHAR(100)     │ nullable                         │
│ created_at      │ DATETIME(tz)     │ auto-set on insert               │
│ updated_at      │ DATETIME(tz)     │ auto-updated on change           │
│ completed_at    │ DATETIME(tz)     │ nullable                         │
│ duration_seconds│ INTEGER          │ nullable                         │
│ error_message   │ TEXT             │ set if status=failed             │
└─────────────────┴──────────────────┴─────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  TABLE: task_logs                                                     │
├─────────────────┬──────────────────┬─────────────────────────────────┤
│ id              │ INTEGER      PK  │ auto-increment                   │
│ task_id         │ VARCHAR(36)  FK  │ → tasks.id (CASCADE DELETE)      │
│ timestamp       │ DATETIME(tz)     │ when this event was received     │
│ event_type      │ VARCHAR(50)      │ STARTED|PROGRESS|COMPLETE|ERROR  │
│ message         │ TEXT             │ human-readable description       │
│ level           │ ENUM             │ info|warning|error|debug         │
│ metadata_json   │ JSON             │ raw data from TinyFish (nullable)│
└─────────────────┴──────────────────┴─────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  TABLE: task_results                                                  │
├─────────────────┬──────────────────┬─────────────────────────────────┤
│ id              │ INTEGER      PK  │ auto-increment                   │
│ task_id         │ VARCHAR(36)  FK  │ → tasks.id (CASCADE DELETE) 1:1  │
│ data            │ JSON             │ structured extracted data        │
│ raw_text        │ TEXT             │ plain text summary               │
│ screenshot_url  │ VARCHAR(1000)    │ optional screenshot URL          │
│ created_at      │ DATETIME(tz)     │ auto-set on insert               │
└─────────────────┴──────────────────┴─────────────────────────────────┘
```

---

## 5. Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Technology Choices                        │
│                                                             │
│  Layer            Technology        Why                     │
│  ─────────────────────────────────────────────────────────  │
│  Frontend         React 18          Modern UI, hooks,       │
│                                     EventSource SSE support │
│                                                             │
│  State Mgmt       React useState    Simple enough — no      │
│                                     Redux needed            │
│                                                             │
│  HTTP Client      Axios             Cleaner than fetch,     │
│  (frontend)                         interceptors, auto JSON │
│                                                             │
│  SSE Client       EventSource API   Native browser API,     │
│  (frontend)                         auto-reconnect built-in │
│                                                             │
│  Notifications    react-hot-toast   Minimal, looks great    │
│                                                             │
│  Backend          FastAPI + Python  Async, auto OpenAPI     │
│                   3.11              docs, fast              │
│                                                             │
│  ORM              SQLAlchemy 2.0    Industry standard,      │
│                                     async support           │
│                                                             │
│  Database         SQLite (dev)      Zero config for dev     │
│                   PostgreSQL (prod) Scalable for production  │
│                                                             │
│  HTTP Client      httpx + httpx-sse Async SSE reading       │
│  (backend)                                                  │
│                                                             │
│  Retry Logic      tenacity          Exponential backoff     │
│                                     for API resilience      │
│                                                             │
│  Container        Docker + nginx    Production-grade        │
│                   (multi-stage)     small images            │
│                                                             │
│  AI/Automation    TinyFish API      Natural language →      │
│                                     browser actions         │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Security Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Measures                         │
│                                                             │
│  Threat            Mitigation                               │
│  ─────────────────────────────────────────────────────────  │
│  API key exposure  Stored in .env (never committed to Git)  │
│                    .env.example has placeholder only        │
│                                                             │
│  SQL injection     SQLAlchemy ORM with parameterised        │
│                    queries — no raw SQL                     │
│                                                             │
│  XSS               React auto-escapes JSX output            │
│                    No dangerouslySetInnerHTML used           │
│                                                             │
│  CORS              Only localhost:3000 whitelisted          │
│                    (update CORS_ORIGINS for production)     │
│                                                             │
│  SSRF              target_url is sent to TinyFish           │
│                    (TinyFish acts as sandbox — no direct    │
│                    internal network access from backend)    │
│                                                             │
│  Dependency        Pin all versions in requirements.txt &  │
│  vulnerabilities   package.json for reproducible builds    │
│                                                             │
│  Container         Non-root user in backend Dockerfile      │
│                    Minimal base images (slim, alpine)       │
│                                                             │
│  Input validation  Pydantic validates all API inputs        │
│                    URL format check, length limits          │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Deployment Guide

### Local Development
```bash
# Backend:  http://localhost:8000
cd backend && uvicorn main:app --reload

# Frontend: http://localhost:3000
cd frontend && npm start
```

### Docker (All-in-one)
```bash
# Edit .env first!
docker compose up --build
```

### Production Checklist

Before deploying to a server, make sure to:

1. **Secrets**
   - [ ] Generate a strong `TINYFISH_API_KEY` (never use a test key in prod)
   - [ ] Set a strong `POSTGRES_PASSWORD` in `docker-compose.yml`
   - [ ] Remove `DEBUG=True` from `.env`

2. **Backend**
   - [ ] Set `CORS_ORIGINS` to your real frontend domain
   - [ ] Use PostgreSQL instead of SQLite (`DATABASE_URL=postgresql+asyncpg://...`)
   - [ ] Put the API behind a reverse proxy (nginx) with HTTPS/TLS

3. **Frontend**
   - [ ] Set `REACT_APP_API_URL` to your real backend URL
   - [ ] Run `npm run build` and serve the `/build` folder
   - [ ] Enable HTTPS on your domain

4. **Infrastructure**
   - [ ] Set up automated backups for the PostgreSQL volume
   - [ ] Add monitoring / alerting (e.g. Uptime Robot for the `/api/health` endpoint)
   - [ ] Configure log rotation

---

## 8. Extension Ideas

Once you have the base system running, here are ideas to extend it:

| Feature | How to implement |
|---------|------------------|
| **Scheduled tasks** | Add APScheduler to the backend + a cron-like UI |
| **Email alerts** | Use sendgrid/smtp when a task completes |
| **Multi-user** | Add JWT auth (FastAPI Users library) |
| **Result diffing** | Compare today's result vs yesterday (price tracking) |
| **Webhook output** | POST result to Slack/Discord/Zapier |
| **Rate limiting** | Add fastapi-limiter to prevent API abuse |
| **Task templates** | Save favourite tasks for one-click re-run |
| **Export to CSV** | Add a GET /api/tasks/export CSV download route |
