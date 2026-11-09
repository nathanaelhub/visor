# Handoff: Visor showcase

Updated: 2026-11-06

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

## In progress / unfinished

- **PR #30: spec US-5.7, transcript upload** (issue #29). It is open and waiting for Nathanael's
  approval. **Decision needed:** should the public site accept any uploaded file (labelled
  "fictional only"), or only the three bundled demo transcripts? Real transcripts are FERPA Level 4
  and need IT sign-off from Brett Hanson. No code is written yet.
- **Open issues:**
  - #20: on the live site, "Flag for review" shows a token error. Writes are correctly closed; the
    message needs fixing.
  - #2: the plan page hides transfer courses that don't count. Needs a layout decision.
  - #8: spec 06, advisor editing and approval. Needs Nathanael's decisions.
- **The Ask Visor key expires around 2026-12-05.** Get a replacement before then. The old key was
  pasted in chat, so it lives in that session's transcript.

## Next steps

1. Get the US-5.7 decision, merge PR #30, then build transcript upload test-first. That includes the
   three fictional transcripts in `data/demo/transcripts/`.
2. Fix #20, so the live site says flagging is turned off in the public demo.
3. Before about 2026-12-05, replace `VISOR_ANTHROPIC_API_KEY` in Vercel production. Suggest a
   dedicated key in its own Console workspace with a monthly spend cap.
4. Decide and do #2 and #8 (spec 06).

## Run and test

```bash
# backend (venv at backend/.venv)
cd backend
.venv/bin/ruff check . && .venv/bin/python -m pytest -q          # 141 tests
DATABASE_URL=sqlite:///visor-demo.db VISOR_DATA_DIR=../data/catalog/2026-27 \
  VISOR_EQUIV_DATA_DIR=../data/demo .venv/bin/flask --app wsgi seed
.venv/bin/flask --app wsgi run --debug --port 5050                # macOS: 5000 is AirPlay

# frontend (Node 22+)
cd frontend
npm install && npm run build && npm test
VITE_API_URL=http://localhost:5050 npm run dev
```

Deploying: merging to `main` deploys automatically. By hand, from the repo root on `main`:
`vercel deploy --prod`. To re-seed Neon, pull the production env to a file outside the repo, then run
`flask seed` with `DATABASE_URL` set to `DATABASE_URL_UNPOOLED` from that file.

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
