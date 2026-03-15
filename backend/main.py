"""
main.py  —  Neurax AI Project Management Agent
===============================================
SQLite-backed FastAPI server.

Endpoints called by App.js
─────────────────────────────────────────────────────────────
GET    /health
GET    /api/projects
POST   /api/analyze/custom          ← must come before /{project_id}
POST   /api/analyze/{project_id}
GET    /api/cache
GET    /api/employees
GET    /api/notifications
POST   /api/progress
GET    /api/progress/employee/{employee_id}
GET    /api/progress/project/{project_id}
GET    /api/progress/all-projects
POST   /api/collaboration-score
POST   /api/simulate
POST   /api/auth/login              ← NEW: employee login

Additional endpoints (Swagger UI / admin)
─────────────────────────────────────────────────────────────
GET    /api/projects/{project_id}
GET    /api/employees/{employee_id}/scorecard
GET    /api/history
GET    /api/tools
GET    /api/analytics
GET    /api/dashboard
GET    /api/report/{project_id}      (PDF download)
POST   /api/chat/{project_id}        (AI Risk Advisor)
POST   /api/assistant                (Global chatbot)
PATCH  /api/projects/{project_id}/status
GET    /api/auth/credentials         ← NEW: list all credentials (admin)

Run:   uvicorn main:app --reload --port 8000
Env:   GROQ_API_KEY=your_key   (in backend/.env)
Dep:   pip install reportlab --break-system-packages

Default credentials
─────────────────────────────────────────────────────────────
Username: first name in lowercase  (e.g. "alice")
Password: employee_id in lowercase (e.g. "emp001")
All passwords can be changed via PATCH /api/auth/change-password
"""

import hashlib
import io
import json
import os
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agents.workflow import run_project_agent
from services.groq_client   import call_groq_json


# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

DB_PATH  = "datasets/neurax.db"
CSV_SEEDS = {
    "employees": "datasets/neurax_employees_dataset.csv",
    "history":   "datasets/neurax_project_history_dataset.csv",
    "projects":  "datasets/neurax_projects_dataset.csv",
    "tools":     "datasets/neurax_tools_dataset.csv",
}
DATASETS = CSV_SEEDS


# ─────────────────────────────────────────────────────────────
# Password helpers  (SHA-256, no external deps)
# ─────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Return a hex SHA-256 digest of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


def _make_username(name: str) -> str:
    """
    Derive a default username from an employee's full name.
    e.g.  "Alice Johnson"  →  "alice"
          "Bob Smith"      →  "bob"
    """
    return name.strip().split()[0].lower()


# ─────────────────────────────────────────────────────────────
# SQLite helpers
# ─────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row) -> dict:
    return dict(row)


# ─────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id      TEXT PRIMARY KEY,
    project_name    TEXT NOT NULL,
    description     TEXT,
    required_skills TEXT,
    deadline_days   INTEGER,
    priority        TEXT,
    status          TEXT DEFAULT 'Planning',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id              TEXT PRIMARY KEY,
    name                     TEXT NOT NULL,
    role                     TEXT,
    skills                   TEXT,
    experience_years         INTEGER,
    current_workload_percent INTEGER
);

CREATE TABLE IF NOT EXISTS tools (
    tool_id   TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    tool_type TEXT,
    purpose   TEXT
);

CREATE TABLE IF NOT EXISTS history (
    history_id      TEXT PRIMARY KEY,
    project_id      TEXT,
    project_name    TEXT,
    team_size       INTEGER,
    tools_used      TEXT,
    completion_days INTEGER,
    success_score   REAL
);

CREATE TABLE IF NOT EXISTS analyses (
    project_id  TEXT PRIMARY KEY,
    plan_json   TEXT NOT NULL,
    saved_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_progress (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  TEXT NOT NULL,
    project_id   TEXT NOT NULL,
    task_id      TEXT NOT NULL,
    task_name    TEXT NOT NULL,
    progress_pct INTEGER DEFAULT 0,
    status       TEXT    DEFAULT 'Not Started',
    notes        TEXT    DEFAULT '',
    updated_at   TEXT    DEFAULT (datetime('now')),
    UNIQUE(employee_id, project_id, task_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    employee_id TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
"""


def _init_db():
    os.makedirs("datasets", exist_ok=True)
    with get_db() as conn:
        conn.executescript(_DDL)

        # ── Seed from CSVs (only if tables are empty) ──
        def _empty(t): return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0

        if _empty("projects") and os.path.exists(CSV_SEEDS["projects"]):
            df = pd.read_csv(CSV_SEEDS["projects"])
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR IGNORE INTO projects "
                    "(project_id,project_name,description,required_skills,deadline_days,priority) "
                    "VALUES(?,?,?,?,?,?)",
                    (r["project_id"], r["project_name"], r.get("description",""),
                     r["required_skills"], int(r["deadline_days"]), r["priority"]),
                )
            print(f"  🌱  Seeded projects ({len(df)} rows)")

        if _empty("employees") and os.path.exists(CSV_SEEDS["employees"]):
            df = pd.read_csv(CSV_SEEDS["employees"])
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR IGNORE INTO employees "
                    "(employee_id,name,role,skills,experience_years,current_workload_percent) "
                    "VALUES(?,?,?,?,?,?)",
                    (r["employee_id"], r["name"], r.get("role",""),
                     r["skills"], int(r["experience_years"]), int(r["current_workload_percent"])),
                )
            print(f"  🌱  Seeded employees ({len(df)} rows)")

        if _empty("tools") and os.path.exists(CSV_SEEDS["tools"]):
            df = pd.read_csv(CSV_SEEDS["tools"])
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR IGNORE INTO tools (tool_id,tool_name,tool_type,purpose) VALUES(?,?,?,?)",
                    (r["tool_id"], r["tool_name"], r.get("tool_type",""), r.get("purpose","")),
                )
            print(f"  🌱  Seeded tools ({len(df)} rows)")

        if _empty("history") and os.path.exists(CSV_SEEDS["history"]):
            df = pd.read_csv(CSV_SEEDS["history"])
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT OR IGNORE INTO history "
                    "(history_id,project_id,project_name,team_size,tools_used,completion_days,success_score) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (r["history_id"], r.get("project_id",""), r["project_name"],
                     int(r["team_size"]), r["tools_used"],
                     int(r["completion_days"]), float(r["success_score"])),
                )
            print(f"  🌱  Seeded history ({len(df)} rows)")

        # ── Ensure status column exists on projects ──
        proj_cols = [c[1] for c in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "status" not in proj_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'Planning'")

        # ── Ensure users table exists (safe for existing DBs) ──
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                employee_id   TEXT NOT NULL UNIQUE,
                created_at    TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
            );
        """)

        # ── Seed default credentials for every employee who has no account yet ──
        employees = conn.execute("SELECT employee_id, name FROM employees").fetchall()
        seeded_users = 0
        for emp in employees:
            existing = conn.execute(
                "SELECT user_id FROM users WHERE employee_id=?", (emp["employee_id"],)
            ).fetchone()
            if not existing:
                username = _make_username(emp["name"])
                # Ensure username is unique — append number if collision
                base_username = username
                counter = 1
                while conn.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone():
                    username = f"{base_username}{counter}"
                    counter += 1
                # Default password = employee_id in lowercase
                default_password = str(emp["employee_id"]).lower()
                conn.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash, employee_id) VALUES(?,?,?)",
                    (username, _hash_password(default_password), emp["employee_id"]),
                )
                seeded_users += 1

        if seeded_users:
            print(f"  🔑  Seeded {seeded_users} employee login accounts")
            print(f"      Default: username=<first_name_lowercase>  password=<employee_id_lowercase>")

        total_proj  = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        total_anal  = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    print(f"✅  DB ready — {total_proj} projects, {total_anal} cached analyses, {total_users} user accounts.")


