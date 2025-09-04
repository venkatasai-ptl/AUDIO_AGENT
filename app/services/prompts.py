# app/services/prompts.py
from pathlib import Path
import json

SYSTEM_TEMPLATE = """You are my voice in a job interview.
Speak in the first person ("I"), in a natural, conversational style — like I am sitting across the table.

If earlier content conflicts with later content, prefer the most recent messages—especially the latest user transcript.

Guidelines:
Length & depth: Give answers with enough substance (2-4 paragraphs).
Don't stop at a headline — explain context, process, decisions, and impact.

When asked "how" or "elaborate": go step-by-step, describing tools, design, trade-offs, and lessons learned.

Variety: Mix results with stories. Sometimes highlight metrics, sometimes highlight teamwork or problem-solving.

STAR: Use Situation, Task, Action, Result when helpful, but keep it conversational.

Honesty: Don't invent fake company names, dates, or facts.

Takeaway: End with a short, natural summary of why it matters.
"""


# new one 
def build_messages_from_db(resume: str, projects: str, job_description: str,
                           history: list[dict], transcript: str, max_turns: int = 5) -> list[dict]:

    ordered = list(reversed(history)) if history else []
    hist = ordered[-max_turns:] 

    messages = [{"role": "system", "content": SYSTEM_TEMPLATE}]
    messages.append({"role": "user", "content":
        f"HERE IS MY RESUME\n{resume or ''}\n\n"
        f"HERE IS MY PROJECTS\n{projects or ''}\n\n"
        f"HERE IS MY JOB_DESCRIPTION\n{job_description or ''}"
    })
    for turn in hist:
        u = (turn.get("user") or "").strip()
        a = (turn.get("assistant") or "").strip()
        if u: messages.append({"role": "user", "content": u})
        if a: messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content":
        "Answer the interviewer’s latest question based on this transcript.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        "[OUTPUT_INSTRUCTIONS]\n"
        "- Speak as me, in first person.\n"
        "- Be concise and confident. No fluff or hedging. No invented facts.\n"
        "- Use STAR when helpful; quantify impact if available.\n"
        "- If details are missing, keep them generic but realistic.\n"
        "- End with one-line takeaway.\n"
    })
    return messages


def messages_snapshot(messages: list[dict]) -> str:
    """Optional: flatten the messages into a readable snapshot string for debugging."""
    lines = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        lines.append(f"[{role}]\n{content}\n")
    return "\n".join(lines)
