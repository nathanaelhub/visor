"""Course lists scraped from the top five transfer schools' public catalogs (spec 07, US-7.1)."""
import csv
import re
from pathlib import Path

import pytest

from visor import create_app
from visor.models import ExternalCourse, School, db
from visor.seed import load, load_equivalencies, load_external_catalogs

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "data" / "external"
SCHOOLS = list(csv.DictReader(open(EXTERNAL / "schools.csv", newline="")))


def rows(slug):
    with open(EXTERNAL / slug / "courses.csv", newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("slug", [s["slug"] for s in SCHOOLS])
def test_external_catalogs_are_clean(slug):
    courses = rows(slug)
    assert len(courses) >= 200, f"{slug}: only {len(courses)} courses"
    codes = [(c["subject"], c["number"]) for c in courses]
    assert len(codes) == len(set(codes)), "duplicate course codes"
    for c in courses:
        assert re.fullmatch(r"[A-Z][A-Z&]{1,5}", c["subject"]) and re.match(r"\d", c["number"]), c
        assert not c["number"].startswith("0"), "learning-support courses are not college credit"
        assert c["title"] and c["credits"] and float(c["credits"]) >= 0, c  # 0-credit courses exist (portfolio reviews)
        assert re.fullmatch(r"20\d\d", c["catalog_year"]) and c["source_url"].startswith("https://"), c
        assert len(c["description"]) <= 400


@pytest.fixture()
def app():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app
        db.drop_all()


def test_seed_loads_external_catalogs(app):
    added = load_external_catalogs(EXTERNAL)
    for s in SCHOOLS:
        school = School.query.filter_by(name=s["name"]).one()
        codes = {(c["subject"], c["number"]) for c in rows(s["slug"])}
        stored = {(e.subject, e.number) for e in ExternalCourse.query.filter_by(school_id=school.id)}
        assert codes <= stored, s["slug"]
        assert added[s["slug"]] > 0
    assert sum(load_external_catalogs(EXTERNAL).values()) == 0  # idempotent


def test_lookup_shows_scraped_title(app):
    load_external_catalogs(EXTERNAL)
    school = School.query.filter_by(name="University of Tennessee at Chattanooga").one()
    course = rows("utc")[0]
    r = app.test_client().post("/api/equivalencies/lookup", json={
        "school_id": school.id, "subject": course["subject"], "number": course["number"]})
    body = r.get_json()
    assert r.status_code == 200 and body["status"] == "unknown"
    assert body["external_course"]["title"] == course["title"][:160]


def test_transfer_page_examples_show_what_they_promise(app):
    """R3-F2: the Transfer page suggests three lookups, one per status; seeded the way production is."""
    from visor.seed import load_proposals
    load_external_catalogs(EXTERNAL)
    load_proposals(EXTERNAL / "proposed_equivalencies.csv")
    c = app.test_client()
    schools = {s["name"]: s["id"] for s in c.get("/api/schools").get_json()}
    for school, subject, number, status in [("Nashville State Community College", "CISP", "1020", "confirmed"),
                                            ("Columbia State Community College", "CSCI", "1020", "proposed"),
                                            ("Nashville State Community College", "ADMN", "1305", "unknown")]:
        r = c.post("/api/equivalencies/lookup", json={"school_id": schools[school], "subject": subject, "number": number})
        assert r.get_json()["status"] == status, (subject, number)
    hint = (ROOT / "frontend" / "src" / "views" / "Transfer.jsx").read_text()
    assert "ADMN 1305" in hint and "HIST 2010" not in hint
