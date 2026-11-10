"""Start from a transcript (spec 05, US-5.7). A fake Anthropic client returns scripted structured
output, so these tests check Visor's side: what is sent, how the reply becomes a record, the
demo-only rule on the public site, the caps, and that nothing is stored or logged."""
import base64
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from visor import create_app
from visor.models import ChatUsage, db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]
KEY = "sk-ant-test-key-0123456789"
SHARED = "sk-ant-shared-0123456789"
SITE = "http://localhost"


def read(**over):
    """A structured-output reply as the schema in visor.transcript describes it."""
    body = {"is_transcript": True, "student_name": "Casey Lin",
            "courses": [{"code": "cs2233", "title": "Data Structures", "credits": 3, "grade": "D+",
                         "term": "Spring 2026"},
                        {"code": "CS 2243", "title": "Algorithms", "credits": 3, "grade": "IP",
                         "term": "Fall 2026"}],
            "transfer": [{"school": "Nashville State Community College", "subject": "CISP", "number": "1010",
                          "title": "Computer Science I", "credits": 4, "grade": "B"}],
            "unreadable": []}
    body.update(over)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(body))],
                           stop_reason="end_turn", model="claude-sonnet-5-5")


class FakeClient:
    def __init__(self, script):
        self.script, self.calls, self.keys = list(script), [], []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0)


@pytest.fixture()
def make(monkeypatch):
    monkeypatch.delenv("VISOR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VISOR_WRITE_TOKEN", raising=False)

    def _make(script=()):
        fake = FakeClient(script)
        app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True,
                          "ANTHROPIC_CLIENT_FACTORY": lambda key: (fake.keys.append(key), fake)[1]})
        ctx = app.app_context()
        ctx.push()
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        return app.test_client(), fake
    yield _make
    db.drop_all()


def demo(client, tid="retake", key=KEY, headers=None):
    h = {"X-Anthropic-Key": key} if key else {}
    return client.post("/api/transcript", headers=h | (headers or {}), json={"demo": tid})


def upload(client, data: bytes, name="t.pdf", headers=None):
    return client.post("/api/transcript", headers={"X-Anthropic-Key": KEY} | (headers or {}),
                       data={"file": (__import__("io").BytesIO(data), name)}, content_type="multipart/form-data")


def pdf(pages=1, pad=0):
    return b"%PDF-1.4\n" + b"<< /Type /Page >>\n" * pages + b"0" * pad + b"\n%%EOF"


def test_demo_transcripts_are_listed(make):
    c, _ = make()
    demos = c.get("/api/transcript/demos").get_json()
    assert [d["id"] for d in demos] == ["freshman", "transfer", "retake"]
    assert all("(fictional)" in d["name"] for d in demos)
    pdf_ = c.get("/api/transcript/demos/transfer.pdf")
    assert pdf_.status_code == 200 and pdf_.mimetype == "application/pdf" and pdf_.data.startswith(b"%PDF")
    pdf_.close()
    assert c.get("/api/transcript/demos/nobody.pdf").status_code == 404


def test_transcript_is_read_into_courses(make):
    c, fake = make([read()])
    r = demo(c)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    rec = body["record"]
    assert rec["program_id"] == "cs-bs-2026-27" and rec["start_term"] == "2027SP"
    assert rec["name"] == "Casey Lin (from transcript)"
    assert {"code": "CS 2233", "grade": "D+", "credits": 3, "title": "Data Structures", "term": "2026SP"} \
        in rec["taken"]
    assert next(t for t in rec["taken"] if t["code"] == "CS 2243")["grade"] is None  # IP = in progress
    assert rec["transfer"][0]["subject"] == "CISP" and rec["transfer"][0]["school_id"]

    sent = fake.calls[0]
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    doc = sent["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(doc["source"]["data"]) == (ROOT / "data/demo/transcripts/retake.pdf").read_bytes()

    audit = c.post("/api/audit", json=rec)  # the record runs exactly like a demo student
    assert audit.status_code == 200 and audit.get_json()["retakes"][0]["code"] == "CS 2233"


def test_transcript_unknown_codes_are_flagged(make):
    c, _ = make([read(courses=[{"code": "XYZ 9999", "title": "Basket Weaving", "credits": 3, "grade": "A",
                                "term": "Fall 2025"}], unreadable=["line 14: smudged"])])
    body = demo(c).get_json()
    assert [t["code"] for t in body["record"]["taken"]] == ["XYZ 9999"]  # kept, not dropped
    assert body["unknown_codes"] == ["XYZ 9999"]
    assert body["unreadable"] == ["line 14: smudged"]


def test_unknown_grade_is_reported_not_guessed(make):
    c, _ = make([read(courses=[{"code": "CS 1213", "title": "", "credits": 3, "grade": "Q", "term": None}])])
    body = demo(c).get_json()
    assert body["record"]["taken"][0]["grade"] is None
    assert any("CS 1213" in u and "Q" in u for u in body["unreadable"])


def test_non_transcript_is_refused(make):
    c, _ = make([read(is_transcript=False, courses=[], transfer=[])])
    r = demo(c)
    assert r.status_code == 422 and r.get_json()["error"] == "not_transcript"
    assert "record" not in r.get_json()


def test_transcript_stores_nothing(make, caplog):
    c, _ = make([read()])
    caplog.set_level(logging.DEBUG)
    assert demo(c).status_code == 200
    assert ChatUsage.query.count() == 0  # own key: nothing counted, nothing saved
    assert "Data Structures" not in caplog.text and "Casey" not in caplog.text


def test_public_site_reads_demo_transcripts_only(make, monkeypatch):
    monkeypatch.setenv("VISOR_WRITE_TOKEN", "letmein")
    c, fake = make([read()])
    r = upload(c, pdf())
    assert r.status_code == 403 and r.get_json()["error"] == "uploads_off" and fake.calls == []
    assert upload(c, pdf(), headers={"X-Visor-Token": "letmein"}).status_code == 200
    assert demo(c, "nobody").status_code == 404
    assert demo(c, "../students/01-new-freshman").status_code == 404


def test_transcript_limits(make, monkeypatch):
    c, fake = make()
    assert upload(c, pdf(pad=5 * 1024 * 1024)).get_json()["error"] == "too_large"
    assert upload(c, pdf(pages=7)).get_json()["error"] == "too_many_pages"
    assert upload(c, b"hello", name="t.txt").get_json()["error"] == "bad_file"
    assert fake.calls == []

    monkeypatch.setenv("VISOR_ANTHROPIC_API_KEY", SHARED)
    c, fake = make([read()])
    assert demo(c, key=None, headers={"Origin": SITE}).status_code == 200
    assert fake.keys == [SHARED]
    assert ChatUsage.query.filter_by(visitor="site").one().units == 4
    assert demo(c, key=None).status_code == 403  # shared key: only from the site itself


def test_no_key_no_call(make):
    c, fake = make()
    r = demo(c, key=None)
    assert r.status_code == 401 and fake.calls == []
