# Visor

Course planning and transfer advising for Lipscomb University: a degree audit and a
semester-by-semester plan to graduation, with the reason every course sits where it does, plus
transfer-credit lookup and an AI assistant that explains the plan using your own Anthropic key.

> **Showcase build.** This repository extends the
> [Lunatic Labs Visor](https://github.com/Lunatic-Labs/Visor) Software Studio project. It was built
> by their graduate assistant to show one way the team's design can grow; any piece can be borrowed.
> All student data is fictional. The course catalog is Lipscomb's public 2026-27 catalog.

## What it does

- **My Plan (students):** progress toward the degree, projected graduation, a term-by-term plan
  that respects prerequisites, when courses are offered, class standing and credit load, and a reason
  on every course ("Unlocks 6 later courses", "Offered Spring only", "Retake: earned D+, needs C").
- **Students (advisors):** every advisee with flags for retakes and pending transfer credit; open any
  plan, with warnings when the planner can't place something.
- **Transfer (registrar):** what a course from another school counts as: Confirmed, Proposed (a person
  must confirm) or Unknown (flag it for a professor).
- **Ask Visor:** Claude answers questions about the plan through read-only tools that call Visor's
  own planner, catalog and equivalency table. It explains the plan; it can never change it. Bring your
  own Anthropic API key (kept in the browser session only) or set one key for the deployment.

The plan comes from a deterministic rules engine: the same record always gives the same plan, and
an independent checker re-verifies every plan in the tests.

## Run it

```bash
cd backend
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///visor-demo.db
VISOR_DATA_DIR=../data/catalog/2026-27 VISOR_EQUIV_DATA_DIR=../data/demo flask --app wsgi seed
flask --app wsgi run --debug                     # API on :5000

cd ../frontend
npm install && npm run dev                       # http://localhost:5173
```

Ask Visor is optional: paste a key on the Ask Visor tab, or `export VISOR_ANTHROPIC_API_KEY=sk-ant-…`
before `flask run` to use one shared key.

On macOS, port 5000 is often taken by AirPlay: run `flask --app wsgi run --debug --port 5050` and start the
frontend with `VITE_API_URL=http://localhost:5050 npm run dev`.

Checks: `cd backend && ruff check . && pytest -q` and `cd frontend && npm run build`.

## Where to look

| Path | What |
|---|---|
| `SHOWCASE.md` | Guide for the student team: what was added and what to borrow |
| `docs/user-cases/Visor-User-Cases.pdf` | 25 hands-on user cases (student, advisor, registrar, Ask Visor) with screenshots and ranked findings |
| `specs/05-design-forecast.md` | Spec for the audit, forecast and Ask Visor (extends the team's `specs/04`) |
| `backend/visor/rules/` | Pure rules: terms, grades, audit, forecast, independent plan checker |
| `backend/visor/audit_api.py`, `chat.py` | Audit/plan API and the Ask Visor relay |
| `data/catalog/2026-27/` | The real CS B.S. catalog as data, with `notes.md` listing every judgment call |
| `data/demo/` | Fictional students and sample equivalencies |
| `frontend/src/` | React app (landing, My Plan, Students, Transfer, Ask Visor) |

## Credits

- **Original Visor project** (transfer equivalencies, SIS import, data model, specs 00–04,
  scheduling rules): Austin Patton, Gabriel Pop and Firas Adas, Lunatic Labs, Lipscomb University
  Software Studio, with Dr. Steve Nordstrom. Their commit history is kept in this repository.
- **Showcase extensions** (spec 05, degree audit and forecast engine, catalog data, Ask Visor, new UI):
  Nathanael Johnson, with Claude.
- UI designed with Claude Design.
