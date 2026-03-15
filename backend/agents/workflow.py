"""
workflow_agent.py
Orchestrates all Neurax services to produce a complete project execution plan.

Accepts:
    project  — a single project dict (row from neurax_projects_dataset.csv)
    datasets — dict mapping dataset keys to CSV file paths

Neurax CSV column reference
─────────────────────────────────────────────────────────────
employees : employee_id | name | role | skills (;) |
            experience_years | current_workload_percent
history   : history_id | project_id | project_name | team_size |
            tools_used (;) | completion_days | success_score
projects  : project_id | project_name | description |
            required_skills (;) | deadline_days | priority
tools     : tool_id | tool_name | tool_type | purpose
─────────────────────────────────────────────────────────────
"""

import json
from datetime import datetime, timezone

import pandas as pd

from services.groq_client import call_groq_json
from services.task_decomposer import decompose_tasks
from services.employee_matcher import match_employees
from services.overload_detector import detect_overloads
from services.skill_gap_detector import detect_skill_gaps
from services.tool_recommender import recommend_tools
from services.deadline_analyzer import analyze_deadline


# ──────────────────────────────────────────────
# Dataset loader
# ──────────────────────────────────────────────

def _load(datasets: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all four neurax CSVs and return DataFrames."""
    employees_df = pd.read_csv(datasets["employees"])
    history_df   = pd.read_csv(datasets["history"])
    projects_df  = pd.read_csv(datasets["projects"])   # not used inside agent, passed through
    tools_df     = pd.read_csv(datasets["tools"])
    return employees_df, tools_df, history_df, projects_df


# ──────────────────────────────────────────────
# Project understanding summary (LLM)
# ──────────────────────────────────────────────

def _build_project_summary(project: dict, history_df: pd.DataFrame) -> dict:
    """Generate a structured project understanding summary via Groq."""
    history_records = history_df.to_dict(orient="records")

    prompt = f"""
You are a senior project manager at Neurax, an AI-first software company.

PROJECT:
{json.dumps(project, indent=2)}

PAST NEURAX PROJECTS (for context):
{json.dumps(history_records, indent=2)}

Produce a concise project understanding summary.
Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "objective": "one-sentence goal",
  "key_deliverables": ["deliverable1", "deliverable2"],
  "technical_complexity": "Low | Medium | High",
  "business_impact": "brief statement",
  "critical_constraints": ["constraint1", "constraint2"],
  "recommended_team_size": 3
}}
"""
    return call_groq_json(prompt)


# ──────────────────────────────────────────────
# Execution workflow builder
# ──────────────────────────────────────────────

def _build_execution_workflow(tasks: list[dict]) -> list[dict]:
    """
    Sort tasks by phase order → task_id and attach a sequential step number.
    Returns a clean, ordered workflow list.
    """
    phase_order = {
        "Planning": 1, "Design": 2, "Development": 3,
        "Testing": 4, "Deployment": 5, "Review": 6,
    }

    sorted_tasks = sorted(
        tasks,
        key=lambda t: (
            phase_order.get(t.get("phase", "Development"), 3),
            t.get("task_id", "T99"),
        ),
    )

    return [
        {
            "step":           idx,
            "task_id":        t["task_id"],
            "task_name":      t["task_name"],
            "phase":          t.get("phase", "Development"),
            "assigned_to":    t.get("assigned_employees", []),
            "estimated_days": t.get("estimated_days", 0),
            "dependencies":   t.get("dependencies", []),
            "description":    t.get("description", ""),
        }
        for idx, t in enumerate(sorted_tasks, start=1)
    ]


# ──────────────────────────────────────────────
# Main agent entry point
# ──────────────────────────────────────────────

def run_project_agent(project: dict, datasets: dict[str, str]) -> dict:
    """
    Run the full Neurax AI project planning pipeline.

    Args:
        project:  Row dict from neurax_projects_dataset.csv.
                  Must contain: project_id, project_name, description,
                                required_skills, deadline_days, priority
        datasets: Mapping of dataset keys → CSV file paths.

    Returns:
        Complete execution plan as a nested dict (serialised to JSON by FastAPI).
    """
    employees_df, tools_df, history_df, _ = _load(datasets)

    # Normalise required_skills: always a semicolon string for service prompts
    project = dict(project)  # don't mutate caller's dict
    if isinstance(project.get("required_skills"), list):
        project["required_skills"] = ";".join(project["required_skills"])

    project_name = project.get("project_name", "Unknown")
    print(f"\n{'='*58}")
    print(f"  NEURAX AI AGENT  →  {project_name}")
    print(f"{'='*58}")

    # ── 1. Project Understanding ───────────────
    print("  [1/6] Building project understanding …")
    summary = _build_project_summary(project, history_df)

    # ── 2. Task Decomposition ──────────────────
    print("  [2/6] Decomposing tasks …")
    tasks = decompose_tasks(project)
    print(f"        → {len(tasks)} tasks identified.")

    # ── 3. Tool Recommendation ─────────────────
    print("  [3/6] Recommending tools …")
    tools_result = recommend_tools(project, tools_df, history_df)

    # ── 4. Employee Assignment ─────────────────
    print("  [4/6] Assigning employees …")
    tasks = match_employees(tasks, employees_df)

    # ── 5. Overload & Skill Gap Detection ──────
    print("  [5/6] Running risk analysis …")
    overload_result   = detect_overloads(tasks, employees_df)
    skill_gap_result  = detect_skill_gaps(project, tasks, employees_df)

    # ── 6. Deadline Analysis ───────────────────
    print("  [6/6] Analysing deadline & building schedule …")
    deadline_result = analyze_deadline(project, tasks, employees_df, history_df)

    # ── Ordered Workflow ───────────────────────
    workflow = _build_execution_workflow(tasks)

    print(f"  ✅  Plan complete for '{project_name}'\n")

    # ── Final Plan ─────────────────────────────
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_version": "1.0.0",
        },
        "project": {
            "project_id":       project.get("project_id", ""),
            "project_name":     project.get("project_name", ""),
            "description":      project.get("description", ""),
            "required_skills":  [s.strip() for s in str(project["required_skills"]).split(";")],
            "deadline_days":    project.get("deadline_days"),
            "priority":         project.get("priority", ""),
        },
        "project_understanding":  summary,
        "task_decomposition":     tasks,
        "recommended_tools":      tools_result,
        "employee_assignments": [
            {
                "task_id":            t["task_id"],
                "task_name":          t["task_name"],
                "phase":              t.get("phase", ""),
                "assigned_employees": t.get("assigned_employees", []),
                "assignment_reason":  t.get("assignment_reason", ""),
                "required_skills":    t.get("required_skills", []),
                "estimated_days":     t.get("estimated_days", 0),
                "dependencies":       t.get("dependencies", []),
            }
            for t in tasks
        ],
        "risk_analysis": {
            "overload_analysis":   overload_result,
            "skill_gap_analysis":  skill_gap_result,
        },
        "execution_workflow": {
            "deadline_analysis": deadline_result,
            "ordered_workflow":  workflow,
        },
    }