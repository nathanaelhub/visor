"""Degree audit + forecast API (spec 05; contract extends spec 04's ``POST /api/audit``).

Nothing here writes to the database: the audit takes the student's courses in the request and
returns a result (spec 04, "No student records are stored in v1"). Transfer courses go through the
same equivalency rows the lookup page uses, read-only — an unknown course is reported, not recorded.

``compute_audit()`` is the one entry point; the HTTP routes and the Ask Visor tools both call it, so
the chat can never describe a plan the planner did not produce.
"""
from __future__ import annotations

import csv
import functools
import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, jsonify, request

from .catalog_files import DEFAULT_CATALOG, load_catalog
from .equivalencies import _live_rows
from .models import ExternalCourse, School, db
from .rules.audit import ReqItem, Taken, audit, matches
from .rules.forecast import Edits, Hold, Pin, Settings, project
from .rules.grades import is_known
from .rules.terms import describe_offerings, parse_term
from .rules.verify import verify

bp = Blueprint("audit", __name__, url_prefix="/api")

DEMO_STUDENTS = Path(__file__).resolve().parents[2] / "data" / "demo" / "students"


class AuditError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


def catalog_and_programs():
    return load_catalog(os.environ.get("VISOR_CATALOG_DIR", str(DEFAULT_CATALOG)))


@functools.cache
def _gates_from(path: str) -> dict[str, list[tuple[ReqItem, str]]]:
    out: dict[str, list[tuple[ReqItem, str]]] = {}
    f = Path(path) / "program_gates.csv"
    if f.exists():
        for r in csv.DictReader(open(f, newline="")):
            out.setdefault(r["program"], []).append((ReqItem(course=None, pattern=r["pattern"], tag=None), r["message"]))
    return out


def program_gates(program_id: str) -> list[tuple[ReqItem, str]]:
    """Admission gates a program has (spec 07: nursing). Shown as warnings, never enforced."""
    return _gates_from(os.environ.get("VISOR_CATALOG_DIR", str(DEFAULT_CATALOG))).get(program_id, [])


def current_term() -> str:
    """The term in progress now. Configuration, never the clock (spec 05)."""
    return parse_term(os.environ.get("VISOR_CURRENT_TERM", "2026FA")).code


def course_code(raw: str) -> str:
    """'cs2233', ' CS  2233 ' -> 'CS 2233'."""
    s = "".join(str(raw).split()).upper()
    i = next((k for k, ch in enumerate(s) if ch.isdigit()), len(s))
    return f"{s[:i]} {s[i:]}".strip()


# --- Transfer --------------------------------------------------------------------------------------


_ABBREV = {"st": "state", "cmty": "community", "comm": "community", "coll": "college", "univ": "university",
           "u": "university", "tech": "technical", "cc": "community college", "&": "and"}


def school_key(name: str) -> str:
    """'COLUMBIA ST. CMTY COLL.' -> 'columbia state community college': how scans abbreviate names."""
    words = re.sub(r"[^a-z& ]", " ", name.lower().replace(",", " ")).split()
    return " ".join(_ABBREV.get(w, w) for w in words)


def find_school(school_id=None, name: str | None = None) -> School | None:
    if isinstance(school_id, int):
        return db.session.get(School, school_id)
    if name:
        n = school_key(name)
        if not n:
            return None
        schools = School.query.all()
        return (next((s for s in schools if school_key(s.name) == n), None)
                or next((s for s in schools if n in school_key(s.name)), None))
    return None


