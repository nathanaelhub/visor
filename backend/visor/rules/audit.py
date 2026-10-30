"""Degree audit (spec 04, scaled up in spec 05). Pure logic: dataclasses in, dataclasses out.

The question it answers: given a program and the courses a student has, which requirement groups
are met, which are in progress, and what is still needed?

The one rule that makes this interesting: **a course counts toward one requirement only** (spec
04), except in groups the catalog marks ``shareable`` (Diverse Perspectives). When a course could
fit several groups we want the assignment that meets the most groups, not just the first fit:

1. Assign each course to the most *specific* group that still needs it (a group naming the course
   beats a pattern like "CS 3000+", which beats a tag like DP).
2. Then *augment*: for each group still unmet, look for a course sitting in a group that would stay
   met without it, and move it over. Repeat until nothing moves.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import grades

# --- Catalog and program ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Course:
    code: str  # "CS 2233"
    title: str
    credits: float


@dataclass(frozen=True)
class PrereqGroup:
    """One OR-group: any one of ``any_of`` passed at ``min_grade``. A course's groups are ANDed."""
    any_of: tuple[str, ...]
    min_grade: str | None = None


@dataclass(frozen=True)
class Catalog:
    courses: dict  # code -> Course
    prereqs: dict  # code -> tuple[PrereqGroup, ...]
    offered: dict  # code -> tuple[terms.Offering, ...]
    tags: dict  # code -> frozenset[str]
    tag_order: dict = field(default_factory=dict)  # tag -> tuple of codes, in catalog list order
    min_hours: dict = field(default_factory=dict)  # code -> hours needed first (class standing)

    def credits(self, code: str, default: float = 3) -> float:
        c = self.courses.get(code)
        return c.credits if c else default


@dataclass(frozen=True)
class ReqItem:
    """Exactly one of: a specific course, a pattern (``CS|SENG|SEC|IT:3000``), or a tag (``DP``)."""
    course: str | None = None
    pattern: str | None = None
    tag: str | None = None

    @property
    def specificity(self) -> int:  # lower = more specific
        return 0 if self.course else 1 if self.pattern else 2


@dataclass(frozen=True)
class ReqGroup:
    id: str
    name: str
    rule: str  # all / choose_n / hours
    items: tuple[ReqItem, ...]
    n: int = 0  # for choose_n
    hours: float = 0  # for hours
    min_grade: str | None = None
    shareable: bool = False


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    degree: str
    catalog_year: str
    total_hours: int
    groups: tuple[ReqGroup, ...]


# --- Student side ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Taken:
    """One course the student has. ``grade=None`` means in progress."""
    code: str
    credits: float
    grade: str | None
    source: str = "lipscomb"  # lipscomb / transfer
    detail: str = ""  # e.g. "Nashville State CC: CISP 1020"
    elective_only: bool = False  # transfer elective credit: counts toward hours, matches no item

    @property
    def in_progress(self) -> bool:
        return self.grade is None

    @property
    def passed(self) -> bool:
        return grades.meets(self.grade, None)


@dataclass(frozen=True)
class Counted:
    code: str
    credits: float
    via: str  # completed / in_progress / transfer
    detail: str = ""


@dataclass(frozen=True)
class Retake:
    code: str
    grade: str
    group_id: str
    min_grade: str


@dataclass
class GroupResult:
    id: str
    name: str
    status: str  # met / in_progress / needed
    used: list  # list[Counted]
    remaining: str  # human text
    outstanding_courses: list  # course codes still required by name ("all" groups)
    outstanding_count: int = 0  # choose_n
    outstanding_hours: float = 0  # hours
    required_hours: float = 0  # size of the group in hours (for progress bars)
    counted_hours: float = 0  # hours counted so far, finished + in progress
    done_hours: float = 0  # finished only


@dataclass
class AuditResult:
    program: str
    hours_done: float
    hours_in_progress: float
    hours_required: int
    groups: list  # list[GroupResult]
    unused: list  # codes that counted toward nothing
    retakes: list  # list[Retake]
    projected_term: str | None = None


# --- Matching ----------------------------------------------------------------------------------

_LEVEL = re.compile(r"^(\d)")


def matches(item: ReqItem, code: str, catalog: Catalog) -> bool:
    if item.course:
        return item.course == code
    if item.pattern:
        subjects, _, level = item.pattern.partition(":")
        subject, _, number = code.partition(" ")
        m = _LEVEL.match(number)
        return subject in subjects.split("|") and bool(m) and int(m.group(1)) * 1000 >= int(level or 0)
    if item.tag:
        return item.tag in catalog.tags.get(code, frozenset())
    return False


def _best_attempts(taken: list[Taken]) -> list[Taken]:
    """One row per course. An in-progress attempt wins (it is the retake that will replace the old
    grade); otherwise the best grade; a fail only if there is nothing else."""
    def rank(t: Taken):
        g = grades.normalize(t.grade)
        if t.in_progress:
            return (0, 0)
        if g in grades.GRADES and t.passed:
            return (1, grades.GRADES.index(g))
        return (2, 0)

    best: dict[str, Taken] = {}
    for t in taken:
        if t.code not in best or rank(t) < rank(best[t.code]):
            best[t.code] = t
    return sorted(best.values(), key=lambda t: t.code)


def _counts_in(t: Taken, group: ReqGroup) -> bool:
    """In-progress work counts (as in progress); finished work must meet the group's minimum."""
    return t.in_progress or grades.meets(t.grade, group.min_grade)


