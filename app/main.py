import os, io, wave, uuid, json, asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from urllib.parse import parse_qs
import sqlalchemy as sa
import uvicorn
import webrtcvad

# Socket.IO (ASGI)
import socketio

# ---- bring in YOUR logic (copy these files into app/services) ----
from app.services.transcribe import transcribe_audio
from app.services.prompts import  messages_snapshot, build_messages_from_db
from app.services.llm import get_llm_response
from app.services.db import SessionLocal, engine, Base
from app.services.auth import hash_password, verify_password, create_access_token, decode_token
from app.services import models
from app.services.models import User as DBUser

# Create tables automatically at startup
Base.metadata.create_all(bind=engine)


# ---------------------- config ----------------------
RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(RATE * FRAME_MS / 1000) * 2  # 960 bytes (16kHz mono s16le)
SILENCE_SEC = 2.5
MIN_TEXT_CHARS = 5          # drop text shorter than this
MIN_TEXT_TOKENS = 2          # also require at least 2 tokens/words
SAVE_SEGMENTS = True
FILLER_PHRASES = {
    # Short fillers & interjections
    "um", "uh", "hmm", "mm", "er", "ah", "eh", "huh",
    "hmmm", "hmm..", "hmm...", "hmmm...", "hmm.", "hmm...",
    
    # Common Whisper hallucinations / YouTube-style phrases
    "thanks for watching",
    " Thanks for Watching ",
    "Thank you for watching.",
    "Thank you for watching!",
    "Thanks for watching!",
    "Thank you. Good.",
    "Thanks for watching. Bye.",
    "I'll see you in the next video.",
    "Thank you very much.",
    "please like",
    "please like share",
    "please like share subscribe",
    "like share subscribe",
    "subscribe to my channel",
    "see you in the next video",
    "see you next time",
    "check out my other videos",
    "don't forget to like",
    "don't forget to subscribe",
    "hit the bell icon",
    "smash that like button",
    "follow for more",
    "follow me for more",
    "share and subscribe",
    "and subscribe",
    "watch my other videos",
    "watch next video",
    "watch next"
}



BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
for p in ["recordings", "transcripts", "responses", "prompts", "sessions"]:
    (DATA / p).mkdir(parents=True, exist_ok=True)
(Path(BASE / "segments")).mkdir(exist_ok=True)

print("Loaded main from:", __file__)

# ---------------------- app wiring ----------------------
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
fastapi = FastAPI()
app = socketio.ASGIApp(sio, fastapi)

# Serve worklet and index
fastapi.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")

@fastapi.get("/")
async def root():
# Optional: redirect root to login or app if token cookie is present (front-end handles token in localStorage)
   return RedirectResponse(url="/login")


@fastapi.get("/register")
async def register_page():
   return FileResponse(str(BASE / "app" / "templates" / "register.html"))


@fastapi.get("/login")
async def login_page():
   return FileResponse(str(BASE / "app" / "templates" / "login.html"))


