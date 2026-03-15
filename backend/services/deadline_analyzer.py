"""
deadline_analyzer.py
Analyses deadline feasibility and builds a phase-based schedule.

Uses neurax_employees_dataset and neurax_project_history_dataset for context.
"""

import pandas as pd
from services.groq_client import call_groq_json


def analyze_deadline(
    project: dict,
    tasks: list[dict],
    employees_df: pd.DataFrame,
    history_df: pd.DataFrame,
) -> dict:
    """
    Evaluate whether the project can be delivered within the deadline.

    Args:
        project:       Project dict.
        tasks:         Staffed tasks list.
        employees_df:  neurax_employees_dataset DataFrame.
        history_df:    neurax_project_history_dataset DataFrame.

    Returns:
        {
          "total_estimated_days":    int,
          "effective_estimated_days": int  (parallelism-adjusted),
          "deadline_days":           int,
          "buffer_days":             int   (negative = overrun),
          "feasibility":             "Feasible" | "Tight" | "At Risk" | "Infeasible",
          "risk_factors":            list[str],
          "schedule":                list[{ phase, tasks, start_day, end_day }],
          "recommendations":         list[str]
        }
    """
    total_sequential = sum(t.get("estimated_days", 0) for t in tasks)
    # Parallelism heuristic: 70 % of sequential for a small team
    effective = max(1, int(total_sequential * 0.7))
    deadline  = int(project.get("deadline_days", 30))
    buffer    = deadline - effective

    feasibility = (
        "Feasible"   if buffer >= 10 else
        "Tight"      if buffer >= 0  else
        "At Risk"    if buffer >= -7 else
        "Infeasible"
    )

    avg_workload = employees_df["current_workload_percent"].mean()

    # Parse history for prompt
    history_records = history_df.to_dict(orient="records")
    for r in history_records:
        if isinstance(r.get("tools_used"), str):
            r["tools_used"] = [t.strip() for t in r["tools_used"].split(";")]

    # Build a minimal task summary for the prompt (avoid sending full task objects)
    task_summary = [
        {
            "task_id":        t["task_id"],
            "task_name":      t["task_name"],
            "phase":          t.get("phase", "Development"),
            "estimated_days": t.get("estimated_days", 0),
            "dependencies":   t.get("dependencies", []),
        }
        for t in tasks
    ]

    prompt = f"""
You are a project scheduling expert at Neurax.

PROJECT          : {project['project_name']}
DEADLINE         : {deadline} days
SEQUENTIAL EFFORT: {total_sequential} days
EFFECTIVE EFFORT : {effective} days (parallelism applied)
BUFFER           : {buffer} days
FEASIBILITY      : {feasibility}
TEAM AVG WORKLOAD: {avg_workload:.0f}%

TASKS:
{task_summary}

NEURAX PAST PROJECTS (completion benchmarks):
{history_records}

YOUR TASKS:
1. List 2–4 specific deadline risk factors for this project.
2. Build a phase schedule grouping tasks by their "phase" field.
   Assign start_day and end_day respecting dependencies and parallelism.
   Keep the total schedule within {deadline} days if at all possible.
3. Provide 2–4 actionable recommendations to meet the deadline.

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "risk_factors": ["Risk 1", "Risk 2"],
  "schedule": [
    {{
      "phase": "Planning",
      "tasks": ["T1", "T2"],
      "start_day": 1,
      "end_day": 4
    }}
  ],
  "recommendations": ["Recommendation 1", "Recommendation 2"]
}}
"""
    llm_output = call_groq_json(prompt)

    return {
        "total_estimated_days":     total_sequential,
        "effective_estimated_days": effective,
        "deadline_days":            deadline,
        "buffer_days":              buffer,
        "feasibility":              feasibility,
        "risk_factors":             llm_output.get("risk_factors", []),
        "schedule":                 llm_output.get("schedule", []),
        "recommendations":          llm_output.get("recommendations", []),
    }