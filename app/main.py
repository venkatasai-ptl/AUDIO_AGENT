import os, io, wave, uuid, json, asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import webrtcvad

# Socket.IO (ASGI)
import socketio

# ---- bring in YOUR logic (copy these files into app/services) ----
from app.services.transcribe import transcribe_audio
from app.services.llm import get_llm_response

# ---------------------- config ----------------------
RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(RATE * FRAME_MS / 1000) * 2  # 960 bytes (16kHz mono s16le)
SILENCE_SEC = 2.0
SAVE_SEGMENTS = True

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
for p in ["recordings", "transcripts", "responses", "prompts", "sessions"]:
    (DATA / p).mkdir(parents=True, exist_ok=True)
(Path(BASE / "segments")).mkdir(exist_ok=True)

# ---------------------- app wiring ----------------------
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
fastapi = FastAPI()
app = socketio.ASGIApp(sio, fastapi)

# Serve worklet and index
fastapi.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")

@fastapi.get("/")
async def index():
    return FileResponse(str(BASE / "app" / "templates" / "index.html"))

# Return latest session for the capture JS to use
@fastapi.get("/active-session")
async def active_session():
    sid = _read_last_session_id()
    if not sid:
        return JSONResponse({"error": "No active session"}, status_code=404)
    return {"session_id": sid}

# ---------------------- helpers ----------------------
vad = webrtcvad.Vad(3)