# ─────────────────────────────────────────────────────────────
# Analysis cache helpers
# ─────────────────────────────────────────────────────────────

def _save_analysis(project_id: str, plan: dict) -> None:
    saved_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyses (project_id,plan_json,saved_at) VALUES(?,?,?)",
            (project_id, json.dumps(plan, ensure_ascii=False), saved_at),
        )
    print(f"  💾  Analysis saved for {project_id}")


def _load_all_analyses() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT project_id,plan_json,saved_at FROM analyses ORDER BY saved_at DESC"
        ).fetchall()
    result = []
    for r in rows:
        plan = json.loads(r["plan_json"])
        result.append({
            "project_id":   r["project_id"],
            "project_name": plan.get("project",{}).get("project_name", r["project_id"]),
            "saved_at":     r["saved_at"],
            "plan":         plan,
        })
    return result


def _load_one_analysis(project_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT plan_json,saved_at FROM analyses WHERE project_id=?", (project_id,)
        ).fetchone()
    if not row:
        return None
    plan = json.loads(row["plan_json"])
    return {
        "project_id":   project_id,
        "project_name": plan.get("project",{}).get("project_name", project_id),
        "saved_at":     row["saved_at"],
        "plan":         plan,
    }


# ─────────────────────────────────────────────────────────────
# Project ID helper
# ─────────────────────────────────────────────────────────────

def _next_project_id() -> str:
    with get_db() as conn:
        rows = conn.execute("SELECT project_id FROM projects").fetchall()
    nums = []
    for r in rows:
        m = re.match(r"PRJ(\d+)", str(r["project_id"]).upper())
        if m:
            nums.append(int(m.group(1)))
    return f"PRJ{(max(nums, default=0)+1):03d}"


# ─────────────────────────────────────────────────────────────
# App lifespan
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("GROQ_API_KEY"):
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "  .env file:          GROQ_API_KEY=your_key_here\n"
            "  Windows CMD:        set GROQ_API_KEY=your_key_here\n"
            "  Windows PowerShell: $env:GROQ_API_KEY='your_key_here'\n"
            "  Mac/Linux:          export GROQ_API_KEY=your_key_here"
        )
    _init_db()
    yield


app = FastAPI(
    title="Neurax AI Project Management Agent",
    version="4.1.0",
    description="Full-stack AI agent — SQLite persistence, Groq LLM, employee auth.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:5173",
        "http://127.0.0.1:3000", "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────

class CustomProjectRequest(BaseModel):
    project_name:    str
    description:     str
    required_skills: str   # semicolon-separated
    deadline_days:   int
    priority:        str   # High | Medium | Low


class ProgressUpdate(BaseModel):
    employee_id:  str
    project_id:   str
    task_id:      str
    task_name:    str
    progress_pct: int
    status:       str
    notes:        str = ""


class CollabRequest(BaseModel):
    employee_id_1: str
    employee_id_2: str


class SimulatorRequest(BaseModel):
    project_id:        str
    new_deadline_days: int
    new_team_size:     int


class StatusUpdate(BaseModel):
    status: str


class ChatMessage(BaseModel):
    message: str
    history: list[dict] = []


# ── Auth models ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    username:     str
    old_password: str
    new_password: str


# ─────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health_check():
    with get_db() as conn:
        proj  = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        anal  = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {"status":"ok","version":"4.1.0","total_projects":proj,
            "cached_analyses":anal,"total_users":users}


# ─────────────────────────────────────────────────────────────
# AUTH  — login + credentials management
# ─────────────────────────────────────────────────────────────

@app.post("/api/auth/login", tags=["Auth"])
def employee_login(payload: LoginRequest):
    """
    Authenticate an employee with username + password.
    Returns the full employee record on success so App.js can
    set loggedInEmployee state directly.

    Default credentials (auto-created on first startup):
      username = first name in lowercase   (e.g. "alice")
      password = employee_id in lowercase  (e.g. "emp001")
    """
    if not payload.username.strip() or not payload.password:
        raise HTTPException(status_code=422, detail="Username and password are required.")

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE LOWER(username)=LOWER(?)",
            (payload.username.strip(),)
        ).fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        if not _verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        # Fetch the linked employee record
        emp = conn.execute(
            "SELECT * FROM employees WHERE employee_id=?", (user["employee_id"],)
        ).fetchone()

        if not emp:
            raise HTTPException(status_code=404,
                detail=f"Employee record not found for account '{payload.username}'.")

    emp_dict = row_to_dict(emp)
    emp_dict["skills"] = [s.strip() for s in str(emp_dict.get("skills","")).split(";")]

    print(f"  🔐  Login: {payload.username} → {emp_dict['name']} ({emp_dict['employee_id']})")

    return {
        "success":     True,
        "username":    user["username"],
        "employee_id": emp_dict["employee_id"],
        "employee":    emp_dict,
    }


