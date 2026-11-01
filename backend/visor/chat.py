"""Ask Visor: a chat relay to Claude that answers with Visor's own data (spec 05, design "Ask Visor").

Rules this module keeps:

* **The planner decides; the chat explains.** Claude gets three read-only tools that call the same
  code as the API (`compute_audit`, the equivalency lookup, the catalog). It has no tool that changes
  a plan, and the system prompt tells it to say so.
* **The key is never stored.** A key arrives per request in the ``X-Anthropic-Key`` header (the
  browser keeps it in session storage) and is used for that one request only. A deployment can set
  ``VISOR_ANTHROPIC_API_KEY`` instead ("shared key" mode); then no key is sent from the browser.
* **Stateless.** The browser sends the text of earlier turns; tool calls and thinking from earlier
  turns are not replayed. Within one turn the tool loop appends Claude's content unchanged.
"""
from __future__ import annotations

import json
import os

import anthropic
from flask import Blueprint, current_app, jsonify, request

from .audit_api import AuditError, compute_audit, course_code, course_info, translate_transfer, catalog_and_programs
from .rules.grades import meets
from .rules.terms import parse_term

bp = Blueprint("chat", __name__, url_prefix="/api/chat")

MODELS = {
    "opus": {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "blurb": "Most thorough", "fallbacks": True},
    "sonnet": {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "blurb": "Balanced", "fallbacks": True},
    "haiku": {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "blurb": "Fastest, lowest cost",
              "fallbacks": False},
}
DEFAULT_MODEL = "opus"
MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 20

SYSTEM = """You are Ask Visor, the assistant inside Visor, Lipscomb University's course-planning and \
transfer-advising app.

How Visor works: a deterministic planner reads the published 2026-27 catalog and the student's record \
and produces the degree audit and the term-by-term plan. You explain that plan; you never decide it.

Rules:
- Answer from tool results, not memory. Use run_degree_audit for anything about the student's \
requirements or plan, transfer_lookup for what a course from another school counts as, and \
course_info for prerequisites, offerings and which requirements a course fills. If a tool does not \
have the answer, say so.
- Before saying a course is blocked, delayed or required by a prerequisite, call course_info for that \
course and read `met_by` on each prerequisite. A prerequisite is satisfied by any one of its options; \
never call a course necessary when the student already has another option.
- You cannot change a plan, move a course, register a student, or confirm a transfer equivalency. \
If asked, start your answer with "I can't edit your plan. Ask your advisor." and then explain why the \
planner placed things where they are.
- Only `confirmed` transfer equivalencies count toward the degree; `proposed` ones wait for a person.
- Be brief and concrete: course codes, terms, hours. Use a short markdown table when comparing \
several requirements. No preamble.
- All students in this demo are fictional. Remind the user to check with their advisor before \
registering when the answer affects what to register for."""

