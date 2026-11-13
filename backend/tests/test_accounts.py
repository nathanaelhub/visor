"""Login and roles (spec 08). Tokens are signed with a throwaway RSA key standing in for Clerk's."""
import json
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from visor import create_app
from visor.models import db
from visor.seed import load, load_equivalencies

ROOT = Path(__file__).resolve().parents[2]
ISS = "https://test-instance.clerk.accounts.dev"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())), "kid": "k1", "use": "sig", "alg": "RS256"}
PEOPLE = {"user_admin": {"email": "boss@lipscomb.edu", "name": "Ada Admin"},
          "user_adv": {"email": "adv@lipscomb.edu", "name": "Dr. Advisor"},
          "user_reg": {"email": "reg@lipscomb.edu", "name": "Ms. Registrar"},
          "user_stu": {"email": "stu@example.com", "name": "Sam Student"}}


def token(sub, azp="http://localhost", key=KEY, exp=300, iss=ISS):
    now = int(time.time())
    return jwt.encode({"sub": sub, "iss": iss, "azp": azp, "iat": now, "nbf": now, "exp": now + exp},
                      key, algorithm="RS256", headers={"kid": "k1"})


def as_(sub, **kw):
    return {"Authorization": f"Bearer {token(sub, **kw)}"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("VISOR_WRITE_TOKEN", "script-token")  # writes closed unless a role allows them
    monkeypatch.setenv("VISOR_ADMIN_EMAILS", "boss@lipscomb.edu")
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True, "CLERK_ISSUER": ISS,
                      "CLERK_JWKS": {"keys": [JWK]}, "CLERK_USER_LOOKUP": lambda sub: PEOPLE[sub]})
    with app.app_context():
        load(ROOT / "data" / "catalog" / "2026-27")
        load_equivalencies(ROOT / "data" / "demo")
        yield app.test_client()
        db.drop_all()


def user_id(c, sub):
    return c.get("/api/me", headers=as_(sub)).get_json()["id"]


def promote(c, sub, role, advisees=()):
    uid = user_id(c, sub)
    assert c.put(f"/api/admin/users/{uid}", json={"role": role}, headers=as_("user_admin")).status_code == 200
    if advisees:
        c.put(f"/api/admin/users/{uid}/advisees", json={"advisees": list(advisees)}, headers=as_("user_admin"))
    return uid


def jordan(c):
    return next(s for s in c.get("/api/demo/students").get_json() if s["id"] == "demo-02")


# --- US-8.1 / US-8.4 -------------------------------------------------------------------------------

def test_signed_out_is_the_demo(client):
    assert client.get("/api/me").get_json() is None
    assert client.post("/api/audit", json=jordan(client)).status_code == 200
    assert client.get("/api/transcript/config").get_json()["uploads_open"] is False
    assert client.put("/api/students/L00402115/plan-edits", json={"edits": {}}).status_code in (401, 403)


def test_forged_or_expired_tokens_are_refused(client):
    for headers in (as_("user_admin", key=OTHER_KEY), as_("user_admin", exp=-60), as_("user_admin", iss="https://evil"),
                    as_("user_admin", azp="https://evil.example"), {"Authorization": "Bearer not-a-jwt"}):
        assert client.get("/api/me", headers=headers).get_json() is None, headers
    me = client.get("/api/me", headers=as_("user_stu")).get_json()
    assert me["role"] == "student" and me["name"] == "Sam Student"


# --- US-8.2 ----------------------------------------------------------------------------------------

def test_admins_come_from_the_env(client):
    me = client.get("/api/me", headers=as_("user_admin")).get_json()
    assert me["role"] == "admin"
    r = client.put(f"/api/admin/users/{me['id']}", json={"role": "student"}, headers=as_("user_admin"))
    assert r.status_code == 400


def test_admin_sets_roles_and_advisees(client):
    uid = promote(client, "user_adv", "advisor", ["L00402115"])
    users = {u["name"]: u for u in client.get("/api/admin/users", headers=as_("user_admin")).get_json()}
    adv = users["Dr. Advisor"]
    assert adv["id"] == uid and adv["role"] == "advisor" and adv["advisees"] == ["L00402115"]
    assert adv["role_set_by"] == "Ada Admin" and adv["role_set_at"]


def test_only_admins_change_roles(client):
    uid = user_id(client, "user_stu")
    assert client.put(f"/api/admin/users/{uid}", json={"role": "admin"}, headers=as_("user_stu")).status_code == 403
    assert client.get("/api/admin/users", headers=as_("user_stu")).status_code == 403
    assert client.get("/api/admin/users").status_code == 403


# --- US-8.3 ----------------------------------------------------------------------------------------

def test_advisor_edits_own_advisees_only(client):
    promote(client, "user_adv", "advisor", ["L00402115"])
    edits = {"edits": {"holds": [{"code": "CS 2623", "not_before": "2027FA"}]}}
    assert client.put("/api/students/L00402115/plan-edits", json=edits, headers=as_("user_adv")).status_code == 200
    assert client.put("/api/students/L00421788/plan-edits", json=edits, headers=as_("user_adv")).status_code == 403
    got = client.get("/api/students/L00402115/plan-edits", headers=as_("user_adv")).get_json()
    assert got["can_save"] is True and got["updated_by"] == "Dr. Advisor"
    assert client.get("/api/students/L00421788/plan-edits", headers=as_("user_adv")).get_json()["can_save"] is False
    s = jordan(client)
    fp = client.post("/api/audit", json=s).get_json()["fingerprint"]
    a = client.post("/api/students/L00402115/approval", headers=as_("user_adv"),
                    json={"student": s, "fingerprint": fp, "approved_by": "someone else", "note": ""})
    assert a.status_code == 201 and a.get_json()["approval"]["approved_by"] == "Dr. Advisor"  # the account, not the body


def test_registrar_decides_equivalencies(client):
    promote(client, "user_reg", "registrar")
    eq = client.get("/api/equivalencies?status=proposed").get_json()
    target = eq[0] if isinstance(eq, list) else eq["items"][0]
    r = client.put(f"/api/equivalencies/{target['id']}", headers=as_("user_reg"),
                   json={"status": "confirmed", "decided_by": "not me"})
    assert r.status_code == 200 and r.get_json()["decided_by"] == "Ms. Registrar"
    assert client.put(f"/api/equivalencies/{target['id']}", headers=as_("user_stu"),
                      json={"status": "rejected"}).status_code == 403


def test_uploads_open_for_staff_only(client):
    promote(client, "user_reg", "registrar")
    assert client.get("/api/transcript/config", headers=as_("user_reg")).get_json()["uploads_open"] is True
    assert client.get("/api/transcript/config", headers=as_("user_stu")).get_json()["uploads_open"] is False


def test_token_still_works_for_scripts(client):
    r = client.put("/api/students/L00402115/plan-edits", json={"edits": {}}, headers={"X-Visor-Token": "script-token"})
    assert r.status_code == 200
