"""Spec 05: degree audit + semester forecast, pure rules.

Test names match the bracketed names in specs/05-design-forecast.md. Most tests use a tiny made-up
catalog so each rule is visible; the "whole demo set" tests use the real 2026-27 catalog files.
"""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from visor.catalog_files import load_catalog
from visor.rules.audit import Catalog, Course, PrereqGroup, Program, ReqGroup, ReqItem, Taken, audit
from visor.rules.forecast import Settings, project
from visor.rules.terms import Offering, next_term, parse_term
from visor.rules.verify import verify

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "data" / "demo" / "students"

FA, SP = Offering("FA"), Offering("SP")


def tiny_catalog(**extra) -> Catalog:
    """A1 -> A2 -> A3 chain, a Spring-only course, a tagged course, two electives."""
    courses = {c: Course(c, c, 3) for c in ["AA 1000", "AA 2000", "AA 3000", "SP 1000", "TG 1000",
                                            "EL 3100", "EL 3200", "GAP 1000", "NEEDY 2000"]}
    base = dict(
        courses=courses,
        prereqs={"AA 2000": (PrereqGroup(("AA 1000",), "C"),), "AA 3000": (PrereqGroup(("AA 2000",), "C"),),
                 "NEEDY 2000": (PrereqGroup(("GAP 1000",), None),)},
        offered={c: (FA, SP) for c in courses} | {"SP 1000": (SP,)},
        tags={"TG 1000": frozenset({"DP"})},
        tag_order={"DP": ("TG 1000",)},
    )
    base.update(extra)
    return Catalog(**base)


def tiny_program(*groups) -> Program:
    return Program("p", "Test", "B.S.", "2026-27", 30, tuple(groups) or (
        ReqGroup("core", "Core", "all", tuple(ReqItem(course=c) for c in ["AA 1000", "AA 2000", "AA 3000", "SP 1000"]),
                 min_grade="C"),
    ))


def run(program, catalog, taken, start="2027SP", settings=Settings()):
    result = audit(program, catalog, taken)
    return result, project(program, catalog, taken, result, start, settings)


def demo_students():
    return [json.loads(f.read_text()) for f in sorted(DEMO.glob("*.json"))]


def demo_taken(student, catalog) -> list[Taken]:
    """Demo students' Lipscomb courses only; transfer is exercised through the API tests."""
    return [Taken(t["code"], catalog.credits(t["code"]), t["grade"]) for t in student["taken"]]


# --- Terms -------------------------------------------------------------------------------------

def test_terms_order_and_next():
    assert parse_term("2026FA") < parse_term("2027SP") < parse_term("2027SU") < parse_term("2027FA")
    assert next_term(parse_term("2027SP")).code == "2027FA"
    assert next_term(parse_term("2027SP"), include_summer=True).code == "2027SU"
    assert next_term(parse_term("2027FA")).code == "2028SP"
    with pytest.raises(ValueError):
        parse_term("Fall 2027")


# --- Audit -------------------------------------------------------------------------------------

def test_course_counts_once_and_moves_to_meet_more_groups():
    """EL 3100 fits both a choose-one list and a pattern-hours group. Greedy puts it in the list
    (more specific); the only course that can fill the list is EL 3100, so a second elective must
    land in the hours group — and the audit should end with both groups met."""
    cat = tiny_catalog()
    prog = tiny_program(
        ReqGroup("pick", "Pick one", "choose_n", (ReqItem(course="EL 3100"),), n=1),
        ReqGroup("upper", "Upper hours", "hours", (ReqItem(pattern="EL:3000"),), hours=3),
    )
    r = audit(prog, cat, [Taken("EL 3100", 3, "A"), Taken("EL 3200", 3, "A")])
    assert [g.status for g in r.groups] == ["met", "met"]
    used = [u.code for g in r.groups for u in g.used]
    assert sorted(used) == ["EL 3100", "EL 3200"] and len(used) == len(set(used))


def test_augmenting_move_frees_a_course():
    """EL 3100 lands in the hours group first (it's the only pattern match), then the choose group
    needs it: the audit moves it because the hours group stays met with EL 3200."""
    cat = tiny_catalog()
    prog = tiny_program(
        ReqGroup("upper", "Upper hours", "hours", (ReqItem(pattern="EL:3000"),), hours=3),
        ReqGroup("pick", "Pick one", "choose_n", (ReqItem(pattern="EL:3000"), ReqItem(course="EL 3100")), n=1),
    )
    r = audit(prog, cat, [Taken("EL 3100", 3, "A"), Taken("EL 3200", 3, "A")])
    assert [g.status for g in r.groups] == ["met", "met"]


