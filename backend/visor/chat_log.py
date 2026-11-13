"""Saved chats and the conversation log (spec 09).

* Only signed-in people's chats are saved; signed-out demo chats are never stored.
* Rows are only added. Each message stores ``hash = sha256(prev_hash + content)``, so a changed or
  missing message shows up when the chain is checked ("Log verified").
* Readers: the person themselves, the advisor of the student record discussed, and admins. Reads by
  anyone but the owner are recorded.
* Retention: conversations older than 365 days are deleted by a daily Vercel Cron call.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from .accounts import advisee_keys, current_user
from .auth import write_guard
from .models import ChatMessage, Conversation, LogAccess, db

bp = Blueprint("chat_log", __name__, url_prefix="/api")

RETENTION_DAYS = 365
GENESIS = "0" * 64


def _now():
    return datetime.now(timezone.utc)


def _content(m: ChatMessage) -> str:
    stamp = m.created_at.replace(tzinfo=None).isoformat(timespec="seconds")
    return json.dumps({"seq": m.seq, "role": m.role, "text": m.text, "tools": m.tools, "model": m.model,
                       "created_at": stamp}, sort_keys=True, default=str)


def _hash(prev: str, m: ChatMessage) -> str:
    return hashlib.sha256((prev + _content(m)).encode()).hexdigest()


def student_key(student: dict | None) -> tuple[str | None, str | None]:
    if not student:
        return None, None
    if student.get("student_number"):
        return student["student_number"], student.get("name")
    return (f"transcript:{student.get('id')}" if student.get("id") else None), student.get("name")


def _append(conv: Conversation, role: str, text: str, tools=None, model=None) -> None:
    last = ChatMessage.query.filter_by(conversation_id=conv.id).order_by(ChatMessage.seq.desc()).first()
    m = ChatMessage(conversation_id=conv.id, seq=(last.seq + 1) if last else 1, role=role, text=text, tools=tools,
                    model=model, created_at=_now().replace(microsecond=0), prev_hash=last.hash if last else GENESIS,
                    hash="")
    m.hash = _hash(m.prev_hash, m)
    db.session.add(m)


def open_conversation(conversation_id, student: dict | None, model: str):
    """(conversation or None, error response or None) for a chat request. None when signed out."""
    user = current_user()
    if user is None:
        return None, None
    if conversation_id:
        conv = db.session.get(Conversation, int(conversation_id)) if str(conversation_id).isdigit() else None
        if conv is None or conv.user_id != user.id:
            return None, (jsonify({"error": "forbidden", "message": "That conversation isn't yours."}), 403)
        return conv, None
    key, name = student_key(student)
    conv = Conversation(user_id=user.id, student_key=key, student_name=name, model=model)
    db.session.add(conv)
    db.session.flush()
    return conv, None


def record(conv: Conversation | None, question: str, result: dict) -> None:
    """Save one question and its answer (tool summaries only, never full tool results)."""
    if conv is None:
        return
    tools = [{"tool": t["tool"], "input": t.get("input"), "summary": t.get("summary"), "status": t.get("status")}
             for t in result.get("tool_calls", [])]
    _append(conv, "user", question)
    _append(conv, "assistant", result.get("answer", ""), tools, result.get("model"))
    conv.last_at = _now()
    db.session.commit()


def _verify(msgs: list[ChatMessage]) -> int | None:
    """The seq of the first message whose chain doesn't hold, or None."""
    prev = GENESIS
    for i, m in enumerate(msgs, 1):
        if m.seq != i or m.prev_hash != prev or m.hash != _hash(prev, m):
            return m.seq
        prev = m.hash
    return None


def _can_read(user, conv: Conversation) -> bool:
    return user is not None and (conv.user_id == user.id or user.role == "admin"
                                 or (user.role == "advisor" and conv.student_key in advisee_keys(user)))


def _summary(conv: Conversation) -> dict:
    first = ChatMessage.query.filter_by(conversation_id=conv.id, role="user").order_by(ChatMessage.seq).first()
    return {"id": conv.id, "user": conv.user.name, "student_key": conv.student_key, "student_name": conv.student_name,
            "model": conv.model, "started_at": conv.started_at.isoformat(), "last_at": conv.last_at.isoformat(),
            "first_question": first.text if first else ""}


@bp.get("/chats")
def my_chats():
    user = current_user()
    if user is None:
        return jsonify({"error": "signed_out", "message": "Sign in to see saved chats."}), 401
    rows = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.last_at.desc()).all()
    return jsonify([_summary(c) for c in rows])


@bp.get("/chats/<int:cid>")
def one_chat(cid: int):
    user = current_user()
    conv = db.session.get(Conversation, cid)
    if conv is None:
        return jsonify({"error": "not_found"}), 404
    if not _can_read(user, conv):
        return jsonify({"error": "forbidden", "message": "You can't read this conversation."}), 403
    if user.id != conv.user_id:
        db.session.add(LogAccess(conversation_id=conv.id, reader_id=user.id))
        db.session.commit()
    msgs = ChatMessage.query.filter_by(conversation_id=conv.id).order_by(ChatMessage.seq).all()
    broken = _verify(msgs)
    reads = LogAccess.query.filter_by(conversation_id=conv.id).order_by(LogAccess.read_at).all()
    return jsonify({**_summary(conv), "verified": broken is None, "broken_at": broken,
                    "messages": [{"seq": m.seq, "role": m.role, "text": m.text, "tools": m.tools or [], "model": m.model,
                                  "created_at": m.created_at.isoformat()} for m in msgs],
                    "read_by": [{"reader": r.reader.name, "at": r.read_at.isoformat()} for r in reads]})


@bp.get("/admin/conversations")
def all_chats():
    user = current_user()
    if user is None or user.role not in ("admin", "advisor"):
        return jsonify({"error": "forbidden", "message": "Only advisors and admins can read the log."}), 403
    q = Conversation.query
    if user.role == "advisor":
        q = q.filter(Conversation.student_key.in_(advisee_keys(user) or ["-"]))
    return jsonify([_summary(c) for c in q.order_by(Conversation.last_at.desc()).limit(500)])


@bp.route("/cron/purge-chats", methods=["GET", "POST"])
def purge():
    """Vercel Cron calls this daily with ``Authorization: Bearer $CRON_SECRET``."""
    secret = os.environ.get("CRON_SECRET")
    by_cron = bool(secret) and request.headers.get("Authorization") == f"Bearer {secret}"
    if not by_cron and (not os.environ.get("VISOR_WRITE_TOKEN") or write_guard() is not None):
        return jsonify({"error": "forbidden"}), 403
    cutoff = _now() - timedelta(days=RETENTION_DAYS)
    old = [c.id for c in Conversation.query.filter(Conversation.last_at < cutoff)]
    if old:
        ChatMessage.query.filter(ChatMessage.conversation_id.in_(old)).delete(synchronize_session=False)
        LogAccess.query.filter(LogAccess.conversation_id.in_(old)).delete(synchronize_session=False)
        Conversation.query.filter(Conversation.id.in_(old)).delete(synchronize_session=False)
        db.session.commit()
    return jsonify({"deleted": len(old)})
