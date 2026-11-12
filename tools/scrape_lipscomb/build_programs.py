"""Add Biology, Management (B.B.A.), Nursing (BSN) and Psychology to data/catalog/2026-27/ (spec 07, US-7.3).

Reads the cached catalog pages through ``parse.py`` and appends rows to the catalog CSVs. Rows that
already exist (the CS program's courses, prerequisites and offerings) are never changed, so the CS
plans stay exactly as they were. Every simplification is appended to ``notes.md``.

    python3 tools/scrape_lipscomb/build_programs.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse  # noqa: E402

CAT = parse.ROOT / "data" / "catalog" / "2026-27"
SRC = "https://catalog.lipscomb.edu/preview_program.php?catoid=33&poid="
NOTES: list[str] = []


def note(text: str) -> None:
    NOTES.append(text)


def section(sections, heading_pattern: str) -> list[dict]:
    """Course lines under the first heading matching ``heading_pattern``, or under the next heading
    that has any (a page often puts 'Five courses selected from:' between a heading and its list)."""
    for k, (h, _) in enumerate(sections):
        if re.search(heading_pattern, h, re.I):
            for _, items in sections[k:]:
                found = [i for i in items if "code" in i]
                if found:
                    return found
    raise LookupError(heading_pattern)


def codes(items) -> list[str]:
    return [i["code"] for i in items]


def menu(items) -> list[str]:
    """A choose-from list in the planner's recommendation order: courses taught in fall or spring first,
    then summer-only ones (the planner leaves summers out unless asked), keeping the catalog's order."""
    return [i["code"] for i in sorted(items, key=lambda i: 0 if {"FA", "SP"} & set(i.get("terms") or ["FA"]) else 1)]


# --- The Core (Journey) groups every non-CS program needs --------------------------------------
# The CS program models the Core groups its major does not already cover (notes.md, item 4). The
# other majors need the ones CS skipped too. Menus come from the Core page (navoid 2779) where it was
# readable, else from the CS rows, which were transcribed from that page.

def core_groups(key: str, *, skip: set[str] = frozenset(), extra: dict | None = None) -> list[dict]:
    g = [
        {"id": "core-compass", "name": "Core: Compass first-year seminar", "rule": "all", "items": ["LU 1303"]},
        {"id": "core-powers", "name": "Core: POWERS (writing and speaking)", "rule": "all", "items": ["LU 1013", "LU 1023"]},
        {"id": "core-bible-story", "name": "Core: Seek through scripture", "rule": "all",
         "items": ["BI 1093", "BI 1073", "BI 1083"]},
        {"id": "core-christianity-society", "name": "Core: Christianity & Society", "rule": "choose_n", "n": 1,
         "items": ["BI 3213", "BI 4213", "BI 1003"]},
        {"id": "core-literature", "name": "Core: Literary inquiry", "rule": "choose_n", "n": 1,
         "items": ["EN 2103", "EN 2113", "EN 2123", "EN 2133", "EN 2143"]},
        {"id": "core-history", "name": "Core: Great Ideas in History", "rule": "all", "items": ["HI 1003"]},
        {"id": "core-great-ideas", "name": "Core: Great Ideas in Politics or Philosophy", "rule": "choose_n", "n": 1,
         "items": ["PO 1003", "PL 1003"]},
        {"id": "core-vfv", "name": "Core: Virtue, Flourishing & Vocation", "rule": "choose_n", "n": 1,
         "items": ["BI 3433"]},
        {"id": "core-science", "name": "Core: Scientific Inquiry", "rule": "choose_n", "n": 1,
         "items": ["SCI 2304", "BY 1134", "BY 2213", "CM 1024"]},
        {"id": "core-social-inquiry", "name": "Core: Social Inquiry", "rule": "hours", "hours": 3,
         "tags": ["SOCIAL_INQUIRY"]},
        {"id": "core-artistic-inquiry", "name": "Core: Artistic Inquiry", "rule": "all", "items": ["ARTS 2303"]},
        {"id": "core-diverse-perspectives", "name": "Core: Diverse Perspectives", "rule": "hours", "hours": 3,
         "tags": ["DP"], "shareable": True},
    ]
    for e in (extra or {}).values():
        g.append(e)
    return [{**x, "id": f"{key}-{x['id']}"} for x in g if x["id"] not in skip]