@app.patch("/api/auth/change-password", tags=["Auth"])
def change_password(payload: ChangePasswordRequest):
    """Allow an employee to change their own password."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE LOWER(username)=LOWER(?)",
            (payload.username.strip(),)
        ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not _verify_password(payload.old_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(payload.new_password) < 4:
        raise HTTPException(status_code=422, detail="New password must be at least 4 characters.")

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE LOWER(username)=LOWER(?)",
            (_hash_password(payload.new_password), payload.username.strip()),
        )

    return {"success": True, "message": "Password updated successfully."}


@app.get("/api/auth/credentials", tags=["Auth"])
def list_credentials():
    """
    Admin endpoint — returns all usernames + employee names.
    Passwords are never returned.
    Useful during development to see what credentials were auto-generated.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.username, u.employee_id, u.created_at,
                      e.name, e.role
               FROM users u
               JOIN employees e ON u.employee_id = e.employee_id
               ORDER BY e.name"""
        ).fetchall()

    return [
        {
            "username":    r["username"],
            "employee_id": r["employee_id"],
            "name":        r["name"],
            "role":        r["role"],
            "default_password": str(r["employee_id"]).lower(),   # shown only here for dev
            "created_at":  r["created_at"],
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────

@app.get("/api/projects", tags=["Projects"])
def get_projects():
    """All projects — used by the Project Analyser selector and Home page."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
    result = []
    for r in rows:
        d = row_to_dict(r)
        d["required_skills"] = [s.strip() for s in str(d.get("required_skills","")).split(";")]
        result.append(d)
    return result


@app.get("/api/projects/{project_id}", tags=["Projects"])
def get_project(project_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE UPPER(project_id)=UPPER(?)", (project_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    d = row_to_dict(row)
    d["required_skills"] = [s.strip() for s in str(d.get("required_skills","")).split(";")]
    return d


@app.patch("/api/projects/{project_id}/status", tags=["Projects"])
def update_status(project_id: str, payload: StatusUpdate):
    valid = {"Planning","In Progress","Completed","On Hold"}
    if payload.status not in valid:
        raise HTTPException(status_code=422, detail=f"Status must be one of {valid}")
    with get_db() as conn:
        row = conn.execute(
            "SELECT project_id FROM projects WHERE UPPER(project_id)=UPPER(?)", (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
        conn.execute(
            "UPDATE projects SET status=? WHERE UPPER(project_id)=UPPER(?)",
            (payload.status, project_id),
        )
    return {"project_id": project_id, "status": payload.status, "updated": True}


# ─────────────────────────────────────────────────────────────
# Employees
# ─────────────────────────────────────────────────────────────

@app.get("/api/employees", tags=["Employees"])
def get_employees():
    """All employees — used by Employee Dashboard and Collaboration Score."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
    result = []
    for r in rows:
        d = row_to_dict(r)
        d["skills"] = [s.strip() for s in str(d.get("skills","")).split(";")]
        result.append(d)
    return result


@app.get("/api/employees/{employee_id}/scorecard", tags=["Employees"])
def get_employee_scorecard(employee_id: str):
    """AI-generated employee scorecard (skill breadth, availability, etc.)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE UPPER(employee_id)=UPPER(?)", (employee_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")

    emp = row_to_dict(row)
    emp["skills"] = [s.strip() for s in str(emp.get("skills","")).split(";")]

    prompt = f"""
You are an HR analytics expert at Neurax.

EMPLOYEE: {json.dumps(emp)}

Rate this employee across 5 dimensions (0-100 each). Respond ONLY with valid JSON:
{{
  "overall_score": 78,
  "overall_label": "Strong Performer",
  "summary": "2-sentence summary",
  "dimensions": {{
    "skill_breadth":      {{"score":80,"note":"..."}},
    "availability":       {{"score":60,"note":"..."}},
    "experience_level":   {{"score":85,"note":"..."}},
    "project_engagement": {{"score":70,"note":"..."}},
    "specialisation":     {{"score":75,"note":"..."}}
  }},
  "strengths": ["strength1","strength2"],
  "development_areas": ["area1","area2"]
}}
"""
    return call_groq_json(prompt)


# ─────────────────────────────────────────────────────────────
# Tools / History
# ─────────────────────────────────────────────────────────────

@app.get("/api/tools", tags=["Tools"])
def get_tools():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tools ORDER BY tool_name").fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/api/history", tags=["History"])
def get_history():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM history ORDER BY success_score DESC").fetchall()
    result = []
    for r in rows:
        d = row_to_dict(r)
        d["tools_used"] = [t.strip() for t in str(d.get("tools_used","")).split(";")]
        result.append(d)
    return result


# ─────────────────────────────────────────────────────────────
# Dashboard + Analytics  (Home page / Analytics page)
# ─────────────────────────────────────────────────────────────

@app.get("/api/dashboard", tags=["Dashboard"])
def get_dashboard():
    """Single call returning all stats + projects list for the Home page."""
    with get_db() as conn:
        proj_rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        emp_rows  = conn.execute("SELECT current_workload_percent FROM employees").fetchall()
        hist_rows = conn.execute("SELECT * FROM history ORDER BY success_score DESC LIMIT 3").fetchall()
        total_emp  = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        total_tool = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
        total_hist = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        total_anal = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]

    avail      = sum(1 for r in emp_rows if r[0] <= 50)
    busy       = sum(1 for r in emp_rows if 50 < r[0] <= 80)
    overloaded = sum(1 for r in emp_rows if r[0] > 80)
    high_pri   = sum(1 for r in proj_rows if str(r["priority"]).lower() == "high")

    all_projects = []
    for r in proj_rows:
        d = row_to_dict(r)
        d["required_skills"] = [s.strip() for s in str(d.get("required_skills","")).split(";")]
        all_projects.append(d)

    top_history = []
    for r in hist_rows:
        d = row_to_dict(r)
        d["tools_used"] = [t.strip() for t in str(d.get("tools_used","")).split(";")]
        top_history.append(d)

    return {
        "total_projects": len(proj_rows), "total_employees": total_emp,
        "total_tools": total_tool,        "total_history": total_hist,
        "cached_analyses": total_anal,
        "available_employees": avail,     "busy_employees": busy,
        "overloaded_employees": overloaded, "high_priority_projects": high_pri,
        "all_projects": all_projects,     "top_history": top_history,
    }