def test_shareable_group_reuses_a_course():
    cat = tiny_catalog()
    prog = tiny_program(
        ReqGroup("lit", "Literature", "choose_n", (ReqItem(course="TG 1000"),), n=1),
        ReqGroup("dp", "Diverse Perspectives", "hours", (ReqItem(tag="DP"),), hours=3, shareable=True),
    )
    r = audit(prog, cat, [Taken("TG 1000", 3, "B")])
    assert [g.status for g in r.groups] == ["met", "met"]


def test_retake_below_minimum_grade():
    cat = tiny_catalog()
    r, plan = run(tiny_program(), cat, [Taken("AA 1000", 3, "A"), Taken("AA 2000", 3, "D+")])
    assert [(x.code, x.grade, x.min_grade) for x in r.retakes] == [("AA 2000", "D+", "C")]
    planned = {c.code: c for t in plan.terms for c in t.courses}
    assert "AA 2000" in planned and any(rs.kind == "retake" for rs in planned["AA 2000"].reasons)
    # AA 3000 has to wait for the retake: the D+ does not meet its C prerequisite.
    terms = {c.code: t.term for t in plan.terms for c in t.courses}
    assert parse_term(terms["AA 3000"]) > parse_term(terms["AA 2000"])


# --- US-5.1 ------------------------------------------------------------------------------------

@pytest.mark.parametrize("student", demo_students(), ids=lambda s: s["id"])
def test_every_requirement_placed_or_warned(student):
    """If the student finishes everything in the plan, every requirement group is met — or the
    plan carries a warning about it. Nothing is silently dropped."""
    cat, programs = load_catalog()
    prog = programs[student["program_id"]]
    taken = demo_taken(student, cat)
    _, plan = run(prog, cat, taken, student["start_term"])
    finished = [replace(t, grade=t.grade or "B") for t in taken] + \
               [Taken(c.code, c.credits, "B") for t in plan.terms for c in t.courses]
    after = audit(prog, cat, finished)
    warned = {w.group for w in plan.warnings}
    for g in after.groups:
        assert g.status == "met" or g.id in warned, f"{g.name}: {g.remaining}"


@pytest.mark.parametrize("student", demo_students(), ids=lambda s: s["id"])
def test_plan_respects_prereqs_offerings_and_load(student):
    cat, programs = load_catalog()
    taken = demo_taken(student, cat)
    _, plan = run(programs[student["program_id"]], cat, taken, student["start_term"])
    assert verify(plan, cat, taken) == []
    assert all(t.hours <= 18 for t in plan.terms)
    assert all(t.light == (t.hours < 12) for t in plan.terms)


def test_verify_catches_broken_plans():
    """The checker must disagree with a planner that cheats, one rule at a time. Plans are built by
    hand (duck-typed), the same way an advisor's edited plan would be checked."""
    cat = tiny_catalog(min_hours={"AA 3000": 6})
    taken = [Taken("AA 1000", 3, "A")]

    def plan(*terms):
        return SimpleNamespace(terms=[SimpleNamespace(term=code, courses=[SimpleNamespace(code=c, credits=3)
                                                                          for c in codes])
                                      for code, codes in terms])

    good = plan(("2027SP", ["AA 2000", "SP 1000"]), ("2027FA", ["AA 3000"]))
    assert verify(good, cat, taken) == []
    rules = lambda p: {v.rule for v in verify(p, cat, taken)}  # noqa: E731
    assert "prerequisite" in rules(plan(("2027SP", ["AA 3000", "AA 2000"])))
    assert "standing" in rules(plan(("2027SP", ["AA 2000", "AA 3000"])))
    assert "offering" in rules(plan(("2027FA", ["SP 1000"])))
    assert "duplicate" in rules(plan(("2027SP", ["AA 2000"]), ("2027FA", ["AA 2000"])))
    assert "unknown_course" in rules(plan(("2027SP", ["ZZ 9999"])))
    assert "load" in rules(plan(("2027SP", ["AA 2000", "SP 1000", "TG 1000", "EL 3100", "EL 3200",
                                            "GAP 1000", "NEEDY 2000"])))


@pytest.mark.parametrize("student", demo_students(), ids=lambda s: s["id"])
def test_forecast_is_deterministic(student):
    cat, programs = load_catalog()
    prog = programs[student["program_id"]]
    taken = demo_taken(student, cat)
    a = run(prog, cat, taken, student["start_term"])[1]
    b = run(prog, cat, list(reversed(taken)), student["start_term"])[1]
    assert a == b


