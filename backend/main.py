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

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Campux Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WaitlistIn(BaseModel):
    email: EmailStr
    source: str | None = None


class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                source TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def require_smtp() -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not SMTP_FROM or not SMTP_TO:
        raise HTTPException(status_code=500, detail="SMTP is not configured on the server")


def send_email(subject: str, html_body: str, text_body: str) -> None:
    require_smtp()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = SMTP_TO
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        if SMTP_TLS:
            smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def campux_email(title: str, rows: list[tuple[str, str]]) -> tuple[str, str]:
    row_html = "".join(
        f"""
        <tr>
          <td style=\"padding:10px 0;color:#0F1E16;font-weight:600;width:140px\">{label}</td>
          <td style=\"padding:10px 0;color:#0F1E16\">{value}</td>
        </tr>
        """
        for label, value in rows
    )
    html = f"""
    <html>
      <body style="margin:0;padding:0;background:#F1FFF7;font-family:Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
          <tr>
            <td align="center">
              <table width="600" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:16px;border:1px solid #E2ECE6;overflow:hidden;">
                <tr>
                  <td style="background:#25D366;padding:20px 28px;color:#FFFFFF;font-size:20px;font-weight:700;letter-spacing:0.3px;">
                    Campux
                  </td>
                </tr>
                <tr>
                  <td style="padding:28px;">
                    <div style="font-size:18px;font-weight:700;color:#07140E;margin-bottom:16px;">{title}</div>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      {row_html}
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:18px 28px;background:#E9FBF1;color:#128C7E;font-size:12px;">
                    Campux keeps your campus connected — fast, trusted, and student-first.
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    text_lines = [title] + [f"{label}: {value}" for label, value in rows]
    return html, "\n".join(text_lines)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/waitlist")
def create_waitlist(payload: WaitlistIn) -> dict:
    created_at = utc_now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO waitlist (email, source, created_at) VALUES (?, ?, ?)",
            (payload.email, payload.source or "web", created_at),
        )

    html, text = campux_email(
        "New Waitlist Signup",
        [
            ("Email", payload.email),
            ("Source", payload.source or "web"),
            ("Time (UTC)", created_at),
        ],
    )
    send_email("Campux Waitlist Signup", html, text)
    return {"ok": True}


@app.post("/api/contact")
def create_contact(payload: ContactIn) -> dict:
    created_at = utc_now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO contact (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (payload.name, payload.email, payload.message, created_at),
        )

    html, text = campux_email(
        "New Contact Message",
        [
            ("Name", payload.name),
            ("Email", payload.email),
            ("Message", payload.message),
            ("Time (UTC)", created_at),
        ],
    )
    send_email("Campux Contact Message", html, text)
    return {"ok": True}
