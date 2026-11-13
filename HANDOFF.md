# Handoff: Visor showcase

Updated: 2026-11-13

## What this is

The Visor showcase: Nathanael's scaled-up build of the Lunatic Labs Visor student project (Lipscomb
course planning and transfer advising), on the students' stack: Flask, SQLAlchemy, React/Vite.
It adds a degree audit, a term-by-term forecast with reasons, the 2026-27 CS catalog as data, and
Ask Visor (a Claude chat limited to Visor topics).

- **Repo:** https://github.com/nathanaelhub/visor (standalone, public, not a fork). The students'
  history is kept for credit; see the README section "Built on".
- **Live site:** https://visor-showcase.vercel.app
- **Students' repo:** https://github.com/Lunatic-Labs/Visor. **Never push there.** The local
  `upstream` remote's push URL is disabled on purpose.

This session (2026-10-31 to 2026-11-05) covered:
- user-case testing
- the GitHub process
- the bug fixes
- deploying to Vercel
- Ask Visor on one server-side key, with usage limits

## Process (required)

Every change follows the `github-flow` skill (`~/.claude/skills/github-flow/SKILL.md`):
issue → `type/desc` branch → failing-test commit → fix commit → PR (template) → CI green → squash-merge.

- `main` is protected: a PR is required, checks `backend` and `frontend` must pass with the branch up
  to date, history must be linear, and admins are included.
- Merge only with Nathanael's go-ahead.
- A new feature gets a spec PR first (`specs/05-design-forecast.md`), and code only after approval.
- Several PRs in a row: merge one, run `gh pr update-branch N --rebase`, wait for CI, then merge the next.
- `gh repo set-default nathanaelhub/visor` is pinned, because the clone also has `upstream`.

## Finished

