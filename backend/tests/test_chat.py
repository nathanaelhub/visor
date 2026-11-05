"""Ask Visor relay (spec 05 showcase). A fake Anthropic client scripts Claude's replies, so these
tests check Visor's side: key handling, the tool loop, tool results built from Visor's own data,
error mapping, and that nothing is stored."""
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2 as httpx  # the SDK's HTTP client (anthropic 2.x)
import pytest

from visor import create_app
from visor.models import ExternalCourse, db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]
KEY = "sk-ant-test-key-0123456789"


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(id_, name, args):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def reply(*blocks, stop="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop, model="claude-opus-5-5")


class FakeClient:
    def __init__(self, script, error=None):
        self.script, self.error, self.calls, self.keys = list(script), error, [], []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(retrieve=self._retrieve)

    def _create(self, **kw):
        if self.error:
            raise self.error
        self.calls.append(kw)
        return self.script.pop(0)

    def _retrieve(self, model_id):
        if self.error:
            raise self.error
        return SimpleNamespace(id=model_id)


@pytest.fixture()
def make(monkeypatch):
    monkeypatch.delenv("VISOR_ANTHROPIC_API_KEY", raising=False)

    def _make(script=(), error=None):
        fake = FakeClient(script, error)
        app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True,
                          "ANTHROPIC_CLIENT_FACTORY": lambda key: (fake.keys.append(key), fake)[1]})
        ctx = app.app_context()
        ctx.push()
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        return app.test_client(), fake
    yield _make
    db.drop_all()


def student(client, sid="demo-03"):
    return next(s for s in client.get("/api/demo/students").get_json() if s["id"] == sid)


def ask(client, question, sid="demo-03", key=KEY, model="opus"):
    headers = {"X-Anthropic-Key": key} if key else {}
    return client.post("/api/chat", headers=headers, json={
        "model": model, "student": student(client, sid), "messages": [{"role": "user", "text": question}]})


def test_config_lists_current_models(make):
    c, _ = make()
    cfg = c.get("/api/chat/config").get_json()
    assert cfg["shared_key"] is False and cfg["default_model"] == "opus"
    assert [m["id"] for m in cfg["models"]] == ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


def test_no_key_is_refused_before_any_call(make):
    c, fake = make()
    r = ask(c, "hi", key=None)
    assert r.status_code == 401 and r.get_json()["error"] == "no_key" and fake.calls == []


def test_transfer_question_uses_the_equivalency_table(make):
    c, fake = make([
        reply(tool_use("t1", "transfer_lookup", {"school": "Nashville State", "subject": "CISP", "number": "1020"}),
              stop="tool_use"),
        reply(text("CISP 1020 counts as **CS 2233**.")),
    ])
    r = ask(c, "What does my Nashville State CISP 1020 count as?").get_json()
    assert r["answer"].startswith("CISP 1020 counts as")
    call = r["tool_calls"][0]
    assert call["status"] == "confirmed" and call["result"]["counts_as"] == "CS 2233"
    assert call["summary"] == "Looked up CISP 1020 at Nashville State → CS 2233"
    assert r["sources"] == ["Equivalency table"]
    # the key came from the header, and the tool result went back to Claude as JSON
    assert fake.keys == [KEY]
    second = fake.calls[1]["messages"]
    assert second[-1]["content"][0]["tool_use_id"] == "t1" and '"counts_as": "CS 2233"' in second[-1]["content"][0]["content"]


def test_audit_tool_returns_the_planners_plan(make):
    c, _ = make([reply(tool_use("t1", "run_degree_audit", {}), stop="tool_use"), reply(text("ok"))])
    r = ask(c, "What am I missing?", sid="demo-02").get_json()
    result = r["tool_calls"][0]["result"]
    planned = [x["code"] for t in result["plan"] for x in t["courses"]]
    expected = c.post("/api/audit", json=student(c, "demo-02")).get_json()
    assert planned == [x["code"] for t in expected["plan"]["terms"] for x in t["courses"]]
    assert result["projected_graduation"] == "Fall 2028"
    assert r["tool_calls"][0]["summary"].startswith("Ran the degree audit")