TOOLS = [
    {
        "name": "run_degree_audit",
        "description": "Run Visor's degree audit and semester planner for the student in context. Returns "
                       "requirement groups (met / in progress / needed), hours, the term-by-term plan with "
                       "the reason each course is placed, transfer credit, warnings and the projected "
                       "graduation term.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "transfer_lookup",
        "description": "Look up what a course from another school counts as at Lipscomb in the equivalency "
                       "table. Status is confirmed (counts now), proposed (a person must confirm) or "
                       "unknown (no match on file).",
        "input_schema": {
            "type": "object",
            "properties": {
                "school": {"type": "string", "description": "School name, e.g. 'Nashville State'"},
                "subject": {"type": "string", "description": "Course subject at that school, e.g. 'CISP'"},
                "number": {"type": "string", "description": "Course number, e.g. '1020'"},
            },
            "required": ["school", "subject", "number"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "course_info",
        "description": "Catalog facts for one Lipscomb course: title, credits, prerequisites (with minimum "
                       "grade), when it is offered, class-standing needs, which courses it unlocks, which "
                       "requirement groups it fills, and where it sits in the student's plan.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Course code, e.g. 'CS 3633'"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

SOURCE = {"run_degree_audit": "Your plan", "transfer_lookup": "Equivalency table", "course_info": "Catalog 2026–27"}


# --- Keys and clients ----------------------------------------------------------------------------


def _shared_key() -> str | None:
    return os.environ.get("VISOR_ANTHROPIC_API_KEY") or None


def _key_from_request() -> str | None:
    return (request.headers.get("X-Anthropic-Key") or "").strip() or _shared_key()


def _client(key: str):
    factory = current_app.config.get("ANTHROPIC_CLIENT_FACTORY")
    if factory:
        return factory(key)
    return anthropic.Anthropic(api_key=key, max_retries=1, timeout=90)


def _api_error(e: Exception):
    """Map SDK errors onto the states the UI designs for."""
    if isinstance(e, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return jsonify({"error": "invalid_key", "message": "That key was not accepted by Anthropic."}), 401
    if isinstance(e, anthropic.RateLimitError):
        retry = e.response.headers.get("retry-after") if getattr(e, "response", None) is not None else None
        return jsonify({"error": "rate_limited", "retry_after": int(retry) if retry and retry.isdigit() else 30,
                        "message": "Anthropic is rate limiting this key. Try again shortly."}), 429
    if isinstance(e, anthropic.NotFoundError):
        return jsonify({"error": "model_unavailable", "message": "This key cannot use that model."}), 400
    if isinstance(e, anthropic.APIStatusError) and e.status_code < 500:
        return jsonify({"error": "bad_request", "message": e.message}), 400
    return jsonify({"error": "api_down", "message": "Anthropic's API did not respond. Try again."}), 503


# --- Tools ---------------------------------------------------------------------------------------


def _term_name(code: str | None) -> str | None:
    return parse_term(code).name if code else None


def _audit_digest(r: dict) -> dict:
    """The audit, trimmed to what the model needs (no ids, no duplicated fields)."""
    return {
        "program": r["program"], "hours": {"done": r["hours_done"], "in_progress": r["hours_in_progress"],
                                           "required": r["hours_required"], "transfer": r["transfer_hours"]},
        "projected_graduation": _term_name(r["projected_term"]),
        "requirements": [{"name": g["name"], "status": g["status"], "remaining": g["remaining"],
                          "counted": [u["code"] + (f" ({u['via']})" if u["via"] != "completed" else "")
                                      for u in g["used"]]} for g in r["groups"]],
        "in_progress": [c["code"] for c in r["in_progress"]["courses"]],
        "plan": [{"term": t["name"], "hours": t["hours"], "courses": [
            {"code": c["code"], "title": c["title"], "why": [x["text"] for x in c["reasons"]]}
            for c in t["courses"]]} for t in (r["plan"] or {}).get("terms", [])],
        "free_elective_hours_still_needed": (r["plan"] or {}).get("free_elective_hours"),
        "transfer": [{k: t[k] for k in ("school", "external", "status", "counts_as", "note")} for t in r["transfer"]],
        "retakes": [{"code": x["code"], "grade": x["grade"], "needs": x["min_grade"]} for x in r["retakes"]],
        "warnings": [w["message"] for w in r["warnings"]],
    }


def _prerequisite_status(info: dict, student: dict, r: dict) -> None:
    """Mark each prerequisite of ``info`` with the option this student has met, if any: passed (at the
    minimum grade), in progress, or planned before the course. Adds ``prerequisites_met``."""
    grades = {course_code(t["code"]): t.get("grade") for t in student.get("taken", [])}
    grades |= {t["counts_as"]: "TR" for t in r["transfer"] if t["counted"]}  # confirmed transfer credit
    terms = (r["plan"] or {}).get("terms", [])
    at = next((i for i, t in enumerate(terms) for c in t["courses"] if c["code"] == info["code"]), len(terms))
    planned = {c["code"]: t["name"] for t in terms[:at] for c in t["courses"]}
    for p in info["prerequisites"]:
        p["met_by"] = None
        for code in p["any_of"]:
            if code in grades and grades[code] is None:
                p["met_by"] = {"code": code, "how": "in progress"}
            elif code in grades and meets(grades[code], p["min_grade"]):
                p["met_by"] = {"code": code, "how": f"passed with {grades[code]}"}
            elif code in planned:
                p["met_by"] = {"code": code, "how": f"planned for {planned[code]}"}
            if p["met_by"]:
                break
    info["prerequisites_met"] = all(p["met_by"] for p in info["prerequisites"])


def _run_tool(name: str, args: dict, student: dict | None) -> tuple[dict, str, str]:
    """Returns (result for the model, one-line summary for the UI card, status for the UI pill)."""
    if name == "run_degree_audit":
        if not student:
            return {"error": "No student is in context."}, "No student in context", "error"
        r = compute_audit(student)
        needed = sum(1 for g in r["groups"] if g["status"] == "needed")
        return _audit_digest(r), f"Ran the degree audit · {needed} group{'s' if needed != 1 else ''} still needed", \
            "review" if r["needs_review"] else "ok"
    if name == "transfer_lookup":
        _, report = translate_transfer([{"school": args.get("school"), "subject": args.get("subject"),
                                         "number": args.get("number")}], catalog_and_programs()[0])
        e = report[0]
        where = (e["school"] or args.get("school") or "").replace(" Community College", "")
        arrow = f" → {e['counts_as']}" if e["counts_as"] else ""
        return e, f"Looked up {e['external']} at {where}{arrow}", e["status"]
    if name == "course_info":
        info = course_info(args.get("code", ""))
        if info is None:
            return {"error": f"{args.get('code')} is not in the 2026-27 catalog."}, \
                f"{args.get('code')} is not in the catalog", "error"
        if student:
            r = compute_audit(student)
            info["in_this_plan"] = next(({"term": t["name"], "why": [x["text"] for x in c["reasons"]]}
                                         for t in (r["plan"] or {}).get("terms", []) for c in t["courses"]
                                         if c["code"] == info["code"]), None)
            info["student_has"] = next((u["code"] for g in r["groups"] for u in g["used"]
                                        if u["code"] == info["code"]), None)
            _prerequisite_status(info, student, r)
        return info, f"Checked {info['code']} {info['title']} in the catalog", "ok"
    return {"error": f"unknown tool {name}"}, f"Unknown tool {name}", "error"


# --- Routes --------------------------------------------------------------------------------------


@bp.get("/config")
def config():
    return jsonify({"shared_key": bool(_shared_key()), "default_model": DEFAULT_MODEL,
                    "models": [{"key": k, "id": m["id"], "label": m["label"], "blurb": m["blurb"]}
                               for k, m in MODELS.items()]})


@bp.post("/verify")
def verify_key():
    """Check a key without spending tokens: look up the chosen model with it."""
    key = _key_from_request()
    if not key:
        return jsonify({"error": "no_key", "message": "Enter an API key."}), 400
    model = MODELS.get((request.get_json(silent=True) or {}).get("model") or DEFAULT_MODEL)
    if model is None:
        return jsonify({"error": "bad_model", "message": "Unknown model."}), 400
    try:
        _client(key).models.retrieve(model["id"])
    except anthropic.APIError as e:
        return _api_error(e)
    return jsonify({"ok": True, "model": model["label"]})


@bp.post("")
def chat():
    key = _key_from_request()
    if not key:
        return jsonify({"error": "no_key", "message": "Connect an API key first."}), 401
    body = request.get_json(silent=True) or {}
    model = MODELS.get(body.get("model") or DEFAULT_MODEL)
    if model is None:
        return jsonify({"error": "bad_model", "message": "Unknown model."}), 400

    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("text")]
    history = history[-MAX_HISTORY:]
    while history and history[0]["role"] != "user":
        history.pop(0)
    if not history or history[-1]["role"] != "user":
        return jsonify({"error": "bad_request", "message": "The last message must be the user's."}), 400
    messages: list = [{"role": m["role"], "content": m["text"]} for m in history]

    student = body.get("student")
    system = SYSTEM
    if student:
        system += (f"\n\nStudent in context: {student.get('name', 'unnamed')} "
                   f"({student.get('program_id')}), planning from {student.get('start_term')}.")

    client = _client(key)
    params: dict = dict(model=model["id"], max_tokens=16000, system=system, tools=TOOLS,
                        output_config={"effort": "medium"})
    if model["fallbacks"]:
        params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    tool_calls: list[dict] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = client.beta.messages.create(messages=messages, **params)
            if response.stop_reason == "refusal":
                return jsonify({"answer": "I can't help with that one. Try asking about your plan, a course, "
                                          "or transfer credit.", "refused": True, "tool_calls": tool_calls,
                                "sources": [], "model": response.model})
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not uses:
                break
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for u in uses:
                args = u.input if isinstance(u.input, dict) else json.loads(u.input or "{}")
                try:
                    result, summary, status = _run_tool(u.name, args, student)
                    is_error = status == "error"
                except AuditError as e:
                    result, summary, status, is_error = {"error": str(e)}, str(e), "error", True
                tool_calls.append({"tool": u.name, "input": args, "summary": summary, "status": status,
                                   "result": result, "source": SOURCE.get(u.name)})
                results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": is_error,
                                "content": json.dumps(result, default=str)})
            messages.append({"role": "user", "content": results})
        else:
            response = None
    except anthropic.APIError as e:
        return _api_error(e)

    answer = "" if response is None else "".join(b.text for b in response.content if b.type == "text").strip()
    if not answer:
        answer = "I ran out of steps before finishing. Try a narrower question."
    sources = sorted({c["source"] for c in tool_calls if c["source"] and c["status"] != "error"})
    return jsonify({"answer": answer, "refused": False, "tool_calls": tool_calls, "sources": sources,
                    "model": getattr(response, "model", model["id"]),
                    "truncated": getattr(response, "stop_reason", None) == "max_tokens"})