@app.get("/api/analytics", tags=["Analytics"])
def get_analytics():
    """Pre-aggregated data for all six charts on the Analytics page."""
    with get_db() as conn:
        proj_rows = conn.execute("SELECT priority, created_at FROM projects").fetchall()
        emp_rows  = conn.execute("SELECT name, role, skills, current_workload_percent FROM employees").fetchall()
        hist_rows = conn.execute("SELECT project_name, success_score, completion_days, tools_used FROM history").fetchall()
        anal_rows = conn.execute("SELECT plan_json FROM analyses").fetchall()

    pri_counts: dict[str,int] = {"High":0,"Medium":0,"Low":0}
    monthly:    dict[str,int] = {}
    for r in proj_rows:
        p = str(r["priority"] or "Low").strip().capitalize()
        if p not in pri_counts: p = "Low"
        pri_counts[p] += 1
        try:
            month = str(r["created_at"])[:7]
            monthly[month] = monthly.get(month, 0) + 1
        except Exception:
            pass

    workload_dist = [{"name":r["name"],"role":r["role"],"workload":r["current_workload_percent"]}
                     for r in emp_rows]

    skill_counter: dict[str,int] = {}
    for r in emp_rows:
        for s in str(r["skills"]).split(";"):
            s = s.strip()
            if s: skill_counter[s] = skill_counter.get(s,0) + 1

    success_scores = []
    tool_counter: dict[str,int] = {}
    for r in hist_rows:
        success_scores.append({"project_name":r["project_name"],
                                "success_score":round(r["success_score"]*100),
                                "completion_days":r["completion_days"]})
        for t in str(r["tools_used"]).split(";"):
            t = t.strip()
            if t: tool_counter[t] = tool_counter.get(t,0)+1

    feasibility_counts = {"Feasible":0,"Tight":0,"At Risk":0,"Infeasible":0}
    for r in anal_rows:
        try:
            plan = json.loads(r["plan_json"])
            f = plan.get("execution_workflow",{}).get("deadline_analysis",{}).get("feasibility","")
            if f in feasibility_counts: feasibility_counts[f] += 1
        except Exception:
            pass

    return {
        "priority_breakdown":    pri_counts,
        "workload_distribution": workload_dist,
        "success_scores":        success_scores,
        "skill_frequency":       [{"skill":k,"count":v}
                                  for k,v in sorted(skill_counter.items(),key=lambda x:-x[1])[:10]],
        "tool_usage":            [{"tool":k,"count":v}
                                  for k,v in sorted(tool_counter.items(),key=lambda x:-x[1])[:10]],
        "deadline_feasibility":  feasibility_counts,
        "monthly_projects":      dict(sorted(monthly.items())),
    }


# ─────────────────────────────────────────────────────────────
# Analysis cache  — GET /api/cache  (App.js reads this on load)
# ─────────────────────────────────────────────────────────────

@app.get("/api/cache", tags=["Cache"])
def get_all_cached():
    """
    Return all persisted analysis results, newest first.
    App.js calls this on startup to restore the Home page analysed-projects list
    and the active project state.
    """
    return {"count": len(_load_all_analyses()), "analyses": _load_all_analyses()}


# ─────────────────────────────────────────────────────────────
# Task Progress  — used by App.js
# ─────────────────────────────────────────────────────────────

@app.post("/api/progress", tags=["Progress"])
def upsert_progress(payload: ProgressUpdate):
    """Employee saves/updates their task progress."""
    if not 0 <= payload.progress_pct <= 100:
        raise HTTPException(status_code=422, detail="progress_pct must be 0–100.")
    valid_statuses = {"Not Started","In Progress","Completed","Blocked"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid_statuses}")
    with get_db() as conn:
        conn.execute(
            """INSERT INTO task_progress
               (employee_id,project_id,task_id,task_name,progress_pct,status,notes,updated_at)
               VALUES(?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(employee_id,project_id,task_id) DO UPDATE SET
                 progress_pct=excluded.progress_pct, status=excluded.status,
                 notes=excluded.notes, updated_at=excluded.updated_at""",
            (payload.employee_id, payload.project_id, payload.task_id,
             payload.task_name, payload.progress_pct, payload.status, payload.notes),
        )
    return {"saved":True,"task_id":payload.task_id,"progress_pct":payload.progress_pct}


@app.get("/api/progress/employee/{employee_id}", tags=["Progress"])
def get_employee_progress(employee_id: str):
    """All task progress for one employee, grouped by project with overall_pct."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT tp.*, p.project_name FROM task_progress tp
               LEFT JOIN projects p ON tp.project_id=p.project_id
               WHERE UPPER(tp.employee_id)=UPPER(?)
               ORDER BY tp.project_id, tp.task_id""",
            (employee_id,)
        ).fetchall()

    projects: dict[str,dict] = {}
    for r in rows:
        pid = r["project_id"]
        if pid not in projects:
            projects[pid] = {"project_id":pid,"project_name":r["project_name"] or pid,"tasks":[]}
        projects[pid]["tasks"].append({
            "task_id":r["task_id"],"task_name":r["task_name"],
            "progress_pct":r["progress_pct"],"status":r["status"],
            "notes":r["notes"],"updated_at":r["updated_at"],
        })

    result = []
    for proj in projects.values():
        t = proj["tasks"]
        proj["overall_pct"] = round(sum(x["progress_pct"] for x in t)/len(t)) if t else 0
        result.append(proj)
    return {"employee_id":employee_id,"projects":result}


