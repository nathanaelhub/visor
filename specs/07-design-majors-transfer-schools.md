# Visor: More majors, top transfer schools, real-looking transcripts (design, v0.1)

Status: **draft for approval**. Builds on specs 03 (equivalencies), 05 (audit, forecast, transcripts)
and 06 (advisor edits). No code until this is approved.

## Why

Every demo student is a CS major, the transfer data is a handful of sample rows, and the demo
transcripts are clean Lipscomb printouts. Real incoming students bring a scanned transcript from
**another** school that lists transfer blocks from two or three more schools. This spec makes Visor
work for five majors, know the course catalogs of the schools most students transfer from, propose
equivalencies for them (people confirm), and read realistic, messy, fictional transcripts.

## Decisions (Nathanael, 2026-11-11)

| Question | Decision |
|---|---|
| Which transfer schools first? | The first five on Ms. Hood's "Top Incoming Transfer Schools" list: **Nashville State, Vol State, Columbia State, UT Knoxville, UT Chattanooga**. |
| Which Lipscomb majors next? | **Biology (B.S.), Business Administration, Nursing (BSN), Psychology**, alongside Computer Science. |
| How do scraped courses get equivalencies? | **Claude proposes, people confirm.** Every suggestion is `proposed`; nothing auto-confirms (CLAUDE.md rule 2). |
| The real MTSU sample transcript | A real person's record. Kept only in `data/private/` (git-ignored, never deployed) for local tests, and used as the **layout model** for fictional transcripts. |

## User stories

### US-7.1 Registrar / advisor: know the courses from the top five schools

1. **Given** the scraped catalogs, **when** Visor is seeded, **then** every undergraduate course from
   the five schools is an `external_course` with subject, number, title, credits and catalog year.
   [`test_external_catalogs_are_clean`, `test_seed_loads_external_catalogs`]
2. **Given** a lookup for one of those courses with no equivalency, **then** the status is `unknown`
   and the course's title is shown. [`test_lookup_shows_scraped_title`]
3. **Given** the scraper, **then** it reads only public catalog pages, obeys robots.txt, waits at
   least one second between requests, and records the date and URLs in `data/external/sources.md`.

### US-7.2 Registrar: see Claude's proposed equivalencies, and confirm or reject them

1. **Given** a scraped course, **when** a person runs `flask propose-equivalencies`, **then** Claude
   suggests one Lipscomb course, elective credit, or no match, with a confidence and a one-line
   reason, from a short list of real Lipscomb candidates. [`test_proposals_are_checked_against_the_catalog`]
2. **Given** a suggestion, **then** it is stored as `status = proposed`, `source = ai_proposed`, with
   no `decided_by`. It never counts toward a degree until a person confirms it.
   [`test_ai_proposals_never_count`, `test_seed_never_confirms_ai_proposals`]
3. **Given** the Transfer page, **then** a Claude proposal says **"Proposed by Claude · needs a person
   to confirm"** and shows the reason.
4. **Given** a run, **then** it uses the Message Batches API, it is never called at request time, and
   its cost is estimated and approved before it runs.

### US-7.3 Student / advisor: plan for Biology, Business Administration, Nursing or Psychology

1. **Given** each new program, **then** its requirements, courses, prerequisites and offerings are
   transcribed from the 2026-27 catalog, with every judgment call in `notes.md`.
2. **Given** any demo student in any program, **then** every requirement is placed or warned about,
   and the independent checker finds no violations. [`test_every_program_plans_cleanly`]
3. **Given** Nursing, **then** upper-division nursing courses carry an admission gate shown as a
   warning ("needs admission to the nursing program"), not a rule the planner makes up.
4. **Given** the demo, **then** there is a first-year and a transfer student for each new major, and
   each transfer student comes from one of the five schools.

### US-7.4 Student / advisor: start from a transcript issued by another school

1. **Given** a transcript whose issuing school isn't Lipscomb, **then** its courses become **transfer
   rows from that school**, and each "transfer credit accepted" block becomes rows from the school it
   names. [`test_other_school_courses_become_transfer_rows`]
2. **Given** such a transcript, **then** the review step asks which Lipscomb major to plan for,
   because the transcript can't say. [`test_major_choice_reaches_the_audit`]
3. **Given** the public demo, **then** it still reads only bundled fictional transcripts (US-5.7). A
   file picker appears only where uploads are open (local dev or the write token); the server says
   so with `uploads_open`. [`test_uploads_open_only_when_writes_are`]
4. **Given** a transcript being read, **then** the page can show rows appearing as Claude reads them
   (streamed), ending in the same record as the non-streamed read.
   [`test_streamed_read_matches_the_plain_read`]

### US-7.5 Team: test transcript reading on messy, realistic transcripts

1. **Given** `data/test-transcripts/`, **then** it holds about seven fictional transcripts (clean PDFs
   and scanned-looking JPEGs in the MTSU layout: two columns, term blocks per school, "Total Earned
   Credits" lines, a repeat column, slight rotation, watermark text and noise), each stamped FICTIONAL
   with an `expected/<id>.json` answer.
2. **Given** `flask transcript-eval`, **then** each transcript is read with the real API and compared
   with its answer (codes, grades, credits, schools), with accuracy printed per transcript. It costs
   cents and is run by a person, never in CI.

## Design

### Data layout

| Path | What | In git |
|---|---|---|
| `data/external/<school>/courses.csv` | subject, number, title, credits, description (≤400 chars), catalog_year, source_url | yes (public catalogs) |
| `data/external/sources.md` | dates, URLs, what was skipped | yes |
| `data/external/proposed_equivalencies.csv` | school, external, lipscomb, kind, confidence, reason | yes (reviewed in the PR) |
| `data/catalog/2026-27/*.csv` | four more programs; group ids prefixed by program (`bio-major-core`) | yes |
| `data/test-transcripts/` | fictional test transcripts and `expected/` answers | yes |
| `data/private/transcripts/` | the real MTSU sample | **no** (git-ignored) |

### Code

| Piece | Where |
|---|---|
| Scraper (headless browser, per-school config) | `tools/scrape_external/` |
| Seeding external catalogs and proposals | `backend/visor/seed.py` (`load_equivalencies`) |
| `flask propose-equivalencies` | `backend/visor/propose.py` |
| Other-school transcripts, `uploads_open`, streaming | `backend/visor/transcript.py` |
| `flask transcript-eval` | `backend/visor/transcript_eval.py` |
| UI | `Transcript.jsx` (picker, major choice, live rows), `Transfer.jsx` (Claude proposals) |

### Cost (estimated before each run, approved by Nathanael)

- **Proposals:** only subjects relevant to the five majors and the Core, about 1,500–2,500 courses;
  Sonnet 5.5 through the Batches API at about 1.5k input and 150 output tokens each, roughly
  **$3–6** in total.
- **Transcript eval:** about seven reads on Sonnet, **under $0.50** per run.

## Delivery

One PR per story group, in order: US-7.1, US-7.2, US-7.3, then US-7.4 with US-7.5. Each starts with
failing tests and ends with a check on the live site.

## Open questions (don't build around these yet)

- Ms. Hood's list order: is it ranked by volume? The first five were taken as listed.
- Should Claude's proposals be shown to students at all, or to staff only?
- When the real SIS export is loaded on a staff deployment, its confirmed rows win over any proposal.
