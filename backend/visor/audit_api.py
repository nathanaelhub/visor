"""Degree audit + forecast API (spec 05; contract extends spec 04's ``POST /api/audit``).

Nothing here writes to the database: the audit takes the student's courses in the request and
returns a result (spec 04, "No student records are stored in v1"). Transfer courses go through the
same equivalency rows the lookup page uses, read-only — an unknown course is reported, not recorded.
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
from .rules.audit import Taken, audit
from .rules.forecast import Settings, project
from .rules.terms import parse_term

bp = Blueprint("audit", __name__, url_prefix="/api")

DEMO_STUDENTS = Path(__file__).resolve().parents[2] / "data" / "demo" / "students"


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _catalog():
    return load_catalog(os.environ.get("VISOR_CATALOG_DIR", str(DEFAULT_CATALOG)))


def _code(raw: str) -> str:
    """'cs2233', ' CS  2233 ' -> 'CS 2233'."""
    s = "".join(str(raw).split()).upper()
    i = next((k for k, ch in enumerate(s) if ch.isdigit()), len(s))
    return f"{s[:i]} {s[i:]}".strip()


@bp.get("/programs")
def list_programs():
    _, programs = _catalog()
    return jsonify([{"id": p.id, "name": p.name, "degree": p.degree, "catalog_year": p.catalog_year,
                     "total_hours": p.total_hours} for p in programs.values()])


@bp.get("/demo/students")
def demo_students():
    """Fictional students for the Degree Progress tab. Schools are given by name in the files and
    resolved to ids here, so the files don't depend on database ids."""
    schools = {s.name: s.id for s in School.query.all()}
    out = []
    for f in sorted(DEMO_STUDENTS.glob("*.json")):
        s = json.loads(f.read_text())
        for t in s.get("transfer", []):
            t["school_id"] = schools.get(t.pop("school", None))
        out.append(s)
    return jsonify(out)


def _translate_transfer(rows: list[dict], catalog) -> tuple[list[Taken], list[dict]]:
    """Each transfer course -> what it counts as. Only `confirmed` counts (spec 04)."""
    taken, report = [], []
    for r in rows:
        school = db.session.get(School, r.get("school_id")) if isinstance(r.get("school_id"), int) else None
        subject, number = str(r.get("subject", "")).strip().upper(), str(r.get("number", "")).strip()
        label = f"{school.name if school else 'Unknown school'}: {subject} {number}"
        entry = {"school": school.name if school else None, "external": f"{subject} {number}",
                 "status": "unknown", "counts_as": None, "counted": False, "note": ""}
        ext = (ExternalCourse.query.filter_by(school_id=school.id, subject=subject, number=number)
               .order_by(ExternalCourse.catalog_year.desc()).first()) if school else None
        if ext is None:
            entry["note"] = "Not in the equivalency table yet; look it up and flag it for review."
            report.append(entry)
            continue
        confirmed, proposed, _ = _live_rows(ext)
        grade = r.get("grade") or "TR"
        if confirmed:
            q = confirmed[0]
            entry["status"] = "confirmed"
            if q.kind == "direct" and q.course is not None:
                entry.update(counts_as=q.course.code, counted=True)
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
            entry.update(status="proposed", counts_as=proposed[0].course.code if proposed[0].course else None,
                         note="Pending: a person has to confirm this before it counts.")
        report.append(entry)
    return taken, report


@bp.post("/audit")
def run_audit():
    body = request.get_json(silent=True) or {}
    catalog, programs = _catalog()
    program = programs.get(body.get("program_id"))
    if program is None:
        return _err(f"program_id must be one of {', '.join(programs)}", 404)
    start_term = body.get("start_term")
    if start_term:
        try:
            start_term = parse_term(start_term).code
        except ValueError as e:
            return _err(str(e))

    taken: list[Taken] = []
    for r in body.get("taken", []):
        if not r.get("code"):
            return _err("every taken course needs a code")
        code = _code(r["code"])
        credits = r.get("credits") or catalog.credits(code)
        taken.append(Taken(code, float(credits), r.get("grade") or None))
    transfer_taken, transfer_report = _translate_transfer(body.get("transfer", []), catalog)
    taken += transfer_taken

    s = body.get("settings") or {}
    settings = Settings(include_summer=bool(s.get("include_summer", False)),
                        max_hours=int(s.get("max_hours", 18)), target_hours=int(s.get("target_hours", 15)))
    result = audit(program, catalog, taken)
    plan = project(program, catalog, taken, result, start_term, settings) if start_term else None
    if plan is not None:
        result.projected_term = plan.projected_term

    out = asdict(result)
    out.update(
        transfer=transfer_report,
        plan=None if plan is None else {
            "start_term": plan.start_term, "complete": plan.complete,
            "free_elective_hours": plan.free_elective_hours,
            "terms": [asdict(t) for t in plan.terms]},
        warnings=[] if plan is None else [asdict(w) for w in plan.warnings],
        needs_review=bool(plan and plan.needs_review),
        unknown_codes=sorted({t.code for t in taken if t.code not in catalog.courses
                              and not t.elective_only}),
    )
    return jsonify(out)
