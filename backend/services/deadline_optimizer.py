def optimize_deadline(tasks, deadline):

    total_days = sum(task["days"] for task in tasks)

    if total_days <= deadline:

        return {
            "estimated_days": total_days,
            "deadline": deadline,
            "risk_level": "LOW",
            "suggestion": "Project timeline is feasible"
        }

    elif total_days <= deadline * 1.2:

        return {
            "estimated_days": total_days,
            "deadline": deadline,
            "risk_level": "MEDIUM",
            "suggestion": "Consider parallel task execution"
        }

    else:

        return {
            "estimated_days": total_days,
            "deadline": deadline,
            "risk_level": "HIGH",
            "suggestion": "Increase team size or extend deadline"
        }