@fastapi.get("/app")
async def app_page():
   return FileResponse(str(BASE / "app" / "templates" / "app.html"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def save_turn_db(db: Session, *, user_id, session_id, user_text, assistant_text, tokens=0, meta=None):
    row = models.Transcript(
        user_id=user_id,
        session_id=session_id,
        text=user_text,
        assistant_text=assistant_text,
        tokens=tokens or 0,
        meta=meta or {}
    )
    db.add(row)
    db.commit()
    return row

def list_history_db(db: Session, *, user_id, session_id):
    q = (
        db.query(models.Transcript)
        .filter(models.Transcript.user_id == user_id, models.Transcript.session_id == session_id)
        .order_by(models.Transcript.created_at.desc())
    )
    rows = q.all()
    return [
        {
            "timestamp": r.created_at.isoformat(),
            "user": r.text or "",
            "assistant": r.assistant_text or "",
            "id": str(r.id),
        }
        for r in rows
    ]

# ---------- Auth: routes ----------
@fastapi.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    u = models.User(email=email, password_hash=hash_password(payload.password))
    db.add(u); db.commit()
    return {"ok": True}

@fastapi.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    u = db.query(models.User).filter(models.User.email == email).first()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(u.id))
    return TokenOut(access_token=token)

# ---------- Auth: current user dependency ----------
security = HTTPBearer(auto_error=False)

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Missing credentials")
    data = decode_token(creds.credentials)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid/expired token")
    uid = data.get("sub")
    u = db.get(models.User, uid)
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return u

# ---------- Test route to verify auth works ----------
@fastapi.get("/me")
def me(user = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email}

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


def _load_profile_and_history(user_id: str | None, session_id: str | None):
    """Fetch resume/projects/JD and the short chat history for this session."""
    resume = projects = jd = ""
    history = []
    if not user_id:
        return resume, projects, jd, history

    db: Session = SessionLocal()
    try:
        prof = db.get(models.UserProfile, user_id)
        if prof:
            resume   = prof.resume or ""
            projects = prof.projects or ""
            jd       = prof.job_description or ""
        if session_id:
            history = list_history_db(db, user_id=user_id, session_id=session_id)
    finally:
        try: db.close()
        except Exception: pass
    return resume, projects, jd, history


# app/main.py
@fastapi.put("/profile")
def upsert_profile(payload: dict,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    resume = (payload.get("resume") or "").strip()
    projects = (payload.get("Projects") or "").strip()
    jd = (payload.get("job_description") or "").strip()

    row = db.get(models.UserProfile, user.id)
    if row:
        row.resume, row.projects, row.job_description = resume, projects, jd
    else:
        row = models.UserProfile(user_id=user.id, resume=resume, projects=projects, job_description=jd)
        db.add(row)
    db.commit()
    return {"ok": True}

@fastapi.get("/profile")
def get_profile(db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    row = db.get(models.UserProfile, user.id)
    return {
        "resume": row.resume if row else "",
        "Projects": row.projects if row else "",
        "job_description": row.job_description if row else ""
    }

@fastapi.post("/start-chat")
def start_chat(db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    # Just mint a fresh session_id and return it; no disk writes.
    session_id = uuid.uuid4().hex
    return {"session_id": session_id}


@fastapi.get("/get_chat_history")
def get_chat_history(request: Request,
                     db: Session = Depends(lambda: SessionLocal()),
                     user: models.User = Depends(get_current_user)):
    sid = request.headers.get("X-Session-Id") #or _read_last_session_id()
    if not sid:
        return JSONResponse({"error": "No active session"}, status_code=400)

    rows = (
        db.query(models.Transcript)
          .filter(models.Transcript.user_id == user.id,
                  models.Transcript.session_id == sid)
          .order_by(models.Transcript.created_at.desc())
          .all()
    )

    return [
        {
            "id": str(r.id),
            "timestamp": r.created_at.isoformat(),
            "user": r.text or "",
            "assistant": r.assistant_text or "",
        }
        for r in rows
    ]

@fastapi.get("/history/sessions")
def list_user_sessions(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return all distinct session IDs for this user, newest activity first."""
    rows = (
        db.query(
            models.Transcript.session_id.label("session_id"),
            sa.func.max(models.Transcript.created_at).label("last_created"),
        )
        .filter(
            models.Transcript.user_id == user.id,
            models.Transcript.session_id.isnot(None),
            models.Transcript.session_id != "",
        )
        .group_by(models.Transcript.session_id)
        .order_by(sa.desc(sa.func.max(models.Transcript.created_at)))
        .all()
    )
    return {
        "sessions": [
            {
                "session_id": r.session_id,
                "last_created": r.last_created.isoformat() if r.last_created else None,
            }
            for r in rows
        ]
    }


@fastapi.get("/history/transcripts")
def transcripts_for_session(
    session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return all messages for the selected session, oldest → newest."""
    rows = (
        db.query(models.Transcript)
        .filter(
            models.Transcript.user_id == user.id,
            models.Transcript.session_id == session_id,
        )
        .order_by(models.Transcript.created_at.asc(), models.Transcript.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": str(r.id),
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "text": r.text or "",
                "assistant_text": r.assistant_text or "",
                "meta": r.meta or {},
            }
            for r in rows
        ],
    }


# ---------------------- WebSocket: audio -> VAD -> process ----------------------
@fastapi.websocket("/ws-audio")
async def ws_audio(ws: WebSocket):
    await ws.accept()
    print("[ws-audio] client connected")

    try:
        qs = parse_qs(ws.url.query or "")
        token = (qs.get("token") or [None])[0]
        claims = decode_token(token or "")
        user_id = claims.get("sub") if claims else None
    except Exception:
        user_id = None

    # Initial hello {session_id, sample_rate, frame_ms}
    try:
        hello = json.loads(await ws.receive_text())
        session_id = hello.get("session_id") #or _read_last_session_id()
    except Exception:
        session_id = None #_read_last_session_id()

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


        # 1) transcribe (your function)
        text = await asyncio.to_thread(transcribe_audio, wav_bytes)

        # --- POST-TRANSCRIPTION GUARD: drop fillers, hallucinations, and empty outputs ---
        clean = (text or "").strip()

        # Tokenize roughly
        tokens = [t for t in clean.replace(",", " ").split() if t]

        # Check 1: Empty or whitespace-only transcript
        if not clean:
            return

        # Check 2: Too short (very likely meaningless)
        if len(tokens) < 2 or len(clean) < 12:
            return

        # Check 3: Filler / hallucination phrases (match anywhere in text)
        if clean in FILLER_PHRASES:
                return 


        resume, projects, jd, history = _load_profile_and_history(user_id, session_id)
        # 2) build prompt w/ short history (your format)
        messages = build_messages_from_db(resume=resume, projects=projects, job_description=jd, history=history, transcript=text, max_turns=5)

  
        # 3) stream tokens via Socket.IO and buffer final
        await sio.emit('clear')
        buf = []
        for tok in get_llm_response(messages, stream=True):
            buf.append(tok)
            await sio.emit('token', {'token': tok})

        full = "".join(buf)

        if user_id:
            try:
                db: Session = SessionLocal()
                # If you already defined save_turn_db in Step 3, use it:
                try:
                    # save_turn_db(db, *, user_id, session_id, user_text, assistant_text, tokens=0, meta=None)
                
                    save_turn_db(
                        db,
                        user_id=user_id,
                        session_id=session_id or "",
                        user_text=text,
                        assistant_text=full,
                        tokens=0,
                        meta={"messages": messages,},
                    )
                finally:
                    db.close()
            except Exception as e:
                print("[save_turn_db] error:", e)
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