@app.get("/api/progress/project/{project_id}", tags=["Progress"])
def get_project_progress(project_id: str):
    """
    Per-task average progress for a project (averaged across all reporters).
    Used by Project Analyser task list to show % complete per task.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT task_id, task_name,
                      AVG(progress_pct) as avg_progress,
                      COUNT(*) as reporter_count,
                      MAX(updated_at) as last_updated
               FROM task_progress WHERE UPPER(project_id)=UPPER(?)
               GROUP BY task_id, task_name ORDER BY task_id""",
            (project_id,)
        ).fetchall()

    tasks = [{"task_id":r["task_id"],"task_name":r["task_name"],
              "avg_progress":round(r["avg_progress"]),
              "reporter_count":r["reporter_count"],
              "last_updated":r["last_updated"]} for r in rows]
    overall = round(sum(t["avg_progress"] for t in tasks)/len(tasks)) if tasks else 0
    return {"project_id":project_id,"overall_pct":overall,"task_count":len(tasks),"tasks":tasks}


@app.get("/api/progress/all-projects", tags=["Progress"])
def get_all_projects_progress():
    """Overall % for every project that has any progress data."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT tp.project_id, p.project_name,
                      AVG(tp.progress_pct) as overall_pct,
                      COUNT(DISTINCT tp.task_id) as task_count,
                      COUNT(DISTINCT tp.employee_id) as contributor_count
               FROM task_progress tp
               LEFT JOIN projects p ON tp.project_id=p.project_id
               GROUP BY tp.project_id"""
        ).fetchall()
    return [{"project_id":r["project_id"],"project_name":r["project_name"] or r["project_id"],
             "overall_pct":round(r["overall_pct"]),"task_count":r["task_count"],
             "contributor_count":r["contributor_count"]} for r in rows]


# ─────────────────────────────────────────────────────────────
# Agent endpoints
# IMPORTANT: /api/analyze/custom MUST come before /api/analyze/{project_id}
# ─────────────────────────────────────────────────────────────

@app.post("/api/analyze/custom", tags=["Agent"])
def analyze_custom(payload: CustomProjectRequest):
    """
    Run full AI pipeline for a new user-submitted project.
    Saves the project to SQLite with a real PRJxxx ID and caches the analysis.
    Returns the plan + saved_to_dataset flag + assigned_project_id.
    """
    project_id = _next_project_id()
    project = {
        "project_id":      project_id,
        "project_name":    payload.project_name.strip(),
        "description":     payload.description.strip(),
        "required_skills": payload.required_skills.strip(),
        "deadline_days":   payload.deadline_days,
        "priority":        payload.priority.strip(),
    }
    try:
        plan = run_project_agent(project=project, datasets=DATASETS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    saved = False
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO projects "
                "(project_id,project_name,description,required_skills,deadline_days,priority) "
                "VALUES(?,?,?,?,?,?)",
                (project_id, project["project_name"], project["description"],
                 project["required_skills"], project["deadline_days"], project["priority"]),
            )
        saved = True
        print(f"  💾  Saved custom project {project_id}")
    except Exception as exc:
        print(f"  ⚠  Could not save project: {exc}")

    try:
        _save_analysis(project_id, plan)
    except Exception as exc:
        print(f"  ⚠  Could not cache analysis: {exc}")

    if "project" in plan:
        plan["project"]["project_id"] = project_id

    plan["saved_to_dataset"]    = saved
    plan["assigned_project_id"] = project_id
    return plan


@app.post("/api/analyze/{project_id}", tags=["Agent"])
def analyze_project(project_id: str):
    """
    Run full AI pipeline for an existing project from the database.
    Result is cached in the analyses table for instant retrieval on the Home page.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE UPPER(project_id)=UPPER(?)", (project_id,)
        ).fetchone()
    if not row:
        with get_db() as conn:
            ids = [r["project_id"] for r in conn.execute("SELECT project_id FROM projects").fetchall()]
        raise HTTPException(status_code=404,
            detail=f"Project '{project_id}' not found. Available: {ids}")

    project = row_to_dict(row)
    try:
        plan = run_project_agent(project=project, datasets=DATASETS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    try:
        _save_analysis(project_id, plan)
    except Exception as exc:
        print(f"  ⚠  Could not cache analysis: {exc}")

    return plan


# ─────────────────────────────────────────────────────────────
# Collaboration Score  — POST /api/collaboration-score
# ─────────────────────────────────────────────────────────────

@app.post("/api/collaboration-score", tags=["Collaboration"])
def collaboration_score(payload: CollabRequest):
    """Rate how well two employees would collaborate."""
    with get_db() as conn:
        def _get(eid):
            r = conn.execute(
                "SELECT * FROM employees WHERE UPPER(employee_id)=UPPER(?)", (eid,)
            ).fetchone()
            if not r:
                raise HTTPException(status_code=404, detail=f"Employee '{eid}' not found.")
            d = row_to_dict(r)
            d["skills"] = [s.strip() for s in str(d.get("skills","")).split(";")]
            return d
        emp1 = _get(payload.employee_id_1)
        emp2 = _get(payload.employee_id_2)

    prompt = f"""
You are a team dynamics expert at Neurax.

EMPLOYEE 1: {json.dumps(emp1)}
EMPLOYEE 2: {json.dumps(emp2)}

