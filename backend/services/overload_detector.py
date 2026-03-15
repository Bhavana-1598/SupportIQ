"""
overload_detector.py
Detects workload overloads after new task assignments and recommends rebalancing.

Neurax employee columns:
    employee_id | name | role | skills (;) | experience_years | current_workload_percent
"""

import pandas as pd
from services.groq_client import call_groq_json

OVERLOAD_THRESHOLD = 90   # projected % above which an employee is flagged
WORKLOAD_PER_TASK  = 10   # estimated % added per task assignment


def _estimate_additions(tasks: list[dict], name: str) -> int:
    """Return total added workload % for the given employee name."""
    count = sum(
        1 for t in tasks
        if name in t.get("assigned_employees", [])
    )
    return count * WORKLOAD_PER_TASK


def detect_overloads(tasks: list[dict], employees_df: pd.DataFrame) -> dict:
    """
    Project post-assignment workload for every employee and flag overloads.

    Args:
        tasks:         Staffed tasks list (with assigned_employees using names).
        employees_df:  neurax_employees_dataset DataFrame.

    Returns:
        {
          "overloaded_employees": [...],
          "safe_employees":       [...],
          "recommendations":      [...],
          "risk_level":           "Low" | "Medium" | "High"
        }
    """
    projections = []
    for _, row in employees_df.iterrows():
        name    = row["name"]
        current = int(row["current_workload_percent"])
        added   = _estimate_additions(tasks, name)
        projections.append({
            "name":               name,
            "role":               row["role"],
            "current_workload":   current,
            "added_workload":     added,
            "projected_workload": current + added,
        })

    overloaded = [p for p in projections if p["projected_workload"] > OVERLOAD_THRESHOLD]
    safe       = [p for p in projections if p["projected_workload"] <= OVERLOAD_THRESHOLD]

    risk_level = (
        "High"   if len(overloaded) >= 3 else
        "Medium" if len(overloaded) >= 1 else
        "Low"
    )

    if overloaded:
        task_summary = [
            {
                "task_id":            t["task_id"],
                "task_name":          t["task_name"],
                "assigned_employees": t.get("assigned_employees", []),
            }
            for t in tasks
        ]
        prompt = f"""
You are a workforce planning specialist at Neurax.

OVERLOADED EMPLOYEES (projected workload > {OVERLOAD_THRESHOLD}%):
{overloaded}

SAFE / AVAILABLE EMPLOYEES:
{safe}

CURRENT TASK ASSIGNMENTS:
{task_summary}

Provide 2–4 concise rebalancing recommendations.
Suggest specific reassignments from overloaded to safe employees where skills allow.

Respond ONLY with a valid JSON array of recommendation strings.
["Reassign T3 from X to Y who has matching skills and 35% workload.", "..."]
"""
        recommendations = call_groq_json(prompt)
        if not isinstance(recommendations, list):
            recommendations = list(recommendations.values()) if isinstance(recommendations, dict) else []
    else:
        recommendations = [
            "No rebalancing required. All employees are within safe workload limits."
        ]

    return {
        "overloaded_employees": overloaded,
        "safe_employees":       safe,
        "recommendations":      recommendations,
        "risk_level":           risk_level,
    }