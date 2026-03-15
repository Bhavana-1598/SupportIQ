"""
groq_client.py
Handles communication with the Groq LLM API for AI-powered analysis.
"""

import os
import json
from groq import Groq


def get_groq_client() -> Groq:
    """Initialize and return a Groq client using the API key from environment."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is not set. "
            "Please export your Groq API key before running."
        )
    return Groq(api_key=api_key)


def call_groq(
    prompt: str,
    system_prompt: str = "You are an expert AI Project Management Agent.",
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    Send a prompt to Groq and return the text response.

    Args:
        prompt:        The user-facing prompt.
        system_prompt: The system instruction for the model.
        model:         Groq model ID to use.
        temperature:   Sampling temperature (lower = more deterministic).
        max_tokens:    Maximum tokens in the response.

    Returns:
        The model's text response as a string.
    """
    client = get_groq_client()

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return chat_completion.choices[0].message.content


def call_groq_json(
    prompt: str,
    system_prompt: str = "You are an expert AI Project Management Agent. Always respond with valid JSON only.",
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict:
    """
    Send a prompt to Groq and parse the response as JSON.

    Args:
        prompt:        The user-facing prompt (should request JSON output).
        system_prompt: System instruction emphasising JSON-only responses.
        model:         Groq model ID to use.
        temperature:   Sampling temperature.
        max_tokens:    Maximum tokens in the response.

    Returns:
        Parsed JSON as a Python dict.

    Raises:
        ValueError: If the response cannot be parsed as JSON.
    """
    raw = call_groq(prompt, system_prompt, model, temperature, max_tokens)

    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop opening fence (```json or ```) and closing fence
        cleaned = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Groq response is not valid JSON.\nRaw response:\n{raw}\nError: {exc}"
        ) from exc