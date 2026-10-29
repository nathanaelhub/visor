"""Read ``data/catalog/<year>/*.csv`` into the pure ``rules.audit`` dataclasses (spec 05).

File reading lives here, not in ``rules/``, so the rules stay pure (CLAUDE.md rule 3). Spec 04's
plan is to move programs and requirement groups into database tables; when that lands, only this
module changes.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from .rules.audit import Catalog, Course, PrereqGroup, Program, ReqGroup, ReqItem
from .rules.terms import Offering

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data" / "catalog" / "2026-27"


def _rows(d: Path, name: str) -> list[dict]:
    with open(d / name, newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=4)
def load_catalog(data_dir: str | Path = DEFAULT_CATALOG) -> tuple[Catalog, dict[str, Program]]:
    """Returns (catalog, programs by id). Cached: the files only change with a deploy."""
    d = Path(data_dir)
    courses = {f"{r['subject']} {r['number']}": Course(f"{r['subject']} {r['number']}", r["title"],
                                                       float(r["credits"]))
               for r in _rows(d, "courses.csv")}

    prereqs: dict[str, list[PrereqGroup]] = {}
    for r in _rows(d, "prereqs.csv"):
        prereqs.setdefault(r["course"], []).append(PrereqGroup(
            tuple(x.strip() for x in r["any_of"].split("|")), (r.get("min_grade") or "").strip() or None))

    offered: dict[str, list[Offering]] = {}
    for r in _rows(d, "course_terms.csv"):
        offered.setdefault(r["course"], []).append(Offering(r["season"], r["years"] or "every"))

    tags: dict[str, set[str]] = {}
    tag_order: dict[str, list[str]] = {}
    for r in _rows(d, "course_tags.csv"):
        tags.setdefault(r["course"], set()).add(r["tag"])
        tag_order.setdefault(r["tag"], []).append(r["course"])

    standing = {r["course"]: float(r["min_hours"]) for r in _rows(d, "course_standing.csv")} \
        if (d / "course_standing.csv").exists() else {}

    catalog = Catalog(
        courses=courses,
        prereqs={k: tuple(v) for k, v in prereqs.items()},
        offered={k: tuple(v) for k, v in offered.items()},
        tags={k: frozenset(v) for k, v in tags.items()},
        tag_order={k: tuple(v) for k, v in tag_order.items()},
        min_hours=standing,
    )

    items: dict[str, list[tuple[int, ReqItem]]] = {}
    for r in _rows(d, "req_items.csv"):
        item = ReqItem(course=r["course"] or None, pattern=r["pattern"] or None, tag=r["tag"] or None)
        items.setdefault(r["group"], []).append((int(r["sort"] or 0), item))

    groups: dict[str, list[tuple[int, ReqGroup]]] = {}
    for r in _rows(d, "req_groups.csv"):
        groups.setdefault(r["program"], []).append((int(r["sort"] or 0), ReqGroup(
            id=r["id"], name=r["name"], rule=r["rule"],
            items=tuple(i for _, i in sorted(items.get(r["id"], []), key=lambda x: x[0])),
            n=int(r["n"] or 0), hours=float(r["hours"] or 0), min_grade=r["min_grade"] or None,
            shareable=r["shareable"] == "1")))

    programs = {r["id"]: Program(
        id=r["id"], name=r["name"], degree=r["degree"], catalog_year=r["catalog_year"],
        total_hours=int(r["total_hours"]),
        groups=tuple(g for _, g in sorted(groups.get(r["id"], []), key=lambda x: x[0])))
        for r in _rows(d, "programs.csv")}
    return catalog, programs