def _wav_from_pcm16(pcm: bytes, rate=RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()

def _ts_slug(dt: datetime) -> str:
    return dt.strftime("%Y%m%d_%H%M%S")

def _human_from_slug(slug: str) -> str:
    return f"{slug[0:4]}-{slug[4:6]}-{slug[6:8]} {slug[9:11]}:{slug[11:13]}:{slug[13:15]}"

def _ensure_session_dir(session_id: str) -> Path:
    d = DATA / "sessions" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def _chat_file(session_id: str) -> Path:
    return _ensure_session_dir(session_id) / "chat.json"

def _append_chat(session_id: str, ts: str, user_text: str, assistant_text: str):
    f = _chat_file(session_id)
    hist = []
    if f.exists():
        try: hist = json.loads(f.read_text(encoding="utf-8")) or []
        except Exception: hist = []
    hist.append({"timestamp": ts, "user": user_text, "assistant": assistant_text})
    f.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")

def _read_last_session_id() -> str | None:
    p = DATA / "last_session_id.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None

def _write_last_session_id(sid: str):
    (DATA / "last_session_id.txt").write_text(sid, encoding="utf-8")

def _build_messages_text(session_id: str, transcript: str, max_turns: int = 5) -> str:
    d = DATA / "sessions" / session_id
    resume = (d / "resume.txt").read_text(encoding="utf-8") if (d / "resume.txt").exists() else ""
    Projects = (d / "Projects.txt").read_text(encoding="utf-8") if (d / "Projects.txt").exists() else ""
    jd     = (d / "job_description.txt").read_text(encoding="utf-8") if (d / "job_description.txt").exists() else ""
    chat_f = _chat_file(session_id)

    history = []
    if chat_f.exists():
        try: history = json.loads(chat_f.read_text(encoding="utf-8")) or []
        except Exception: history = []

    # last N turns, chronological
    history = sorted(history, key=lambda t: t.get("timestamp",""))[-max_turns:]
    hist_lines = [
        f"- Q: {t.get('user','').strip()}\n  A: {t.get('assistant','').strip()}"
        for t in history if t.get('user') or t.get('assistant')
    ]
    hist_block = "\n".join(hist_lines) if hist_lines else "(none)"

    return f"""[CONTEXT]
RESUME:
{resume}

Projects:
{Projects}

JOB_DESCRIPTION:
{jd}

[CHAT_HISTORY_LAST_{max_turns}_TURNS]
{hist_block}

[NEW_PROMPT]
You are answering the interviewer’s last question based on the transcript below.

TRANSCRIPT:
{transcript}

[OUTPUT_INSTRUCTIONS]
- Speak as me, in first person.
- Be concise and confident. No fluff or hedging. No invented facts.
- Use STAR when helpful; quantify impact if available.
- If details are missing, keep them generic but realistic.
- End with one-line takeaway.
"""

# ---------------------- HTTP endpoints ----------------------
@fastapi.post("/start-session")
async def start_session(req: Request):
    data = await req.json()
    if not data or "resume" not in data or "Projects" not in data or "job_description" not in data:
        return JSONResponse({"error": "Missing resume, Projects or job description"}, status_code=400)

    session_id = uuid.uuid4().hex
    d = _ensure_session_dir(session_id)
    (d / "resume.txt").write_text(data["resume"], encoding="utf-8")
    (d / "Projects.txt").write_text(data["Projects"], encoding="utf-8")
    (d / "job_description.txt").write_text(data["job_description"], encoding="utf-8")
    _write_last_session_id(session_id)
    return {"status": "success", "session_id": session_id, "message": "Session started successfully"}

@fastapi.get("/get_chat_history")
async def get_chat_history(request: Request):
    sid = request.headers.get("X-Session-Id") or _read_last_session_id()
    if not sid:
        return JSONResponse({"error": "No active session"}, status_code=400)
    f = _chat_file(sid)
    hist = []
    if f.exists():
        try: hist = json.loads(f.read_text(encoding="utf-8")) or []
        except Exception: hist = []
    hist.sort(key=lambda t: t.get("timestamp",""), reverse=True)
    return hist

# ---------------------- WebSocket: audio -> VAD -> process ----------------------
@fastapi.websocket("/ws-audio")
async def ws_audio(ws: WebSocket):
    await ws.accept()
    print("[ws-audio] client connected")

    # Initial hello {session_id, sample_rate, frame_ms}
    try:
        hello = json.loads(await ws.receive_text())
        session_id = hello.get("session_id") or _read_last_session_id()
    except Exception:
        session_id = _read_last_session_id()

    if not session_id:
        print("[ws-audio] no session; audio will be ignored until /start-session is called")

    frames, in_speech, silence_ms = [], False, 0.0

    async def finalize_segment():
        nonlocal frames
        if not frames:
            return
        pcm = b"".join(frames)
        frames = []

        wav_bytes = _wav_from_pcm16(pcm)
        now = datetime.now(); slug = _ts_slug(now); uid = uuid.uuid4().hex
        rec_path = DATA / "recordings" / f"{slug}_{uid}.wav"
        rec_path.write_bytes(wav_bytes)

        # 1) transcribe (your function)
        text = await asyncio.to_thread(transcribe_audio, str(rec_path))
        (DATA / "transcripts" / f"{slug}_{uid}.txt").write_text(text, encoding="utf-8")

        # 2) build prompt w/ short history (your format)
        prompt = _build_messages_text(session_id or "", text, max_turns=5)

        # save exact prompt for debugging
        (DATA / "prompts" / f"{slug}_{uid}.json").write_text(
            json.dumps({
                "timestamp": _human_from_slug(slug),
                "session_id": session_id,
                "transcript": text,
                "prompt": prompt
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # 3) stream tokens via Socket.IO and buffer final
        await sio.emit('clear')
        buf = []
        for tok in get_llm_response(prompt, stream=True):
            buf.append(tok)
            await sio.emit('token', {'token': tok})

        full = "".join(buf)
        (DATA / "responses" / f"{slug}_{uid}.txt").write_text(full, encoding="utf-8")
        _append_chat(session_id or "", _human_from_slug(slug), text, full)
        await sio.emit('complete')

    try:
        while True:
            try:
                m = await ws.receive()
            except WebSocketDisconnect:
                break

            t = m.get("type")
            if t == "websocket.disconnect":
                break

            if "bytes" not in m:
                continue

            frame = m["bytes"]
            if len(frame) != FRAME_BYTES:
                continue

            if vad.is_speech(frame, RATE):
                frames.append(frame); in_speech = True; silence_ms = 0.0
            elif in_speech:
                frames.append(frame); silence_ms += FRAME_MS
                if silence_ms >= SILENCE_SEC * 1000:
                    await finalize_segment()
                    in_speech = False; silence_ms = 0.0
    finally:
        try:
            await finalize_segment()
        except Exception as e:
            print("[ws-audio] finalize error:", e)
        print("[ws-audio] client disconnected")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
