"""
skill_gap_detector.py
Detects skills required by the project that no available employee can cover.

Neurax employee columns:
    employee_id | name | role | skills (;) | experience_years | current_workload_percent
Neurax project column:
    required_skills — semicolon-separated string
"""

import pandas as pd
from services.groq_client import call_groq_json

AVAILABLE_WORKLOAD_THRESHOLD = 85  # % — employees above this aren't considered "available"


def detect_skill_gaps(
    project: dict,
    tasks: list[dict],
    employees_df: pd.DataFrame,
) -> dict:
    """
    Compare all required skills against the neurax employee skill pool.

    Args:
        project:       Project dict (required_skills as semicolon string or list).
        tasks:         Decomposed tasks list (each has required_skills list).
        employees_df:  neurax_employees_dataset DataFrame.

    Returns:
        {
          "required_skills":  sorted list,
          "covered_skills":   sorted list,
          "gap_skills":       sorted list — no employee has these,
          "partial_gaps":     sorted list — skill exists but only overloaded employees have it,
          "recommendations":  list of strings,
          "gap_severity":     "None" | "Low" | "Medium" | "High"
        }
    """
    # ── Collect all required skills ──
    raw_project_skills = project.get("required_skills", "")
    if isinstance(raw_project_skills, list):
        project_skills = {s.strip() for s in raw_project_skills}
    else:
        project_skills = {s.strip() for s in str(raw_project_skills).split(";")}

    task_skills: set[str] = set()
    for t in tasks:
        for s in t.get("required_skills", []):
            task_skills.add(s.strip())

    all_required = project_skills | task_skills

    # ── Build employee skill pools ──
    all_pool: set[str]       = set()  # every skill in the company
    available_pool: set[str] = set()  # skills held by non-overloaded employees

    for _, row in employees_df.iterrows():
        skills  = {s.strip() for s in str(row["skills"]).split(";")}
        workload = int(row["current_workload_percent"])
        all_pool |= skills
        if workload <= AVAILABLE_WORKLOAD_THRESHOLD:
            available_pool |= skills

    def _match(skill: str, pool: set[str]) -> bool:
        return any(skill.lower() == s.lower() for s in pool)

    gap_skills    = sorted(s for s in all_required if not _match(s, all_pool))
    partial_gaps  = sorted(
        s for s in all_required
        if _match(s, all_pool) and not _match(s, available_pool)
    )
    covered_skills = sorted(s for s in all_required if s not in gap_skills)

    # ── Severity ──
    n_gaps = len(gap_skills)
    gap_severity = (
        "None"   if n_gaps == 0 else
        "Low"    if n_gaps <= 2 else
        "Medium" if n_gaps <= 4 else
        "High"
    )

    # ── LLM recommendations ──
    if gap_skills or partial_gaps:
        prompt = f"""
You are a talent acquisition specialist at Neurax.

PROJECT: {project.get('project_name', '')}

SKILL GAPS (no Neurax employee has these):
{gap_skills}

PARTIAL GAPS (skill exists but only in overloaded employees):
{partial_gaps}

Provide 3–5 actionable recommendations to address these gaps.
Consider: hiring, freelancers, training, outsourcing, or scope adjustment.

Respond ONLY with a valid JSON array of recommendation strings.
["Hire a contract NLP specialist for the 30-day engagement.", "..."]
"""
        recommendations = call_groq_json(prompt)
        if not isinstance(recommendations, list):
            recommendations = []
    else:
        recommendations = [
            "No skill gaps detected. The current Neurax team fully covers all required skills."
        ]

    return {
        "required_skills":  sorted(all_required),
        "covered_skills":   covered_skills,
        "gap_skills":       gap_skills,
        "partial_gaps":     partial_gaps,
        "recommendations":  recommendations,
        "gap_severity":     gap_severity,
    }