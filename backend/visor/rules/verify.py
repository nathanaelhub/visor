"""Independent plan checker (spec 05, SC-002).

Re-checks a finished plan against the catalog rules **without importing the planner**. If the
planner has a bug, this is written differently enough that it should disagree. Tests run it over
every demo student; a person can run it over a plan an advisor edited by hand.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import grades
from .audit import Catalog, Taken
from .terms import is_offered, parse_term


@dataclass(frozen=True)
class Violation:
    rule: str  # prerequisite / offering / load / duplicate / unknown_course / standing
    code: str | None
    term: str | None
    message: str


def verify(plan, catalog: Catalog, taken: list[Taken], max_hours: int = 18) -> list[Violation]:
    """``plan`` is anything with ``.terms`` → ``.term``, ``.courses`` → ``.code`` (duck-typed on
    purpose, so a hand-edited plan from the advisor UI can be checked the same way)."""
    out: list[Violation] = []
    # What the student already has, with grades; in-progress counts as a C-level pass.
    before: dict[str, str] = {}
    for t in taken:
        g = "C" if t.grade is None else grades.normalize(t.grade)
        if g and (t.grade is None or grades.meets(g, None)):
            if t.code not in before or grades.meets(g, before[t.code]):
                before[t.code] = g

    seen: dict[str, str] = {}
    # Hours finished or in progress before the plan; grows by each planned term (class standing).
    hours = sum(t.credits for t in taken if t.grade is None or grades.meets(t.grade, None))
    for pt in sorted(plan.terms, key=lambda pt: parse_term(pt.term)):
        term = parse_term(pt.term)
        load = 0.0
        for pc in pt.courses:
            code = pc.code
            load += pc.credits
            if code not in catalog.courses:
                out.append(Violation("unknown_course", code, pt.term, f"{code} is not in the catalog"))
                continue
            if code in seen:
                out.append(Violation("duplicate", code, pt.term, f"{code} is planned in {seen[code]} and {pt.term}"))
            if not is_offered(catalog.offered.get(code, ()), term):
                out.append(Violation("offering", code, pt.term, f"{code} is not offered in {term.name}"))
            for group in catalog.prereqs.get(code, ()):
                ok = any((o in before and grades.meets(before[o], group.min_grade))
                         or (o in seen and parse_term(seen[o]) < term) for o in group.any_of)
                if not ok:
                    out.append(Violation("prerequisite", code, pt.term,
                                         f"{code} in {term.name} needs one of {', '.join(group.any_of)} "
                                         f"(at {group.min_grade or 'a passing grade'}) in an earlier term"))
            need = catalog.min_hours.get(code, 0)
            if hours < need:
                out.append(Violation("standing", code, pt.term,
                                     f"{code} in {term.name} needs {need:g} hours first; the student has {hours:g}"))
            seen.setdefault(code, pt.term)
        hours += load
        if load > max_hours:
            out.append(Violation("load", None, pt.term, f"{term.name} has {load:g} hours (max {max_hours})"))
    return out
