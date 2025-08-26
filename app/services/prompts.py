# app/services/prompts.py
from pathlib import Path
import json

INTERVIEW_SYSTEM_TEMPLATE = """You are my voice in a job interview.
Speak in the first person ("I"), in a natural, conversational style — like I am sitting across the table.

Guidelines:
Length & depth: Give answers with enough substance (2–4 paragraphs).
Don’t stop at a headline — explain context, process, decisions, and impact.

When asked "how" or "elaborate": go step-by-step, describing tools, design, trade-offs, and lessons learned.

Variety: Mix results with stories. Sometimes highlight metrics, sometimes highlight teamwork or problem-solving.

STAR: Use Situation, Task, Action, Result when helpful, but keep it conversational.

Honesty: Don’t invent fake company names, dates, or facts.

Takeaway: End with a short, natural summary of why it matters.
"""

def build_messages(session_id: str, transcript: str, data_dir: Path, max_turns: int = 5) -> list[dict]:
    """Builds chat messages with cache flags for stable parts (system/resume/JD)."""
    d = data_dir / "sessions" / session_id

    def _safe_read(p: Path) -> str:
        return p.read_text(encoding="utf-8") if p.exists() else ""

    resume   = _safe_read(d / "resume.txt")
    projects = _safe_read(d / "Projects.txt")
    jd       = _safe_read(d / "job_description.txt")

    # Read last N turns from chat.json if present
    hist = []
    chat_f = d / "chat.json"
    if chat_f.exists():
        try:
            hist = json.loads(chat_f.read_text(encoding="utf-8")) or []
        except Exception:
            hist = []
    hist = sorted(hist, key=lambda t: t.get("timestamp", ""))[-max_turns:]
    hist_lines = [
        f"- Q: {t.get('user','').strip()}\n  A: {t.get('assistant','').strip()}"
        for t in hist if t.get('user') or t.get('assistant')
    ]
    hist_block = "\n".join(hist_lines) if hist_lines else "(none)"

    return [
        {
            "role": "system",
            "content": INTERVIEW_SYSTEM_TEMPLATE,
            "cache_control": {"type": "ephemeral"}  # cached
        },
        {
            "role": "system",
            "content": f"[RESUME]\n{resume}\n\n[PROJECTS]\n{projects}\n\n[JOB_DESCRIPTION]\n{jd}",
            "cache_control": {"type": "ephemeral"}  # cached
        },
        {
            "role": "system",
            "content": f"[CHAT_HISTORY_LAST_{max_turns}_TURNS]\n{hist_block}"
        },
        {
            "role": "user",
            "content": (
                "You are answering the interviewer’s last question based on the transcript below.\n\n"
                f"TRANSCRIPT:\n{transcript}\n\n"
                "[OUTPUT_INSTRUCTIONS]\n"
                "- Speak as me, in first person.\n"
                "- Be concise and confident. No fluff or hedging. No invented facts.\n"
                "- Use STAR when helpful; quantify impact if available.\n"
                "- If details are missing, keep them generic but realistic.\n"
                "- End with one-line takeaway.\n"
            )
        }
    ]


def messages_snapshot(messages: list[dict]) -> str:
    """Optional: flatten the messages into a readable snapshot string for debugging."""
    lines = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        lines.append(f"[{role}]\n{content}\n")
    return "\n".join(lines)
