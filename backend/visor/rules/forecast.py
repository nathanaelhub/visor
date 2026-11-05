"""Semester forecast (spec 05). Pure logic: no clock, no I/O, no randomness.

Takes the audit's "still needed" list and places each course in a future term:

1. **Outstanding courses**: missing courses, the first unused choices in "choose" groups, enough
   courses for "hours" groups, and retakes. Shareable groups (DP) are checked last, because a
   course planned for something else usually covers them.
2. **Prerequisite gaps**: if a planned course needs something nobody required (``EN 3143`` needs
   ``EN 1223`` or ``LU 1013``), the first option is added with the reason "Needed before …".
3. **Priority**: courses that unlock the most later courses go first, then the ones offered least
   often, then requirement order, then the course code (so ties always break the same way).
4. **Placement**: walk the terms from ``start_term``; fill each up to the target hours, never past
   the maximum, with courses whose prerequisites are passed and that are offered that term.
5. Anything still unplaced after the horizon becomes a **warning**, and the plan needs review.
6. **Compaction**: if the whole last term fits into earlier terms (up to the maximum load), move it
   and graduate a term sooner. The plan also reports how many free-elective hours are still needed
   to reach the degree total.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import grades
from .audit import AuditResult, Catalog, Program, Taken, matches
from .terms import Term, describe_offerings, is_offered, next_term, parse_term


@dataclass(frozen=True)
class Settings:
    include_summer: bool = False
    min_hours: int = 12
    target_hours: int = 15
    max_hours: int = 18
    horizon: int = 16  # terms to look ahead before giving up


@dataclass(frozen=True)
class Reason:
    kind: str  # requirement / unlocks / offering / retake / prerequisite / standing / needs
    text: str


@dataclass
class PlannedCourse:
    code: str
    title: str
    credits: float
    counts_toward: list  # group ids
    reasons: list  # list[Reason]
    deferred_from: str | None = None  # term code it could first have gone in


@dataclass
class PlannedTerm:
    term: str  # code, e.g. 2027SP
    name: str  # "Spring 2027"
    courses: list  # list[PlannedCourse]
    hours: float
    light: bool  # under the minimum load


@dataclass(frozen=True)
class Warning:
    kind: str  # unplaceable / not_in_catalog
    code: str | None
    group: str | None
    message: str


@dataclass
class Plan:
    start_term: str
    terms: list  # list[PlannedTerm]
    projected_term: str | None
    complete: bool  # nothing left to plan
    warnings: list = field(default_factory=list)  # list[Warning]
    free_elective_hours: float = 0  # hours still short of the degree total after everything planned

    @property
    def needs_review(self) -> bool:
        return bool(self.warnings)


# --- Step 1 and 2: what to plan ------------------------------------------------------------------


@dataclass
class _Need:
    code: str
    counts_toward: list
    reasons: list
    order: int  # requirement order, for priority


def _outstanding(program: Program, catalog: Catalog, taken: list[Taken], result: AuditResult,
                 warnings: list) -> dict[str, _Need]:
    have = {t.code for t in taken if t.in_progress or t.passed}
    retake_codes = {r.code: r for r in result.retakes}
    have -= set(retake_codes)  # a course that must be retaken is not "had"
    needs: dict[str, _Need] = {}
    groups = {g.id: g for g in program.groups}

    def add(code: str, gi: int, group_id: str, group_name: str):
        if code not in catalog.courses:
            warnings.append(Warning("not_in_catalog", code, group_id,
                                    f"{code} is required by '{group_name}' but is not in the catalog"))
            return
        n = needs.setdefault(code, _Need(code, [], [], gi))
        n.counts_toward.append(group_id)
        n.reasons.append(Reason("requirement", f"Fills: {group_name}"))
        if code in retake_codes:
            r = retake_codes[code]
            n.reasons.append(Reason("retake", f"Retake: earned {r.grade}, needs {r.min_grade}"))

    for gi, gr in enumerate(result.groups):
        g = groups[gr.id]
        if gr.status != "needed" or g.shareable:
            continue
        if g.rule == "all":
            for code in gr.outstanding_courses:
                add(code, gi, g.id, g.name)
            continue
        # choose_n / hours: explicit courses first (list order is the recommendation order),
        # then tagged or pattern-matched catalog courses.
        explicit = [i.course for i in g.items if i.course]
        tagged = [c for i in g.items if i.tag for c in catalog.tag_order.get(i.tag, ())]
        pattern = sorted(c for i in g.items if i.pattern for c in catalog.courses if matches(i, c, catalog))
        want_n, want_h = gr.outstanding_count, gr.outstanding_hours
        for code in dict.fromkeys(explicit + tagged + pattern):
            if (g.rule == "choose_n" and want_n <= 0) or (g.rule == "hours" and want_h <= 0):
                break
            if code in have or code in needs or not catalog.offered.get(code):
                continue
            add(code, gi, g.id, g.name)
            want_n -= 1
            want_h -= catalog.credits(code)
        if (g.rule == "choose_n" and want_n > 0) or (g.rule == "hours" and want_h > 0):
            warnings.append(Warning("unplaceable", None, g.id,
                                    f"'{g.name}' has no more offered courses to choose from"))

    # Shareable groups (DP): covered if anything taken or planned carries a matching item.
    for gi, gr in enumerate(result.groups):
        g = groups[gr.id]
        if not g.shareable or gr.status != "needed":
            continue
        pool = list(have) + list(needs)
        if any(matches(i, c, catalog) for i in g.items for c in pool):
            for c in pool:
                if c in needs and any(matches(i, c, catalog) for i in g.items):
                    needs[c].counts_toward.append(g.id)
                    needs[c].reasons.append(Reason("requirement", f"Also fills: {g.name}"))
                    break
            continue
        for c in (c for i in g.items if i.tag for c in catalog.tag_order.get(i.tag, ())):
            if c not in have and catalog.offered.get(c):
                add(c, gi, g.id, g.name)
                break

    # Step 2: prerequisite gaps, until nothing new is added.
    changed = True
    while changed:
        changed = False
        for code in sorted(needs):
            for pg in catalog.prereqs.get(code, ()):
                if any(o in have or o in needs for o in pg.any_of):
                    continue
                first = next((o for o in pg.any_of if o in catalog.courses), None)
                if first is None:
                    continue
                needs[first] = _Need(first, [], [Reason("prerequisite", f"Needed before {code}")],
                                     needs[code].order)
                changed = True
    return needs


# --- Step 3: priority --------------------------------------------------------------------------


def _unlocks(code: str, needs: dict[str, _Need], catalog: Catalog) -> int:
    """How many other outstanding courses depend on ``code``, directly or through a chain."""
    dependents: dict[str, set[str]] = {}
    for c in needs:
        for pg in catalog.prereqs.get(c, ()):
            for o in pg.any_of:
                dependents.setdefault(o, set()).add(c)
    seen, stack = set(), [code]
    while stack:
        for d in dependents.get(stack.pop(), ()):
            if d not in seen:
                seen.add(d)
                stack.append(d)
    return len(seen)


def _scarcity(code: str, catalog: Catalog, include_summer: bool) -> int:
    """Usable offerings per two years: Fall+Spring every year = 4, Spring of odd years = 1.
    Summer only counts when the plan uses summers."""
    return sum(2 if o.years == "every" else 1 for o in catalog.offered.get(code, ())
               if include_summer or o.season != "SU")


# --- Step 6: compaction ---------------------------------------------------------------------------


def _compact(terms: list, catalog: Catalog, passed: dict, hours_at_start: float, settings: Settings) -> list:
    """Greedy filling leaves a thin last term when a scarce course was crowded out earlier. If every
    course in the last term fits into an earlier term (up to the *maximum* load, offered then,
    prerequisites and standing still met), move them and drop the term: graduation moves up."""
    while len(terms) > 1:
        last, earlier = terms[-1], terms[:-1]
        moves: list[tuple[PlannedCourse, PlannedTerm]] = []
        load = {pt.term: pt.hours for pt in earlier}
        for pc in last.courses:
            target = None
            for i, pt in enumerate(earlier):
                term = parse_term(pt.term)
                before = {c.code for e in earlier[:i] for c in e.courses} | {m[0].code for m in moves
                                                                          if parse_term(m[1].term) < term}
                hours_then = hours_at_start + sum(e.hours for e in earlier[:i])
                if (is_offered(catalog.offered.get(pc.code, ()), term)
                        and load[pt.term] + pc.credits <= settings.max_hours
                        and _prereqs_ok(pc.code, catalog, passed, before)
                        and hours_then >= catalog.min_hours.get(pc.code, 0)):
                    target = pt
                    break
            if target is None:
                return terms
            moves.append((pc, target))
            load[target.term] += pc.credits
        for pc, pt in moves:
            pc.deferred_from = None
            pt.courses.append(pc)
            pt.hours += pc.credits
            pt.light = pt.hours < settings.min_hours
        terms = earlier
    return terms


# --- Step 4: placement -------------------------------------------------------------------------


def _passed_before(taken: list[Taken]) -> dict[str, str | None]:
    """Course -> grade for everything finished or in progress before the plan starts.

    In-progress courses count as passed from the first planned term (spec 04)."""
    out: dict[str, str | None] = {}
    for t in taken:
        if t.in_progress:
            out[t.code] = "C"  # assumed to pass at the usual minimum
        elif t.passed and (t.code not in out or grades.meets(t.grade, out[t.code])):
            out[t.code] = t.grade
    return out


def _prereqs_ok(code: str, catalog: Catalog, passed: dict[str, str | None], planned: set[str]) -> bool:
    for pg in catalog.prereqs.get(code, ()):
        if not any((o in passed and grades.meets(passed[o], pg.min_grade)) or o in planned
                   for o in pg.any_of):
            return False
    return True


def project(program: Program, catalog: Catalog, taken: list[Taken], result: AuditResult,
            start_term: str, settings: Settings = Settings()) -> Plan:
    warnings: list[Warning] = []
    needs = _outstanding(program, catalog, taken, result, warnings)
    if not needs:
        short = program.total_hours - (result.hours_done + result.hours_in_progress)
        return Plan(start_term, [], None, complete=not warnings, warnings=warnings,
                    free_elective_hours=max(0.0, short))

    unlocks = {c: _unlocks(c, needs, catalog) for c in needs}
    for c, n in unlocks.items():
        if n:
            needs[c].reasons.append(Reason("unlocks", f"Unlocks {n} later course{'s' if n != 1 else ''}"))
    for c in needs:
        offs = catalog.offered.get(c, ())
        if offs and _scarcity(c, catalog, settings.include_summer) < 4:
            needs[c].reasons.append(Reason("offering", f"Offered {describe_offerings(offs)}"))
        if c in catalog.min_hours:
            needs[c].reasons.append(Reason("standing", f"Needs {catalog.min_hours[c]:g}+ hours (class standing)"))
    order = sorted(needs, key=lambda c: (-unlocks[c], _scarcity(c, catalog, settings.include_summer),
                                         needs[c].order, c))

    passed = _passed_before(taken)
    done_before: set[str] = set()  # planned in an earlier term
    first_ready: dict[str, str] = {}
    remaining = list(order)
    terms: list[PlannedTerm] = []
    t: Term = parse_term(start_term)
    hours_before = result.hours_done + result.hours_in_progress  # grows as terms are planned
    for _ in range(settings.horizon):
        if not remaining:
            break
        placed: list[PlannedCourse] = []
        hours = 0.0
        for code in list(remaining):
            if not _prereqs_ok(code, catalog, passed, done_before):
                continue
            if hours_before < catalog.min_hours.get(code, 0):
                continue
            credits = catalog.credits(code)
            if not is_offered(catalog.offered.get(code, ()), t):
                first_ready.setdefault(code, t.code)  # ready, but not offered this term
                continue
            if hours >= settings.target_hours or hours + credits > settings.max_hours:
                continue
            n = needs[code]
            deferred = first_ready.get(code)
            # "Needs X": a prerequisite this plan places in an earlier term.
            needs_reasons = [Reason("needs", f"Needs {o}") for pg in catalog.prereqs.get(code, ())
                             for o in pg.any_of if o in done_before][:2]
            placed.append(PlannedCourse(code, catalog.courses[code].title, credits, list(n.counts_toward),
                                        list(n.reasons) + needs_reasons, deferred))
            hours += credits
            remaining.remove(code)
        if placed:
            terms.append(PlannedTerm(t.code, t.name, placed, hours, hours < settings.min_hours))
            done_before |= {p.code for p in placed}
            hours_before += hours
        t = next_term(t, settings.include_summer)

    terms = _compact(terms, catalog, passed, result.hours_done + result.hours_in_progress, settings)

    for code in remaining:
        if not catalog.offered.get(code):
            why = "it has no regular term in the catalog"
        elif not _prereqs_ok(code, catalog, passed, done_before):
            why = "its prerequisites could not be placed"
        elif hours_before < catalog.min_hours.get(code, 0):
            why = f"the student never reaches {catalog.min_hours[code]:g} hours (class standing)"
        else:
            why = f"it did not fit within {settings.horizon} terms"
        warnings.append(Warning("unplaceable", code, (needs[code].counts_toward or [None])[0],
                                f"{code} could not be placed: {why}"))
    planned_hours = sum(pt.hours for pt in terms)
    short = program.total_hours - (result.hours_done + result.hours_in_progress + planned_hours)
    # Every warning here is a requirement with no place in the plan, so its last term is not a
    # graduation term; there is none until an advisor resolves the warnings.
    projected = terms[-1].term if terms and not warnings else None
    return Plan(start_term, terms, projected, complete=False, warnings=warnings,
                free_elective_hours=max(0.0, short))
