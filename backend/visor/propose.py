"""``flask propose-equivalencies``: Claude proposes what scraped transfer courses count as at Lipscomb
(spec 07, US-7.2). A person runs it; it is never called while serving a request.

Rules it keeps:

* **Nothing auto-confirms.** Every answer is written as a proposal (``status = proposed``,
  ``source = ai_proposed``, no ``decided_by``); the planner only counts ``confirmed`` rows.
* **Claude picks from real courses.** Each request carries a short list of Lipscomb candidates from
  the catalog (same subject family, ranked by title overlap). An answer naming anything else is
  dropped and reported, never stored.
* **Half price, offline.** Requests go through the Message Batches API; the command waits for the
  batch and writes ``data/external/proposed_equivalencies.csv`` for review in a pull request.
"""
from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

MODEL = "claude-sonnet-5-5"
MAX_CANDIDATES = 8

# External subject -> Lipscomb prefixes worth comparing. Subjects not listed are skipped: they don't
# matter to the five majors or the Core, so asking about them would only cost money.
SUBJECT_FAMILIES = {
    "CISP": ["CS", "IT", "CCT", "SENG"], "CSCI": ["CS", "IT", "CCT", "SENG"], "CS": ["CS", "IT", "CCT", "SENG"],
    "CPSC": ["CS", "IT", "CCT", "SENG"], "COSC": ["CS", "IT", "CCT", "SENG"], "INFS": ["IT", "CS", "DS"],
    "CITC": ["IT", "CS"], "MATH": ["MA"], "STAT": ["MA", "PS"], "ENGL": ["EN", "LU"], "HIST": ["HI"],
    "BIOL": ["BY"], "CHEM": ["CM"], "PSYC": ["PS"], "PSY": ["PS"], "SOCI": ["SO"], "SOC": ["SO"],
    "ECON": ["EC"], "ACCT": ["AC"], "BUSN": ["MG", "BU"], "BUS": ["MG", "BU"], "BUAD": ["MG", "BU"],
    "MGT": ["MG"], "MGMT": ["MG"], "MKTG": ["MK"], "MKT": ["MK"], "FIN": ["FI"], "NURS": ["NURS"],
    "NUR": ["NURS"], "NUTR": ["NUTR"], "COMM": ["CO", "LU"], "SPCH": ["CO", "LU"], "CMST": ["CO", "LU"],
    "PHYS": ["PH"], "ART": ["ARTS"], "ARTH": ["ARTS"], "PHIL": ["PL"], "POLS": ["PO"], "PSCI": ["PO"],
    "COM": ["CO", "LU"], "NRSG": ["NURS"], "HMGT": ["MG"], "HCMT": ["MG"], "LOGI": ["OSCM", "MG"],
    "SPAN": ["SN"], "FREN": ["FR"], "GERM": ["GE"], "PHED": ["KIN"], "EDUC": ["ED"], "ECED": ["ED"],
    "ENTR": ["MG"], "INFO": ["IT", "DS"], "DATA": ["DS"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "lipscomb_code": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "kind": {"type": "string", "enum": ["direct", "elective", "none"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["lipscomb_code", "kind", "confidence", "reason"],
    "additionalProperties": False,
}

SYSTEM = """You help Lipscomb University's registrar draft transfer-credit equivalencies. A person \
reviews every answer before it counts, so be careful rather than generous.

Given one course from another school and a short list of Lipscomb candidates, answer:
- kind "direct" with lipscomb_code set to one candidate's code, when that candidate covers the same \
content at the same level (both introductory, or both upper division) for about the same credit;
- kind "elective" with lipscomb_code null, when it is college-level work in a related area but no \
candidate matches;
- kind "none" with lipscomb_code null, for remedial, non-credit or unrelated work.
Never name a code that is not in the candidate list. confidence is 0 to 1. reason is one short \
sentence a registrar can check."""

_WORDS = re.compile(r"[a-z]+")
_STOP = {"of", "and", "the", "to", "in", "for", "i", "ii", "iii", "introduction", "intro", "principles", "a"}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORDS.findall(text.lower()) if w not in _STOP and len(w) > 2}


def candidates(external: dict, lipscomb: list[dict]) -> list[dict]:
    """Up to ``MAX_CANDIDATES`` Lipscomb courses for one external course: its subject family first,
    ranked by shared title words, then by matching level (1xxx with 1xxx), then by code."""
    prefixes = SUBJECT_FAMILIES.get(external["subject"])
    if not prefixes:
        return []
    want = _tokens(external["title"])
    level = (re.match(r"\d", external["number"]) or [None])[0]
    pool = [c for c in lipscomb if c["subject"] in prefixes]
    pool.sort(key=lambda c: (-len(want & _tokens(c["title"])),
                             0 if c["number"][:1] == level else 1, prefixes.index(c["subject"]), c["number"]))
    return pool[:MAX_CANDIDATES]


def request_for(external: dict, cands: list[dict]) -> dict:
    lines = "\n".join(f"- {c['subject']} {c['number']}: {c['title']} ({c['credits']} credits)" for c in cands)
    user = (f"Course from {external['school']}: {external['subject']} {external['number']} "
            f"{external['title']} ({external['credits']} credits).\nDescription: {external['description'] or 'none'}"
            f"\n\nLipscomb candidates:\n{lines}")
    return {"model": MODEL, "max_tokens": 400, "system": SYSTEM,
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            "messages": [{"role": "user", "content": user}]}


def custom_id(slug: str, external: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", f"{slug}-{external['subject']}-{external['number']}")[:64]


def clean(text: str) -> str:
    """Drop control characters: Postgres rejects NUL bytes in text, and none belong in a reason (#46)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()


def checked(answer: dict, cands: list[dict]) -> tuple[dict | None, str | None]:
    """(row fields, None) for a usable answer, or (None, why it was dropped)."""
    codes = {f"{c['subject']} {c['number']}" for c in cands}
    kind, code = answer.get("kind"), answer.get("lipscomb_code")
    if kind == "direct":
        if code not in codes:
            return None, f"named {code!r}, which was not a candidate"
    elif code:
        return None, f"kind {kind} but named {code!r}"
    if kind not in ("direct", "elective", "none"):
        return None, f"unknown kind {kind!r}"
    conf = max(0.0, min(1.0, float(answer.get("confidence") or 0)))
    return {"lipscomb": code or "", "kind": kind, "confidence": round(conf, 2),
            "reason": clean(answer.get("reason") or "")[:300]}, None


def plan(external_root: Path, lipscomb_courses: Path, slugs: list[str] | None = None) -> list[tuple[str, dict, dict, list]]:
    """Every (custom_id, external course, request, candidates) worth asking about."""
    with open(lipscomb_courses, newline="") as f:
        lipscomb = list(csv.DictReader(f))
    schools = {r["slug"]: r["name"] for r in csv.DictReader(open(external_root / "schools.csv", newline=""))}
    out = []
    for slug, name in schools.items():
        if slugs and slug not in slugs or not (external_root / slug / "courses.csv").exists():
            continue
        for r in csv.DictReader(open(external_root / slug / "courses.csv", newline="")):
            ext = {**r, "school": name}
            cands = candidates(ext, lipscomb)
            if cands:
                out.append((custom_id(slug, ext), ext, request_for(ext, cands), cands))
    return out


def estimate(jobs: list) -> float:
    """Rough dollars at Batches prices (half of $2 in / $10 out per million on Sonnet 5.5)."""
    chars = sum(len(json.dumps(j[2])) for j in jobs)
    return (chars / 4 * 1.0 + len(jobs) * 150 * 5.0) / 1_000_000


def run(client, jobs: list, out_csv: Path, poll: int = 30, log=print) -> dict:
    by_id = {j[0]: j for j in jobs}
    batch = client.messages.batches.create(requests=[{"custom_id": j[0], "params": j[2]} for j in jobs])
    log(f"batch {batch.id}: {len(jobs)} requests")
    while (b := client.messages.batches.retrieve(batch.id)).processing_status != "ended":
        log(f"  {b.request_counts.succeeded} done, {b.request_counts.processing} processing")
        time.sleep(poll)
    rows, dropped = [], []
    for res in client.messages.batches.results(batch.id):
        _, ext, _, cands = by_id[res.custom_id]
        if res.result.type != "succeeded":
            dropped.append((res.custom_id, res.result.type))
            continue
        text = "".join(b.text for b in res.result.message.content if b.type == "text")
        try:
            row, why = checked(json.loads(text), cands)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            row, why = None, f"unreadable answer: {e}"
        if row is None:
            dropped.append((res.custom_id, why))
            continue
        rows.append({"school": ext["school"], "external": f"{ext['subject']} {ext['number']}", **row})
    rows.sort(key=lambda r: (r["school"], r["external"]))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["school", "external", "lipscomb", "kind", "confidence", "reason"])
        w.writeheader()
        w.writerows(rows)
    for cid, why in dropped:
        log(f"  dropped {cid}: {why}")
    return {"batch": batch.id, "proposals": len(rows), "dropped": len(dropped),
            "direct": sum(r["kind"] == "direct" for r in rows), "elective": sum(r["kind"] == "elective" for r in rows),
            "none": sum(r["kind"] == "none" for r in rows)}


def client_from_env():
    import os

    import anthropic
    key = os.environ.get("VISOR_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set VISOR_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) to run this.")
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=120)
