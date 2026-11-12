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
    assert "cs-bs-2026-27" in [p["id"] for p in programs] and len(programs) == 5  # spec 07 added four
    students = demo_client.get("/api/demo/students").get_json()
    assert len(students) == 13 and all("(fictional)" in s["name"] for s in students)
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
    assert "flag it for review" in by["HIST 2010"]["note"]
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


def test_audit_api_rejects_empty_or_missing_program(demo_client):
    empty = demo_client.post("/api/audit")
    assert empty.status_code == 400 and "program_id is required" in empty.get_json()["error"]
    assert demo_client.post("/api/audit", json={}).status_code == 400


def test_audit_api_rejects_unknown_grades(demo_client):
    r = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27",
                                             "taken": [{"code": "CS 1213", "grade": "Q"}]})
    assert r.status_code == 400 and "CS 1213" in r.get_json()["error"]
    ok = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "taken": [
        {"code": "CS 1213", "grade": "b+"}, {"code": "CS 1223", "grade": "W"}, {"code": "MA 1314", "grade": None}]})
    assert ok.status_code == 200


def test_audit_api_rejects_non_numeric_numbers(demo_client):
    base = {"program_id": "cs-bs-2026-27", "start_term": "2027SP"}
    assert demo_client.post("/api/audit", json={**base, "settings": {"max_hours": "lots"}}).status_code == 400
    assert demo_client.post("/api/audit", json={**base, "taken": [
        {"code": "CS 1213", "credits": "three", "grade": "A"}]}).status_code == 400


def test_unknown_course_code_warns_and_needs_review(demo_client):
    r = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "start_term": "2027SP",
                                             "taken": [{"code": "ZZ 9999", "credits": 3, "grade": "A"}]}).get_json()
    assert r["unknown_codes"] == ["ZZ 9999"] and r["needs_review"] is True
    assert any(w["kind"] == "unknown_course" and w["code"] == "ZZ 9999" for w in r["warnings"])


def test_audit_api_normalizes_codes_and_fills_credits(demo_client):
    r = demo_client.post("/api/audit", json={"program_id": "cs-bs-2026-27", "start_term": "2027SP",
                                             "taken": [{"code": "cs1213", "grade": "A"}]}).get_json()
    assert r["hours_done"] == 3 and r["unknown_codes"] == []


def test_advisor_student_list(demo_client):
    rows = {r["id"]: r for r in demo_client.get("/api/students").get_json()}
    assert len(rows) == 13
    assert rows["demo-04"]["flags"]["retake"] and rows["demo-03"]["flags"]["transfer_pending"]
    assert rows["demo-02"]["projected_term"] == "2028FA" and rows["demo-02"]["student_number"] == "L00402115"


def test_advisor_list_names_the_pending_transfer_courses(demo_client):
    """#2: the advisee list says which transfer courses are waiting, not just that some are."""
    rows = {r["id"]: r for r in demo_client.get("/api/students").get_json()}
    assert rows["demo-03"]["pending_transfer"] == ["CIS 2350", "HIST 2010"]
    assert rows["demo-02"]["pending_transfer"] == []


def test_course_info(demo_client):
    info = demo_client.get("/api/courses/CS 2233/info").get_json()
    assert info["title"] == "Data Structures" and "CS 2623" in info["unlocks"]
    assert any(f["group"] == "major-core" for f in info["fills"])
    assert demo_client.get("/api/courses/ZZ 9999/info").status_code == 404


def test_plan_checks_and_in_progress(demo_client):
    r = demo_client.post("/api/audit", json=_student(demo_client, "demo-04")).get_json()
    assert r["checks"]["prerequisites_ok"] and r["checks"]["retakes"] == ["CS 2233"]
    assert r["checks"]["max_load"] <= r["checks"]["load_limit"]
    assert r["in_progress"]["term"] == "2026FA" and {c["code"] for c in r["in_progress"]["courses"]} >= {"CS 2243"}
    core = next(g for g in r["groups"] if g["id"] == "major-core")
    assert 0 < core["done_hours"] <= core["counted_hours"] <= core["required_hours"]
