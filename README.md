# Neurax AI — Project Management Agent

> Full-Stack AI system powered by **Groq LLM** · FastAPI + React + SQLite

Neurax is an autonomous AI-powered project management platform. Give it a project brief and it will decompose tasks, assign the right employees, recommend tools, analyse deadline feasibility, and flag risks — all in one click.

---

## Features

- **AI Project Analysis** — task decomposition, employee assignment, risk analysis, deadline feasibility
- **Custom Project Submission** — submit any project brief and have it saved + analysed instantly
- **Employee Dashboard** — team profiles, skills, workload bars, task assignments
- **Task Progress Tracking** — employees log in and update progress per task
- **AI Risk Advisor** — project-scoped chat powered by Groq LLM
- **Timeline Simulator** — drag sliders to see how deadline/team size affects feasibility
- **Collaboration Score** — AI rates how well two employees would work together
- **Smart Notifications** — live alerts for infeasible deadlines, skill gaps, overload
- **Analytics** — 6 live charts (priority, feasibility, workload, skills, tools, scores)
- **Project History** — completed projects with success scores and tool usage
- **PDF Reports** — downloadable analysis reports via ReportLab

---

## Project Structure

```
neurax/
├── backend/
│   ├── main.py                        # FastAPI app — all endpoints
│   ├── agents/
│   │   └── workflow.py                # AI pipeline orchestrator
│   ├── services/
│   │   ├── groq_client.py             # Groq LLM wrapper
│   │   ├── task_decomposer.py
│   │   ├── employee_matcher.py
│   │   ├── overload_detector.py
│   │   ├── skill_gap_detector.py
│   │   ├── tool_recommender.py
│   │   └── deadline_analyzer.py
│   ├── datasets/
│   │   ├── neurax_employees_dataset.csv
│   │   ├── neurax_tools_dataset.csv
│   │   ├── neurax_project_history_dataset.csv
│   │   ├── neurax_projects_dataset.csv
│   │   └── neurax.db                  # SQLite DB (auto-created on first run)
│   ├── .env                           # GROQ_API_KEY goes here
│   └── requirements.txt
└── frontend/
    ├── src/
    │   └── App.js                     # Single-file React app
    ├── package.json
    └── vite.config.js
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 1. Clone the repository

```bash
git clone https://github.com/yourname/neurax.git
cd neurax
```

### 2. Set up the backend

```bash
cd backend
pip install -r requirements.txt

# Create your .env file
echo "GROQ_API_KEY=your_key_here" > .env

# Start the server
uvicorn main:app --reload --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`

### 4. Verify everything is working

```bash
# Health check
curl http://localhost:8000/health

# Swagger UI (all endpoints)
http://localhost:8000/docs
```

---

## Environment Variables

Create a `.env` file inside the `backend/` directory:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> The server will **refuse to start** if `GROQ_API_KEY` is missing. Get a free key at [console.groq.com](https://console.groq.com).

---

## Database

Neurax uses **SQLite** (`datasets/neurax.db`) with WAL mode. The database is auto-created on first startup and seeded from the CSV files in `datasets/`.

| Table | Description |
|---|---|
| `projects` | All projects with status tracking |
| `employees` | Employee profiles, skills, workload |
| `tools` | Recommended dev tools catalogue |
| `history` | Completed project records + scores |
| `analyses` | Cached AI analysis results (JSON) |
| `task_progress` | Per-employee task completion tracking |
| `users` | Employee login credentials (SHA-256 hashed) |

---

## Default Credentials

Employee accounts are **auto-created on first startup** from the employees CSV.

| Field | Format | Example |
|---|---|---|
| Username | First name in lowercase | `alice` |
| Password | Employee ID in lowercase | `emp001` |

---

## API Reference

### Projects

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get a single project |
| PATCH | `/api/projects/{id}/status` | Update project status |
| POST | `/api/analyze/{project_id}` | Run AI analysis on an existing project |
| POST | `/api/analyze/custom` | Analyse and save a new custom project |

### Employees & Auth

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/employees` | List all employees |
| GET | `/api/employees/{id}/scorecard` | AI-generated employee scorecard |
| POST | `/api/auth/login` | Employee login |
| PATCH | `/api/auth/change-password` | Change employee password |
| GET | `/api/auth/credentials` | Admin: list all usernames and default passwords |

### Progress & Cache

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/progress` | Save or update task progress |
| GET | `/api/progress/employee/{id}` | All task progress for one employee |
| GET | `/api/progress/project/{id}` | Per-task average progress for a project |
| GET | `/api/progress/all-projects` | Overall completion % for all projects |
| GET | `/api/cache` | All cached analysis results |
| GET | `/api/report/{project_id}` | Download PDF analysis report |

### Intelligence Features

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/collaboration-score` | AI collaboration score for two employees |
| POST | `/api/simulate` | What-if: change deadline or team size |
| POST | `/api/chat/{project_id}` | AI Risk Advisor chat (project-scoped) |
| POST | `/api/assistant` | Global AI assistant (full workspace context) |
| GET | `/api/notifications` | Smart alerts from live project data |

### Dashboard & Analytics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard` | Home page stats and projects list |
| GET | `/api/analytics` | Pre-aggregated chart data (6 charts) |
| GET | `/api/history` | Completed projects with success scores |
| GET | `/api/tools` | Tools catalogue |
| GET | `/health` | Health check |

---

## Frontend Pages

| Page | Description |
|---|---|
| Home | Overview — cached analyses, team workload, recent projects |
| Project Analyser | Select any project and run the full AI pipeline |
| Custom Project | Submit a new project brief — saved to dataset automatically |
| AI Risk Advisor | Project-scoped chat powered by Groq LLM |
| Timeline Simulator | Drag sliders to see how deadline/team changes affect feasibility |
| Analytics | 6 live charts — priority, feasibility, workload, skills, tools, scores |
| Employee Dashboard | Team cards with skills, workload bars, and task assignments |
| Collaboration Score | AI rates how well two employees would work together |
| Notifications | Smart alerts — infeasible deadlines, skill gaps, overload warnings |
| Project History | Completed projects with success scores and tool usage |

---

## Requirements

### Backend — `requirements.txt`

```
fastapi
uvicorn[standard]
python-dotenv
pandas
groq
pydantic
reportlab
```

Install:

```bash
pip install -r requirements.txt

# If reportlab gives issues
pip install reportlab --break-system-packages
```

### Frontend — `package.json`

```
react
react-dom
axios
vite
@vitejs/plugin-react
```

Install:

```bash
npm install
```

---

## Troubleshooting

**Server won't start**
Check that `GROQ_API_KEY` is set correctly in `backend/.env`.

**CORS errors in the browser**
The frontend must run on port `3000` or `5173` — both are whitelisted in `main.py`. If you use a different port, add it to the `allow_origins` list in `main.py`.

**Login fails**
Call `GET /api/auth/credentials` to see all valid usernames and their default passwords.

**No analyses showing on Home page**
Go to the Project Analyser page and run an analysis on any project first.

**PDF download is a `.txt` file**
ReportLab is not installed. Run:
```bash
pip install reportlab --break-system-packages
```

**SQLite database locked**
The database uses WAL mode for concurrent reads. If you see lock errors, restart the server.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq — llama3-70b-8192 |
| Backend | FastAPI, Python 3.10+ |
| Database | SQLite (WAL mode) |
| Frontend | React 18, Vite, Axios |
| Auth | SHA-256 password hashing |
| PDF | ReportLab |

---

*Neurax AI · v4.1.0 · Powered by Groq LLM*
