"""Spec 05: POST /api/audit end to end (real 2026-27 catalog + fictional demo equivalencies)."""
from pathlib import Path

import pytest

from visor import create_app
from visor.models import Equivalency, ExternalCourse, School, db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def demo_client():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app.test_client()
        db.drop_all()


def _student(client, sid):
    return next(s for s in client.get("/api/demo/students").get_json() if s["id"] == sid)


def test_programs_and_demo_students(demo_client):
    programs = demo_client.get("/api/programs").get_json()
    assert [p["id"] for p in programs] == ["cs-bs-2026-27"]
    students = demo_client.get("/api/demo/students").get_json()
    assert len(students) == 5 and all("(fictional)" in s["name"] for s in students)
    sam = next(s for s in students if s["id"] == "demo-03")
    assert all(isinstance(t["school_id"], int) for t in sam["transfer"])


def test_audit_api_transfer_statuses(demo_client):
    r = demo_client.post("/api/audit", json=_student(demo_client, "demo-03")).get_json()
    by = {t["external"]: t for t in r["transfer"]}
    assert by["CISP 1020"] == {**by["CISP 1020"], "status": "confirmed", "counts_as": "CS 2233", "counted": True}
    assert by["ENGL 1010"]["counted"] and "elective" in by["ENGL 1010"]["counts_as"]
    assert by["PHED 1110"]["status"] == "confirmed" and not by["PHED 1110"]["counted"]
    assert by["CIS 2350"]["status"] == "proposed" and not by["CIS 2350"]["counted"]
    assert by["HIST 2010"]["status"] == "unknown" and not by["HIST 2010"]["counted"]
    # The confirmed CS 2233 counts in the major core, and the plan starts above it.
    core = next(g for g in r["groups"] if g["id"] == "major-core")
    assert any(u["code"] == "CS 2233" and u["via"] == "completed" for u in core["used"]) is False
    assert any(u["code"] == "CS 2233" and u["detail"].startswith("Nashville State") for u in core["used"])
    planned = [c["code"] for t in r["plan"]["terms"] for c in t["courses"]]
    assert "CS 2233" not in planned and "CS 1213" not in planned


def test_audit_api_stores_nothing(demo_client):
    before = (ExternalCourse.query.count(), Equivalency.query.count(), School.query.count())
    demo_client.post("/api/audit", json=_student(demo_client, "demo-03"))
    assert (ExternalCourse.query.count(), Equivalency.query.count(), School.query.count()) == before


def test_audit_api_validation(demo_client):
    assert demo_client.post("/api/audit", json={"program_id": "nope"}).status_code == 404
    bad = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "start_term": "Fall 27"})
    assert bad.status_code == 400
    no_term = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "taken": []}).get_json()
    assert no_term["plan"] is None and no_term["projected_term"] is None


def test_audit_api_normalizes_codes_and_fills_credits(demo_client):
    r = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "start_term": "2027SP",
                                             "taken": [{"code": "cs1213", "grade": "A"}]}).get_json()
    assert r["hours_done"] == 3 and r["unknown_codes"] == []