Analyse collaboration potential. Respond ONLY with valid JSON:
{{
  "collaboration_score": 82,
  "compatibility_label": "Highly Compatible",
  "dimensions": {{
    "skill_complementarity": {{"score":90,"note":"..."}},
    "experience_balance":    {{"score":75,"note":"..."}},
    "workload_compatibility":{{"score":85,"note":"..."}},
    "role_synergy":          {{"score":80,"note":"..."}}
  }},
  "shared_skills": ["Python"],
  "complementary_skills": {{"emp1_brings":["LangChain"],"emp2_brings":["RAG","NLP"]}},
  "strengths": ["..."],
  "risks": ["..."],
  "best_project_types": ["NLP chatbots"],
  "summary": "..."
}}
"""
    result = call_groq_json(prompt)
    result["employee_1"] = emp1
    result["employee_2"] = emp2
    return result


# ─────────────────────────────────────────────────────────────
# Timeline Simulator  — POST /api/simulate
# ─────────────────────────────────────────────────────────────

@app.post("/api/simulate", tags=["Simulator"])
def simulate_timeline(payload: SimulatorRequest):
    """
    What-if simulator — instantly recalculate feasibility when deadline or
    team size changes, without re-running the full AI pipeline.
    """
    entry = _load_one_analysis(payload.project_id)
    if not entry:
        raise HTTPException(status_code=404,
            detail=f"No cached analysis for '{payload.project_id}'. Run an analysis first.")

    plan  = entry["plan"]
    proj  = plan.get("project", {})
    dl    = plan.get("execution_workflow",{}).get("deadline_analysis",{})
    tasks = plan.get("task_decomposition", [])
    orig_ov = plan.get("risk_analysis",{}).get("overload_analysis",{})

    orig_deadline    = int(proj.get("deadline_days", 30))
    orig_feasibility = dl.get("feasibility", "Unknown")
    orig_buffer      = dl.get("buffer_days", 0)
    orig_estimated   = dl.get("effective_estimated_days", 0)
    total_seq        = sum(t.get("estimated_days",0) for t in tasks)
    orig_team        = int(plan.get("project_understanding",{}).get("recommended_team_size",3) or 3)

    new_team     = max(1, payload.new_team_size)
    new_deadline = max(1, payload.new_deadline_days)
    para = max(0.40, min(0.90, 0.70 * (1 - 0.05 * max(0, new_team - orig_team))))
    new_estimated = max(1, int(total_seq * para))
    new_buffer    = new_deadline - new_estimated

    def _feas(b):
        if b >= 10: return "Feasible"
        if b >= 0:  return "Tight"
        if b >= -7: return "At Risk"
        return "Infeasible"

    new_feasibility = _feas(new_buffer)
    orig_risk       = orig_ov.get("risk_level","Low")
    new_risk = "Low" if (new_team > orig_team and orig_risk in ("High","Medium")) \
        else "High" if (new_team < orig_team and orig_risk == "Low") else orig_risk

    prompt = f"""
You are a project scheduling expert at Neurax.

ORIGINAL: deadline={orig_deadline}d feasibility={orig_feasibility} buffer={orig_buffer}d
SIMULATED: deadline={new_deadline}d ({new_deadline-orig_deadline:+d}) team={new_team} ({new_team-orig_team:+d})
new_estimated={new_estimated}d new_buffer={new_buffer}d new_feasibility={new_feasibility}
PROJECT: {proj.get('project_name','')}

