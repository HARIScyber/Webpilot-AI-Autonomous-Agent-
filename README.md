# WebPilot AI 🤖
## Autonomous Web Agent · Powered by TinyFish

WebPilot AI is a full-stack application that lets you submit natural language tasks
to an autonomous AI agent that navigates real websites, extracts data, and returns
structured results — all without writing a single line of browser automation code.

**Example:**  Type *"Find the price of AirPods Pro on Amazon"* → the agent opens
Amazon, searches, and returns the price in seconds.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Quick Start (Local Dev)](#quick-start-local-dev)
5. [VS Code Setup](#vs-code-setup)
6. [API Reference](#api-reference)
7. [Example Tasks](#example-tasks)
8. [Docker Deployment](#docker-deployment)
9. [Troubleshooting](#troubleshooting)
10. [How It Works](#how-it-works)

---

## Features

| Feature | Description |
|---------|-------------|
| 🌐 Real browser automation | TinyFish controls a real browser — handles JS, login walls, dynamic UIs |
| ⚡ Live streaming | Progress events stream to your dashboard in real-time via SSE |
| 🗄 Task history | Every task and its result are saved to a local database |
| 📊 React dashboard | Clean UI to submit tasks, watch progress, and view results |
| 🔌 REST API | Full FastAPI backend with Swagger docs at `/docs` |
| 🐳 Docker ready | One command to run the entire stack with PostgreSQL |
| 🔒 Secure by default | `.env` for secrets, CORS whitelisting, parameterised queries |

---

## Project Structure

```
webpilot-agent/
│
├── backend/
│   ├── main.py           ← FastAPI app, all routes
│   ├── agent_service.py  ← TinyFish API integration + SSE streaming
│   ├── database.py       ← SQLAlchemy async engine + session
│   ├── models.py         ← ORM models (Task, TaskLog, TaskResult)
│   ├── schemas.py        ← Pydantic request/response schemas
│   ├── config.py         ← Settings loaded from .env
│   ├── requirements.txt  ← Python dependencies
│   └── Dockerfile        ← Backend container
│
├── frontend/
│   ├── package.json      ← React dependencies
│   ├── Dockerfile        ← Frontend container (nginx)
│   ├── nginx.conf        ← SPA routing config
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── index.js      ← React entry point
│       ├── index.css     ← Global styles + CSS variables
│       ├── App.js        ← Root component, state management
│       └── components/
│           ├── TaskForm.js      ← Submit new tasks
│           ├── ResultViewer.js  ← Live stream + result display
│           └── TaskHistory.js   ← Past tasks sidebar
│
├── scripts/
│   └── run_agent_example.py  ← CLI test runner
│
├── .env.example          ← Copy to .env and fill in your API key
├── docker-compose.yml    ← Full stack Docker setup
├── README.md
└── architecture.md       ← System diagrams
```

---

## Prerequisites

| Tool | Version | Install Link |
|------|---------|--------------|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | Included with Node.js |
| Git | any | https://git-scm.com |
| TinyFish API key | — | https://tinyfish.ai |

Optional (for Docker setup):
- Docker Desktop: https://docker.com/products/docker-desktop

---

## Quick Start (Local Dev)

### Step 1 — Clone or open the project

```bash
cd webpilot-agent
```

### Step 2 — Create your `.env` file

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open `.env` and replace `your-tinyfish-api-key-here` with your real TinyFish API key.

### Step 3 — Set up the Python backend

```bash
cd backend

# Create a virtual environment (keeps dependencies isolated)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Browse to **http://localhost:8000/docs** to see the interactive Swagger UI.

### Step 4 — Set up the React frontend

Open a **new terminal** (keep the backend running):

```bash
cd frontend

# Install npm packages
npm install

# Start the dev server
npm start
```

The browser should open **http://localhost:3000** automatically.

### Step 5 — Run your first task

1. Open http://localhost:3000
2. Click the **"🛒 Price Check"** example button (top-left)
3. Click **"🚀 Run Agent"**
4. Watch the live progress log in the centre panel
5. See the extracted price in the result card when done!

---

## VS Code Setup

### Recommended Extensions

Install these extensions in VS Code for the best experience:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next",
    "bradlc.vscode-tailwindcss",
    "ms-azuretools.vscode-docker",
    "mtxr.sqltools",
    "christian-kohler.path-intellisense"
  ]
}
```

### VS Code Launch Configuration

Create `.vscode/launch.json` to run both servers with F5:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

### VS Code Workspace Settings

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./backend/venv/Scripts/python.exe",
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  }
}
```

---

## API Reference

### Base URL
```
http://localhost:8000
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/tasks` | Create and queue a new task |
| `GET` | `/api/tasks` | List all tasks (paginated) |
| `GET` | `/api/tasks/{id}` | Get full task detail (logs + result) |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `GET` | `/api/tasks/{id}/stream` | SSE stream for live progress |

### Create a Task — Example

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Find AirPods Pro price",
    "target_url": "https://www.amazon.com",
    "goal": "Search for AirPods Pro 2nd generation and return the price and title",
    "category": "price_check"
  }'
```

Response:
```json
{
  "id": "abc-123-def-456",
  "title": "Find AirPods Pro price",
  "target_url": "https://www.amazon.com",
  "goal": "Search for AirPods Pro 2nd generation...",
  "status": "pending",
  "category": "price_check",
  "created_at": "2024-03-12T10:00:00Z"
}
```

### Stream Task Progress

```bash
curl -N http://localhost:8000/api/tasks/abc-123-def-456/stream
```

Output (one line per event):
```
data: {"event": "STARTED",   "task_id": "abc-123", "message": "Agent started. Navigating to https://www.amazon.com…"}
data: {"event": "PROGRESS",  "task_id": "abc-123", "message": "Typed 'AirPods Pro' into search bar"}
data: {"event": "PROGRESS",  "task_id": "abc-123", "message": "Clicked search button"}
data: {"event": "COMPLETE",  "task_id": "abc-123", "message": "Found price: $249.00", "data": {"price": "$249.00"}}
```

---

## Example Tasks

### 1. Price Comparison
```json
{
  "title": "AirPods Pro price comparison",
  "target_url": "https://www.amazon.com",
  "goal": "Search for 'AirPods Pro 2nd generation' and return all seller prices, ratings, and Prime availability",
  "category": "price_check"
}
```

### 2. Job Search Automation
```json
{
  "title": "ML Engineer jobs",
  "target_url": "https://www.linkedin.com/jobs",
  "goal": "Search for 'Machine Learning Engineer' jobs in New York and return the first 5 results with company names and apply links",
  "category": "job_search"
}
```

### 3. Competitor Monitoring
```json
{
  "title": "OpenAI API pricing",
  "target_url": "https://openai.com/pricing",
  "goal": "Extract the full pricing table including all model names, input price per 1M tokens, and output price per 1M tokens",
  "category": "competitor_monitoring"
}
```

### 4. Product Availability
```json
{
  "title": "PS5 console stock check",
  "target_url": "https://www.bestbuy.com",
  "goal": "Search for 'PlayStation 5 console' and tell me which models are in stock with their current prices",
  "category": "availability_check"
}
```

### 5. Research & News
```json
{
  "title": "Hacker News top stories",
  "target_url": "https://news.ycombinator.com",
  "goal": "Return the top 10 story titles, point counts, and comment counts from the front page",
  "category": "research"
}
```

---

## Docker Deployment

### Start everything with one command:

```bash
# Copy and edit .env first!
copy .env.example .env

# Build and start all containers
docker compose up --build
```

Services started:
- React frontend: http://localhost:3000
- FastAPI backend (Swagger): http://localhost:8000/docs
- PostgreSQL: localhost:5432

### Stop everything:
```bash
docker compose down
```

### Stop and wipe database:
```bash
docker compose down -v
```

---

## Troubleshooting

### "Cannot reach the backend"
- Is `uvicorn main:app --reload` running in the `backend/` folder?
- Check that port 8000 is not blocked by a firewall or used by another app.

### "401 Unauthorized" from TinyFish
- Your API key is wrong or expired. Double-check `.env` → `TINYFISH_API_KEY`.

### "Task stuck on PENDING"
- The SSE stream connects when the frontend navigates to the task.
- Try clicking the task in the History sidebar to manually trigger the stream.

### Frontend shows blank page
- Did `npm install` complete without errors?
- Delete `node_modules` and run `npm install` again.

### Module not found errors in Python
- Make sure your virtual environment is activated (`venv\Scripts\activate`).
- Run `pip install -r requirements.txt` again.

---

## How It Works

```
User submits task
      │
      ▼
POST /api/tasks
  Creates Task (status=PENDING) in SQLite
      │
      ▼
Frontend opens SSE stream
GET /api/tasks/{id}/stream
      │
      ▼
agent_service.execute_task_stream()
  POST https://agent.tinyfish.ai/v1/automation/run-sse
  ← Streams: STARTED, PROGRESS..., COMPLETE
      │
      ▼
Each event saved as TaskLog row
Final result saved as TaskResult row
Task status updated to COMPLETED
      │
      ▼
Frontend EventSource receives events
Updates live log timeline + progress bar
Displays final result card
```

See [architecture.md](architecture.md) for full system diagrams.

---

## License

MIT — free to use, modify, and distribute.
