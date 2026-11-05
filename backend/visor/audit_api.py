"""Degree audit + forecast API (spec 05; contract extends spec 04's ``POST /api/audit``).

Nothing here writes to the database: the audit takes the student's courses in the request and
returns a result (spec 04, "No student records are stored in v1"). Transfer courses go through the
same equivalency rows the lookup page uses, read-only — an unknown course is reported, not recorded.

``compute_audit()`` is the one entry point; the HTTP routes and the Ask Visor tools both call it, so
the chat can never describe a plan the planner did not produce.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, jsonify, request

from .catalog_files import DEFAULT_CATALOG, load_catalog
from .equivalencies import _live_rows
from .models import ExternalCourse, School, db
from .rules.audit import Taken, audit, matches
from .rules.forecast import Settings, project
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


def current_term() -> str:
    """The term in progress now. Configuration, never the clock (spec 05)."""
    return parse_term(os.environ.get("VISOR_CURRENT_TERM", "2026FA")).code


def course_code(raw: str) -> str:
    """'cs2233', ' CS  2233 ' -> 'CS 2233'."""
    s = "".join(str(raw).split()).upper()
    i = next((k for k, ch in enumerate(s) if ch.isdigit()), len(s))
    return f"{s[:i]} {s[i:]}".strip()


# --- Transfer --------------------------------------------------------------------------------------


def find_school(school_id=None, name: str | None = None) -> School | None:
    if isinstance(school_id, int):
        return db.session.get(School, school_id)
    if name:
        n = name.strip().lower()
        return next((s for s in School.query.all() if s.name.lower() == n or n in s.name.lower()), None)
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
    settings = Settings(include_summer=bool(s.get("include_summer", False)),
                        max_hours=_number(s.get("max_hours", 18), "settings.max_hours", int),
                        target_hours=_number(s.get("target_hours", 15), "settings.target_hours", int))
    result = audit(program, catalog, taken)
    plan = project(program, catalog, taken, result, start_term, settings) if start_term else None
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
    out["needs_review"] = bool(unknown) or bool(plan and plan.needs_review)
    if plan is not None:
        violations = verify(plan, catalog, taken, settings.max_hours)
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
        })
    return jsonify(rows)
