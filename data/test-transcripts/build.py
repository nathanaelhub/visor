"""Build fictional test transcripts for transcript reading (spec 07, US-7.5).

Each student below is made up. One description per student renders two things: the transcript image
(``<id>.pdf`` or ``<id>.jpeg``) and the answer key (``expected/<id>.json``) that
``flask transcript-eval`` compares Claude's reading with.

Two styles:
* ``clean``: a printed PDF, like a student downloads from a portal.
* ``scan``: the layout of a real university transcript scan (two columns, dot-matrix type, a term
  block per school, "Total Earned Credits" lines, a repeat column, tiled watermark text), rendered,
  then rotated slightly, given grain and saved as a JPEG. Every page says FICTIONAL.

Course codes are real codes from the schools' public catalogs; names, IDs and grades are invented.

    python3 data/test-transcripts/build.py      # needs Chrome (or CHROME=...) and Pillow
"""
from __future__ import annotations

import html
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "demo" / "transcripts"))
from build import _chrome  # noqa: E402  (same browser finder as the demo transcripts)

# A block is (school, term label, [(subject, number, title, credits, grade, repeat_flag)]).
STUDENTS = [
    {"id": "nscc-clean", "style": "clean", "issuer": "Nashville State Community College",
     "name": "Avery T. Lindqvist", "sid": "N00419927", "major": "Computer Information Technology",
     "blocks": [
         ("Nashville State Community College", "Fall 2025", [
             ("CISP", "1010", "Computer Science I", 4, "A", ""), ("ENGL", "1010", "Composition I", 3, "B", ""),
             ("MATH", "1130", "College Algebra", 3, "B+", ""), ("PSYC", "1030", "General Psychology", 3, "A-", "")]),
         ("Nashville State Community College", "Spring 2026", [
             ("CISP", "1020", "Computer Science II", 4, "B", ""), ("ENGL", "1020", "Composition II", 3, "B", ""),
             ("MATH", "1910", "Calculus I", 4, "C+", ""), ("HIST", "2010", "Survey of American History I", 3, "A", "")]),
         ("Nashville State Community College", "Fall 2026", [
             ("CITC", "1301", "Data Communications", 3, "IP", ""), ("ECON", "2100", "Principles of Macroeconomics", 3, "IP", "")]),
     ]},
    {"id": "volstate-scan", "style": "scan", "issuer": "Volunteer State Community College",
     "name": "Marisol D. Achterberg", "sid": "V00388150", "major": "General Studies",
     "blocks": [
         ("Volunteer State Community College", "08/25-12/25", [
             ("BIOL", "1110", "General Biology I", 4, "B", ""), ("ENGL", "1010", "Composition I", 3, "A", ""),
             ("MATH", "1530", "Elementary Probability & Statistics", 3, "C", ""), ("PSYC", "1030", "General Psychology", 3, "B", "")]),
         ("Volunteer State Community College", "01/26-05/26", [
             ("BIOL", "1120", "General Biology II", 4, "C+", ""), ("CHEM", "1110", "General Chemistry I", 4, "D", ""),
             ("SOCI", "1010", "Introduction to Sociology", 3, "A", "")]),
         ("Volunteer State Community College", "06/26-07/26", [
             ("CHEM", "1110", "General Chemistry I", 4, "B", "I")]),
     ]},
    {"id": "columbiastate-scan", "style": "scan", "issuer": "Columbia State Community College",
     "name": "Desmond R. Okonkwo-Hale", "sid": "C00510274", "major": "Business Administration",
     "blocks": [
         ("Columbia State Community College", "08/25-12/25", [
             ("ACCT", "1010", "Principles of Accounting I", 3, "B", ""), ("ECON", "2100", "Principles of Macroeconomics", 3, "B", ""),
             ("ENGL", "1010", "Composition I", 3, "A", ""), ("MATH", "1630", "Finite Mathematics", 3, "C", "")]),
         ("Columbia State Community College", "01/26-05/26", [
             ("ACCT", "1020", "Principles of Accounting II", 3, "C", ""), ("ECON", "2200", "Principles of Microeconomics", 3, "B+", ""),
             ("BUSN", "1305", "Introduction to Business", 3, "A", ""), ("COMM", "2025", "Fundamentals of Communication", 3, "A-", "")]),
     ]},
    {"id": "utk-clean", "style": "clean", "issuer": "University of Tennessee, Knoxville",
     "name": "Priya N. Vasquez-Holm", "sid": "K00266031", "major": "Psychology",
     "blocks": [
         ("University of Tennessee, Knoxville", "Fall 2025", [
             ("PSYC", "110", "General Psychology", 3, "A", ""), ("ENGL", "101", "English Composition I", 3, "B+", ""),
             ("MATH", "115", "Statistical Reasoning", 3, "B", ""), ("BIOL", "101", "Biodiversity", 4, "B-", "")]),
         ("University of Tennessee, Knoxville", "Spring 2026", [
             ("PSYC", "295", "Research Methods in Psychology", 3, "B", ""), ("ENGL", "102", "English Composition II", 3, "A-", ""),
             ("SOCI", "120", "General Sociology", 3, "A", ""), ("HIST", "221", "History of the United States I", 3, "C", "")]),
     ]},
    {"id": "utc-scan", "style": "scan", "issuer": "University of Tennessee at Chattanooga",
     "name": "Ezekiel M. Fairweather", "sid": "U00731882", "major": "Nursing (pre-nursing)",
     "blocks": [
         ("University of Tennessee at Chattanooga", "08/25-12/25", [
             ("BIOL", "2010", "Human Anatomy and Physiology I", 4, "B", ""), ("CHEM", "1010", "General Chemistry I", 4, "C+", ""),
             ("ENGL", "1010", "Rhetoric and Composition I", 3, "B", ""), ("PSY", "1010", "Introduction to Psychology", 3, "A", "")]),
         ("University of Tennessee at Chattanooga", "01/26-05/26", [
             ("BIOL", "2020", "Human Anatomy and Physiology II", 4, "B-", ""), ("BIOL", "2060", "Microbiology", 4, "C", ""),
             ("MATH", "1010", "Elementary Statistics", 3, "B", "")]),
     ]},
    {"id": "mtsu-multi-scan", "style": "scan", "issuer": "Middle Tennessee State University",
     "name": "Theodora J. Brightwater", "sid": "M00804416", "major": "Undeclared",
     "transfer_heading": True,
     "blocks": [
         ("Columbia State Community College", "08/23-12/23", [
             ("ENGL", "1010", "Composition I", 3, "B", ""), ("PSYC", "1030", "General Psychology", 3, "A", ""),
             ("SOCI", "1010", "Introduction to Sociology", 3, "B", ""), ("MATH", "1130", "College Algebra", 3, "F", "E")]),
         ("Columbia State Community College", "01/24-05/24", [
             ("MATH", "1130", "College Algebra", 3, "C", "I"), ("HIST", "2010", "Survey of American History I", 3, "A", ""),
             ("BIOL", "2010", "Human Anatomy & Physiology I", 4, "C", "")]),
         ("Nashville State Community College", "08/24-12/24", [
             ("CISP", "1010", "Computer Science I", 4, "B", ""), ("ECON", "2100", "Principles of Macroeconomics", 3, "C", "")]),
         ("Middle Tennessee State University", "Fall 2025", [
             ("ENGL", "1020", "Research and Argumentative Writing", 3, "B", ""), ("CSCI", "1170", "Computer Science I", 4, "B-", ""),
             ("PSY", "1410", "General Psychology", 3, "A", ""), ("COMM", "2200", "Fundamentals of Communication", 3, "A", "")]),
         ("Middle Tennessee State University", "Spring 2026", [
             ("CSCI", "2170", "Computer Science II", 4, "C", ""), ("MATH", "1910", "Calculus I", 4, "D", ""),
             ("HIST", "2020", "Survey of United States History II", 3, "B", "")]),
     ]},
]