def test_course_info_tool_reports_where_it_sits(make):
    c, _ = make([reply(tool_use("t1", "course_info", {"code": "cs3633"}), stop="tool_use"), reply(text("ok"))])
    info = ask(c, "Why is CS 3633 where it is?", sid="demo-02").get_json()["tool_calls"][0]["result"]
    assert info["code"] == "CS 3633" and info["offered"] == "Spring only"
    assert info["in_this_plan"]["term"] == "Spring 2028"


def test_course_info_tool_says_which_prerequisites_the_student_has_met(make):
    c, _ = make([reply(tool_use("t1", "course_info", {"code": "CS 3433"}), stop="tool_use"), reply(text("ok"))])
    info = ask(c, "Does skipping MA 3213 delay CS 3433?", sid="demo-04").get_json()["tool_calls"][0]["result"]
    math = next(p for p in info["prerequisites"] if "MA 3213" in p["any_of"])
    assert math["met_by"] == {"code": "MA 2314", "how": "passed with C"}
    assert info["prerequisites_met"] is True


def test_system_prompt_requires_a_lookup_before_prerequisite_claims():
    from visor.chat import SYSTEM
    assert "call course_info" in SYSTEM and "any one" in SYSTEM


def test_fallbacks_and_effort_are_set_on_opus_but_not_haiku(make):
    c, fake = make([reply(text("a")), reply(text("b"))])
    ask(c, "hi", model="opus")
    ask(c, "hi", model="haiku")
    opus, haiku = fake.calls
    assert opus["model"] == "claude-opus-5-5" and opus["fallbacks"] == "default"
    assert opus["betas"] == ["server-side-fallback-2026-07-01"] and opus["output_config"] == {"effort": "medium"}
    assert haiku["model"] == "claude-haiku-5-5" and "fallbacks" not in haiku
    assert "tool_choice" not in opus  # forced tool choice is a 400 on current models


def _status_error(cls, status, headers=None):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("x", response=httpx.Response(status, request=req, headers=headers or {}), body=None)


@pytest.mark.parametrize("error,status,code", [
    (_status_error(anthropic.AuthenticationError, 401), 401, "invalid_key"),
    (_status_error(anthropic.RateLimitError, 429, {"retry-after": "12"}), 429, "rate_limited"),
    (_status_error(anthropic.InternalServerError, 529), 503, "api_down"),
    (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), 503, "api_down"),
])
def test_errors_map_to_the_designed_states(make, error, status, code):
    c, _ = make(error=error)
    r = ask(c, "hi")
    assert r.status_code == status and r.get_json()["error"] == code
    if code == "rate_limited":
        assert r.get_json()["retry_after"] == 12
    v = c.post("/api/chat/verify", headers={"X-Anthropic-Key": KEY}, json={"model": "opus"})
    assert v.status_code == status


def test_refusal_is_answered_politely(make):
    c, _ = make([reply(stop="refusal")])
    r = ask(c, "something it declines").get_json()
    assert r["refused"] and "can't help" in r["answer"]


def test_chat_stores_nothing(make):
    c, _ = make([reply(tool_use("t1", "transfer_lookup", {"school": "Nashville State", "subject": "ZZZ",
                                                          "number": "9999"}), stop="tool_use"), reply(text("ok"))])
    before = ExternalCourse.query.count()
    r = ask(c, "What does ZZZ 9999 count as?").get_json()
    assert r["tool_calls"][0]["status"] == "unknown" and ExternalCourse.query.count() == before


def test_shared_key_mode(make, monkeypatch):
    monkeypatch.setenv("VISOR_ANTHROPIC_API_KEY", "sk-ant-shared-0123456789")
    c, fake = make([reply(text("ok"))])
    assert c.get("/api/chat/config").get_json()["shared_key"] is True
    assert ask(c, "hi", key=None).status_code == 200 and fake.keys == ["sk-ant-shared-0123456789"]


def test_history_must_end_with_the_user(make):
    c, _ = make()
    r = c.post("/api/chat", headers={"X-Anthropic-Key": KEY},
               json={"messages": [{"role": "user", "text": "a"}, {"role": "assistant", "text": "b"}]})
    assert r.status_code == 400


