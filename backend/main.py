from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# ----------------------------
# ENV SETUP
# ----------------------------
load_dotenv()

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.getenv("DB_PATH", "app.db")

if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, DB_PATH)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TO = os.getenv("SMTP_TO", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes"}

# ----------------------------
# FASTAPI LIFESPAN
# ----------------------------
@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Campux Backend",
    version="1.0.0",
    lifespan=lifespan
)

# ----------------------------
# MIDDLEWARE
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# SCHEMAS
# ----------------------------
class WaitlistIn(BaseModel):
    email: EmailStr
    source: str | None = None


class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str

# ----------------------------
# DB HELPERS
# ----------------------------
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                source TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

# ----------------------------
# EMAIL HELPERS
# ----------------------------
def require_smtp():
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP not configured")


def send_email(subject: str, html_body: str, text_body: str, to_email: str):
    try:
        require_smtp()

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            if SMTP_TLS:
                smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

    except Exception as e:
        print(f"❌ Email failed: {e}")


def user_success_email(title: str, message: str):
    html = f"""
    <html>
      <body style="background:#F1FFF7;font-family:Arial;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#fff;border-radius:12px;padding:20px;">
          <h2 style="color:#25D366;">Campux</h2>
          <h3>{title}</h3>
          <p>{message}</p>
          <small style="color:#888;">🚀 Stay tuned for updates</small>
        </div>
      </body>
    </html>
    """
    return html, message


def campux_email(title: str, rows: list[tuple[str, str]]):
    row_html = "".join(
        f"<p><strong>{k}:</strong> {v}</p>" for k, v in rows
    )

    html = f"""
    <html>
      <body style="font-family:Arial;padding:20px;">
        <h2>Campux Notification</h2>
        <h3>{title}</h3>
        {row_html}
      </body>
    </html>
    """

    text = "\n".join([f"{k}: {v}" for k, v in rows])
    return html, text

# ----------------------------
# ROUTES
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/waitlist")
def create_waitlist(payload: WaitlistIn):
    created_at = utc_now()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO waitlist (email, source, created_at) VALUES (?, ?, ?)",
            (payload.email, payload.source or "web", created_at),
        )

    # Admin notification
    html, text = campux_email(
        "New Waitlist Signup",
        [
            ("Email", payload.email),
            ("Source", payload.source or "web"),
            ("Time", created_at),
        ],
    )

    send_email("New Waitlist Signup", html, text, SMTP_TO)

    # User email
    user_html, user_text = user_success_email(
        "You're on the Waitlist 🎉",
        "Thanks for joining Campux! We'll notify you when we launch."
    )

    send_email("Welcome to Campux 🚀", user_html, user_text, payload.email)

    return {"ok": True}


@app.post("/api/contact")
def create_contact(payload: ContactIn):
    created_at = utc_now()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO contact (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (payload.name, payload.email, payload.message, created_at),
        )

    # Admin email
    html, text = campux_email(
        "New Contact Message",
        [
            ("Name", payload.name),
            ("Email", payload.email),
            ("Message", payload.message),
            ("Time", created_at),
        ],
    )

    send_email("New Contact Message", html, text, SMTP_TO)

    # User confirmation
    user_html, user_text = user_success_email(
        "Message Received ✅",
        f"Hi {payload.name}, we received your message and will reply soon."
    )

    send_email("We got your message 📩", user_html, user_text, payload.email)

    return {"ok": True}