def expected(st: dict) -> dict:
    """The answer key: what a correct reading contains."""
    own, transfer = [], []
    for school, _, rows in st["blocks"]:
        for subj, num, title, cr, grade, _rep in rows:
            row = {"code": f"{subj} {num}", "grade": None if grade == "IP" else grade, "credits": cr}
            (own if school == st["issuer"] else transfer).append({**row, "school": school} if school != st["issuer"] else row)
    return {"issuing_school": st["issuer"], "student_name": st["name"], "courses": own, "transfer": transfer}


CLEAN_CSS = """
@page { size: letter; margin: 0.6in; } body { font: 10.5pt/1.35 Georgia, serif; color: #111; }
.stamp { position: fixed; top: 42%; left: 0; right: 0; text-align: center; transform: rotate(-24deg);
  font: bold 60pt Helvetica, sans-serif; color: rgba(200,0,0,.12); letter-spacing: 6px; }
h1 { font-size: 15pt; margin: 0 0 4px; } h3 { font-size: 11pt; margin: 14px 0 4px; }
.banner { background: #fde8e8; border: 1px solid #c00; padding: 4px 8px; font: 9pt Helvetica, sans-serif; }
table { width: 100%; border-collapse: collapse; font-size: 9.5pt; } th, td { text-align: left; padding: 2px 6px; border-bottom: 1px solid #ddd; }
.n { text-align: right; } .meta { font-size: 9.5pt; display: flex; gap: 24px; flex-wrap: wrap; }
"""


