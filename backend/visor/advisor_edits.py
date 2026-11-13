"""Advisor edits and plan approval (spec 06).

Edits are inputs to the planner (settings, pins, holds); ``POST /api/audit`` applies them without
saving anything. These routes keep them, and the approvals, on a staff deployment. Saving needs the
write token (KAN-46), so the public demo answers 401/403 and the browser keeps edits in the tab.

An approval stores the plan's fingerprint. It is current only while the fingerprint of the plan the
student sees today still matches; otherwise the plan has changed and needs re-approval.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from .audit_api import AuditError, compute_audit, parse_edits
from .accounts import current_user, staff_guard
from .models import PlanApproval, PlanEdits, db

bp = Blueprint("advisor_edits", __name__, url_prefix="/api/students")


def _who(typed: str | None) -> str | None:
    """A signed-in person's own name wins over a typed one (spec 08); scripts still type it."""
    u = current_user()
    return u.name if u else typed


def _approval(a: PlanApproval | None) -> dict | None:
    return None if a is None else {"fingerprint": a.fingerprint, "approved_by": a.approved_by,
                                   "approved_at": a.approved_at.isoformat(), "note": a.note}


def _save_edits(key: str, edits: dict, by: str | None) -> PlanEdits:
    row = PlanEdits.query.filter_by(student_key=key).one_or_none() or PlanEdits(student_key=key, edits={})
    row.edits, row.updated_by = edits, by
    row.updated_at = datetime.now(timezone.utc)
    db.session.add(row)
    return row


@bp.get("/<key>/plan-edits")
def get_edits(key):
    row = PlanEdits.query.filter_by(student_key=key).one_or_none()
    history = PlanApproval.query.filter_by(student_key=key).order_by(PlanApproval.id.desc()).all()
    return jsonify({"edits": row.edits if row else None, "updated_by": row.updated_by if row else None,
                    "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
                    "approval": _approval(history[0] if history else None),
                    "history": [_approval(a) for a in history],
                    "can_save": staff_guard("advisor", student_key=key) is None})


@bp.put("/<key>/plan-edits")
def put_edits(key):
    if (denied := staff_guard("advisor", student_key=key)) is not None:
        return denied
    body = request.get_json(silent=True) or {}
    try:
        _, _, edits = parse_edits(body.get("edits"))
    except AuditError as e:
        return jsonify({"error": "bad_edits", "message": str(e)}), 400
    _save_edits(key, edits, _who((body.get("updated_by") or "").strip() or None))
    db.session.commit()
    return get_edits(key)


@bp.post("/<key>/approval")
def approve(key):
    if (denied := staff_guard("advisor", student_key=key)) is not None:
        return denied
    body = request.get_json(silent=True) or {}
    student = body.get("student") or {}
    by = _who((body.get("approved_by") or "").strip())
    if not by:
        return jsonify({"error": "bad_request", "message": "Say who is approving the plan."}), 400
    if key not in (student.get("student_number"), student.get("id")):
        return jsonify({"error": "bad_request", "message": "The student in the body is not this student."}), 400
    try:
        r = compute_audit(student)
    except AuditError as e:
        return jsonify({"error": "bad_request", "message": str(e)}), e.status
    if r["fingerprint"] != body.get("fingerprint"):
        return jsonify({"error": "plan_changed", "message": "The plan changed since you looked at it. "
                                                             "Review it again, then approve."}), 409
    reasons = [v["message"] for v in (r.get("checks") or {}).get("violations", [])]
    reasons += [w["message"] for w in r["warnings"] if w["kind"] == "unplaceable"]
    if r["plan"] is None:
        reasons.append("There is no plan to approve (no start term).")
    if reasons:
        return jsonify({"error": "plan_fails_checks", "message": "Fix these before approving.",
                        "reasons": reasons}), 409
    _save_edits(key, r["edits"], by)  # the approval covers these exact edits
    db.session.add(PlanApproval(student_key=key, fingerprint=r["fingerprint"], approved_by=by,
                                note=(body.get("note") or "").strip() or None))
    db.session.commit()
    return get_edits(key), 201