- **User cases:** a report with 25 cases at `docs/user-cases/Visor-User-Cases.pdf` (PR #1). Its
  findings became issues #2–#8.
- **PR template** (PR #9).
- **Bug fixes**, each on its own branch and PR:
  - #10: duplicate transfer flags
  - #11: audit API input validation and unknown-course warnings
  - #12: transfer course-code parsing; first frontend tests; CI moved to Node 22
  - #13: no graduation date shown while courses can't be placed
  - #14: Ask Visor checks which prerequisites are already met
- **README:** "Built on" section (#16) and the live demo link (#21).
- **Deploy fixes:** `anthropic` added to the root `requirements.txt` that Vercel installs, with a sync
  test (#18); `.vercel` and `.env*` ignored in git and in uploads (#19).
- **Vercel project `visor-showcase`** under Nathanael's account. It is separate from the students'
  `visor-steel`.
  - Neon Postgres database `visor-showcase-db`, seeded with demo data.
  - GitHub is linked: merges to `main` deploy production, and PRs get preview checks.
- **US-5.6, Ask Visor on one shared key with limits:** spec #23, code #24.
  - Per visitor: 20 units an hour and 60 a day. Haiku costs 1 unit, Sonnet 2, Opus 4.
  - Site-wide: 600 units a day.
  - Size caps: 1,000-character questions, 20-message chats, 2,000 output tokens.
  - Requests are accepted only from the site itself, and off-topic questions are declined.
  - The usage table holds counts only.
- **Model picker in shared mode** (#28): it sits in the chat header, shows each model's units, and
  defaults to Sonnet.
- **"Needs X" plan reasons** no longer name a prerequisite the student already met another way (#26).
- **Live-site tests on 2026-11-05:** 12 Ask Visor cases passed, including off-topic, jailbreak and
  prompt-extraction attempts. The guards (403 for a foreign or missing origin, 400 for an oversized
  question) and the model picker were checked in a browser.

## Finished since 2026-11-06

- **Transcript upload (US-5.7)**: spec #30, code #33. The public site reads only bundled fictional transcripts.
- **Small fixes**: landing page and README (#35); flag message (#36); every transfer course shown on the plan (#37); course info failing live because Vercel passes the path encoded (#49).
- **Spec 06, advisor edits and approval** (#38, #39): advisors change settings, pin or hold courses, and approve. Approvals are tied to a fingerprint and go stale when the plan changes. Edits save with the write token; on the public demo they stay in the tab.
- **Spec 07** (#41–#45, #47, #50):
  - **Majors**: Biology, Management (B.B.A., standing in for "Business Administration"), Nursing (BSN) and Psychology, with 8 more fictional students (13 in total). There are 35 judgment calls at the end of `data/catalog/2026-27/notes.md` to confirm with the department.
  - **Planner**: free-elective slots so students reach class standing; Nursing's admission gate is shown as a notice, not enforced.
  - **Transfer schools**: course lists for Nashville State, Vol State, Columbia State, UT Chattanooga and UT Knoxville, 9,183 courses in `data/external/`. They come from public catalogs, read at each site's 120-second crawl-delay.
  - **Claude-proposed equivalencies**: 2,983 answers (Batches API), stored only as `proposed / ai_proposed`, and shown on the Transfer page as "Proposed by Claude · needs a person to confirm".
  - **Transcripts from other schools**: the transfer blocks keep their own schools, rows stream live as Claude reads, and a file picker appears only where uploads are open. There are 6 fictional test transcripts (scanned style) in `data/test-transcripts/`; the eval read 57/57 rows exactly.
  - **The real MTSU sample** lives only in `data/private/transcripts/` (git-ignored, never committed or deployed).

## Finished 2026-11-12 to 13

- **Ask Visor 📎** (US-7.6, #52/#53): start from a transcript inside the chat.
- **Spec 08, login and roles** (#55/#56):
  - Clerk through the Vercel Marketplace (`visor-showcase-auth`, a **development** instance).
  - Admins come from `VISOR_ADMIN_EMAILS` (production: Nathanael's Lipscomb address); an admin page sets roles and advisees.
  - Advisors save and approve for their advisees; registrars confirm or reject equivalencies (Claude's too); staff can upload transcripts.
  - Flask verifies the Clerk JWT (`backend/visor/accounts.py`).
- **Spec 09, saved chats and the conversation log** (#60/#61):
  - Signed-in chats are saved, with History; advisors and admins get the Conversations page.
  - The log is hash-chained ("Log verified"), and reads are recorded.
  - A daily Vercel Cron purge after 365 days (`CRON_SECRET`).
  - IT sign-off is still needed before real students use it.
- **MTSU** (#62): the sixth school, with 3,471 courses and 1,198 proposals. Test transcripts were updated to ECON 2100/2200 (#63).
- **User-case report** refreshed (#58 and this PR): 35 cases with the status of every finding.
- **Test accounts** in the Clerk dev instance: `visor-{admin,advisor,student}+clerk_test@example.com`, code 424242. Delete them when no longer needed.

## In progress / unfinished

- No open issues.
- **The Ask Visor key expires around 2026-12-05.** Replace `VISOR_ANTHROPIC_API_KEY` in Vercel production, ideally in its own Console workspace with a spend cap.
- Clerk is a development instance. A production instance needs a custom domain; Lipscomb Microsoft sign-in needs an IT app registration.
- Low findings F6 and F10–F13 are fixed (PRs #66, #69, #71, #73). Still open: N-F3, optional (most proposals are "elective" because Visor holds only five majors' Lipscomb courses).

## Next steps

1. Get the department or advising office to confirm the judgment calls in `data/catalog/2026-27/notes.md` (the four new majors).
2. Replace the Ask Visor key before about 2026-12-05.
3. Optional: read more Lipscomb course prefixes, then rerun `flask propose-equivalencies --school <slug>` (it replaces only that school's rows).
4. Optional: the next schools on Ms. Hood's list (Harding, Tennessee State, MTSU …) with `tools/scrape_external/scrape.py`.

## Run and test

```bash
# backend (venv at backend/.venv)
cd backend
.venv/bin/ruff check . && .venv/bin/python -m pytest -q          # 258 tests
DATABASE_URL=sqlite:///visor-demo.db VISOR_DATA_DIR=../data/catalog/2026-27 \
  VISOR_EQUIV_DATA_DIR=../data/demo .venv/bin/flask --app wsgi seed
.venv/bin/flask --app wsgi run --debug --port 5050                # macOS: 5000 is AirPlay

# frontend (Node 22+)
cd frontend
npm install && npm run build && npm test
VITE_API_URL=http://localhost:5050 npm run dev
```

Deploying: merging to `main` deploys automatically. By hand, from the repo root on `main`:
`vercel deploy --prod`.

Production data is seeded by hand after data changes. Pull the production env to a file outside the
repo, then run `flask --app wsgi seed` from `backend/` with `DATABASE_URL` set to
`DATABASE_URL_UNPOOLED` from that file, plus `VISOR_DATA_DIR=../data/catalog/2026-27` and
`VISOR_EQUIV_DATA_DIR=../data/demo`. It is idempotent: it loads the external catalogs and Claude's
proposals too.

Data tools (all read caches in git-ignored `data/private/scrape-cache/`; `--parse-only` makes no requests):

```bash
python3 tools/scrape_external/scrape.py [slug ...] [--parse-only]   # transfer schools
cd tools/scrape_lipscomb && npm install && node scrape.mjs name=URL ...  # Lipscomb pages (headless)
python3 tools/scrape_lipscomb/build_programs.py                      # the four new majors
python3 data/test-transcripts/build.py                               # fictional test transcripts
cd backend && flask --app wsgi propose-equivalencies [--school s] [--dry-run]   # Batches API, costs money
cd backend && flask --app wsgi transcript-eval ../data/test-transcripts         # real API, costs cents
```

## Outside the repo

- **Vercel project** `visor-showcase` (team "nathanaelhub's projects", Hobby plan). Environment
  variables, names only:
  - production: `VISOR_ANTHROPIC_API_KEY`, `VISOR_CHAT_SALT`, `VISOR_WRITE_TOKEN`
  - preview: `VISOR_WRITE_TOKEN`
  - from the Neon integration: `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `POSTGRES_*`, `PG*`,
    `NEON_*`
  - optional, not set (defaults apply): `VISOR_CHAT_PER_HOUR`, `VISOR_CHAT_PER_DAY`,
    `VISOR_CHAT_DAILY_UNITS`, `VISOR_ALLOWED_ORIGINS`
- **Local link:** `.vercel/project.json` (git-ignored). Re-create it on a new machine with
  `vercel link --project visor-showcase`.
- **Neon database** `visor-showcase-db`, created through the Vercel Marketplace.
- **Anthropic keys on the old Mac:** two valid keys, …YQAA (LiveCoach portal, PT Assist) and …AAAA
  (claude-api-test). The keys in `~/.zshrc` and in the Commentary and hume-voice-demo projects are
  revoked.
- **Skills:** `~/.claude/skills/github-flow/`, and the task-observer log at
  `~/.claude/skill-observations/`.
- **Memory:** `~/.claude/projects/-Users-nathanaeljohnson-opt-LU-GRAD-ASSIST/memory/`. See
  `visor-showcase-project.md` and `github-process-preference.md`.
- **No local dev servers or background jobs are running.**