def _satisfied(group: ReqGroup, used: list[Taken]) -> bool:
    codes = {t.code for t in used}
    if group.rule == "all":
        return all(i.course in codes for i in group.items if i.course)
    if group.rule == "choose_n":
        return len(used) >= group.n
    return sum(t.credits for t in used) >= group.hours


def _needs(group: ReqGroup, used: list[Taken], t: Taken) -> bool:
    if group.rule == "all":
        return t.code not in {u.code for u in used}
    return not _satisfied(group, used)


def audit(program: Program, catalog: Catalog, taken: list[Taken]) -> AuditResult:
    attempts = _best_attempts(taken)
    groups = list(program.groups)
    exclusive = [g for g in groups if not g.shareable]

    # Which exclusive groups each course could count toward, most specific first.
    options: dict[str, list[tuple[int, int, ReqGroup]]] = {}
    retakes: list[Retake] = []
    for t in attempts:
        if t.elective_only:
            continue
        for gi, g in enumerate(exclusive):
            spec = min((i.specificity for i in g.items if matches(i, t.code, catalog)), default=None)
            if spec is None:
                continue
            if _counts_in(t, g):
                options.setdefault(t.code, []).append((spec, gi, g))
            elif not t.in_progress and spec == 0:
                retakes.append(Retake(t.code, t.grade or "", g.id, g.min_grade or grades.PASSING))
    by_code = {t.code: t for t in attempts}

    # 1. Greedy by specificity.
    used: dict[str, list[Taken]] = {g.id: [] for g in groups}
    home: dict[str, str] = {}
    for code in sorted(options, key=lambda c: (min(o[0] for o in options[c]), c)):
        t = by_code[code]
        for _, _, g in sorted(options[code], key=lambda o: (o[0], o[1])):
            if _needs(g, used[g.id], t):
                used[g.id].append(t)
                home[code] = g.id
                break

    # 2. Augment: move a course out of a group that stays met, into one that is not met yet.
    gmap = {g.id: g for g in groups}
    for _ in range(len(attempts) * len(groups) + 1):
        moved = False
        for g in exclusive:
            if _satisfied(g, used[g.id]):
                continue
            for code in sorted(c for c, opts in options.items() if any(o[2].id == g.id for o in opts)):
                t, src = by_code[code], home.get(code)
                if src == g.id or not _needs(g, used[g.id], t):
                    continue
                if src is not None:
                    rest = [u for u in used[src] if u.code != code]
                    if not _satisfied(gmap[src], rest):
                        continue
                    used[src] = rest
                used[g.id].append(t)
                home[code] = g.id
                moved = True
                break
        if not moved:
            break

    # 3. Shareable groups count every matching course, used elsewhere or not.
    for g in groups:
        if g.shareable:
            used[g.id] = [t for t in attempts if not t.elective_only and _counts_in(t, g)
                          and any(matches(i, t.code, catalog) for i in g.items)]

    results = [_group_result(g, used[g.id], catalog) for g in groups]
    counted = {t.code for g in groups for t in used[g.id]}
    done = sum(t.credits for t in attempts if not t.in_progress and t.passed)
    in_prog = sum(t.credits for t in attempts if t.in_progress)
    return AuditResult(
        program=f"{program.name}, {program.degree} ({program.catalog_year})",
        hours_done=done, hours_in_progress=in_prog, hours_required=program.total_hours,
        groups=results, unused=sorted(t.code for t in attempts if t.code not in counted),
        retakes=retakes,
    )


def _required_hours(g: ReqGroup, catalog: Catalog) -> float:
    if g.rule == "all":
        return sum(catalog.credits(i.course) for i in g.items if i.course)
    if g.rule == "choose_n":
        return g.n * 3.0  # a "choose" group is counted in courses; 3 hours each for the progress bar
    return g.hours


def _group_result(g: ReqGroup, used: list[Taken], catalog: Catalog) -> GroupResult:
    done = [t for t in used if not t.in_progress]
    counted = [Counted(t.code, t.credits, "in_progress" if t.in_progress else
                       ("transfer" if t.source == "transfer" else "completed"), t.detail) for t in used]
    if _satisfied(g, done):
        status = "met"
    elif _satisfied(g, used):
        status = "in_progress"
    else:
        status = "needed"

    have = {t.code for t in used}
    missing = [i.course for i in g.items if g.rule == "all" and i.course and i.course not in have]
    need_n = max(0, g.n - len(used)) if g.rule == "choose_n" else 0
    need_h = max(0.0, g.hours - sum(t.credits for t in used)) if g.rule == "hours" else 0.0
    if status != "needed":
        remaining = "nothing" if status == "met" else "finish the courses in progress"
    elif g.rule == "all":
        remaining = f"{len(missing)} course{'s' if len(missing) != 1 else ''}: {', '.join(missing)}"
    elif g.rule == "choose_n":
        remaining = f"{need_n} more course{'s' if need_n != 1 else ''} from the list"
    else:
        remaining = f"{need_h:g} more hours"
    req = _required_hours(g, catalog)
    return GroupResult(g.id, g.name, status, counted, remaining, missing, need_n, need_h,
                       required_hours=req,
                       counted_hours=min(req, sum(t.credits for t in used)),
                       done_hours=min(req, sum(t.credits for t in done)))
