"""Build the three fictional demo transcripts (spec 05, US-5.7) from the demo students.

Each PDF is generated from `data/demo/students/<file>.json`, so what Claude reads back can be checked
against the record it came from. Every page is stamped FICTIONAL. Never put a real record here.

    python3 data/demo/transcripts/build.py        # needs Chrome or Chromium (set CHROME=... to pick one)
"""
from __future__ import annotations

import csv
import glob
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1]
CATALOG = DATA / "catalog" / "2026-27"

# transcript id -> (student file, label shown in the app)
TRANSCRIPTS = {
    "freshman": ("01-new-freshman", "First-year student, courses in progress"),
    "transfer": ("03-transfer-nashville-state", "Transfer student from Nashville State"),
    "retake": ("04-needs-a-retake", "Student who needs a retake"),
}
IN_PROGRESS = "Fall 2026"
PAST_TERMS = ["Spring 2026", "Fall 2025", "Spring 2025", "Fall 2024"]  # newest first
PER_TERM = 5

QUALITY = {"A": 4, "A-": 3.7, "B+": 3.3, "B": 3, "B-": 2.7, "C+": 2.3, "C": 2, "C-": 1.7,
           "D+": 1.3, "D": 1, "D-": 0.7, "F": 0}


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        *sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-*/"
                                             "chrome-headless-shell-*/chrome-headless-shell")), reverse=True),
        *glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/"
                                      "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")),
        shutil.which("google-chrome") or "", shutil.which("chromium") or "",
    ]
    for c in candidates:
        if c and os.access(c, os.X_OK):
            return c
    sys.exit("No Chrome/Chromium found; set CHROME=/path/to/chrome")


def _terms(taken: list[dict]) -> list[tuple[str, list[dict]]]:
    """In-progress courses go in the current term; finished ones fill earlier terms, oldest first."""
    done = [t for t in taken if t.get("grade")]
    now = [t for t in taken if not t.get("grade")]
    chunks = [done[i:i + PER_TERM] for i in range(0, len(done), PER_TERM)]
    past = list(zip(reversed(PAST_TERMS[:len(chunks)]), chunks))
    return past + ([(IN_PROGRESS, now)] if now else [])


def render(student: dict, titles: dict, credits: dict, external: dict) -> str:
    e = html.escape
    name = student["name"].replace(" (fictional)", "")
    body = []
    total_h = total_q = 0.0
    for term, courses in _terms(student["taken"]):
        rows = []
        for t in courses:
            h = credits.get(t["code"], 3)
            g = t.get("grade") or "IP"
            if g in QUALITY:
                total_h += h
                total_q += h * QUALITY[g]
            rows.append(f"<tr><td>{e(t['code'])}</td><td>{e(titles.get(t['code'], ''))}</td>"
                        f"<td class=n>{h:g}</td><td class=n>{e(g)}</td></tr>")
        body.append(f"<h3>{e(term)}{' (in progress)' if term == IN_PROGRESS else ''}</h3>"
                    f"<table><tr><th>Course</th><th>Title</th><th class=n>Hours</th><th class=n>Grade</th></tr>"
                    f"{''.join(rows)}</table>")
    if student.get("transfer"):
        rows = []
        for t in student["transfer"]:
            title, h = external.get((t["school"], t["subject"], t["number"]), ("", "3"))
            rows.append(f"<tr><td>{e(t['school'])}</td><td>{e(t['subject'])} {e(t['number'])}</td>"
                        f"<td>{e(title)}</td><td class=n>{e(h)}</td><td class=n>{e(t.get('grade') or '')}</td></tr>")
        body.append("<h3>Transfer credit received</h3><table><tr><th>Institution</th><th>Course</th>"
                    "<th>Title</th><th class=n>Hours</th><th class=n>Grade</th></tr>" + "".join(rows) + "</table>")
    gpa = f"{total_q / total_h:.2f}" if total_h else "—"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Unofficial transcript (fictional)</title>
<style>
  @page {{ size: letter; margin: 0.6in; }}
  body {{ font: 10.5pt/1.35 Georgia, serif; color: #111; }}
  .stamp {{ position: fixed; top: 40%; left: 0; right: 0; text-align: center; transform: rotate(-24deg);
           font: bold 64pt Helvetica, sans-serif; color: rgba(200, 0, 0, .12); letter-spacing: 6px; }}
  header {{ border-bottom: 2px solid #111; padding-bottom: 6px; margin-bottom: 10px; }}
  h1 {{ font-size: 15pt; margin: 0; }} h3 {{ font-size: 11pt; margin: 14px 0 4px; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 4px 28px; font-size: 9.5pt; }}
  .banner {{ background: #fde8e8; border: 1px solid #c00; padding: 4px 8px; font: 9pt Helvetica, sans-serif; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
  th, td {{ text-align: left; padding: 2px 6px; border-bottom: 1px solid #ddd; }} .n {{ text-align: right; }}
</style></head><body>
<div class="stamp">FICTIONAL · DEMO</div>
<p class="banner">Fictional student for the Visor demo. Not a real record and not issued by any university.</p>
<header><h1>Unofficial Academic Transcript</h1>
<div class="meta"><span>Student: <b>{e(name)}</b></span><span>ID: {e(student['student_number'])}</span>
<span>Program: B.S. Computer Science (catalog 2026-27)</span><span>Printed: November 2026</span></div></header>
{''.join(body)}
<p class="meta" style="margin-top:14px"><span>Lipscomb hours graded: {total_h:g}</span><span>GPA: {gpa}</span></p>
<p class="banner" style="margin-top:18px">End of fictional transcript.</p>
</body></html>"""


def main() -> None:
    courses = _rows(CATALOG / "courses.csv")
    titles = {f"{r['subject']} {r['number']}": r["title"] for r in courses}
    credits = {f"{r['subject']} {r['number']}": float(r["credits"]) for r in courses}
    external = {(r["school"], r["subject"], r["number"]): (r["title"], r["credits"])
                for r in _rows(DATA / "demo" / "external_courses.csv")}
    chrome = _chrome()
    index = []
    with tempfile.TemporaryDirectory() as tmp:
        for tid, (stem, label) in TRANSCRIPTS.items():
            student = json.loads((DATA / "demo" / "students" / f"{stem}.json").read_text())
            page = Path(tmp) / f"{tid}.html"
            page.write_text(render(student, titles, credits, external))
            out = HERE / f"{tid}.pdf"
            subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True)
            index.append({"id": tid, "label": label, "file": out.name, "student_id": student["id"],
                          "name": student["name"]})
            print(f"Wrote {out}")
    (HERE / "index.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
