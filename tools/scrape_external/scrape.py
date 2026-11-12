"""Scrape the course lists of the top transfer schools' public catalogs (spec 07, US-7.1).

All five schools publish their catalogs on Acalog. The "courses" page of a catalog, opened with
``expand=1``, lists 100 courses per page with each description inline, so a whole catalog is a few
dozen requests. The scraper:

* reads robots.txt first, skips anything it disallows, and waits the crawl-delay it asks for (120 s
  for every crawler on these sites) between requests to the same host;
* keeps every page it fetched in ``data/private/scrape-cache/`` (git-ignored), so a rerun or a parser
  fix never fetches a page twice;
* keeps undergraduate courses only (no learning-support 0xxx courses, nothing numbered 500 or above
  at a university) and writes ``data/external/<slug>/courses.csv``.

    python3 tools/scrape_external/scrape.py                 # all schools
    python3 tools/scrape_external/scrape.py volstate utk    # some of them
    python3 tools/scrape_external/scrape.py --parse-only    # rebuild CSVs from the cache, no requests
"""
from __future__ import annotations

import csv
import html
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external"
CACHE = ROOT / "data" / "private" / "scrape-cache"
BROWSER_HOSTS = {"nscc", "columbiastate", "utk", "utc"}  # their course pages answer with a challenge
BROWSER = ROOT / "tools" / "scrape_lipscomb" / "scrape.mjs"  # headless fetch for challenge pages
AGENT = "VisorCatalogReader/0.1 (Lipscomb University student project; public course lists only)"


@dataclass(frozen=True)
class School:
    slug: str
    name: str  # as in data/demo/schools.csv
    base: str  # catalog host
    kind: str  # community_college / university
    catalog_hint: str = "Undergraduate"  # which catalog in the picker, newest first


SCHOOLS = [
    School("nscc", "Nashville State Community College", "https://nscc.catalog.acalog.com", "community_college"),
    School("volstate", "Volunteer State Community College", "https://catalog.volstate.edu", "community_college"),
    School("columbiastate", "Columbia State Community College", "https://catalog.columbiastate.edu",
           "community_college"),
    School("utk", "University of Tennessee, Knoxville", "https://catalog.utk.edu", "university"),
    School("utc", "University of Tennessee at Chattanooga", "https://utc.catalog.acalog.com", "university"),
]


class Fetcher:
    """One host at a time, robots.txt honoured, every page cached."""

    def __init__(self, school: School, offline: bool):
        self.school, self.offline, self.last = school, offline, 0.0
        self.cache = CACHE / school.slug
        self.cache.mkdir(parents=True, exist_ok=True)
        self.robots = urllib.robotparser.RobotFileParser(f"{school.base}/robots.txt")
        self.delay = 0.0
        self.browser_only = school.slug in BROWSER_HOSTS
        if not offline:
            self.robots.read()
            self.delay = float(self.robots.crawl_delay("*") or 1)
            self.last = time.monotonic()  # reading robots.txt was a request too

    def get(self, path: str, name: str) -> str:
        cached = self.cache / f"{name}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8", errors="replace")
        if self.offline:
            raise FileNotFoundError(f"{cached} is not cached (run without --parse-only)")
        url = urllib.parse.urljoin(self.school.base, path)
        if not self.robots.can_fetch("*", url):
            raise PermissionError(f"robots.txt disallows {url}")
        wait = self.delay - (time.monotonic() - self.last)
        if wait > 0:
            print(f"  waiting {wait:.0f}s (crawl-delay {self.delay:g}s)", flush=True)
            time.sleep(wait)
        body = ""
        if not self.browser_only:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode("utf-8", errors="replace") if r.status == 200 else ""
            self.last = time.monotonic()
        if not body.strip():
            # An empty 202 is a JavaScript challenge: load the page in a headless browser instead.
            # Once a host has challenged us, go straight to the browser (one request per page, not two).
            if not self.browser_only:
                print(f"  {url} needs a browser; waiting {self.delay:g}s", flush=True)
                time.sleep(self.delay)
                self.browser_only = True
            subprocess.run(["node", str(BROWSER), f"{name}={url}"], check=True, capture_output=True,
                           env={**os.environ, "CACHE_DIR": str(self.cache)})
            self.last = time.monotonic()
            body = cached.read_text(encoding="utf-8", errors="replace") if cached.exists() else ""
            if not body.strip():
                raise RuntimeError(f"empty page even in a browser: {url}")
        else:
            cached.write_text(body, encoding="utf-8")
        print(f"  fetched {url}", flush=True)
        return body


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def find_courses_page(f: Fetcher) -> tuple[str, str, str]:
    """(catoid, navoid, catalog title) for the newest undergraduate catalog's course list."""
    home = f.get("/", "home")
    options = re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', home)
    current = [(v, t.strip()) for v, t in options if "ARCHIVED" not in t.upper()]
    pick = next(((v, t) for v, t in current if f.school.catalog_hint.lower() in t.lower()), None)
    if pick is None:
        sel = re.search(r'<option[^>]*value="(\d+)"[^>]*selected[^>]*>([^<]+)', home)
        pick = (sel[1], sel[2].strip()) if sel else (re.search(r"catoid=(\d+)", home)[1], "")
    catoid, title = pick
    selected = re.search(r'<option[^>]*value="(\d+)"[^>]*selected', home)
    page = home if selected and selected[1] == catoid else f.get(f"/index.php?catoid={catoid}", f"index-{catoid}")
    links = re.findall(rf'href="[^"]*content\.php\?catoid={catoid}&(?:amp;)?navoid=(\d+)"[^>]*>([^<]+)<', page)
    ranked = sorted(links, key=lambda x: (0 if re.search(r"course descriptions", x[1], re.I) else
                                          1 if re.search(r"courses?\b.*alphabetic", x[1], re.I) else
                                          2 if re.fullmatch(r"\s*courses?\s*", x[1], re.I) else 9))
    if not ranked or not re.search(r"course", ranked[0][1], re.I):
        raise LookupError(f"{f.school.slug}: no course list link found in catalog {catoid}")
    return catoid, ranked[0][0], title


