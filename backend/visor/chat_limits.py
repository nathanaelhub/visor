"""Limits for Ask Visor when it runs on one shared key (spec 05, US-5.6).

The key belongs to whoever deploys Visor, so a public demo needs a ceiling: per-visitor hourly and
daily allowances weighted by model, a site-wide daily cap, request size caps, and requests only from
the site itself. Counters live in ``chat_usage`` and hold no message text and no raw IP.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import request
from sqlalchemy.exc import IntegrityError

from .models import ChatUsage, db

UNITS = {"haiku": 1, "sonnet": 2, "opus": 4}  # one message, by model
MAX_CHARS = 1000            # per question
MAX_MESSAGES = 20           # per conversation
MAX_OUTPUT_TOKENS = 2000    # per reply


def _setting(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _visitor() -> str:
    """Salted hash of the caller's IP. Vercel sets X-Real-IP / X-Forwarded-For from the connection."""
    ip = (request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
          or request.remote_addr or "").split(",")[0].strip()
    salt = os.environ.get("VISOR_CHAT_SALT") or os.environ.get("VISOR_ANTHROPIC_API_KEY", "")
    return hashlib.sha256(f"{salt}|{ip}".encode()).hexdigest()


def origin_allowed() -> bool:
    """Only the site itself (or VISOR_ALLOWED_ORIGINS) may use the shared key. Browsers always send
    Origin on a POST, so a missing one means the request didn't come from a page."""
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if not origin:
        return False
    allowed = {o.strip().rstrip("/") for o in os.environ.get("VISOR_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    return origin in allowed or urlparse(origin).netloc == request.host


def size_error(messages: list[dict]) -> tuple[str, str] | None:
    """(code, message) if the request is over the size caps, else None."""
    if len(messages) > MAX_MESSAGES:
        return "conversation_full", "This conversation is full. Start a new chat to keep going."
    if any(m["role"] == "user" and len(m["text"]) > MAX_CHARS for m in messages):
        return "too_long", f"Keep questions under {MAX_CHARS:,} characters."
    return None


def _until(when: datetime, now: datetime) -> int:
    return max(1, int((when - now).total_seconds()))


def charge(model_key: str, units: int | None = None) -> dict | None:
    """Count one message (or ``units``) against the visitor's and the site's allowance. Returns the 429 body if it
    would go over (and counts nothing), else None."""
    now = datetime.now(timezone.utc)
    hour, day = now.strftime("%Y-%m-%dT%H"), now.strftime("%Y-%m-%d")
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    units = units if units is not None else UNITS.get(model_key, max(UNITS.values()))
    who = _visitor()

    rows = {(r.period, r.visitor): r for r in ChatUsage.query.filter(
        ChatUsage.period.in_((hour, day)), ChatUsage.visitor.in_((who, "site")))}

    def used(period: str, visitor: str) -> int:
        row = rows.get((period, visitor))
        return row.units if row else 0

    if used(hour, who) + units > _setting("VISOR_CHAT_PER_HOUR", 20):
        wait = _until(next_hour, now)
        return {"error": "visitor_limit", "retry_after": wait,
                "message": f"You've reached this hour's Ask Visor limit. Try again in about {-(-wait // 60)} min, "
                           "or pick a lighter model."}
    if used(day, who) + units > _setting("VISOR_CHAT_PER_DAY", 60):
        return {"error": "visitor_limit", "retry_after": _until(midnight, now),
                "message": "You've reached today's Ask Visor limit. It resets at midnight UTC."}
    if used(day, "site") + units > _setting("VISOR_CHAT_DAILY_UNITS", 600):
        return {"error": "site_limit", "retry_after": _until(midnight, now),
                "message": "Ask Visor is resting for today: the demo reached its daily limit. "
                           "It resets at midnight UTC."}

    for period, visitor in ((hour, who), (day, who), (day, "site")):
        row = rows.get((period, visitor))
        if row is None:
            row = ChatUsage(period=period, visitor=visitor, day=now.date(), units=0)
            db.session.add(row)
        row.units += units
    ChatUsage.query.filter(ChatUsage.day < now.date() - timedelta(days=2)).delete()
    try:
        db.session.commit()
    except IntegrityError:  # two first messages in the same window at once; let this one through
        db.session.rollback()
    return None
