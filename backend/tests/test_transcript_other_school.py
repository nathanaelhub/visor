"""Transcripts issued by another school, upload gating and the streamed read (spec 07, US-7.4)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from visor import create_app
from visor.models import db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]
KEY = "sk-ant-test-key-0123456789"

MTSU_STYLE = {  # fictional: a student whose transcript comes from a university, with two transfer blocks
    "is_transcript": True, "student_name": "Jordan Q. Example", "issuing_school": "Middle Tennessee State University",
    "courses": [{"code": "ENGL 1010", "title": "Expository Writing", "credits": 3, "grade": "B", "term": "Fall 2025"},
                {"code": "MATH 1910", "title": "Calculus I", "credits": 4, "grade": "A", "term": "Fall 2025"},
                {"code": "CSCI 1170", "title": "Computer Science I", "credits": 4, "grade": "IP", "term": "Fall 2026"}],
    "transfer": [{"school": "Nashville State Community College", "subject": "CISP", "number": "1010",
                  "title": "Computer Science I", "credits": 4, "grade": "A"},
                 {"school": "Columbia State Community College", "subject": "HIST", "number": "2010",
                  "title": "Survey of American History I", "credits": 3, "grade": "B"}],
    "unreadable": []}


def reply(body):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(body))],
                           stop_reason="end_turn", model="claude-sonnet-5-5")


class FakeStream:
    def __init__(self, body):
        self.text, self.final = json.dumps(body), reply(body)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        for i in range(0, len(self.text), 37):  # odd-sized chunks, like real deltas
            yield self.text[i:i + 37]

    def get_final_message(self):
        return self.final


class FakeClient:
    def __init__(self, body):
        self.body, self.calls = body, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create, stream=self._stream))

    def _create(self, **kw):
        self.calls.append(("create", kw))
        return reply(self.body)

    def _stream(self, **kw):
        self.calls.append(("stream", kw))
        return FakeStream(self.body)


@pytest.fixture()
def make(monkeypatch):
    monkeypatch.delenv("VISOR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VISOR_WRITE_TOKEN", raising=False)

    def _make(body=MTSU_STYLE):
        fake = FakeClient(body)
        app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True,
                          "ANTHROPIC_CLIENT_FACTORY": lambda key: fake})
        ctx = app.app_context()
        ctx.push()
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        return app.test_client(), fake
    yield _make
    db.drop_all()


def read(client, **kw):
    return client.post("/api/transcript", headers={"X-Anthropic-Key": KEY}, json={"demo": "transfer"}, **kw)


def test_other_school_courses_become_transfer_rows(make):
    c, _ = make()
    body = read(c).get_json()
    rec = body["record"]
    assert body["issuing_school"] == "Middle Tennessee State University" and body["needs_program"] is True
    assert rec["taken"] == []  # nothing here was taken at Lipscomb
    mtsu = [t for t in rec["transfer"] if t["school"] == "Middle Tennessee State University"]
    assert [(t["subject"], t["number"], t["grade"]) for t in mtsu] == [("ENGL", "1010", "B"), ("MATH", "1910", "A")]
    assert any("CSCI 1170" in n and "in progress" in n for n in body["unreadable"])  # not counted until graded
    schools = {t["school"] for t in rec["transfer"]}
    assert {"Nashville State Community College", "Columbia State Community College"} <= schools
    assert next(t for t in rec["transfer"] if t["subject"] == "CISP")["school_id"]  # known school resolved


def test_lipscomb_transcript_is_unchanged(make):
    body = dict(MTSU_STYLE, issuing_school="Lipscomb University", transfer=[])
    c, _ = make(body)
    out = read(c).get_json()
    assert out["needs_program"] is False and [t["code"] for t in out["record"]["taken"]][:2] == ["ENGL 1010", "MATH 1910"]


def test_major_choice_reaches_the_audit(make):
    c, _ = make()
    rec = read(c).get_json()["record"]
    programs = c.get("/api/programs").get_json()
    rec["program_id"] = programs[-1]["id"]
    r = c.post("/api/audit", json=rec)
    assert r.status_code == 200 and r.get_json()["program_id"] == programs[-1]["id"]


def test_uploads_open_only_when_writes_are(make, monkeypatch):
    c, _ = make()
    assert c.get("/api/transcript/config").get_json()["uploads_open"] is True  # tests run like local dev
    monkeypatch.setenv("VISOR_WRITE_TOKEN", "letmein")
    assert c.get("/api/transcript/config").get_json()["uploads_open"] is False
    assert c.get("/api/transcript/config", headers={"X-Visor-Token": "letmein"}).get_json()["uploads_open"] is True


def test_streamed_read_matches_the_plain_read(make):
    c, fake = make()
    plain = read(c).get_json()
    r = read(c, query_string={"stream": "1"})
    assert r.status_code == 200 and r.mimetype == "application/x-ndjson"
    events = [json.loads(line) for line in r.data.decode().splitlines() if line.strip()]
    rows = [e for e in events if e["type"] == "row"]
    assert len(rows) == 3 + 2  # every course and transfer row arrives on its own, before the end
    assert rows[0]["row"]["code"] == "ENGL 1010"
    done = events[-1]
    assert done["type"] == "done" and done["result"] == plain
    assert [k for k, _ in fake.calls] == ["create", "stream"]