In 2 sentences explain the impact. Then give 2 recommendations.
Respond ONLY with valid JSON:
{{"impact_summary":"...","recommendations":["rec1","rec2"]}}
"""
    groq = call_groq_json(prompt)

    return {
        "original":  {"deadline_days":orig_deadline,"feasibility":orig_feasibility,
                      "buffer_days":orig_buffer,"estimated_days":orig_estimated,
                      "overload_risk":orig_risk,"team_size":orig_team},
        "simulated": {"deadline_days":new_deadline,"feasibility":new_feasibility,
                      "buffer_days":new_buffer,"estimated_days":new_estimated,
                      "overload_risk":new_risk,"team_size":new_team,
                      "parallelism_pct":round(para*100)},
        "delta":     {"deadline_change":new_deadline-orig_deadline,
                      "team_size_change":new_team-orig_team,
                      "buffer_change":new_buffer-orig_buffer,
                      "feasibility_changed":new_feasibility!=orig_feasibility},
        "impact_summary":  groq.get("impact_summary",""),
        "recommendations": groq.get("recommendations",[]),
    }


# ─────────────────────────────────────────────────────────────
# PDF Report  — GET /api/report/{project_id}
# ─────────────────────────────────────────────────────────────

@app.get("/api/report/{project_id}", tags=["Report"])
def download_report(project_id: str):
    """Stream a PDF analysis report. Falls back to plain text if reportlab missing."""
    entry = _load_one_analysis(project_id)
    if not entry:
        raise HTTPException(status_code=404,
            detail=f"No cached analysis for '{project_id}'. Run an analysis first.")

    plan         = entry["plan"]
    project      = plan.get("project",{})
    understanding= plan.get("project_understanding",{})
    tasks        = plan.get("task_decomposition",[])
    assignments  = plan.get("employee_assignments",[])
    risk         = plan.get("risk_analysis",{})
    deadline     = plan.get("execution_workflow",{}).get("deadline_analysis",{})

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units     import cm
        from reportlab.lib           import colors
        from reportlab.platypus      import (SimpleDocTemplate, Paragraph,
                                              Spacer, Table, TableStyle, HRFlowable)

        buf   = io.BytesIO()
        doc   = SimpleDocTemplate(buf, pagesize=A4,
                                  topMargin=2*cm, bottomMargin=2*cm,
                                  leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()
        AMBER  = colors.HexColor("#d97706")
        DARK   = colors.HexColor("#111827")
        GRAY   = colors.HexColor("#6b7280")

        h1  = ParagraphStyle("H1",  parent=styles["Title"],   textColor=DARK,  fontSize=20, spaceAfter=4)
        h2  = ParagraphStyle("H2",  parent=styles["Heading2"],textColor=AMBER, fontSize=13, spaceBefore=16, spaceAfter=4)
        bod = ParagraphStyle("Bod", parent=styles["Normal"],  fontSize=9,  leading=14, textColor=DARK)
        lbl = ParagraphStyle("Lbl", parent=styles["Normal"],  fontSize=8,  textColor=GRAY, spaceBefore=2)

        story = []
        story.append(Paragraph("Project Analysis Report", h1))
        story.append(Paragraph(f"<b>{project.get('project_name','')}</b>", styles["Heading1"]))
        story.append(Paragraph(
            f"ID: {entry['project_id']}  |  Priority: {project.get('priority','')}  |  "
            f"Deadline: {project.get('deadline_days','')}d  |  Generated: {entry['saved_at'][:19]}",
            lbl))
        story.append(HRFlowable(width="100%", thickness=1, color=AMBER, spaceAfter=10))

        story.append(Paragraph("1. Project Understanding", h2))
        story.append(Paragraph(f"<b>Objective:</b> {understanding.get('objective','')}", bod))
        story.append(Paragraph(
            f"<b>Complexity:</b> {understanding.get('technical_complexity','')}  |  "
            f"<b>Team Size:</b> {understanding.get('recommended_team_size','')}", bod))

        story.append(Paragraph("2. Task Decomposition", h2))
        if tasks:
            td = [["ID","Task","Phase","Days","Deps"]]
            for t in tasks:
                td.append([t.get("task_id",""), Paragraph(t.get("task_name",""),bod),
                           t.get("phase",""), str(t.get("estimated_days","")),
                           ", ".join(t.get("dependencies",[])) or "—"])
            tbl = Table(td, colWidths=[1.2*cm,6.8*cm,2.5*cm,1.3*cm,2.7*cm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),AMBER), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTSIZE",(0,0),(-1,-1),8), ("GRID",(0,0),(-1,-1),.3,colors.lightgrey),
                ("VALIGN",(0,0),(-1,-1),"TOP"), ("PADDING",(0,0),(-1,-1),4),
            ]))
            story.append(tbl)

        story.append(Paragraph("3. Employee Assignments", h2))
        if assignments:
            ad = [["Task","Assigned To","Phase","Days"]]
            for a in assignments:
                ad.append([Paragraph(a.get("task_name",""),bod),
                           ", ".join(a.get("assigned_employees",[])),
                           a.get("phase",""), str(a.get("estimated_days",""))])
            atbl = Table(ad, colWidths=[7*cm,4.5*cm,2.5*cm,1.5*cm])
            atbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),AMBER),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),.3,colors.lightgrey),
                ("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),4),
            ]))
            story.append(atbl)

        story.append(Paragraph("4. Risk Analysis", h2))
        ov = risk.get("overload_analysis",{})
        sg = risk.get("skill_gap_analysis",{})
        story.append(Paragraph(f"<b>Workload Risk:</b> {ov.get('risk_level','')}  |  "
                                f"<b>Skill Gap:</b> {sg.get('gap_severity','')}", bod))
        if sg.get("gap_skills"):
            story.append(Paragraph(f"<b>Missing:</b> {', '.join(sg['gap_skills'])}", bod))

        story.append(Paragraph("5. Deadline", h2))
        story.append(Paragraph(
            f"<b>Feasibility:</b> {deadline.get('feasibility','')}  |  "
            f"<b>Estimated:</b> {deadline.get('effective_estimated_days','')}d  |  "
            f"<b>Buffer:</b> {deadline.get('buffer_days','')}d", bod))

        story.append(Spacer(1,16))
        story.append(HRFlowable(width="100%", thickness=.5, color=GRAY))
        story.append(Paragraph("Generated by Neurax AI · Powered by Groq LLM", lbl))

        doc.build(story)
        raw = buf.getvalue()

    except ImportError:
        lines = [
            "NEURAX AI ANALYSIS REPORT",
            f"Project: {project.get('project_name','')} ({entry['project_id']})",
            f"Generated: {entry['saved_at']}",
            f"Feasibility: {deadline.get('feasibility','')}",
        ]
        for t in tasks:
            lines.append(f"  [{t.get('task_id','')}] {t.get('task_name','')} ~{t.get('estimated_days','')}d")
        raw = "\n".join(lines).encode()

    is_pdf   = raw[:4] == b"%PDF"
    media    = "application/pdf" if is_pdf else "text/plain"
    filename = f"neurax_report_{project_id}" + (".pdf" if is_pdf else ".txt")
    return StreamingResponse(io.BytesIO(raw), media_type=media,
                             headers={"Content-Disposition":f"attachment; filename={filename}"})


# ─────────────────────────────────────────────────────────────
# AI Risk Advisor Chat  — POST /api/chat/{project_id}
# ─────────────────────────────────────────────────────────────

@app.post("/api/chat/{project_id}", tags=["AI Advisor"])
def chat_with_advisor(project_id: str, payload: ChatMessage):
    """Project-scoped AI chat. Full analysis plan injected as context."""
    from groq import Groq as _Groq
    client = _Groq(api_key=os.environ["GROQ_API_KEY"])

    entry = _load_one_analysis(project_id)
    if entry:
        plan = entry["plan"]
        ctx  = f"""
