"""Advisor edits and plan approval (spec 06). Uses Jordan Rivera (demo-02, plan starts Spring 2027),
whose default plan has CS 2623 and CS 3123 in Spring 2027 and IT 3313 in Fall 2027."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from visor import create_app
from visor.models import db
from visor.rules.audit import Taken
from visor.rules.terms import parse_term
from visor.rules.verify import verify
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("VISOR_WRITE_TOKEN", raising=False)
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app.test_client()
        db.drop_all()


def jordan(client, **edits):
    s = next(x for x in client.get("/api/demo/students").get_json() if x["id"] == "demo-02")
    return {**s, "edits": edits} if edits else s


def audit(client, student):
    r = client.post("/api/audit", json=student)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def where(r, code):
    return next((t["term"] for t in r["plan"]["terms"] for c in t["courses"] if c["code"] == code), None)


def course(r, code):
    return next(c for t in r["plan"]["terms"] for c in t["courses"] if c["code"] == code)


# --- US-6.1 settings -------------------------------------------------------------------------------

def test_settings_edits_change_the_plan(client):
    base = audit(client, jordan(client))
    summer = audit(client, jordan(client, settings={"include_summer": True}))
    assert not any(t["term"].endswith("SU") for t in base["plan"]["terms"])
    assert any(t["term"].endswith("SU") for t in summer["plan"]["terms"])
    light = audit(client, jordan(client, settings={"target_hours": 12, "max_hours": 12}))
    assert max(t["hours"] for t in light["plan"]["terms"]) <= 12
    assert len(light["plan"]["terms"]) > len(base["plan"]["terms"])


def test_overload_needs_a_note(client):
    def post(**settings):
        return client.post("/api/audit", json=jordan(client, settings=settings,
                                                     **({"overload_note": "Final year"} if "note" in settings else {})))
    assert post(max_hours=20).status_code == 400
    assert post(max_hours=22, note=1).status_code == 400
    assert post(max_hours=11).status_code == 400
    ok = client.post("/api/audit", json=jordan(client, settings={"max_hours": 20, "target_hours": 20},
                                               overload_note="Final year, approved by chair"))
    assert ok.status_code == 200
    assert ok.get_json()["edits"]["overload_note"] == "Final year, approved by chair"


def test_checker_uses_the_advisors_maximum(client):
    r = audit(client, jordan(client, settings={"max_hours": 21, "target_hours": 21}, overload_note="Final year"))
    assert r["checks"]["load_limit"] == 21 and r["checks"]["max_load"] == 21  # all 3-hour courses here
    assert not [v for v in r["checks"]["violations"] if v["rule"] == "load"]


# --- US-6.2 pins -----------------------------------------------------------------------------------

def test_pin_places_the_course(client):
    r = audit(client, jordan(client, pins=[{"code": "it3313", "term": "2028FA"}]))
    assert where(r, "IT 3313") == "2028FA"
    c = course(r, "IT 3313")
    assert c["pinned"] and any(x["text"] == "Pinned by your advisor" for x in c["reasons"])
    assert r["checks"]["violations"] == [] and not r["needs_review"]


def test_bad_pin_is_kept_and_flagged(client):
    r = audit(client, jordan(client, pins=[{"code": "CS 3123", "term": "2027FA"}]))  # Spring only
    assert where(r, "CS 3123") == "2027FA"  # kept where the advisor put it
    assert any(v["rule"] == "offering" and v["code"] == "CS 3123" for v in r["checks"]["violations"])
    assert r["needs_review"]
    assert any("Pinned by advisor" in w["message"] and "CS 3123" in w["message"] for w in r["warnings"])


def test_pin_for_a_course_not_needed_is_ignored(client):
    r = audit(client, jordan(client, pins=[{"code": "CS 1213", "term": "2027FA"}]))  # already passed
    assert where(r, "CS 1213") is None
    assert any(w["kind"] == "pin_ignored" and w["code"] == "CS 1213" for w in r["warnings"])


def test_pin_before_the_start_term_is_refused(client):
    r = client.post("/api/audit", json=jordan(client, pins=[{"code": "IT 3313", "term": "2026FA"}]))
    assert r.status_code == 400


# --- US-6.3 holds ----------------------------------------------------------------------------------

def test_hold_moves_the_course_and_its_dependents(client):
    r = audit(client, jordan(client, holds=[{"code": "CS 2623", "not_before": "2027FA"}]))
    held = where(r, "CS 2623")
    assert parse_term(held) >= parse_term("2027FA")
    c = course(r, "CS 2623")
    assert c["held_until"] == "2027FA" and any("Held until Fall 2027" in x["text"] for x in c["reasons"])
    order = {t["term"]: i for i, t in enumerate(r["plan"]["terms"])}
    for dep in ("CS 3633", "CS 4223"):
        assert order[where(r, dep)] > order[held]
    assert r["checks"]["violations"] == []


def test_checker_enforces_holds(client):
    from visor.audit_api import catalog_and_programs
    catalog, _ = catalog_and_programs()
    plan = SimpleNamespace(terms=[SimpleNamespace(term="2027SP", courses=[SimpleNamespace(code="CS 2623", credits=3)])])
    taken = [Taken("CS 2233", 3, "B")]
    assert verify(plan, catalog, taken) == []
    v = verify(plan, catalog, taken, holds=[("CS 2623", "2027FA")])
    assert [x.rule for x in v] == ["hold"]


# --- US-6.4 approval -------------------------------------------------------------------------------

def approve(client, student, fingerprint, **kw):
    return client.post(f"/api/students/{student['student_number']}/approval",
                       json={"student": student, "fingerprint": fingerprint, "approved_by": "Dr. Advisor",
                             "note": "Agreed in our meeting", **kw})


def test_approve_records_the_fingerprint(client):
    s = jordan(client, pins=[{"code": "IT 3313", "term": "2028FA"}])
    r = audit(client, s)
    assert len(r["fingerprint"]) == 64
    assert audit(client, s)["fingerprint"] == r["fingerprint"]  # same inputs, same fingerprint
    a = approve(client, s, r["fingerprint"])
    assert a.status_code == 201, a.get_json()
    got = client.get(f"/api/students/{s['student_number']}/plan-edits").get_json()
    assert got["approval"]["fingerprint"] == r["fingerprint"] and got["approval"]["approved_by"] == "Dr. Advisor"
    assert got["edits"]["pins"][0]["code"] == "IT 3313"  # approving saves the edits it approved


def test_cannot_approve_a_plan_that_fails_its_checks(client):
    s = jordan(client, pins=[{"code": "CS 3123", "term": "2027FA"}])
    r = audit(client, s)
    a = approve(client, s, r["fingerprint"])
    assert a.status_code == 409 and a.get_json()["error"] == "plan_fails_checks"
    assert approve(client, jordan(client), "0" * 64).get_json()["error"] == "plan_changed"


def test_student_sees_the_approval(client):
    s = jordan(client)
    approve(client, s, audit(client, s)["fingerprint"])
    got = client.get(f"/api/students/{s['student_number']}/plan-edits").get_json()
    assert got["approval"]["note"] == "Agreed in our meeting" and got["approval"]["approved_at"]


def test_approval_goes_out_of_date(client):
    s = jordan(client)
    first = audit(client, s)["fingerprint"]
    approve(client, s, first)
    changed = audit(client, jordan(client, holds=[{"code": "CS 2623", "not_before": "2027FA"}]))["fingerprint"]
    assert changed != first
    s2 = jordan(client)
    s2["taken"] = s2["taken"] + [{"code": "MU 1003", "grade": "A"}]
    assert audit(client, s2)["fingerprint"] != first
    approve(client, s, first)  # history: rows are only added
    assert len(client.get(f"/api/students/{s['student_number']}/plan-edits").get_json()["history"]) == 2


# --- US-6.5 storage and the chat -------------------------------------------------------------------

def test_saved_edits_round_trip(client):
    s = jordan(client)
    put = client.put(f"/api/students/{s['student_number']}/plan-edits",
                     json={"edits": {"holds": [{"code": "CS 2623", "not_before": "2027FA"}]}, "updated_by": "Dr. A"})
    assert put.status_code == 200
    got = client.get(f"/api/students/{s['student_number']}/plan-edits").get_json()
    assert got["edits"]["holds"] == [{"code": "CS 2623", "not_before": "2027FA"}] and got["updated_by"] == "Dr. A"
    bad = client.put(f"/api/students/{s['student_number']}/plan-edits", json={"edits": {"settings": {"max_hours": 30}}})
    assert bad.status_code == 400


def test_public_demo_does_not_save_edits(client, monkeypatch):
    monkeypatch.setenv("VISOR_WRITE_TOKEN", "letmein")
    s = jordan(client)
    key = s["student_number"]
    assert client.put(f"/api/students/{key}/plan-edits", json={"edits": {}}).status_code in (401, 403)
    assert approve(client, s, audit(client, s)["fingerprint"]).status_code in (401, 403)
    assert client.get(f"/api/students/{key}/plan-edits").get_json() == {
        "edits": None, "updated_by": None, "updated_at": None, "approval": None, "history": [], "can_save": False}
    ok = client.put(f"/api/students/{key}/plan-edits", json={"edits": {}}, headers={"X-Visor-Token": "letmein"})
    assert ok.status_code == 200
    assert os.environ["VISOR_WRITE_TOKEN"] == "letmein"


def test_chat_sees_advisor_edits(client):
    from visor.chat import _run_tool
    s = jordan(client, pins=[{"code": "IT 3313", "term": "2028FA"}])
    digest, _, _ = _run_tool("run_degree_audit", {}, s)
    fall28 = next(t for t in digest["plan"] if t["term"] == "Fall 2028")
    assert any(c["code"] == "IT 3313" and "Pinned by your advisor" in c["why"] for c in fall28["courses"])
