"""Claude-proposed equivalencies (spec 07, US-7.2). No API calls: the batch client is faked."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from visor import create_app
from visor.models import Equivalency, ExternalCourse, School, db
from visor.propose import candidates, checked, plan, run
from visor.seed import load, load_equivalencies, load_proposals

ROOT = Path(__file__).resolve().parents[2]
LIPSCOMB = [{"subject": "CS", "number": "1213", "title": "Computer Science I", "credits": "3"},
            {"subject": "CS", "number": "2233", "title": "Data Structures", "credits": "3"},
            {"subject": "IT", "number": "1113", "title": "Introduction to Information Technology", "credits": "3"},
            {"subject": "MA", "number": "1314", "title": "Calculus I", "credits": "4"}]


def test_candidates_come_from_the_subject_family_ranked_by_title():
    ext = {"subject": "CISP", "number": "1010", "title": "Computer Science I", "school": "X"}
    got = [f"{c['subject']} {c['number']}" for c in candidates(ext, LIPSCOMB)]
    assert got[0] == "CS 1213" and "MA 1314" not in got
    assert candidates({"subject": "WELD", "number": "1010", "title": "Welding"}, LIPSCOMB) == []  # not asked


def test_proposals_are_checked_against_the_catalog():
    cands = LIPSCOMB[:2]
    assert checked({"kind": "direct", "lipscomb_code": "CS 1213", "confidence": 0.9, "reason": "Same."}, cands)[0]
    row, why = checked({"kind": "direct", "lipscomb_code": "CS 9999", "confidence": 0.9, "reason": "?"}, cands)
    assert row is None and "not a candidate" in why
    assert checked({"kind": "elective", "lipscomb_code": "CS 1213", "confidence": 1, "reason": ""}, cands)[0] is None
    assert checked({"kind": "elective", "lipscomb_code": None, "confidence": 7, "reason": "x"}, cands)[0]["confidence"] == 1.0


class FakeBatches:
    def __init__(self, answers):
        self.answers, self.requests = answers, None

    def create(self, requests):
        self.requests = requests
        return SimpleNamespace(id="msgbatch_test")

    def retrieve(self, _id):
        return SimpleNamespace(processing_status="ended", request_counts=SimpleNamespace(succeeded=1, processing=0))

    def results(self, _id):
        for r in self.requests:
            text = json.dumps(self.answers.get(r["custom_id"], {"kind": "none", "lipscomb_code": None,
                                                                "confidence": 0.9, "reason": "Unrelated."}))
            yield SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(
                type="succeeded", message=SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])))


def test_run_writes_only_checked_proposals(tmp_path):
    root = tmp_path / "external"
    (root / "demo").mkdir(parents=True)
    (root / "schools.csv").write_text("slug,name,state,kind,catalog_url\ndemo,Demo Community College,TN,community_college,\n")
    with open(root / "demo" / "courses.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "number", "title", "credits", "description", "catalog_year", "source_url"])
        w.writeheader()
        w.writerow({"subject": "CISP", "number": "1010", "title": "Computer Science I", "credits": "4", "description": "",
                    "catalog_year": "2026", "source_url": "https://x"})
        w.writerow({"subject": "CISP", "number": "1020", "title": "Computer Science II", "credits": "4", "description": "",
                    "catalog_year": "2026", "source_url": "https://x"})
        w.writerow({"subject": "WELD", "number": "1010", "title": "Welding", "credits": "3", "description": "",
                    "catalog_year": "2026", "source_url": "https://x"})
    lip = tmp_path / "courses.csv"
    with open(lip, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "number", "title", "credits"])
        w.writeheader()
        w.writerows(LIPSCOMB)
    jobs = plan(root, lip)
    assert [j[0] for j in jobs] == ["demo-CISP-1010", "demo-CISP-1020"]  # welding is never asked about
    batches = FakeBatches({"demo-CISP-1010": {"kind": "direct", "lipscomb_code": "CS 1213", "confidence": 0.92,
                                              "reason": "Same first programming course."},
                           "demo-CISP-1020": {"kind": "direct", "lipscomb_code": "CS 4999", "confidence": 0.8,
                                              "reason": "Made up."}})
    out = tmp_path / "proposed.csv"
    summary = run(SimpleNamespace(messages=SimpleNamespace(batches=batches)), jobs, out, poll=0, log=lambda *_: None)
    rows = list(csv.DictReader(open(out)))
    assert summary["proposals"] == 1 and summary["dropped"] == 1
    assert rows == [{"school": "Demo Community College", "external": "CISP 1010", "lipscomb": "CS 1213", "kind": "direct",
                     "confidence": "0.92", "reason": "Same first programming course."}]


@pytest.fixture()
def app():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app
        db.drop_all()


def write_proposals(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["school", "external", "lipscomb", "kind", "confidence", "reason"])
        w.writeheader()
        w.writerows(rows)


def test_seed_never_confirms_ai_proposals(app, tmp_path):
    nscc = School.query.filter_by(name="Nashville State Community College").one()
    db.session.add(ExternalCourse(school_id=nscc.id, subject="CISP", number="2410", title="Java II", credits=4,
                                  catalog_year="2026"))
    db.session.commit()
    p = tmp_path / "p.csv"
    write_proposals(p, [
        {"school": nscc.name, "external": "CISP 2410", "lipscomb": "CS 2233", "kind": "direct", "confidence": "0.7", "reason": "r"},
        {"school": nscc.name, "external": "CISP 1010", "lipscomb": "CS 2233", "kind": "direct", "confidence": "0.4", "reason": "r"},
        {"school": nscc.name, "external": "CISP 2410", "lipscomb": "", "kind": "none", "confidence": "0.9", "reason": "r"}])
    added = load_proposals(p)
    rows = Equivalency.query.filter_by(source="ai_proposed").all()
    assert added == len(rows) == 2  # "none" answers are not stored
    assert all(r.status == "proposed" and r.decided_by is None for r in rows)
    assert load_proposals(p) == 0  # idempotent


def test_ai_proposals_never_count(app, tmp_path):
    nscc = School.query.filter_by(name="Nashville State Community College").one()
    db.session.add(ExternalCourse(school_id=nscc.id, subject="CISP", number="2410", title="Java II", credits=4,
                                  catalog_year="2026"))
    db.session.commit()
    p = tmp_path / "p.csv"
    write_proposals(p, [{"school": nscc.name, "external": "CISP 2410", "lipscomb": "CS 2233", "kind": "direct",
                         "confidence": "0.95", "reason": "r"}])
    load_proposals(p)
    c = app.test_client()
    s = next(x for x in c.get("/api/demo/students").get_json() if x["id"] == "demo-01")
    s["transfer"] = [{"school": nscc.name, "subject": "CISP", "number": "2410", "grade": "A"}]
    r = c.post("/api/audit", json=s).get_json()
    t = r["transfer"][0]
    assert t["status"] == "proposed" and t["counts_as"] == "CS 2233" and not t["counted"]
    assert "CS 2233" not in {u["code"] for g in r["groups"] for u in g["used"]}


def test_reasons_lose_control_characters(app, tmp_path):
    """Postgres rejects NUL bytes in text; one of Claude's reasons had one (#46)."""
    row, _ = checked({"kind": "elective", "lipscomb_code": None, "confidence": 0.5, "reason": "versus L\x00ipscomb\x07"}, [])
    assert row["reason"] == "versus Lipscomb"
    nscc = School.query.filter_by(name="Nashville State Community College").one()
    db.session.add(ExternalCourse(school_id=nscc.id, subject="CISP", number="2410", title="Java II", credits=4,
                                  catalog_year="2026"))
    db.session.commit()
    p = tmp_path / "p.csv"
    write_proposals(p, [{"school": nscc.name, "external": "CISP 2410", "lipscomb": "CS 2233", "kind": "direct",
                         "confidence": "0.7", "reason": "bad\x00byte"}])
    load_proposals(p)
    assert "\x00" not in Equivalency.query.filter_by(source="ai_proposed").one().notes


def test_committed_proposals_are_clean():
    import re
    text = (ROOT / "data" / "external" / "proposed_equivalencies.csv").read_text()
    assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text)