def translate_transfer(rows: list[dict], catalog) -> tuple[list[Taken], list[dict]]:
    """Each transfer course -> what it counts as. Only `confirmed` counts (spec 04)."""
    taken, report = [], []
    for r in rows:
        school = find_school(r.get("school_id"), r.get("school"))
        subject, number = str(r.get("subject", "")).strip().upper(), str(r.get("number", "")).strip()
        label = f"{school.name if school else 'Unknown school'}: {subject} {number}"
        entry = {"school": school.name if school else None, "external": f"{subject} {number}",
                 "title": None, "status": "unknown", "counts_as": None, "counts_as_title": None,
                 "counted": False, "note": ""}
        ext = (ExternalCourse.query.filter_by(school_id=school.id, subject=subject, number=number)
               .order_by(ExternalCourse.catalog_year.desc()).first()) if school else None
        if ext is None:
            entry["note"] = "Not in the equivalency table yet; look it up and flag it for review."
            report.append(entry)
            continue
        entry["title"] = ext.title
        confirmed, proposed, placeholders = _live_rows(ext)
        grade = r.get("grade") or "TR"
        if confirmed:
            q = confirmed[0]
            entry["status"] = "confirmed"
            if q.kind == "direct" and q.course is not None:
                entry.update(counts_as=q.course.code, counts_as_title=q.course.title, counted=True)
                taken.append(Taken(q.course.code, catalog.credits(q.course.code, q.course.credits), grade,
                                   source="transfer", detail=label))
            elif q.kind == "elective":
                credits = ext.credits or 3
                entry.update(counts_as=f"{credits:g} hours elective credit", counted=True)
                taken.append(Taken(f"{subject} {number} (elective)", credits, grade, source="transfer",
                                   detail=label, elective_only=True))
            else:
                entry["note"] = "Confirmed as not transferring."
        elif proposed:
            top = proposed[0].course
            entry.update(status="proposed", counts_as=top.code if top else None,
                         counts_as_title=top.title if top else None,
                         note="Pending: a person has to confirm this before it counts.")
        elif placeholders:
            entry["note"] = "Flagged for professor review; it counts once someone decides."
        else:
            entry["note"] = "No equivalency yet; flag it for review from the lookup page."
        report.append(entry)
    return taken, report


# --- The audit -------------------------------------------------------------------------------------


def _number(value, what: str, kind=float):
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise AuditError(f"{what} must be a number, got {value!r}") from None


def _grade(value, what: str):
    if not is_known(value):
        raise AuditError(f"{what}: grade {value!r} is not a letter grade (A to F), TR, P, CR, W or I")
    return value or None


MIN_LOAD, MAX_LOAD, OVERLOAD = 12, 18, 21  # spec 06, US-6.1


def parse_edits(raw: dict | None, start_term: str | None = None) -> tuple[dict, Edits, dict]:
    """An advisor's edits (spec 06) -> (settings overrides, rules ``Edits``, the normalized edits to
    echo back and store). Raises AuditError on anything the spec refuses."""
    raw = raw or {}
    if not isinstance(raw, dict):
        raise AuditError("edits must be an object")
    s = raw.get("settings") or {}
    settings: dict = {}
    if "include_summer" in s:
        settings["include_summer"] = bool(s["include_summer"])
    if s.get("max_hours") is not None:
        settings["max_hours"] = _number(s["max_hours"], "edits.settings.max_hours", int)
    if s.get("target_hours") is not None:
        settings["target_hours"] = _number(s["target_hours"], "edits.settings.target_hours", int)
    note = (raw.get("overload_note") or "").strip() or None
    top = settings.get("max_hours", MAX_LOAD)
    if not MIN_LOAD <= top <= OVERLOAD:
        raise AuditError(f"max hours must be between {MIN_LOAD} and {OVERLOAD}")
    if top > MAX_LOAD and not note:
        raise AuditError(f"a maximum above {MAX_LOAD} hours is an overload: add a note saying why")
    if not 1 <= settings.get("target_hours", min(15, top)) <= top:
        raise AuditError("target hours must be between 1 and the maximum")

    def term(value, what):
        try:
            return parse_term(str(value)).code
        except ValueError as e:
            raise AuditError(f"{what}: {e}") from e

    pins, holds = [], []
    for p in raw.get("pins") or []:
        code, t = course_code(p.get("code", "")), term(p.get("term"), "pin term")
        if not code:
            raise AuditError("every pin needs a course code")
        if start_term and parse_term(t) < parse_term(start_term):
            raise AuditError(f"{code} can't be pinned to {parse_term(t).name}: the plan starts "
                             f"{parse_term(start_term).name}")
        pins.append({"code": code, "term": t})
    for h in raw.get("holds") or []:
        code = course_code(h.get("code", ""))
        if not code:
            raise AuditError("every hold needs a course code")
        holds.append({"code": code, "not_before": term(h.get("not_before"), "hold term")})
    normalized = {"settings": settings, "pins": pins, "holds": holds, "overload_note": note}
    edits = Edits(tuple(Pin(**p) for p in pins), tuple(Hold(**h) for h in holds))
    return settings, edits, normalized


