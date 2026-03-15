"""
task_decomposer.py
Decomposes a project into logical tasks using Groq LLM.
Neurax projects use semicolons to separate required_skills.
"""

from services.groq_client import call_groq_json


def decompose_tasks(project: dict) -> list[dict]:
    """
    Break a project into 6–10 actionable tasks.

    Args:
        project: Dict with keys: project_name, description,
                 required_skills (semicolon string), deadline_days, priority

    Returns:
        List of task dicts:
          task_id, task_name, description, required_skills (list),
          estimated_days, dependencies (list of task_ids), phase
    """
    prompt = f"""
You are a senior technical project manager at Neurax, an AI-first company.

PROJECT:
- Name        : {project['project_name']}
- Description : {project['description']}
- Skills      : {project['required_skills']}
- Deadline    : {project['deadline_days']} days
- Priority    : {project['priority']}

Decompose this project into 6–10 well-scoped tasks covering the full lifecycle.
Rules:
  • Each task's estimated_days must be realistic within the {project['deadline_days']}-day deadline.
  • Phases: Planning | Design | Development | Testing | Deployment | Review
  • dependencies lists task_ids that must finish before this task starts.
  • task_ids: T1, T2, T3 …

Respond ONLY with a valid JSON array. No markdown. No explanation.
[
  {{
    "task_id": "T1",
    "task_name": "Requirements Gathering",
    "description": "Define functional and non-functional requirements with stakeholders.",
    "required_skills": ["Project Management"],
    "estimated_days": 3,
    "dependencies": [],
    "phase": "Planning"
  }}
]
"""
    result = call_groq_json(prompt)

    # Normalise: LLM sometimes wraps the array in a dict
    if isinstance(result, dict):
        for key in ("tasks", "task_list", "data", "items"):
            if key in result and isinstance(result[key], list):
                return result[key]
    return result