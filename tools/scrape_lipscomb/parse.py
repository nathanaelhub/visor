"""Turn cached Lipscomb catalog pages into course facts (spec 07, US-7.3). No network: it reads
``data/private/scrape-cache/lipscomb/`` (filled by scrape.mjs).

* ``program_sections(name)``: a program page as [(heading, [item])], where an item is a course line
  (code, title, credits, terms, the "or"/"and" that joins it to the next line) or plain text.
* ``course_entries()``: every course in the cached course-description pages, with its prerequisite
  sentence.
* ``parse_prereq(text)``: a prerequisite sentence as groups of alternatives, a minimum grade and a
  standing (hours) requirement, plus the parts it could not model. Callers write those parts into
  ``notes.md``: every one is a judgment call a person should confirm.
"""
from __future__ import annotations

import glob
import os
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("LIPSCOMB_CACHE", ROOT / "data" / "private" / "scrape-cache" / "lipscomb"))

CODE = r"[A-Z]{2,5}\s?\d{3,4}[A-Za-z]?"
SEASON = {"F": "FA", "FA": "FA", "FALL": "FA", "SP": "SP", "SPRING": "SP", "SU": "SU", "SUMMER": "SU"}
STANDING = {"sophomore": 30, "junior": 60, "senior": 90}


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).replace("\xa0", " ").strip()


def norm_code(code: str) -> str:
    m = re.match(r"([A-Z]{2,5})\s?(\d{3,4}[A-Za-z]?)", code.strip())
    return f"{m[1]} {m[2].upper()}" if m else code.strip()


def terms_of(text: str) -> tuple[list[str], str]:
    """'F, SP, (SU on demand) Offered in alternate years' -> (['FA', 'SP'], 'every' | 'alternate' | 'demand')."""
    t = re.sub(r"\(SU on demand\)", "", text, flags=re.I)
    seasons = []
    for w in re.findall(r"\b(FALL|SPRING|SUMMER|FA|SP|SU|F)\b", t.upper()):
        s = SEASON[w]
        if s not in seasons:
            seasons.append(s)
    years = "alternate" if re.search(r"alternate years|not offered every year", text, re.I) else \
        "demand" if re.search(r"on demand", text, re.I) and not seasons else "every"
    return seasons, years


def _line(item_html: str) -> dict:
    t = _text(item_html)
    m = re.match(rf"({CODE})\s*[-–:]\s*(.+?)\s*(?:\(([\d.,\s-]+)\)|\b(\d)\b)?\s*((?:F|SP|SU|FA|Sp|Fa|Su)\b.*|Offered.*)?$", t)
    if not m:
        return {"text": t}
    rest = (m[5] or "")
    joiner = "or" if re.search(r"\bor\s*$", rest, re.I) or re.search(r"\bOR\s*$", t) else \
        "and" if re.search(r"\band\s*$", rest, re.I) else None
    credits = m[3] or m[4] or ""
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", credits)]
    seasons, years = terms_of(rest)
    return {"code": norm_code(m[1]), "title": m[2].strip(" *"), "credits": max(nums) if nums else None,
            "credit_text": credits.strip(), "terms": seasons, "years": years, "joiner": joiner, "text": t}


def program_sections(name: str) -> list[tuple[str, list[dict]]]:
    page = (CACHE / f"prog-{name}.html").read_text(encoding="utf-8")
    page = page[page.find('class="block_content"'):]
    end = page.rfind("Print (opens")
    page = page[:end] if end > 1000 else page
    out: list[tuple[str, list[dict]]] = [("", [])]
    for m in re.finditer(r"<h[2-6][^>]*>([\s\S]*?)</h[2-6]>|<li[^>]*>([\s\S]*?)</li>", page):
        if m[1] is not None:
            out.append((_text(m[1]), []))
        else:
            out[-1][1].append(_line(m[2]))
    return [(h, items) for h, items in out if h or items]


def course_entries() -> dict[str, dict]:
    """All courses in the cached prefix pages (prefix-XX.html), keyed by code."""
    out = {}
    for f in sorted(glob.glob(str(CACHE / "prefix-*.html"))):
        page = Path(f).read_text(encoding="utf-8")
        for part in re.split(r"<h3>", page)[1:]:
            head, _, rest = part.partition("</h3>")
            line = _line(head)
            if "code" not in line:
                continue
            body = _text(re.split(r"<h3>|</li>", rest)[0])
            pre = re.search(r"Prerequisites?\s*(?:\(s\))?\s*:?\s*(.+?)(?:(?<!\b[A-Z])\.\s+(?:Co-?requisite|Lecture|Laboratory|"
                            r"Fee|Offered|Note|Cross|This|Students|A |The )|\.$|$)", body)
            seasons, years = line["terms"], line["years"]
            out[line["code"]] = {**line, "description": body[:400], "prereq_text": pre[1].strip() if pre else "",
                                 "terms": seasons, "years": years}
    return out


def parse_prereq(text: str) -> tuple[list[tuple[list[str], str | None]], int, list[str]]:
    """'BY 1134 with a minimum grade of "C" and sophomore standing' ->
    ([(['BY 1134'], 'C')], 30, []). Clauses joined by 'and' are separate groups; codes joined by
    'or' are alternatives; a comma list without 'or' needs all of them. Unmodelled parts are returned."""
    if not text:
        return [], 0, []
    # Only the first sentence is the prerequisite; later ones are advice ("For students planning on
    # majoring in accounting a "B" or better in AC 2503 is required for AC 3503").
    t = re.split(r"\.\s+(?=[A-Z])", text.replace("“", '"').replace("”", '"'), maxsplit=1)[0]
    hours = max([STANDING[w] for w in STANDING if re.search(rf"\b{w}\b", t, re.I)] +
                [int(h) for h in re.findall(r"minimum (\d+) hours", t)], default=0)
    grade = None
    g = re.search(r'(?:minimum grade of|grade of|with an?)\s*"?([A-D][+-]?)"?', t)
    if g:
        grade = g[1]
    skipped = []
    groups: list[tuple[list[str], str | None]] = []
    for clause in re.split(r"\s*(?:;|\band\b(?![^()]*\)))\s*", t):
        codes = list(dict.fromkeys(norm_code(c) for c in re.findall(CODE, clause)))
        if codes and re.search(r"\bor\b", clause, re.I):
            groups.append((codes, grade))  # "BY 2424 or BY 3214": any one
        elif codes:
            groups.extend(([c], grade) for c in codes)  # "BY 1134, BY 1144, BY 3114": all of them
        elif clause.strip() and not re.search(r"standing|grade|hours|minimum|^\W*$", clause, re.I):
            skipped.append(clause.strip())
    return groups, hours, skipped