def render_clean(st: dict) -> str:
    e = html.escape
    parts = []
    for school, term, rows in st["blocks"]:
        tr = "".join(f"<tr><td>{e(s)} {e(n)}</td><td>{e(t)}</td><td class=n>{c:g}</td><td class=n>{e(g)}</td></tr>"
                     for s, n, t, c, g, _ in rows)
        parts.append(f"<h3>{e(term)}</h3><table><tr><th>Course</th><th>Title</th><th class=n>Credits</th>"
                     f"<th class=n>Grade</th></tr>{tr}</table>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CLEAN_CSS}</style></head><body>
<div class="stamp">FICTIONAL · TEST</div>
<p class="banner">Fictional student for testing Visor. Not a real record and not issued by any school.</p>
<h1>{e(st['issuer'])}: Unofficial Transcript</h1>
<div class="meta"><span>Name: <b>{e(st['name'])}</b></span><span>Student ID: {e(st['sid'])}</span>
<span>Program: {e(st['major'])}</span><span>Printed: 11/10/2026</span></div>
{''.join(parts)}
<p class="banner" style="margin-top:16px">End of fictional transcript.</p></body></html>"""


SCAN_CSS = """
@page { size: 11in 8.5in; margin: 0; }
body { margin: 0; width: 1600px; height: 1236px; position: relative; background: #f4f1ea; color: #1b1b1b;
  font: 15px/1.28 "Courier New", Courier, monospace; overflow: hidden; }
.bg { position: absolute; inset: 0; color: rgba(60,60,60,.10); font: bold 34px "Courier New", monospace;
  line-height: 46px; word-spacing: 18px; transform: rotate(-8deg) scale(1.3); white-space: normal; padding: 20px; }
.fict { position: absolute; top: 480px; left: 120px; transform: rotate(-30deg); font: bold 120px Helvetica, sans-serif;
  color: rgba(190,20,20,.16); letter-spacing: 10px; }
.page { position: absolute; inset: 30px 50px; }
.head { text-align: center; font: 26px "Times New Roman", serif; letter-spacing: 1px; }
.head small { display: block; font-size: 17px; letter-spacing: .5px; }
.left-meta { position: absolute; top: 8px; left: 0; font-size: 14px; } .right-meta { position: absolute; top: 8px;
  right: 0; width: 330px; font: 13px Helvetica, sans-serif; }
.rec { margin-top: 26px; border-top: 2px solid #222; border-bottom: 1px solid #222; padding: 4px 0; font-size: 16px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 10px; }
.colhead { display: grid; grid-template-columns: 110px 1fr 70px 40px 20px; font-size: 13px; border-bottom: 1px dashed #555; }
.blk { margin-top: 12px; } .blk .t { padding-left: 80px; } .row { display: grid; grid-template-columns: 110px 1fr 70px 40px 20px; }
.tot { padding-left: 110px; } .legend { position: absolute; bottom: 70px; left: 0; font: 12px Helvetica, sans-serif; }
.foot { position: absolute; bottom: 20px; left: 0; right: 0; text-align: center; font: italic 13px "Times New Roman", serif; }
"""


def render_scan(st: dict) -> str:
    e = html.escape
    blocks = []
    if st.get("transfer_heading"):
        blocks.append('<div class="blk">TRANSFER CREDIT ACCEPTED BY THE INSTITUTION:</div>')
        in_transfer = True
    else:
        in_transfer = False
    for school, term, rows in st["blocks"]:
        if in_transfer and school == st["issuer"]:
            blocks.append(f'<div class="blk">INSTITUTION CREDIT: {e(st["issuer"].upper())}</div>')
            in_transfer = False
        lines = "".join(f'<div class="row"><span>{e(s)} {e(n)}</span><span>{e(t)}</span><span>{c:.3f}</span>'
                        f'<span>{e(g)}</span><span>{e(r)}</span></div>' for s, n, t, c, g, r in rows)
        earned = sum(c for _s, _n, _t, c, g, rep in rows if g not in ("F", "IP", "W") and rep != "E")
        blocks.append(f'<div class="blk"><div>{e(term)}<span class="t">{e(school)}</span></div>{lines}'
                      f'<div class="tot">Total Earned Credits&nbsp;&nbsp;&nbsp;{earned:.3f}</div></div>')
    half = (len(blocks) + 1) // 2
    head_row = '<div class="colhead"><span>SUBJ NO.</span><span>COURSE TITLE</span><span>CRED</span><span>GRD</span><span>R</span></div>'
    watermark = ("STUDENT COPY " * 400)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{SCAN_CSS}</style></head><body>
<div class="bg">{watermark}</div><div class="fict">FICTIONAL · TEST</div>
<div class="page">
 <div class="left-meta">Page: 1<br>Date Issued: 10-NOV-2026<br>Level: Undergraduate</div>
 <div class="head">{e(st['issuer'].upper())}<small>UNOFFICIAL ACADEMIC RECORD (FICTIONAL TEST DOCUMENT)</small></div>
 <div class="right-meta">Fictional student made up for testing Visor. Not a real record and not issued by any school.</div>
 <div class="rec">Record of: {e(st['name'])}&nbsp;&nbsp;&nbsp;&nbsp; ID: {e(st['sid'])}&nbsp;&nbsp;&nbsp;&nbsp; Program: {e(st['major'])}</div>
 <div class="cols"><div>{head_row}{''.join(blocks[:half])}</div><div>{head_row}{''.join(blocks[half:])}
   <div class="blk">******** END OF RECORD ********</div></div></div>
 <div class="legend">R Column = Repeat Indicator: E = Excluded from GPA and earned hours; I = Included in GPA and earned hours</div>
 <div class="foot">Fictional test document. Visor demo, Lipscomb University Software Studio.</div>
</div></body></html>"""


def scan_effects(png: Path, out: Path, seed: int) -> None:
    from PIL import Image, ImageFilter
    rnd = random.Random(seed)
    img = Image.open(png).convert("L")
    noise = Image.effect_noise(img.size, 22)
    img = Image.blend(img, noise, 0.10).filter(ImageFilter.GaussianBlur(0.6))
    img = img.rotate(rnd.uniform(-1.2, 1.2), expand=True, fillcolor=235)
    img.convert("RGB").save(out, "JPEG", quality=58)


def main() -> None:
    chrome = _chrome()
    (HERE / "expected").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for i, st in enumerate(STUDENTS):
            page = Path(tmp) / f"{st['id']}.html"
            if st["style"] == "clean":
                page.write_text(render_clean(st))
                out = HERE / f"{st['id']}.pdf"
                subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                                f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True)
            else:
                page.write_text(render_scan(st))
                png = Path(tmp) / f"{st['id']}.png"
                subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=1600,1236",
                                f"--screenshot={png}", page.as_uri()], check=True, capture_output=True)
                out = HERE / f"{st['id']}.jpeg"
                scan_effects(png, out, seed=i)
            (HERE / "expected" / f"{st['id']}.json").write_text(json.dumps(expected(st), indent=2) + "\n")
            print(f"Wrote {out.name}")


if __name__ == "__main__":
    main()
