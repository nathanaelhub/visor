"""Biology, Management (B.B.A.), Nursing (BSN) and Psychology next to Computer Science (spec 07, US-7.3)."""
import csv
from pathlib import Path

import pytest

from visor import create_app
from visor.models import db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]
NEW = {"bio-bs-2026-27", "mgmt-bba-2026-27", "nursing-bsn-2026-27", "psych-bs-2026-27"}
FIVE = {r["name"] for r in csv.DictReader(open(ROOT / "data" / "external" / "schools.csv"))}


@pytest.fixture()
def client():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app.test_client()
        db.drop_all()


def students(client):
    return client.get("/api/demo/students").get_json()


def test_programs_are_listed(client):
    ids = {p["id"] for p in client.get("/api/programs").get_json()}
    assert ids == NEW | {"cs-bs-2026-27"}


def test_every_program_plans_cleanly(client):
    for s in students(client):
        r = client.post("/api/audit", json=s).get_json()
        assert "plan" in r, (s["id"], r)
        assert r["checks"]["violations"] == [], (s["id"], r["checks"]["violations"])
        unplaced = [w["message"] for w in r["warnings"] if w["kind"] == "unplaceable"]
        assert not unplaced, (s["id"], unplaced)
        assert r["projected_term"] or r["plan"]["complete"], s["id"]


def test_each_new_major_has_a_first_year_and_a_transfer_student(client):
    by_program = {}
    for s in students(client):
        by_program.setdefault(s["program_id"], []).append(s)
    for pid in NEW:
        group = by_program.get(pid, [])
        assert len(group) >= 2, pid
        transfers = [s for s in group if s.get("transfer")]
        assert transfers and all(t["school"] in FIVE for s in transfers for t in s["transfer"]), pid


def test_nursing_admission_is_a_warning_not_a_rule(client):
    s = next(s for s in students(client) if s["program_id"] == "nursing-bsn-2026-27")
    r = client.post("/api/audit", json=s).get_json()
    gates = [w for w in r["warnings"] if w["kind"] == "gate"]
    assert gates and "admission to the nursing program" in gates[0]["message"]
    cs = next(s for s in students(client) if s["id"] == "demo-02")
    assert not [w for w in client.post("/api/audit", json=cs).get_json()["warnings"] if w["kind"] == "gate"]


def test_cs_plans_are_unchanged(client):
    """Adding programs must not move a single CS course (the catalog rows CS uses are left alone)."""
    expected = {"demo-01": "2030SP", "demo-02": "2028FA", "demo-03": "2029FA", "demo-04": "2029SP"}
    got = {s["id"]: client.post("/api/audit", json=s).get_json()["projected_term"] for s in students(client)
           if s["id"] in expected}
    assert got == expected


def test_one_demo_student_needs_review(client):
    """F12: the advisor demo needs a plan that asks for review, for a reason a real record would have."""
    flagged = {s["id"]: client.post("/api/audit", json=s).get_json() for s in students(client)}
    flagged = {k: r for k, r in flagged.items() if r["needs_review"]}
    assert list(flagged) == ["demo-14"]
    r = flagged["demo-14"]
    assert [w["code"] for w in r["warnings"] if w["kind"] == "unknown_course"] == ["CS 2113"]
    assert r["projected_term"]  # the rest of the plan still works