def test_start_term_and_summer():
    cat = tiny_catalog(offered={c: (FA, SP, Offering("SU")) for c in tiny_catalog().courses})
    _, plan = run(tiny_program(), cat, [], start="2027SP", settings=Settings(target_hours=3, max_hours=3))
    assert plan.start_term == "2027SP" and plan.terms[0].term == "2027SP"
    assert not any(t.term.endswith("SU") for t in plan.terms)
    _, summer = run(tiny_program(), cat, [], start="2027SP",
                    settings=Settings(include_summer=True, target_hours=3, max_hours=3))
    assert any(t.term.endswith("SU") for t in summer.terms)
    assert parse_term(summer.projected_term) < parse_term(plan.projected_term)
    assert plan.projected_term == plan.terms[-1].term


def test_nothing_left():
    cat = tiny_catalog()
    taken = [Taken(c, 3, "A") for c in ["AA 1000", "AA 2000", "AA 3000", "SP 1000"]]
    _, plan = run(tiny_program(), cat, taken)
    assert plan.complete and plan.terms == [] and plan.projected_term is None


def test_compaction_graduates_sooner():
    """Jordan (demo-02) used to end on a 3-hour Spring because a Spring-only course was crowded out;
    the last term must not be one that fits into earlier terms."""
    cat, programs = load_catalog()
    s = next(s for s in demo_students() if s["id"] == "demo-02")
    _, plan = run(programs[s["program_id"]], cat, demo_taken(s, cat), s["start_term"])
    assert plan.projected_term == "2028FA"


def test_free_elective_hours_reported():
    cat, programs = load_catalog()
    s = next(s for s in demo_students() if s["id"] == "demo-01")
    result, plan = run(programs[s["program_id"]], cat, demo_taken(s, cat), s["start_term"])
    planned = sum(t.hours for t in plan.terms)
    assert plan.free_elective_hours == 127 - (result.hours_done + result.hours_in_progress + planned) > 0


# --- US-5.2 ------------------------------------------------------------------------------------

@pytest.mark.parametrize("student", demo_students(), ids=lambda s: s["id"])
def test_every_planned_course_has_a_reason(student):
    cat, programs = load_catalog()
    _, plan = run(programs[student["program_id"]], cat, demo_taken(student, cat), student["start_term"])
    for t in plan.terms:
        for c in t.courses:
            assert c.reasons, c.code
            for r in c.reasons:  # each reason is checkable against the catalog
                if r.kind == "unlocks":
                    assert any(c.code in pg.any_of for pgs in cat.prereqs.values() for pg in pgs)
                if r.kind == "offering":
                    assert len(cat.offered[c.code]) < 2 or any(o.years != "every" for o in cat.offered[c.code]) \
                        or any(o.season == "SU" for o in cat.offered[c.code])


def test_deferred_course_says_so():
    cat = tiny_catalog()
    _, plan = run(tiny_program(), cat, [Taken("AA 1000", 3, "A"), Taken("AA 2000", 3, "A"),
                                        Taken("AA 3000", 3, "A")], start="2027FA")
    sp = next(c for t in plan.terms for c in t.courses if c.code == "SP 1000")
    assert sp.deferred_from == "2027FA"


def test_prerequisite_gap_is_filled():
    cat = tiny_catalog()
    prog = tiny_program(ReqGroup("x", "Needs a gap", "all", (ReqItem(course="NEEDY 2000"),)))
    _, plan = run(prog, cat, [])
    planned = {c.code: c for t in plan.terms for c in t.courses}
    assert "GAP 1000" in planned
    assert planned["GAP 1000"].reasons[0].text == "Needed before NEEDY 2000"


def test_class_standing_waits_for_hours():
    cat, programs = load_catalog()
    s = next(s for s in demo_students() if s["id"] == "demo-01")
    result, plan = run(programs[s["program_id"]], cat, demo_taken(s, cat), s["start_term"])
    hours = result.hours_done + result.hours_in_progress
    for t in plan.terms:
        for c in t.courses:
            assert hours >= cat.min_hours.get(c.code, 0), f"{c.code} in {t.term} with {hours} hours"
        hours += t.hours


# --- US-5.4 ------------------------------------------------------------------------------------

def test_unplaceable_course_warns():
    cat = tiny_catalog(offered={**tiny_catalog().offered, "SP 1000": ()})
    _, plan = run(tiny_program(), cat, [])
    assert plan.needs_review
    w = next(w for w in plan.warnings if w.code == "SP 1000")
    assert "SP 1000" in w.message and w.group == "core"
