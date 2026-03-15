"""
tool_recommender.py
Recommends tools from neurax_tools_dataset.csv for a given project,
informed by patterns in neurax_project_history_dataset.csv.

Neurax tools columns   : tool_id | tool_name | tool_type | purpose
Neurax history columns : history_id | project_id | project_name | team_size |
                         tools_used (;) | completion_days | success_score
"""

import pandas as pd
from services.groq_client import call_groq_json


def recommend_tools(
    project: dict,
    tools_df: pd.DataFrame,
    history_df: pd.DataFrame,
) -> dict:
    """
    Select 4–7 tools from neurax_tools_dataset.csv that best fit the project.

    Args:
        project:    Project dict (project_name, description, required_skills, …).
        tools_df:   neurax_tools_dataset DataFrame.
        history_df: neurax_project_history_dataset DataFrame.

    Returns:
        {
          "recommended_tools": [
            { tool_name, tool_type, purpose, reason }
          ],
          "similar_projects": [
            { project_name, similarity_reason, success_score, tools_used }
          ],
          "tool_categories": { "Category": ["tool1", "tool2"] }
        }
    """
    tools_list   = tools_df.to_dict(orient="records")
    history_list = history_df.to_dict(orient="records")

    # Parse semicolon tools_used in history for cleaner prompt
    for record in history_list:
        if isinstance(record.get("tools_used"), str):
            record["tools_used"] = [t.strip() for t in record["tools_used"].split(";")]

    prompt = f"""
You are a senior solutions architect at Neurax.

NEW PROJECT:
- Name        : {project['project_name']}
- Description : {project['description']}
- Skills      : {project['required_skills']}
- Deadline    : {project['deadline_days']} days
- Priority    : {project['priority']}

AVAILABLE TOOLS — choose ONLY from this list:
{tools_list}

NEURAX PAST PROJECTS — use for pattern matching:
{history_list}

INSTRUCTIONS:
1. Select 4–7 tools ONLY from the AVAILABLE TOOLS list.
2. Provide a one-sentence reason for each tool selection.
3. Identify 1–3 similar past projects and explain why they are similar.
4. Group selected tools by category (e.g. LLM, Database, Backend, DevOps, AI Framework).

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "recommended_tools": [
    {{
      "tool_name": "OpenAI API",
      "tool_type": "LLM API",
      "purpose": "Natural language reasoning and generation",
      "reason": "Required for the core LLM-powered proposal generation feature."
    }}
  ],
  "similar_projects": [
    {{
      "project_name": "AI Resume Screening",
      "similarity_reason": "Both projects involve NLP-based text analysis with a FastAPI backend.",
      "success_score": 0.89,
      "tools_used": ["Python", "NLP", "FastAPI"]
    }}
  ],
  "tool_categories": {{
    "LLM": ["OpenAI API"],
    "AI Framework": ["LangChain"]
  }}
}}
"""
    return call_groq_json(prompt)