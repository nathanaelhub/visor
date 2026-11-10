"""Start from a transcript (spec 05, US-5.7): Claude reads an unofficial transcript into a course
list; the browser shows it for checking, and only then runs the audit on it.

Rules this module keeps:

* **Demo transcripts only on the public site.** A request names one of the fictional transcripts in
  ``data/demo/transcripts/`` and the server reads that file itself. Uploading your own file needs the
  write token (``X-Visor-Token``) or local dev, because real transcripts are FERPA Level 4.
* **Nothing is stored or logged.** The file goes to Anthropic for this one request; the record goes
  back to the browser and lives in the tab.
* **Nothing is guessed.** Codes the catalog doesn't have are kept and flagged; grades Visor doesn't
  know become blanks with a note.
* **Same key and limits as Ask Visor.** With the shared key a read costs ``UNITS`` of the US-5.6
  allowance and only the site itself may ask.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import anthropic
from flask import Blueprint, jsonify, request, send_file

from . import chat_limits
from .audit_api import catalog_and_programs, course_code, current_term, find_school
from .auth import write_guard
from .chat import _api_error, _client, _key_from_request, _shared_key
from .rules.grades import is_known
from .rules.terms import next_term, parse_term

bp = Blueprint("transcript", __name__, url_prefix="/api/transcript")

DEMO_DIR = Path(__file__).resolve().parents[2] / "data" / "demo" / "transcripts"
MODEL = "claude-sonnet-5-5"
UNITS = 4
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 6
MEDIA = {b"%PDF": "application/pdf", b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}

_TEXT = {"type": "string"}
_MAYBE_TEXT = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_MAYBE_NUMBER = {"anyOf": [{"type": "number"}, {"type": "null"}]}
SCHEMA = {
    "type": "object",
    "properties": {
        "is_transcript": {"type": "boolean"},
        "student_name": _MAYBE_TEXT,
        "courses": {"type": "array", "items": {
            "type": "object",
            "properties": {"code": _TEXT, "title": _MAYBE_TEXT, "credits": _MAYBE_NUMBER, "grade": _MAYBE_TEXT,
                           "term": _MAYBE_TEXT},
            "required": ["code", "title", "credits", "grade", "term"], "additionalProperties": False}},
        "transfer": {"type": "array", "items": {
            "type": "object",
            "properties": {"school": _TEXT, "subject": _TEXT, "number": _TEXT, "title": _MAYBE_TEXT,
                           "credits": _MAYBE_NUMBER, "grade": _MAYBE_TEXT},
            "required": ["school", "subject", "number", "title", "credits", "grade"],
            "additionalProperties": False}},
        "unreadable": {"type": "array", "items": _TEXT},
    },
    "required": ["is_transcript", "student_name", "courses", "transfer", "unreadable"],
    "additionalProperties": False,
}

PROMPT = """Read this unofficial college transcript into the JSON schema.

- `courses`: every course taken at the issuing university, including ones in progress. `code` exactly \
as printed (subject and number). `grade` exactly as printed; in-progress courses are "IP". `term` as \
printed, e.g. "Fall 2026".
- `transfer`: every course listed as transfer credit, with the other school's name, subject and number.
- `unreadable`: any line you could not read with confidence, quoted briefly. Never guess a code or grade.
- If the document is not an academic transcript, set `is_transcript` to false and leave the lists empty."""

SEASONS = {"SPRING": "SP", "SUMMER": "SU", "FALL": "FA"}


def _demos() -> list[dict]:
    return json.loads((DEMO_DIR / "index.json").read_text())


@bp.before_request
def _shared_key_origin():
    """The shared key only answers the site's own pages (US-5.6)."""
    if request.method == "POST" and _shared_key() and not chat_limits.origin_allowed():
        return jsonify({"error": "forbidden_origin", "message": "Visor only reads transcripts from this site."}), 403
    return None


def _err(code: str, message: str, status: int):
    return jsonify({"error": code, "message": message}), status


