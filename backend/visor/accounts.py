"""Login and roles (spec 08).

People sign in with Clerk. The browser sends Clerk's session token as ``Authorization: Bearer``;
this module verifies it against Clerk's published keys (issuer, expiry, and the site it was issued
for), then finds or creates the ``app_user`` row. The role always comes from our database, never from
the browser.

* ``staff_guard(*roles, student_key=None)``: ``None`` when the request may go ahead, else the error
  response. It passes when the write token would (scripts, local dev; ``auth.write_guard``), or when
  the signed-in user is an admin or has one of ``roles``. An advisor passes for a student only if that
  student is one of their advisees.
* Admins are the emails in ``VISOR_ADMIN_EMAILS``; everyone else starts as a student until an admin
  changes their role on the admin page.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from datetime import datetime, timezone
from functools import cache, wraps

import jwt
from flask import Blueprint, current_app, jsonify, request

from .auth import write_guard
from .models import Advisee, AppUser, db

bp = Blueprint("accounts", __name__, url_prefix="/api")

ROLES = ("student", "advisor", "registrar", "admin")
STAFF = ("advisor", "registrar")


# --- Verifying the session token ------------------------------------------------------------------

def _issuer() -> str | None:
    """https://<frontend-api>, from CLERK_ISSUER or decoded from the publishable key."""
    iss = current_app.config.get("CLERK_ISSUER") or os.environ.get("CLERK_ISSUER")
    if iss:
        return iss.rstrip("/")
    pk = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY")
    if not pk or pk.count("_") < 2:
        return None
    b = pk.split("_", 2)[2]
    try:
        return "https://" + base64.b64decode(b + "=" * (-len(b) % 4)).decode().rstrip("$")
    except ValueError:
        return None


@cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def _signing_key(token: str, iss: str):
    jwks = current_app.config.get("CLERK_JWKS")  # tests pass keys in; production fetches Clerk's
    if jwks:
        kid = jwt.get_unverified_header(token).get("kid")
        return next(k.key for k in jwt.PyJWKSet.from_dict(jwks).keys if k.key_id == kid)
    return _jwks_client(f"{iss}/.well-known/jwks.json").get_signing_key_from_jwt(token).key


