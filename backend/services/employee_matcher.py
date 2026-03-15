"""
employee_matcher.py
Matches the best-fit Neurax employees to each task.

Neurax employee columns:
    employee_id | name | role | skills (;-separated) |
    experience_years | current_workload_percent
"""

import pandas as pd
from services.groq_client import call_groq_json

OVERLOAD_THRESHOLD = 85  # % — employees above this are excluded from assignment


def _parse_employees(employees_df: pd.DataFrame) -> list[dict]:
    """Convert the neurax employees DataFrame into a clean list of dicts."""
    result = []
    for _, row in employees_df.iterrows():
        result.append({
            "employee_id":              row["employee_id"],
            "name":                     row["name"],
            "role":                     row["role"],
            "skills":                   [s.strip() for s in str(row["skills"]).split(";")],
            "experience_years":         int(row["experience_years"]),
            "current_workload_percent": int(row["current_workload_percent"]),
        })
    return result


def match_employees(tasks: list[dict], employees_df: pd.DataFrame) -> list[dict]:
    """
    Assign 1–2 employees per task based on skill match, experience, and workload.

    Args:
        tasks:         Task list from task_decomposer (may contain any fields).
        employees_df:  neurax_employees_dataset DataFrame.

    Returns:
        The same tasks list enriched with:
          - "assigned_employees": list of employee names
          - "assignment_reason":  short explanation string
    """
    all_employees  = _parse_employees(employees_df)
    available      = [e for e in all_employees if e["current_workload_percent"] <= OVERLOAD_THRESHOLD]

    prompt = f"""
You are an expert HR staffing analyst at Neurax.

AVAILABLE EMPLOYEES (workload ≤ {OVERLOAD_THRESHOLD}%):
{available}

TASKS TO STAFF:
{tasks}

RULES:
1. Match employees whose skills overlap with each task's required_skills.
2. Consider the employee's role — prefer AI Engineers for ML tasks, etc.
3. Prefer lower current_workload_percent when skills are equal.
4. Prefer more experience_years for complex or high-risk tasks.
5. Assign 1 employee per task; assign 2 only for complex development tasks.
6. Spread work across the team — avoid assigning one person to every task.
7. Use the employee's "name" field (not employee_id) in assigned_employees.
8. Write a 1-sentence assignment_reason.

Respond ONLY with a valid JSON array mirroring the tasks, adding two keys:
  "assigned_employees": ["Name1"]
  "assignment_reason": "..."

No markdown. No explanation. Example response:
[
  {{
    "task_id": "T1",
    "task_name": "...",
    "assigned_employees": ["Aarav Sharma"],
    "assignment_reason": "Aarav's Python and LLM skills directly match this task."
  }}
]
"""
    assignments = call_groq_json(prompt)

    # Normalise if wrapped in a dict
    if isinstance(assignments, dict):
        for key in ("tasks", "assignments", "data"):
            if key in assignments and isinstance(assignments[key], list):
                assignments = assignments[key]
                break

    assignment_map = {a["task_id"]: a for a in assignments}
    for task in tasks:
        match = assignment_map.get(task["task_id"], {})
        task["assigned_employees"] = match.get("assigned_employees", ["Unassigned"])
        task["assignment_reason"]  = match.get("assignment_reason", "")

    return tasks