PROJECT: {json.dumps(plan.get('project',{}),indent=2)}
UNDERSTANDING: {json.dumps(plan.get('project_understanding',{}),indent=2)}
TASKS ({len(plan.get('task_decomposition',[]))}): {json.dumps(plan.get('task_decomposition',[]),indent=2)}
ASSIGNMENTS: {json.dumps(plan.get('employee_assignments',[]),indent=2)}
RISKS: {json.dumps(plan.get('risk_analysis',{}),indent=2)}
DEADLINE: {json.dumps(plan.get('execution_workflow',{}).get('deadline_analysis',{}),indent=2)}
"""
    else:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE UPPER(project_id)=UPPER(?)", (project_id,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
        ctx = f"Project: {row_to_dict(row)}\nNo analysis has been run yet."

    system = (f"You are Neurax, an expert AI project management advisor.\n"
              f"Answer questions about this project using only the data below. "
              f"Be specific. Never hallucinate.\n\n{ctx}")

    msgs = [{"role":"system","content":system}]
    for t in payload.history[-10:]:
        msgs.append({"role":t["role"],"content":t["content"]})
    msgs.append({"role":"user","content":payload.message})

    resp = client.chat.completions.create(
        model="llama3-70b-8192", messages=msgs, temperature=0.4, max_tokens=1024
    )
    return {"reply":resp.choices[0].message.content,"project_id":project_id}


# ─────────────────────────────────────────────────────────────
# Global Assistant  — POST /api/assistant
# ─────────────────────────────────────────────────────────────

@app.post("/api/assistant", tags=["Global Assistant"])
def global_assistant(payload: ChatMessage):
    """Floating chatbot with full workspace context."""
    from groq import Groq as _Groq
    client = _Groq(api_key=os.environ["GROQ_API_KEY"])

    with get_db() as conn:
        projects  = [row_to_dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]
        employees = [row_to_dict(r) for r in conn.execute("SELECT * FROM employees").fetchall()]
        history   = [row_to_dict(r) for r in conn.execute("SELECT * FROM history").fetchall()]
        analyses  = conn.execute("SELECT project_id, plan_json FROM analyses").fetchall()

    for e in employees:
        e["skills"] = [s.strip() for s in str(e.get("skills","")).split(";")]
    for p in projects:
        p["required_skills"] = [s.strip() for s in str(p.get("required_skills","")).split(";")]

    summaries = []
    for row in analyses:
        try:
            plan = json.loads(row["plan_json"])
            dl   = plan.get("execution_workflow",{}).get("deadline_analysis",{})
            ov   = plan.get("risk_analysis",{}).get("overload_analysis",{})
            sg   = plan.get("risk_analysis",{}).get("skill_gap_analysis",{})
            summaries.append({
                "project_id":   row["project_id"],
                "project_name": plan.get("project",{}).get("project_name",""),
                "feasibility":  dl.get("feasibility",""),
                "buffer_days":  dl.get("buffer_days",0),
                "overload_risk":ov.get("risk_level",""),
                "skill_gap":    sg.get("gap_severity",""),
                "task_count":   len(plan.get("task_decomposition",[])),
            })
        except Exception:
            continue

    system = f"""You are the Neurax Global Assistant with full workspace visibility.

PROJECTS ({len(projects)}): {json.dumps(projects)}
EMPLOYEES ({len(employees)}): {json.dumps(employees)}
ANALYSIS SUMMARIES ({len(summaries)}): {json.dumps(summaries)}
HISTORY ({len(history)}): {json.dumps(history)}

Be specific, reference real names/IDs, keep answers concise (3–8 sentences).
Never make up data not in the context."""

    msgs = [{"role":"system","content":system}]
    for t in payload.history[-8:]:
        msgs.append({"role":t["role"],"content":t["content"]})
    msgs.append({"role":"user","content":payload.message})

    resp = client.chat.completions.create(
        model="llama3-70b-8192", messages=msgs, temperature=0.35, max_tokens=800
    )
    return {"reply": resp.choices[0].message.content}


# ─────────────────────────────────────────────────────────────
# Notifications  — GET /api/notifications
# ─────────────────────────────────────────────────────────────

@app.get("/api/notifications", tags=["Notifications"])
def get_notifications():
    """Scan live data and return contextual alerts sorted by severity."""
    notifications = []
    nid = 1

    with get_db() as conn:
        employees = conn.execute("SELECT * FROM employees").fetchall()
        analyses  = conn.execute("SELECT project_id, plan_json FROM analyses").fetchall()

    for row in analyses:
        try:
            plan      = json.loads(row["plan_json"])
            proj      = plan.get("project", {})
            dl        = plan.get("execution_workflow", {}).get("deadline_analysis", {})
            feasibility  = dl.get("feasibility", "")
            buffer_days  = dl.get("buffer_days", 99)
            proj_name    = proj.get("project_name", row["project_id"])

            if feasibility == "Infeasible":
                notifications.append({"id":nid,"type":"infeasible_alert","severity":"critical",
                    "title":f"Infeasible Deadline — {proj_name}",
                    "message":f"Overrun by {abs(buffer_days)} days. Immediate rescoping required.",
                    "project_id":row["project_id"]}); nid += 1

            elif feasibility in ("At Risk","Tight") or (isinstance(buffer_days,(int,float)) and 0<=buffer_days<=5):
                notifications.append({"id":nid,"type":"deadline_warning","severity":"high",
                    "title":f"Tight Deadline — {proj_name}",
                    "message":f"Only {buffer_days} days of buffer remaining.",
                    "project_id":row["project_id"]}); nid += 1

            sg = plan.get("risk_analysis",{}).get("skill_gap_analysis",{})
            if sg.get("gap_skills"):
                notifications.append({"id":nid,"type":"skill_gap_alert","severity":"medium",
                    "title":f"Skill Gap — {proj_name}",
                    "message":f"Missing: {', '.join(sg['gap_skills'][:3])}.",
                    "project_id":row["project_id"]}); nid += 1

            ov = plan.get("risk_analysis",{}).get("overload_analysis",{})
            for emp in ov.get("overloaded_employees",[]):
                notifications.append({"id":nid,"type":"overload_warning","severity":"high",
                    "title":f"Overload Risk — {emp.get('name','')}",
                    "message":f"Projected {emp.get('projected_workload','')}% on {proj_name}.",
                    "project_id":row["project_id"],
                    "employee":emp.get("name","")}); nid += 1
        except Exception:
            continue

    for emp in employees:
        if emp["current_workload_percent"] < 20:
            notifications.append({"id":nid,"type":"idle_alert","severity":"low",
                "title":f"Underutilised — {emp['name']}",
                "message":f"{emp['name']} is at {emp['current_workload_percent']}% workload.",
                "employee_id":emp["employee_id"],"employee":emp["name"]}); nid += 1

    order = {"critical":0,"high":1,"medium":2,"low":3}
    notifications.sort(key=lambda n: order.get(n["severity"],9))
    return {
        "count":    len(notifications),
        "critical": sum(1 for n in notifications if n["severity"]=="critical"),
        "high":     sum(1 for n in notifications if n["severity"]=="high"),
        "notifications": notifications,
    }