def _allowed_parties() -> set[str]:
    parties = {o.strip().rstrip("/") for o in os.environ.get("VISOR_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    parties.add(request.host_url.rstrip("/"))
    if current_app.debug or current_app.testing:
        parties |= {"http://localhost:5173", "http://localhost:5174"}
    return parties


def session_claims() -> dict | None:
    """The verified claims of the request's Clerk session, or None (signed out, or a bad token)."""
    auth = request.headers.get("Authorization", "")
    iss = _issuer()
    if not auth.startswith("Bearer ") or not iss:
        return None
    token = auth[7:].strip()
    try:
        claims = jwt.decode(token, _signing_key(token, iss), algorithms=["RS256"], issuer=iss, leeway=5,
                            options={"require": ["exp", "iat", "sub", "iss"]})
    except (jwt.PyJWTError, StopIteration, ValueError):
        return None
    if claims.get("azp") and claims["azp"].rstrip("/") not in _allowed_parties():
        return None
    return claims


# --- The user --------------------------------------------------------------------------------------

def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("VISOR_ADMIN_EMAILS", "").split(",") if e.strip()}


def _lookup_clerk_user(clerk_id: str) -> dict:
    """Name and primary email from Clerk's Backend API (the session token doesn't carry them)."""
    lookup = current_app.config.get("CLERK_USER_LOOKUP")
    if lookup:
        return lookup(clerk_id)
    secret = os.environ.get("CLERK_SECRET_KEY")
    if not secret:
        return {}
    req = urllib.request.Request(f"https://api.clerk.com/v1/users/{clerk_id}",
                                 headers={"Authorization": f"Bearer {secret}", "User-Agent": "visor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            u = json.load(r)
    except (OSError, ValueError):  # Clerk unreachable: sign in anyway; the name fills in next time
        return {}
    primary = next((e["email_address"] for e in u.get("email_addresses", [])
                    if e.get("id") == u.get("primary_email_address_id")), None)
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or primary or clerk_id
    return {"email": primary, "name": name}


def current_user() -> AppUser | None:
    if "visor.user" in request.environ:  # once per request (not g: an app context can outlive a request)
        return request.environ["visor.user"]
    claims = session_claims()
    user = None
    if claims:
        user = AppUser.query.filter_by(clerk_id=claims["sub"]).one_or_none()
        if user is None or not user.email:
            info = _lookup_clerk_user(claims["sub"])
            if user is None:
                user = AppUser(clerk_id=claims["sub"], role="student", name=claims["sub"])
                db.session.add(user)
            user.email = (info.get("email") or "").lower() or user.email
            user.name = info.get("name") or user.name
        if user.email and user.email in _admin_emails() and user.role != "admin":
            user.role, user.role_set_by, user.role_set_at = "admin", "VISOR_ADMIN_EMAILS", datetime.now(timezone.utc)
        db.session.commit()
    request.environ["visor.user"] = user
    return user


def advisee_keys(user: AppUser) -> list[str]:
    return [a.student_key for a in Advisee.query.filter_by(advisor_id=user.id).order_by(Advisee.student_key)]


def staff_guard(*roles: str, student_key: str | None = None):
    """None if this request may do a staff action, else the error response (spec 08, US-8.3)."""
    if write_guard() is None:  # the write token, or local dev and tests without one
        return None
    user = current_user()
    if user is None:
        return write_guard()
    if user.role == "admin":
        return None
    if user.role in roles and not (user.role == "advisor" and student_key is not None
                                   and student_key not in advisee_keys(user)):
        return None
    return jsonify({"error": "forbidden", "message": "Your role can't do this. Ask a Visor admin."}), 403


def require_role(*roles: str):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if (denied := staff_guard(*roles)) is not None:
                return denied
            return view(*args, **kwargs)
        return wrapper
    return deco


# --- Routes ----------------------------------------------------------------------------------------

def _user_json(u: AppUser) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "advisees": advisee_keys(u),
            "role_set_by": u.role_set_by, "role_set_at": u.role_set_at.isoformat() if u.role_set_at else None}


@bp.get("/me")
def me():
    u = current_user()
    return jsonify(None if u is None else {**_user_json(u), "staff": u.role in STAFF + ("admin",)})


def _admin_only():
    u = current_user()
    if u is None or u.role != "admin":
        return jsonify({"error": "forbidden", "message": "Only a Visor admin can do this."}), 403
    return None


@bp.get("/admin/users")
def list_users():
    if (denied := _admin_only()) is not None:
        return denied
    return jsonify([_user_json(u) for u in AppUser.query.order_by(AppUser.role, AppUser.name)])


@bp.put("/admin/users/<int:uid>")
def set_role(uid: int):
    if (denied := _admin_only()) is not None:
        return denied
    u = db.session.get(AppUser, uid)
    role = (request.get_json(silent=True) or {}).get("role")
    if u is None:
        return jsonify({"error": "not_found"}), 404
    if role not in ROLES:
        return jsonify({"error": "bad_request", "message": f"role must be one of {', '.join(ROLES)}"}), 400
    if u.email and u.email in _admin_emails() and role != "admin":
        return jsonify({"error": "bad_request", "message": "This admin comes from VISOR_ADMIN_EMAILS."}), 400
    u.role, u.role_set_by, u.role_set_at = role, current_user().name, datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_user_json(u))


@bp.put("/admin/users/<int:uid>/advisees")
def set_advisees(uid: int):
    if (denied := _admin_only()) is not None:
        return denied
    u = db.session.get(AppUser, uid)
    if u is None:
        return jsonify({"error": "not_found"}), 404
    keys = sorted({str(k).strip() for k in (request.get_json(silent=True) or {}).get("advisees", []) if str(k).strip()})
    Advisee.query.filter_by(advisor_id=u.id).delete()
    by = current_user().name
    for k in keys:
        db.session.add(Advisee(advisor_id=u.id, student_key=k, assigned_by=by))
    db.session.commit()
    return jsonify(_user_json(u))
