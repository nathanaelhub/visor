"""``flask transcript-eval <dir>``: read each fictional test transcript with the real API and compare
the reading with its answer key (spec 07, US-7.5). Run by a person; it costs a few cents per file.

Scores what matters for an audit: the issuing school, and each course's code and grade (credits are
reported but not scored, since a scan's "3.000" and "3" mean the same thing). Transfer rows must also
carry the right school.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from .audit_api import course_code
from .transcript import MEDIA, parse_reading, request_params


def _school(name: str | None) -> str:
    n = re.sub(r"[^a-z ]", " ", (name or "").lower())
    n = re.sub(r"\b(the|of|at|community|cmty|comm|cc|college|coll|university|univ|state|st)\b", " ", n)
    return " ".join(n.split())


def score(expected: dict, read: dict) -> dict:
    """Matches by (school, code, grade) as a multiset, so a repeated course must appear twice."""
    def rows(items, school_of):
        return Counter((_school(school_of(r)), course_code(r.get("code") or f"{r.get('subject', '')} {r.get('number', '')}"),
                        (r.get("grade") or "").strip().upper().replace("IP", "")) for r in items)
    want = rows(expected["courses"], lambda r: expected["issuing_school"]) + \
        rows(expected["transfer"], lambda r: r["school"])
    got = rows(read.get("courses", []), lambda r: read.get("issuing_school")) + \
        rows(read.get("transfer", []), lambda r: r.get("school"))
    hit = sum((want & got).values())
    return {"issuer_ok": _school(expected["issuing_school"]) == _school(read.get("issuing_school")),
            "expected": sum(want.values()), "read": sum(got.values()), "matched": hit,
            "missed": sorted(" ".join(k) for k in (want - got).elements()),
            "extra": sorted(" ".join(k) for k in (got - want).elements())}


def run(folder: Path, client) -> list[dict]:
    out = []
    for f in sorted(folder.iterdir()):
        answer = folder / "expected" / f"{f.stem}.json"
        if not answer.exists() or f.suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg"):
            continue
        data = f.read_bytes()
        media = next(m for sig, m in MEDIA.items() if data.startswith(sig))
        read, error = parse_reading(client.beta.messages.create(**request_params(data, media)))
        result = {"file": f.name, **(score(json.loads(answer.read_text()), read) if read else {"error": error})}
        out.append(result)
        print(json.dumps(result), flush=True)
    return out


def client_from_env():
    import anthropic
    key = os.environ.get("VISOR_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set VISOR_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) to run the eval.")
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=120)