def fingerprint(body: dict, edits: dict, plan: dict | None) -> str:
    """SHA-256 of the record, the edits and the planner's output (spec 06, US-6.4). Any change to
    one of them changes the fingerprint, which is how an approval goes out of date."""
    record = {"program_id": body.get("program_id"), "start_term": body.get("start_term"),
              "taken": sorted((course_code(t.get("code", "")), t.get("grade") or "") for t in body.get("taken", [])),
              "transfer": sorted((str(t.get("school") or t.get("school_id") or ""), str(t.get("subject", "")),
                                  str(t.get("number", "")), t.get("grade") or "") for t in body.get("transfer", []))}
    planned = [[t["term"], sorted(c["code"] for c in t["courses"])] for t in (plan or {}).get("terms", [])]
    blob = json.dumps({"record": record, "edits": edits, "plan": planned}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def compute_audit(body: dict) -> dict:
    """Run transfer translation, the audit and (with a start term) the forecast. Raises AuditError."""
    catalog, programs = catalog_and_programs()
    if not body.get("program_id"):
        raise AuditError("program_id is required")
    program = programs.get(body.get("program_id"))
    if program is None:
        raise AuditError(f"program_id must be one of {', '.join(programs)}", 404)
    start_term = body.get("start_term")
    if start_term:
        try:
            start_term = parse_term(start_term).code
        except ValueError as e:
            raise AuditError(str(e)) from e

    taken: list[Taken] = []
    for r in body.get("taken", []):
        if not r.get("code"):
            raise AuditError("every taken course needs a code")
        code = course_code(r["code"])
        credits = _number(r["credits"], f"{code} credits") if r.get("credits") else catalog.credits(code)
        taken.append(Taken(code, credits, _grade(r.get("grade"), code)))
    for r in body.get("transfer", []):
        _grade(r.get("grade"), f"transfer {r.get('subject', '')} {r.get('number', '')}".strip())
    transfer_taken, transfer_report = translate_transfer(body.get("transfer", []), catalog)
    taken += transfer_taken

    s = body.get("settings") or {}
    overrides, edits, edits_out = parse_edits(body.get("edits"), start_term)
    settings = Settings(include_summer=bool(overrides.get("include_summer", s.get("include_summer", False))),
                        max_hours=overrides.get("max_hours", _number(s.get("max_hours", 18), "settings.max_hours", int)),
                        target_hours=overrides.get("target_hours",
                                                   _number(s.get("target_hours", 15), "settings.target_hours", int)))
    if settings.target_hours > settings.max_hours:
        settings = Settings(include_summer=settings.include_summer, max_hours=settings.max_hours,
                            target_hours=settings.max_hours)
    result = audit(program, catalog, taken)
    plan = project(program, catalog, taken, result, start_term, settings, edits) if start_term else None
    if plan is not None:
        result.projected_term = plan.projected_term

    out = asdict(result)
    out.update(
        program_id=program.id,
        program_name=f"{program.degree} {program.name}",
        catalog_year=program.catalog_year,
        transfer=transfer_report,
        transfer_hours=sum(t.credits for t in transfer_taken),
        in_progress={"term": current_term(), "courses": [
            {"code": t.code, "title": catalog.courses[t.code].title if t.code in catalog.courses else t.code,
             "credits": t.credits} for t in taken if t.in_progress]},
        plan=None if plan is None else {
            "start_term": plan.start_term, "complete": plan.complete,
            "free_elective_hours": plan.free_elective_hours,
            "terms": [asdict(t) for t in plan.terms]},
        unknown_codes=sorted({t.code for t in taken if t.code not in catalog.courses and not t.elective_only}),
    )
    # A course the catalog doesn't know counts for hours only; an advisor should check the record.
    unknown = [{"kind": "unknown_course", "code": c, "group": None,
                "message": f"{c} is not in the {program.catalog_year} catalog; it counts toward hours only"}
               for c in out["unknown_codes"]]
    out["warnings"] = unknown + ([] if plan is None else [asdict(w) for w in plan.warnings])
    if plan is not None:  # an admission gate is a heads-up for the student, not a reason for review
        planned = [c.code for t in plan.terms for c in t.courses]
        for item, message in program_gates(program.id):
            hit = [c for c in planned if matches(item, c, catalog)]
            if hit:
                out["warnings"].append({"kind": "gate", "code": hit[0], "group": None, "message": message})
    out["needs_review"] = bool(unknown) or bool(plan and plan.needs_review)
    out["edits"] = edits_out
    out["fingerprint"] = fingerprint(body, edits_out, out["plan"])
    if plan is not None:
        violations = verify(plan, catalog, taken, settings.max_hours,
                            holds=[(h.code, h.not_before) for h in edits.holds])
        pinned = {p.code for p in edits.pins}
        bad = [{"kind": "bad_pin", "code": v.code, "group": None, "message": f"Pinned by advisor: {v.message}"}
               for v in violations if v.code in pinned]
        if any(v.rule == "load" for v in violations) and pinned:
            bad += [{"kind": "bad_pin", "code": None, "group": None, "message": f"Pinned by advisor: {v.message}"}
                    for v in violations if v.rule == "load"]
        out["warnings"] += bad
        out["needs_review"] = out["needs_review"] or bool(violations)
        out["checks"] = {
            "prerequisites_ok": not any(v.rule in ("prerequisite", "standing") for v in violations),
            "offerings_ok": not any(v.rule == "offering" for v in violations),
            "violations": [asdict(v) for v in violations],
            "retakes": [r.code for r in result.retakes],
            "max_load": max((t.hours for t in plan.terms), default=0),
            "load_limit": settings.max_hours,
        }
    return out


@bp.post("/audit")
def run_audit():
    try:
        return jsonify(compute_audit(request.get_json(silent=True) or {}))
    except AuditError as e:
        return _err(str(e), e.status)


# --- Catalog and demo data -------------------------------------------------------------------------


@bp.get("/programs")
def list_programs():
    _, programs = catalog_and_programs()
    return jsonify([{"id": p.id, "name": p.name, "degree": p.degree, "catalog_year": p.catalog_year,
                     "total_hours": p.total_hours} for p in programs.values()])


def course_info(code: str) -> dict | None:
    """Everything the catalog says about one course, and which requirement groups it can fill."""
    catalog, programs = catalog_and_programs()
    code = course_code(code)
    c = catalog.courses.get(code)
    if c is None:
        return None
    fills = [{"program": p.id, "group": g.id, "name": g.name} for p in programs.values() for g in p.groups
             if any(matches(i, code, catalog) for i in g.items)]
    return {
        "code": c.code, "title": c.title, "credits": c.credits,
        "prerequisites": [{"any_of": list(pg.any_of), "min_grade": pg.min_grade}
                          for pg in catalog.prereqs.get(code, ())],
        "offered": describe_offerings(catalog.offered.get(code, ())),
        "min_hours": catalog.min_hours.get(code),
        "tags": sorted(catalog.tags.get(code, ())),
        "unlocks": sorted(k for k, pgs in catalog.prereqs.items() if any(code in pg.any_of for pg in pgs)),
        "fills": fills,
    }


@bp.get("/courses/<path:code>/info")
def get_course_info(code):
    info = course_info(code)
    return jsonify(info) if info else _err(f"{course_code(code)} is not in the catalog", 404)


def demo_students() -> list[dict]:
    """Fictional students. Schools are named in the files and resolved to ids here."""
    out = []
    for f in sorted(DEMO_STUDENTS.glob("*.json")):
        s = json.loads(f.read_text())
        for t in s.get("transfer", []):
            school = find_school(name=t.get("school"))
            t["school_id"] = school.id if school else None
        out.append(s)
    return out


@bp.get("/demo/students")
def list_demo_students():
    return jsonify(demo_students())


@bp.get("/students")
def advisor_students():
    """The advisor's list: one summary row per (fictional) student, computed by the real planner."""
    rows = []
    for s in demo_students():
        try:
            r = compute_audit(s)
        except AuditError:
            continue
        rows.append({
            "id": s["id"], "student_number": s.get("student_number"), "name": s["name"],
            "program": r["program_name"], "hours_done": r["hours_done"],
            "hours_in_progress": r["hours_in_progress"], "hours_required": r["hours_required"],
            "projected_term": r["projected_term"],
            "complete": bool(r["plan"] and r["plan"]["complete"]),
            "flags": {
                "needs_review": r["needs_review"],
                "retake": bool(r["retakes"]),
                "transfer_pending": any(t["status"] in ("proposed", "unknown") for t in r["transfer"]),
            },
            "first_warning": r["warnings"][0]["message"] if r["warnings"] else None,
            "pending_transfer": sorted(t["external"] for t in r["transfer"] if t["status"] in ("proposed", "unknown")),
        })
    return jsonify(rows)