# --- US-5.6: one shared key with limits ------------------------------------------------------------

SHARED = "sk-ant-shared-0123456789"
SITE = "http://localhost"  # the Flask test client's host


@pytest.fixture()
def shared(make, monkeypatch):
    monkeypatch.setenv("VISOR_ANTHROPIC_API_KEY", SHARED)
    monkeypatch.setenv("VISOR_CHAT_PER_HOUR", "5")
    monkeypatch.setenv("VISOR_CHAT_PER_DAY", "8")
    monkeypatch.setenv("VISOR_CHAT_DAILY_UNITS", "100")
    return make


def shared_ask(client, question="hi", model="haiku", ip="203.0.113.7", origin=SITE, messages=None):
    headers = {"X-Forwarded-For": ip}
    if origin:
        headers["Origin"] = origin
    return client.post("/api/chat", headers=headers, json={
        "model": model, "student": student(client),
        "messages": messages or [{"role": "user", "text": question}]})


def test_shared_key_ignores_a_key_from_the_browser(shared):
    c, fake = shared([reply(text("ok"))])
    r = c.post("/api/chat", headers={"X-Anthropic-Key": KEY, "Origin": SITE},
               json={"model": "haiku", "messages": [{"role": "user", "text": "hi"}]})
    assert r.status_code == 200 and fake.keys == [SHARED]


def test_visitor_limit(shared):
    c, fake = shared([reply(text("ok")) for _ in range(6)])
    assert [shared_ask(c).status_code for _ in range(5)] == [200] * 5
    r = shared_ask(c)
    assert r.status_code == 429 and r.get_json()["error"] == "visitor_limit"
    assert 0 < r.get_json()["retry_after"] <= 3600 and len(fake.calls) == 5
    assert shared_ask(c, ip="198.51.100.9").status_code == 200  # another visitor is not blocked


def test_opus_costs_more_of_the_allowance(shared):
    c, _ = shared([reply(text("ok")) for _ in range(3)])
    assert shared_ask(c, model="opus").status_code == 200       # 4 of 5 units this hour
    r = shared_ask(c, model="sonnet")                          # 2 more would be 6
    assert r.status_code == 429 and r.get_json()["error"] == "visitor_limit"
    assert shared_ask(c, model="haiku").status_code == 200      # 1 more is exactly 5


def test_site_limit(shared, monkeypatch):
    monkeypatch.setenv("VISOR_CHAT_DAILY_UNITS", "2")
    c, fake = shared([reply(text("ok")) for _ in range(3)])
    assert shared_ask(c, ip="203.0.113.1").status_code == 200
    assert shared_ask(c, ip="203.0.113.2").status_code == 200
    r = shared_ask(c, ip="203.0.113.3")
    assert r.status_code == 429 and r.get_json()["error"] == "site_limit" and len(fake.calls) == 2


def test_request_caps(shared):
    c, fake = shared([reply(text("ok"))])
    assert shared_ask(c, "x" * 1001).status_code == 400
    long = [{"role": "user" if i % 2 == 0 else "assistant", "text": "q"} for i in range(21)]
    assert shared_ask(c, messages=long).status_code == 400
    assert fake.calls == []
    assert shared_ask(c, "x" * 1000).status_code == 200
    assert fake.calls[0]["max_tokens"] == 2000


def test_foreign_origin_refused(shared):
    c, fake = shared([reply(text("ok"))])
    assert shared_ask(c, origin="https://evil.example").status_code == 403
    assert shared_ask(c, origin=None).status_code == 403
    assert fake.calls == []


def test_system_prompt_scopes_topics():
    from visor.chat import SYSTEM
    assert "Only help with" in SYSTEM and "decline in one sentence" in SYSTEM


def test_usage_counters_hold_no_text_or_ip(shared):
    from visor.models import ChatUsage
    c, _ = shared([reply(text("ok"))])
    shared_ask(c, "my secret question", ip="203.0.113.7")
    rows = ChatUsage.query.all()
    assert rows and all("203.0.113.7" not in r.visitor and "secret" not in r.visitor for r in rows)