def programs() -> list[dict]:
    out = []

    # Biology, B.S. ------------------------------------------------------------------------------
    bio = parse.program_sections("biology")
    core = section(bio, r"Biology Core")
    electives = section(bio, r"Biology electives")
    chem = section(bio, r"Chemistry")
    usable = [i for i in electives if not i["code"].endswith("V") and i["years"] != "demand"]
    note("Biology: elective menu 'five courses selected from' modeled as choose 5 of the listed courses; "
         "the 'BY 2213 or (BY 3514 and BY 3524)' and 'BY 2424 or BY 3214' pairs are listed as separate "
         "options, and variable-credit BY 450V/460V (chair approval) are left out. CONFIRM.")
    note("Biology: courses offered 'in alternate years' are modeled as every year (parity not stated).")
    out.append({
        "id": "bio-bs-2026-27", "name": "Biology", "degree": "B.S.", "total": 126, "poid": "11055",
        "groups": [
            {"id": "bio-major-core", "name": "Biology core", "rule": "all", "min_grade": "C", "items": codes(core)},
            {"id": "bio-electives", "name": "Biology electives", "rule": "choose_n", "n": 5, "min_grade": "C",
             "items": menu(usable)},
            {"id": "bio-chemistry", "name": "Chemistry", "rule": "all", "items": codes(chem)},
            {"id": "bio-math", "name": "Core: Quantitative Inquiry (MA 1113 or higher)", "rule": "all",
             "items": ["MA 1113"]},
            *core_groups("bio", skip={"core-science"}),
        ]})
    note("Biology: Scientific Inquiry is met by the major (BY, CM); Quantitative Inquiry by MA 1113. "
         "Total 126 hours is the university minimum (College of Business page); the program page states "
         "only the 56-hour major. Free electives fill the rest.")

    # Psychology, B.S. ---------------------------------------------------------------------------
    ps = parse.program_sections("psychology")
    req = section(ps, r"Required courses")
    elec = [i for i in section(ps, r"Electives") if not i["code"].endswith("V") and i["years"] != "demand"]
    note("Psychology: electives 'choose 9 hours' modeled as 9 hours from the listed courses that are regularly "
         "offered; on-demand courses and variable-credit topics/internships are left out of the planner's "
         "picks (they still count if taken).")
    out.append({
        "id": "psych-bs-2026-27", "name": "Psychology", "degree": "B.S.", "total": 126, "poid": "10973",
        "groups": [
            {"id": "psych-required", "name": "Psychology required courses", "rule": "all", "min_grade": "C",
             "items": codes(req)},
            {"id": "psych-electives", "name": "Psychology electives", "rule": "hours", "hours": 9, "min_grade": "C",
             "items": menu(elec)},
            {"id": "psych-math", "name": "Core: Quantitative Inquiry", "rule": "choose_n", "n": 1,
             "items": ["MA 1113", "MA 2183"]},
            *core_groups("psych"),
        ]})
    note("Psychology: minimum grade C in the major is assumed (prerequisite chains require C); the page "
         "states none. Scientific Inquiry modeled as SCI 2304 or one foundational science course (BY 1134, BY 2213, CM 1024); the Core page says '4 hours of foundational science coursework'. CONFIRM.")

    # Nursing, BSN (traditional) -----------------------------------------------------------------
    nu = parse.program_sections("nursing")
    specific = section(nu, r"Specific courses required")
    nurs = [c for c in codes(specific) if c.startswith("NURS")]
    support = [c for c in codes(specific) if not c.startswith("NURS") and c not in ("MA 2183", "PS 2503")]
    nelect = [i for i in section(nu, r"Nursing Specific Elective") if not i["code"].upper().endswith("V")]
    out.append({
        "id": "nursing-bsn-2026-27", "name": "Nursing", "degree": "B.S.N.", "total": 128, "poid": "11170",
        "gate": {"pattern": "NURS:3", "message": "Upper-division nursing courses need admission to the nursing "
                                                   "program (upper-division BSN curriculum)."},
        "groups": [
            {"id": "nursing-major", "name": "Nursing courses", "rule": "all", "min_grade": "C", "items": nurs},
            {"id": "nursing-support", "name": "Science and support courses", "rule": "all", "min_grade": "C",
             "items": support},
            {"id": "nursing-stats", "name": "Statistics", "rule": "choose_n", "n": 1, "items": ["MA 2183", "PS 2503"]},
            {"id": "nursing-elective", "name": "Nursing elective", "rule": "hours", "hours": 3, "items": menu(nelect)},
            {"id": "nursing-math", "name": "Core: Quantitative Inquiry", "rule": "all", "items": ["MA 1113"]},
            *core_groups("nursing", skip={"core-christianity-society", "core-social-inquiry", "core-great-ideas",
                                          "core-vfv", "core-science"}),
        ]})
    note("Nursing: BI 3213 (Christianity & Society) and PS 1113 (Social Inquiry) are in the nursing course "
         "list, so those Core groups are not repeated. The medical-terminology certificate (non-credit) is not "
         "modeled. Admission to the upper-division program is shown as a warning on every nursing plan, "
         "never decided by the planner.")
    note("Nursing: the program page's Core list has no Great Ideas in Politics/Philosophy course; none is "
         "required here. NURS 3993 is the Virtue, Flourishing & Vocation course and the sciences cover Scientific "
         "Inquiry. CONFIRM.")
    note("Nursing: minimum grade C assumed for nursing and science courses; CONFIRM with the School of Nursing.")

    # Management, B.B.A. -------------------------------------------------------------------------
    mg = parse.program_sections("management")
    major = [c for c in codes(section(mg, r"Specific courses required"))]
    bba_core = ["AC 2503", "AC 2513", "BA 2103", "BA 390V", "BA 3703", "BA 3993", "BA 4503", "DS 2503", "DS 3403",
                "DS 4813", "EC 2403", "EC 2413", "FI 3503", "MG 3503", "MG 3613", "MK 3503", "OSCM 3503",
                "MA 2183", "BA 2601"]
    out.append({
        "id": "mgmt-bba-2026-27", "name": "Management", "degree": "B.B.A.", "total": 126, "poid": "11132",
        "groups": [
            {"id": "mgmt-bba-core", "name": "Business core (B.B.A.)", "rule": "all", "min_grade": "C", "items": bba_core},
            {"id": "mgmt-international", "name": "International business", "rule": "choose_n", "n": 1,
             "items": ["BA 3603", "AC 4803", "FI 3603", "FI 4803", "MG 4803", "MK 4803"]},
            {"id": "mgmt-major", "name": "Management major", "rule": "all", "min_grade": "C", "items": major},
            {"id": "mgmt-upper-electives", "name": "Upper-division business electives", "rule": "hours", "hours": 15,
             "patterns": ["AC|BA|DS|EC|FI|MG|MK|OSCM:3"]},
            *core_groups("mgmt", skip={"core-social-inquiry", "core-vfv"}),
        ]})
    note("Management: the B.B.A. business core is from the College of Business page (navoid 2700). EC 2403 meets "
         "Social Inquiry and MA 2183 meets Quantitative Inquiry (both in the business core), so those Core groups "
         "are not repeated.")
    note("Management: the concentration (9 h) is modeled as the Integrated Management concentration (any upper-"
         "division business), combined with the major's 'one upper-division COB course' and the business core's "
         "'any 3000/4000 business course' into one 15-hour group. A student choosing Healthcare, Data Analytics or "
         "Supply Chain needs those courses named by an advisor (spec 06 pins). CONFIRM.")
    note("Management: BA 3993 (Business Values: Virtue, Flourishing and Vocation) in the business core meets "
         "the Core's Virtue, Flourishing & Vocation requirement.")
    note("Biology and Psychology have no discipline Virtue, Flourishing & Vocation course in the pages read, so "
         "the Core's alternative BI 3433 Practices for Spiritual Formation is used. CONFIRM.")
    note("Lipscomb has no 'Business Administration' major; Management, B.B.A. (the general management degree) "
         "stands in for it (decision 2026-11-12).")
    return out


