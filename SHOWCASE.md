# Scaled-up showcase (branch `scaled-up`)

This branch is one way **spec 04 (degree audit)** can grow into a full semester planner, built on
this repo's own stack and rules so any piece can be lifted into a PR. Nothing on `main` changes;
the existing 61 tests still pass untouched.

**Read first:** `specs/05-design-forecast.md` (what and why), then `data/catalog/2026-27/notes.md`
(the catalog judgment calls).

## Run it

```
cd backend
pip install -r requirements-dev.txt
VISOR_DATA_DIR=../data/catalog/2026-27 VISOR_EQUIV_DATA_DIR=../data/demo flask --app wsgi seed
flask --app wsgi run --debug
cd ../frontend && npm install && npm run dev      # open "Degree Progress"
```

Use a fresh database (e.g. `DATABASE_URL=sqlite:///visor-demo.db`): the demo catalog's course
titles differ from `data/sample/`'s made-up ones.

## What to look at, and what you could borrow

| Piece | File | Borrow it if… |
|---|---|---|
| Term codes, next term, even/odd offerings | `backend/visor/rules/terms.py` | you need `course_term` logic (KAN-28) |
| Grade minimums (`w/C+`), transfer `TR` = C | `backend/visor/rules/grades.py` | you add `min_grade` to prerequisites |
| The audit: specificity + augmenting moves, shareable DP | `backend/visor/rules/audit.py` | you build spec 04's `audit()` |
| The forecast: priority, prerequisite gaps, standing, compaction, reasons | `backend/visor/rules/forecast.py` | you build spec 04's `project()` |
| An independent plan checker | `backend/visor/rules/verify.py` | you want tests that catch planner bugs |
| CSV → rules loader (I/O outside `rules/`) | `backend/visor/catalog_files.py` | until the program tables exist |
| `POST /api/audit` using the equivalency rows read-only | `backend/visor/audit_api.py` | you connect equivalencies to the audit |
| Real CS catalog in seed format | `data/catalog/2026-27/` | you want real data before the importer is done |
| Degree Progress tab | `frontend/src/DegreeProgress.jsx` | Firas's audit page |

## Ideas worth stealing even if you take no code

1. **Write the checker separately from the planner.** `verify.py` never imports `forecast.py`; the
   tests run it over every demo student. It is the cheapest way to trust a scheduler.
2. **Every planned course says why it's there** ("Unlocks 6 later courses", "Offered Spring only").
   Advisors can check a plan line by line instead of trusting it.
3. **Write down every judgment call.** `notes.md` lists 47 places where the catalog was ambiguous
   or wrong (e.g. `CS 3633` requires `CS 3623`, which no longer exists). Each one is a question
   for Ms. Hood instead of a silent guess — the same rule spec 04 already states.
4. **Name tests after acceptance criteria.** Every story in spec 05 lists its tests in brackets,
   like spec 01 does, so a reviewer can see what is covered.
5. **Fictional students tell stories** (`data/demo/students/`): a freshman, an on-track junior, a
   transfer student hitting every equivalency status, a D+ retake, and a one-term-left senior.
   Each one demos a feature.

## Not done here (on purpose)

- Program/requirement **database tables** and the xlsx importer (spec 04's Austin piece).
- Corequisites (none appear in this program's catalog data).
- Advisor edits to a plan, approvals, and login (KAN-30).