CODE = re.compile(r"^([A-Z][A-Z&]{1,5})\s+(\d{2,4}[A-Z]{0,2})\s*[-–]\s*(.+)$")


def parse_courses(page: str) -> list[dict]:
    out = []
    parts = re.split(r"<h3>", page)[1:]
    for part in parts:
        head, _, rest = part.partition("</h3>")
        m = CODE.match(_text(head).replace("\xa0", " "))
        if not m:
            continue
        body = re.split(r"<h3>|</li>", rest)[0]
        cred = re.search(r"Credit(?:s| Hours| Hour\(s\))?:?\s*(?:</strong>)?\s*(?:<strong>)?\s*\(?\s*"
                         r"(\d+(?:\.\d+)?)(?:\s*(?:-|–|to|or)\s*(\d+(?:\.\d+)?))?", body)
        after = body.split("<hr>", 1)[-1]
        if cred is None:  # "(Honors Option Offered)<br>3 Credits *<br>2 Class Hours<br><br>description" (Nashville State)
            cred = re.search(r"\(?(\d+(?:\.\d+)?)(?:\s*(?:-|–|to)\s*(\d+(?:\.\d+)?))?\)?\s*Credits?\b",
                             _text(after[:300]))
            lines = re.split(r"<br\s*/?>", after)
            header = re.compile(r"\(.*\)(?:\s*Credits?\b.*)?|\d[\d.\s*–-]*(?:to\s*\d+\s*)?(?:Credits?\b.*)?|"
                                r"\d.*\bHours?\b.*|")
            while lines and len(_text(lines[0])) < 70 and header.fullmatch(_text(lines[0])):
                bare = re.fullmatch(r"(\d+(?:\.\d+)?)", _text(lines[0]))
                if cred is None and bare:  # "2<br>15 private lesson hours" (applied music)
                    cred = bare
                lines.pop(0)
            # The description is the longest paragraph before the prerequisites, not an availability note.
            paras = [x for x in re.split(r"<br\s*/?>", re.split(r"<strong>", "<br>".join(lines))[0]) if _text(x)]
            after = max(paras, key=lambda x: len(_text(x))) if paras else ""
        desc = _text(re.split(r"<strong>", after)[0])
        out.append({"subject": m[1], "number": m[2], "title": m[3].strip(" *^"),
                    "credits": ((cred.re.groups > 1 and cred[2]) or cred[1]) if cred else "", "description": desc[:400]})
    return out


def undergraduate(c: dict, kind: str) -> bool:
    digits = re.match(r"\d+", c["number"])[0]
    if digits.startswith("0"):
        return False  # learning support: not college credit
    return not (kind == "university" and len(digits) >= 3 and int(digits[:3]) >= 500)


def scrape(school: School, offline: bool) -> dict:
    f = Fetcher(school, offline)
    catoid, navoid, title = find_courses_page(f)
    path = f"/content.php?catoid={catoid}&navoid={navoid}&expand=1"
    first = f.get(path, f"courses-{catoid}-1")
    pages = max([1] + [int(n) for n in re.findall(r"filter%5Bcpage%5D=(\d+)", first)])
    courses = parse_courses(first)
    for n in range(2, pages + 1):
        page = f.get(f"/content.php?catoid={catoid}&navoid={navoid}&filter%5Bitem_type%5D=3"
                     f"&filter%5Bonly_active%5D=1&filter%5B3%5D=1&filter%5Bcpage%5D={n}&expand=1",
                     f"courses-{catoid}-{n}")
        courses += parse_courses(page)
    year = re.search(r"(20\d\d)", title)
    seen, rows, skipped, no_credits = set(), [], 0, []
    for c in courses:
        key = (c["subject"], c["number"])
        if key in seen or not undergraduate(c, school.kind):
            skipped += 1
            continue
        if not c["credits"]:
            no_credits.append(f"{c['subject']} {c['number']}")  # never guessed; listed in sources.md
            continue
        seen.add(key)
        rows.append({**c, "catalog_year": year[1] if year else "", "source_url": urllib.parse.urljoin(school.base, path)})
    (OUT / school.slug).mkdir(parents=True, exist_ok=True)
    with open(OUT / school.slug / "courses.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["subject", "number", "title", "credits", "description", "catalog_year",
                                           "source_url"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["subject"], r["number"])))
    return {"school": school.name, "catalog": title, "pages": pages, "courses": len(rows), "skipped": skipped,
            "no_credits": no_credits}


def main(argv: list[str]) -> None:
    offline = "--parse-only" in argv
    wanted = [a for a in argv if not a.startswith("--")]
    for s in SCHOOLS:
        if wanted and s.slug not in wanted:
            continue
        print(f"{s.slug}: {s.base}", flush=True)
        try:
            print(f"  done: {scrape(s, offline)}", flush=True)
        except Exception as e:  # one school failing shouldn't stop the others
            print(f"  FAILED: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