def _page_count(data: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", data))


def _term_code(text: str | None) -> str | None:
    """'Fall 2026' or '2026FA' -> '2026FA'; anything else -> None."""
    if not text:
        return None
    t = text.strip().upper()
    m = re.fullmatch(r"(SPRING|SUMMER|FALL)\s+(\d{4})", t)
    try:
        return parse_term(f"{m[2]}{SEASONS[m[1]]}" if m else t).code
    except (ValueError, KeyError):
        return None


def _grade(raw, label: str, notes: list[str]) -> str | None:
    g = (raw or "").strip().upper()
    if g in ("", "IP"):
        return None
    if not is_known(g):
        notes.append(f"{label}: grade {raw!r} is not one Visor knows; left blank")
        return None
    return g


def _record(read: dict, source: str) -> dict:
    """Turn Claude's reading into the same shape as a demo student. Keeps every course."""
    catalog, programs = catalog_and_programs()
    notes = list(read.get("unreadable") or [])
    taken = []
    for c in read["courses"]:
        code = course_code(c["code"])
        taken.append({"code": code, "title": c.get("title") or "", "credits": c.get("credits"),
                      "grade": _grade(c.get("grade"), code, notes), "term": _term_code(c.get("term"))})
    transfer = []
    for t in read["transfer"]:
        school = find_school(name=t["school"])
        label = f"transfer {t['subject']} {t['number']}"
        transfer.append({"school": t["school"], "school_id": school.id if school else None,
                         "subject": t["subject"].strip().upper(), "number": t["number"].strip(),
                         "title": t.get("title") or "", "credits": t.get("credits"),
                         "grade": _grade(t.get("grade"), label, notes)})
    name = (read.get("student_name") or "Student").strip()
    record = {"id": f"transcript-{source}", "name": f"{name} (from transcript)", "student_number": None,
              "program_id": next(iter(programs)), "start_term": next_term(parse_term(current_term())).code,
              "story": "Read from a transcript. Check every row before relying on it.",
              "taken": taken, "transfer": transfer}
    unknown = sorted({t["code"] for t in taken if t["code"] not in catalog.courses})
    return {"record": record, "unreadable": notes, "unknown_codes": unknown}


@bp.get("/demos")
def list_demos():
    return jsonify([{k: d[k] for k in ("id", "label", "name", "student_id")} for d in _demos()])


@bp.get("/demos/<tid>.pdf")
def demo_file(tid):
    """The fictional PDF itself, so people can see what Visor is reading."""
    demo = next((d for d in _demos() if d["id"] == tid), None)
    if demo is None:
        return _err("not_found", "There is no demo transcript with that name.", 404)
    return send_file(DEMO_DIR / demo["file"], mimetype="application/pdf", download_name=demo["file"])


@bp.post("")
def read_transcript():
    if request.files:
        if write_guard() is not None:
            return _err("uploads_off", "Uploading your own transcript is turned off on the public demo. "
                                       "Try one of the fictional transcripts.", 403)
        f = request.files.get("file")
        data, source = (f.read(MAX_BYTES + 1) if f else b""), "upload"
    else:
        tid = (request.get_json(silent=True) or {}).get("demo")
        demo = next((d for d in _demos() if d["id"] == tid), None)
        if demo is None:
            return _err("not_found", "There is no demo transcript with that name.", 404)
        data, source = (DEMO_DIR / demo["file"]).read_bytes(), demo["id"]

    if len(data) > MAX_BYTES:
        return _err("too_large", "Transcripts must be 5 MB or smaller.", 400)
    media = next((m for sig, m in MEDIA.items() if data.startswith(sig)), None)
    if media is None:
        return _err("bad_file", "Upload a PDF, PNG or JPG transcript.", 400)
    if media == "application/pdf" and _page_count(data) > MAX_PAGES:
        return _err("too_many_pages", f"Transcripts must be {MAX_PAGES} pages or fewer.", 400)

    key = _key_from_request()
    if not key:
        return _err("no_key", "Connect an API key first.", 401)
    if _shared_key() and (limited := chat_limits.charge("transcript", UNITS)) is not None:
        return jsonify(limited), 429

    block = {"type": "document" if media == "application/pdf" else "image",
             "source": {"type": "base64", "media_type": media, "data": base64.standard_b64encode(data).decode()}}
    try:
        response = _client(key).beta.messages.create(
            model=MODEL, max_tokens=8000, output_config={"effort": "low", "format": {"type": "json_schema",
                                                                                     "schema": SCHEMA}},
            messages=[{"role": "user", "content": [block, {"type": "text", "text": PROMPT}]}])
    except anthropic.APIError as e:
        return _api_error(e)
    if response.stop_reason in ("refusal", "max_tokens"):
        return _err("unreadable", "Visor couldn't read that transcript. Try a clearer copy.", 422)
    try:
        read = json.loads("".join(b.text for b in response.content if b.type == "text"))
    except json.JSONDecodeError:
        return _err("unreadable", "Visor couldn't read that transcript. Try a clearer copy.", 422)
    if not read.get("is_transcript"):
        return _err("not_transcript", "That doesn't look like an academic transcript.", 422)
    return jsonify(_record(read, source))