# --- Writing the catalog files --------------------------------------------------------------------

def _read(name: str) -> tuple[list[str], list[dict]]:
    with open(CAT / name, newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames), list(r)


def _write(name: str, fields: list[str], rows: list[dict]) -> None:
    with open(CAT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build() -> dict:
    progs = programs()
    entries = parse.course_entries()
    from_pages = {i["code"]: i for p in ("biology", "psychology", "nursing", "management")
                  for _, items in parse.program_sections(p) for i in items if "code" in i}
    cf, courses = _read("courses.csv")
    have = {f"{r['subject']} {r['number']}" for r in courses}
    pf, prereqs = _read("prereqs.csv")
    has_prereqs = {r["course"] for r in prereqs}
    tf, terms = _read("course_terms.csv")
    has_terms = {r["course"] for r in terms}
    sf, standing = _read("course_standing.csv")
    has_standing = {r["course"] for r in standing}

    # Two Core courses named on the Core page whose description pages were not read; added by hand.
    manual = {
        "BI 3433": {"code": "BI 3433", "title": "Practices for Spiritual Formation", "credits": 3, "terms": ["FA", "SP"],
                    "years": "every", "standing": 60,
                    "why": "Core page: the Virtue, Flourishing & Vocation course is taken in the junior or senior year"},
        "SCI 2304": {"code": "SCI 2304", "title": "Scientific Inquiry: The Practice of Progress", "credits": 4,
                     "terms": ["FA", "SP"], "years": "every"},
    }
    for code, m in manual.items():
        from_pages.setdefault(code, m)
        note(f"{code} {m['title']}: course row added from the Core page (credits {m['credits']}, fall and spring "
             f"assumed{'; junior standing' if m.get('standing') else ''}); its description page was not read. CONFIRM.")
    wanted = [c for p in progs for g in p["groups"] for c in g.get("items", [])]
    queue, seen, added = list(dict.fromkeys(wanted)), set(), []
    while queue:
        code = queue.pop(0)
        if code in seen:
            continue
        seen.add(code)
        info = entries.get(code) or from_pages.get(code)
        if code not in have:
            if info is None:
                note(f"{code} is named by a program but its course description was not read; left out of the catalog "
                     f"files (the audit lists it as not in the catalog). CONFIRM.")
                continue
            credits = info.get("credits") or 3
            if info.get("credit_text") and re.search(r"[-,]", info["credit_text"]):
                note(f"{code}: variable credit '{info['credit_text']}' modeled as {credits:g}.")
            subject, number = code.split(" ")
            courses.append({"subject": subject, "number": number, "title": info["title"], "credits": f"{credits:g}"})
            have.add(code)
            added.append(code)
        if info is None:
            continue
        if code not in has_terms:
            seasons, years = info.get("terms") or [], info.get("years", "every")
            if not seasons:
                seasons = ["FA", "SP"]
                note(f"{code}: catalog gives no regular term ({'on demand' if years == 'demand' else 'none'}); "
                     f"modeled as fall+spring. CONFIRM.")
            if years == "alternate":
                note(f"{code}: offered in alternate years (parity not stated); modeled as every year.")
            terms += [{"course": code, "season": s, "years": "every"} for s in seasons]
            has_terms.add(code)
        if code in manual and manual[code].get("standing") and code not in has_standing:
            standing.append({"course": code, "min_hours": str(manual[code]["standing"]), "why": manual[code]["why"]})
            has_standing.add(code)
        entry = entries.get(code)
        if entry and code not in has_prereqs:
            groups, hours, skipped = parse.parse_prereq(entry["prereq_text"])
            for any_of, grade in groups:
                usable = [c for c in any_of if c != code and (c in have or c in entries or c in from_pages)]
                if not usable:
                    note(f"{code}: prerequisite {' or '.join(any_of)} is outside the courses read; dropped.")
                    continue
                prereqs.append({"course": code, "any_of": "|".join(usable), "min_grade": grade or ""})
                queue += usable
            if skipped:
                note(f"{code}: prerequisite text not modeled: '{'; '.join(skipped)}'.")
            if hours and code not in has_standing:
                standing.append({"course": code, "min_hours": str(hours),
                                 "why": f"Catalog prerequisite: {entry['prereq_text'][:120]}"})
                has_standing.add(code)
            has_prereqs.add(code)

    courses.sort(key=lambda r: (r["subject"], r["number"]))
    _write("courses.csv", cf, courses)
    _write("prereqs.csv", pf, prereqs)
    _write("course_terms.csv", tf, terms)
    _write("course_standing.csv", sf, standing)

    gf, groups = _read("req_groups.csv")
    itf, items = _read("req_items.csv")
    pgf, prog_rows = _read("programs.csv")
    new_ids = {p["id"] for p in progs}
    groups = [g for g in groups if g["program"] not in new_ids]
    items = [i for i in items if not any(i["group"].startswith(p["id"].split("-")[0] + "-") for p in progs)]
    prog_rows = [r for r in prog_rows if r["id"] not in new_ids]
    for p in progs:
        prog_rows.append({"id": p["id"], "name": p["name"], "degree": p["degree"], "catalog_year": "2026-27",
                          "total_hours": str(p["total"]), "source": SRC + p["poid"], "reviewed_on": "2026-11-12"})
        for sort, g in enumerate(p["groups"], 1):
            groups.append({"id": g["id"], "program": p["id"], "name": g["name"], "rule": g["rule"],
                           "n": str(g.get("n", "")), "hours": str(g.get("hours", "")), "min_grade": g.get("min_grade", ""),
                           "shareable": "1" if g.get("shareable") else "0", "sort": str(sort)})
            k = 0
            for c in g.get("items", []):
                if c in have:
                    k += 1
                    items.append({"group": g["id"], "course": c, "pattern": "", "tag": "", "sort": str(k)})
            for pat in g.get("patterns", []):
                k += 1
                items.append({"group": g["id"], "course": "", "pattern": pat, "tag": "", "sort": str(k)})
            for tag in g.get("tags", []):
                k += 1
                items.append({"group": g["id"], "course": "", "pattern": "", "tag": tag, "sort": str(k)})
    _write("req_groups.csv", gf, groups)
    _write("req_items.csv", itf, items)
    _write("programs.csv", pgf, prog_rows)

    gates = [{"program": p["id"], "pattern": p["gate"]["pattern"], "message": p["gate"]["message"]}
             for p in progs if p.get("gate")]
    _write("program_gates.csv", ["program", "pattern", "message"], gates)

    notes_path = CAT / "notes.md"
    text = notes_path.read_text()
    marker = "\n## Added 2026-11-12: Biology, Management (B.B.A.), Nursing (BSN), Psychology (spec 07)\n"
    text = text.split(marker)[0].rstrip("\n") + "\n" + marker + "\n" + \
        "\n".join(f"- {n}" for n in dict.fromkeys(NOTES)) + "\n"
    notes_path.write_text(text)
    return {"programs": [p["id"] for p in progs], "courses_added": len(added), "notes": len(set(NOTES))}


if __name__ == "__main__":
    print(build())
