"""Saved chats and the conversation log (spec 09). Claude is faked; sessions are signed with the
throwaway key from test_accounts."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.test_accounts import ISS, JWK, PEOPLE, as_
from tests.test_chat import FakeClient, reply, text, tool_use
from visor import create_app
from visor.models import ChatMessage, Conversation, db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def make(monkeypatch):
    monkeypatch.setenv("VISOR_WRITE_TOKEN", "script-token")
    monkeypatch.setenv("VISOR_ADMIN_EMAILS", "boss@lipscomb.edu")
    monkeypatch.setenv("CRON_SECRET", "cron-secret")
    monkeypatch.delenv("VISOR_ANTHROPIC_API_KEY", raising=False)

    def _make(script=()):
        fake = FakeClient(script)
        app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True, "CLERK_ISSUER": ISS,
                          "CLERK_JWKS": {"keys": [JWK]}, "CLERK_USER_LOOKUP": lambda sub: PEOPLE[sub],
                          "ANTHROPIC_CLIENT_FACTORY": lambda key: fake})
        ctx = app.app_context()
        ctx.push()
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        return app.test_client(), fake
    yield _make
    db.drop_all()


def student(c, sid="demo-02"):
    return next(s for s in c.get("/api/demo/students").get_json() if s["id"] == sid)


def ask(c, q, headers=None, conversation_id=None, sid="demo-02"):
    body = {"model": "haiku", "student": student(c, sid), "messages": [{"role": "user", "text": q}]}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return c.post("/api/chat", headers={"X-Anthropic-Key": "sk-ant-test", **(headers or {})}, json=body)


def promote(c, sub, role, advisees=()):
    uid = c.get("/api/me", headers=as_(sub)).get_json()["id"]
    c.put(f"/api/admin/users/{uid}", json={"role": role}, headers=as_("user_admin"))
    if advisees:
        c.put(f"/api/admin/users/{uid}/advisees", json={"advisees": list(advisees)}, headers=as_("user_admin"))


def test_signed_out_chat_is_not_saved(make):
    c, _ = make([reply(text("Hello."))])
    r = ask(c, "hi")
    assert r.status_code == 200 and r.get_json()["conversation_id"] is None
    assert Conversation.query.count() == 0 and ChatMessage.query.count() == 0


def test_signed_in_chat_is_saved(make):
    c, _ = make([reply(tool_use("t1", "course_info", {"code": "CS 2623"}), stop="tool_use"),
                 reply(text("CS 2623 needs CS 2233.")), reply(text("Second answer."))])
    r = ask(c, "What does CS 2623 need?", headers=as_("user_stu")).get_json()
    cid = r["conversation_id"]
    assert cid
    ask(c, "And then?", headers=as_("user_stu"), conversation_id=cid)
    conv = c.get(f"/api/chats/{cid}", headers=as_("user_stu")).get_json()
    assert conv["student_key"] == "L00402115" and conv["verified"] is True
    msgs = conv["messages"]
    assert [(m["role"], m["text"]) for m in msgs] == [
        ("user", "What does CS 2623 need?"), ("assistant", "CS 2623 needs CS 2233."),
        ("user", "And then?"), ("assistant", "Second answer.")]
    assert msgs[1]["tools"][0]["tool"] == "course_info" and "summary" in msgs[1]["tools"][0]
    assert "result" not in msgs[1]["tools"][0]  # summaries only; the planner can recompute results


def test_people_see_only_their_own_history(make):
    c, _ = make([reply(text("a")), reply(text("b"))])
    mine = ask(c, "mine", headers=as_("user_stu")).get_json()["conversation_id"]
    theirs = ask(c, "theirs", headers=as_("user_reg")).get_json()["conversation_id"]
    got = c.get("/api/chats", headers=as_("user_stu")).get_json()
    assert [x["id"] for x in got] == [mine] and got[0]["first_question"] == "mine"
    assert c.get(f"/api/chats/{theirs}", headers=as_("user_stu")).status_code == 403
    assert ask(c, "hijack", headers=as_("user_stu"), conversation_id=theirs).status_code == 403


def test_admin_reads_any_conversation(make):
    c, _ = make([reply(text("a"))])
    cid = ask(c, "hello", headers=as_("user_stu")).get_json()["conversation_id"]
    rows = c.get("/api/admin/conversations", headers=as_("user_admin")).get_json()
    assert [r["id"] for r in rows] == [cid] and rows[0]["user"] == "Sam Student"
    assert c.get(f"/api/chats/{cid}", headers=as_("user_admin")).get_json()["messages"][1]["text"] == "a"


def test_advisor_reads_advisees_conversations_only(make):
    c, _ = make([reply(text("a")), reply(text("b"))])
    promote(c, "user_adv", "advisor", ["L00402115"])
    jordan = ask(c, "about Jordan", headers=as_("user_stu"), sid="demo-02").get_json()["conversation_id"]
    casey = ask(c, "about Casey", headers=as_("user_stu"), sid="demo-04").get_json()["conversation_id"]
    rows = c.get("/api/admin/conversations", headers=as_("user_adv")).get_json()
    assert [r["id"] for r in rows] == [jordan]
    assert c.get(f"/api/chats/{casey}", headers=as_("user_adv")).status_code == 403


def test_students_cannot_read_others(make):
    c, _ = make()
    assert c.get("/api/admin/conversations", headers=as_("user_stu")).status_code == 403
    assert c.get("/api/admin/conversations").status_code == 403


def test_tampering_breaks_the_chain(make):
    c, _ = make([reply(text("The real answer."))])
    cid = ask(c, "q", headers=as_("user_stu")).get_json()["conversation_id"]
    m = ChatMessage.query.filter_by(conversation_id=cid, role="assistant").one()
    m.text = "A different answer."
    db.session.commit()
    conv = c.get(f"/api/chats/{cid}", headers=as_("user_admin")).get_json()
    assert conv["verified"] is False and conv["broken_at"] == m.seq


def test_reading_is_recorded(make):
    c, _ = make([reply(text("a"))])
    cid = ask(c, "q", headers=as_("user_stu")).get_json()["conversation_id"]
    c.get(f"/api/chats/{cid}", headers=as_("user_stu"))  # the owner reading is not recorded
    c.get(f"/api/chats/{cid}", headers=as_("user_admin"))
    reads = c.get(f"/api/chats/{cid}", headers=as_("user_stu")).get_json()["read_by"]
    assert [r["reader"] for r in reads] == ["Ada Admin"]


def test_old_conversations_are_purged(make):
    c, _ = make([reply(text("old")), reply(text("new"))])
    old = ask(c, "old", headers=as_("user_stu")).get_json()["conversation_id"]
    new = ask(c, "new", headers=as_("user_stu")).get_json()["conversation_id"]
    conv = db.session.get(Conversation, old)
    conv.started_at = conv.last_at = datetime.now(timezone.utc) - timedelta(days=366)
    db.session.commit()
    r = c.post("/api/cron/purge-chats", headers={"Authorization": "Bearer cron-secret"})
    assert r.status_code == 200 and r.get_json()["deleted"] == 1
    assert db.session.get(Conversation, old) is None and db.session.get(Conversation, new) is not None
    assert ChatMessage.query.filter_by(conversation_id=old).count() == 0


def test_purge_needs_the_cron_secret(make):
    c, _ = make()
    assert c.post("/api/cron/purge-chats").status_code in (401, 403)
    assert c.post("/api/cron/purge-chats", headers={"Authorization": "Bearer nope"}).status_code in (401, 403)
    assert c.get("/api/cron/purge-chats", headers={"Authorization": "Bearer cron-secret"}).status_code == 200
