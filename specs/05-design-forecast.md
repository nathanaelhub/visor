# Visor: Degree audit + semester forecast, scaled up (design, v0.1)

Status: **showcase draft** — built on branch `scaled-up` to show one way `04-design-degree-audit.md`
can grow. Nothing here replaces the team's plan; take what helps. Ported from the owner-approved
"Pathway" spec (2026-09-23) onto this repo's stack and conventions.

## What this adds on top of spec 04

| Spec 04 says | This builds |
|---|---|
| Audit: met / in progress / needed, hours done | Same, plus per-group "counted" lists with **where each course came from** (Lipscomb, transfer, in progress) |
| "A course counts toward one requirement only… the assignment that meets the most requirements" | Same rule, implemented as greedy-by-specificity **plus augmenting moves**, with one exception the Core page states: groups marked `shareable` (Diverse Perspectives) may reuse a course |
| `project()`: a rough projected term | A full **term-by-term plan**: every course placed, with **reasons** ("Required: Major core", "Unlocks 4 later courses", "Only offered in Spring", "Retake: earned D+, needs C") |
| — | **Warnings** for anything that can't be placed, and a **needs advisor review** flag |
| — | An **independent checker** (`rules/verify.py`) that re-checks every plan without using the planner's code |
| — | The real 2026-27 CS B.S. catalog (`data/catalog/2026-27/`) and fictional demo students |
| `POST /api/audit` | Same contract, plus `plan` and `warnings` in the response |

## User stories

### US-5.1 Student / advisor: see the plan to graduation

**As** a student (or the advisor sitting with them), **I want** to see every remaining semester with
the courses in it, **so that** we both know the path and the graduation term.

1. **Given** a program and the courses taken, **when** the forecast runs, **then** every outstanding
   requirement is either placed in a future term or listed as a warning with the reason. Nothing is
   silently dropped. [`test_every_requirement_placed_or_warned`]
2. **Given** a plan, **then** no course appears before its prerequisites are passed (at the
   prerequisite's minimum grade), only in terms it is offered (season and even/odd year), and each
   term stays at or under the credit maximum (default 18). Terms below the minimum (12) are marked
   `light`. [`test_plan_respects_prereqs_offerings_and_load`, `test_verify_catches_broken_plans`]
3. **Given** the same inputs twice, **then** the plan is identical. [`test_forecast_is_deterministic`]
4. **Given** a start term, **then** the plan starts there, uses Fall and Spring only unless summer is
   turned on, and reports the last planned term as the projected graduation term. If any
   requirement couldn't be placed (a warning), there is no projected term (`null`) until an
   advisor resolves it; the courses that fit are still planned.
   [`test_no_graduation_term_while_a_course_cannot_be_placed`]
   [`test_start_term_and_summer`]
5. **Given** a student with nothing left, **then** the plan is empty and says "complete pending final
   grades". [`test_nothing_left`]

### US-5.2 Student: know *why* each course is in that term

1. **Given** a planned course, **then** it carries at least one reason drawn from the catalog: the
   requirement it fills, how many later courses it unlocks, its offering pattern, or a retake.
   [`test_every_planned_course_has_a_reason`]
2. **Given** a course placed later than its first possible term (not offered, or the term was full),
   **then** it says which term it was deferred from. [`test_deferred_course_says_so`]
3. **Given** a course nobody required but a required course needs first (e.g. `EN 3143` needs
   `EN 1223` or `LU 1013`), **then** it is planned with the reason "Needed before EN 3143".
   [`test_prerequisite_gap_is_filled`]

### US-5.3 Advisor: transfer credit flows into the audit

1. **Given** transfer courses, **when** the audit runs, **then** each goes through the equivalency
   lookup first: `confirmed` direct counts as that Lipscomb course, `confirmed` elective counts toward
   hours only, `none` counts for nothing, and `proposed` / `unknown` are listed as **pending** and don't
   count (spec 04). [`test_audit_api_transfer_statuses`]
2. **Given** any audit request, **then** nothing is stored (spec 04). [`test_audit_api_stores_nothing`]

### US-5.4 Advisor: know when to look closer

1. **Given** a plan with any warning, **then** `needs_review` is true and each warning names the
   course or group and the constraint that failed. [`test_unplaceable_course_warns`]

### US-5.5 Student / advisor: ask Visor about the plan (bring your own key)

**As** a student or advisor, **I want** to ask questions about the plan in plain language, **so that**
I understand it without reading every chip — while the planner, not the AI, stays in charge.

1. **Given** no key, **then** the chat refuses before calling Anthropic, and the UI shows the connect
   card. A key is checked without spending tokens (model lookup). [`test_no_key_is_refused_before_any_call`]
2. **Given** a question about transfer credit, the plan, or a course, **then** Claude answers through
   read-only tools that call Visor's own code (`compute_audit`, the equivalency rows, the catalog), and
   each tool call is shown as a card with its source. [`test_transfer_question_uses_the_equivalency_table`,
   `test_audit_tool_returns_the_planners_plan`, `test_course_info_tool_reports_where_it_sits`]
3. **Given** a question about a course's prerequisites for the student in context, **then**
   `course_info` marks each prerequisite with the option the student has met (`met_by`: passed at the
   minimum grade, in progress, or planned earlier) and `prerequisites_met`, and the system prompt
   requires that lookup before any claim that a course is blocked or delayed.
   [`test_course_info_tool_says_which_prerequisites_the_student_has_met`]
4. **Given** a request to change the plan, **then** the answer says it can't and explains why the
   planner placed the course there (system prompt; no write tool exists).
5. **Given** a rejected key, rate limiting, or an API outage, **then** the response is one of the
   designed states (`invalid_key` 401, `rate_limited` 429 with retry-after, `api_down` 503).
   [`test_errors_map_to_the_designed_states`]
6. **Given** any chat, **then** nothing is stored — not the key, not the conversation, not unknown
   transfer courses. [`test_chat_stores_nothing`]

Models: Claude Opus 5.5 (default), Sonnet 5.5, Haiku 5.5. Opus and Sonnet requests opt into
server-side refusal fallbacks (`fallbacks: "default"`). A deployment may set
`VISOR_ANTHROPIC_API_KEY` to use one shared key instead of per-user keys. [`test_shared_key_mode`]

### US-5.6 Site owner: one shared key that can't be run up

**As** the person paying for the key, **I want** Ask Visor on the public demo to run on one server
key with limits around it, **so that** visitors never paste a key and nobody can run up the bill or
use it as a free general-purpose chatbot.

1. **Given** `VISOR_ANTHROPIC_API_KEY` is set, **then** the key never leaves the server, the
   connect card is not shown, the model picker stays (in the chat header, with each model's cost in
   units), the default model is Sonnet, and a key sent from the browser is ignored.
   [`test_shared_key_mode`, `test_shared_mode_offers_models_with_their_cost`]
2. **Given** a visitor, **then** they get at most `VISOR_CHAT_PER_HOUR` (default 20) and
   `VISOR_CHAT_PER_DAY` (default 60) usage units, where one message costs 1 on Haiku, 2 on Sonnet and
   4 on Opus. Over the limit returns `429 {"error": "visitor_limit", "retry_after": <s>}` and
   Anthropic is not called. Visitors are counted by a salted hash of their IP; the raw IP is never
   stored. [`test_visitor_limit`]
3. **Given** the whole site, **then** it spends at most `VISOR_CHAT_DAILY_UNITS` (default 600) a day
   (UTC). Past that, `429 {"error": "site_limit"}` until midnight UTC, and the UI says Ask Visor is
   resting for today. [`test_site_limit`]
4. **Given** any request, **then** a message is at most 1,000 characters, a conversation at most 20
   messages, a reply at most 2,000 output tokens, and at most 6 tool rounds; anything over the input
   limits is `400` before Anthropic is called. [`test_request_caps`]
5. **Given** a question unrelated to Lipscomb course planning, transfer credit or the student's plan,
   **then** the system prompt has Claude decline in one sentence and point back to what it can help
   with. [system prompt; `test_system_prompt_scopes_topics`]
6. **Given** a request whose `Origin` is not the deployment's own site (`VISOR_ALLOWED_ORIGINS`),
   **then** it is refused with `403` in shared-key mode. [`test_foreign_origin_refused`]
7. **Given** the counters, **then** they live in one database table (`chat_usage`: window, visitor
   hash, units) and hold no message text, so US-5.5 criterion 5 ("nothing stored") still holds for
   conversations. Rows older than two days are deleted on write.

Outside the app: the key is a **dedicated** Anthropic key in its own Console workspace with a
monthly spend limit, so a bug in these limits can never cost more than that cap.

### US-5.7 Student / advisor: start from a transcript instead of a demo student

**As** a student or advisor, **I want** to upload an unofficial transcript and get the audit, plan and
Ask Visor for that record, **so that** Visor works on a real-looking record without typing every
course. (Spec 04 open question 6.)

1. **Given** a PDF, PNG or JPG transcript (at most 5 MB and 6 pages), **when** it is read, **then**
   Claude reads it into a course list (`code`, `title`, `credits`, `grade`, `term`, and transfer rows
   with `school`, `subject`, `number`) using structured output, and the response says which lines it
   could not read. [`test_transcript_is_read_into_courses`]
2. **Given** the course list, **then** the user sees it as an editable table and must press
   **Use this record** before anything runs. Visor never acts on a transcript the user has not
   checked. Then the audit, plan and Ask Visor use that record exactly like a demo student.
3. **Given** course codes Lipscomb's catalog doesn't have, **then** they are kept and flagged
   (`unknown_course`, spec 05 API), never silently dropped or guessed.
   [`test_transcript_unknown_codes_are_flagged`]
4. **Given** any upload, **then** the file and the parsed record are **not stored or logged**. The
   file goes to Anthropic for that one request and is dropped; the record lives in the browser tab.
   [`test_transcript_stores_nothing`]
5. **Given** the shared key, **then** reading a transcript costs 4 units against the US-5.6
   allowance, and files over the size or page caps are `400` before Anthropic is called.
   [`test_transcript_limits`]
6. **Given** the public demo, **then** only the three bundled fictional transcripts can be read
   (a freshman, a Nashville State transfer student, a student with a retake, in
   `data/demo/transcripts/`): the request names one (`{"demo": "<id>"}`) and the server reads the
   file itself. Uploading your own file needs the write token (`X-Visor-Token`, KAN-46) or local dev;
   otherwise it is `403 uploads_off` before Anthropic is called. The panel says **"Demo: fictional
   transcripts only."** Real transcripts are FERPA Level 4 and need IT sign-off (Brett Hanson) before
   any deployment accepts them. [`test_public_site_reads_demo_transcripts_only`]
7. **Given** a file that isn't a transcript, **then** the reply says so and no record is made.
   [`test_non_transcript_is_refused`]

## UI

The frontend follows the Claude Design package (October 2026): landing page, four role-based tabs
(Student: My Plan, Ask Visor · Advisor: Students, Transfer, Ask Visor · Registrar: Transfer, Ask
Visor), light/dark themes, and phone layouts with a bottom nav and a bottom-sheet chat. Every number
on screen comes from the API.

## Design

### Where the code lives (each piece can be lifted on its own)

| File | What | Depends on |
|---|---|---|
| `backend/visor/rules/terms.py` | Term codes (`2027SP`), ordering, next term, offered-in-term | nothing |
| `backend/visor/rules/grades.py` | Letter-grade order, "meets minimum" | nothing |
| `backend/visor/rules/audit.py` | Catalog/program dataclasses, `audit()` | terms, grades |
| `backend/visor/rules/forecast.py` | `project()` → `Plan` with reasons and warnings | audit |
| `backend/visor/rules/verify.py` | `verify()` → list of violations; **does not import forecast** | audit, terms, grades |
| `backend/visor/catalog_files.py` | Reads `data/catalog/<year>/*.csv` into the rules dataclasses | rules (I/O lives here, not in `rules/`) |
| `backend/visor/audit_api.py` | `POST /api/audit`, `GET /api/programs`, `GET /api/demo/students` | the above + the equivalency lookup |
| `backend/visor/chat.py` | Ask Visor relay: `POST /api/chat`, `/api/chat/verify`, `/api/chat/config` | audit_api, `anthropic` |
| `frontend/src/` | Landing, My Plan, Students, Transfer, Ask Visor (`views/`), design tokens (`theme.css`) | the API |

The program tables from spec 04 (`program`, `req_group`, `req_item`, …) are **not** in the database
yet: the catalog files are read directly. Moving them into tables is spec 04's importer work and
doesn't change the rules.

### Catalog files (`data/catalog/2026-27/`)

`courses.csv`, `prereqs.csv`, `terms.csv`, `sections.csv` use the existing seed format, so
`flask seed` loads them unchanged. `prereqs.csv` adds a `min_grade` column. New files:

| File | Columns |
|---|---|
| `course_terms.csv` | course, season (`FA`/`SP`/`SU`), years (`every`/`even`/`odd`) |
| `course_tags.csv` | course, tag (`DP`, `SOCIAL_INQUIRY`) |
| `programs.csv` | id, name, degree, catalog_year, total_hours, source, reviewed_on |
| `req_groups.csv` | id, program, name, rule (`all`/`choose_n`/`hours`), n, hours, min_grade, shareable, sort |
| `req_items.csv` | group, course **or** pattern (`CS\|SENG\|SEC\|IT:3000`) **or** tag, sort |
| `notes.md`, `sources.md` | Every judgment call made reading the catalog, and where it came from |

### The audit (who counts where)

1. Each taken course is a candidate for every group with a matching item (course, pattern, or tag),
   if its grade meets the group's minimum.
2. Assign in order of **specificity**: a group that names the course, then a pattern, then a tag.
3. **Augment:** for every group still unmet, look for a course sitting in another group that would
   still be met without it, and move it. Repeat until nothing moves.
4. Shareable groups (DP) count any taken course carrying the tag, even if it is already used.
5. Courses that count nowhere are listed as `unused` (they still add to hours).

### The forecast

1. **Outstanding courses** come from the audit: missing courses in `all` groups, the first unused
   items in `choose_n` groups, explicit items (in list order) or tagged courses for `hours` groups,
   and retakes for courses below a group's minimum grade.
2. **Prerequisite gaps:** any prerequisite group none of whose options is taken or planned adds its
   first option, with the reason "Needed before …".
3. **Priority** = (number of later courses it unlocks, fewest offering terms, requirement order,
   course code). Ties always break on the code, so the plan is deterministic.
4. **Placement** walks terms from `start_term`. Each term takes eligible courses in priority order
   up to `target` hours (15), never past `max` (18). Eligible = prerequisites passed in an earlier
   term (planned courses count as passed) and offered that season and year.
5. After 16 terms, anything left becomes a warning naming why (never offered again, prerequisite
   unplaceable, …).

### API

`POST /api/audit`

```json
{"program_id": "cs-bs-2026-27", "start_term": "2027SP",
 "taken": [{"code": "CS 1213", "credits": 3, "grade": "A"}, {"code": "MA 1314", "credits": 4, "grade": null}],
 "transfer": [{"school_id": 1, "subject": "CISP", "number": "1020", "grade": "B"}],
 "settings": {"include_summer": false, "max_hours": 18}}
```

Response: spec 04's `AuditResult` (`program`, `hours_done`, `hours_required`, `groups`, `unused`,
`projected_term`) plus `transfer` (what each transfer course became), `plan` (`terms` →
`courses` → `reasons`), `warnings`, and `needs_review`. A `grade` of `null` means in progress.
Nothing is stored.

Input errors return 400 with `{"error": …}`: a missing `program_id`, a grade that isn't a letter
(A to F), `TR`, `P`, `CR`, `W` or `I`, and non-numeric credits or settings. An unknown `program_id`
is 404. A taken course the catalog doesn't know adds a warning of kind `unknown_course` and sets
`needs_review` (it still counts toward hours). [`test_audit_api_rejects_unknown_grades`,
`test_unknown_course_code_warns_and_needs_review`]

## Open questions this surfaced (send to Ms. Hood / the department)

The catalog itself disagrees with itself in places; every case is in `data/catalog/2026-27/notes.md`.
The ones that change plans: `CS 3633` lists prerequisite `CS 3623`, which no longer exists
(modeled as `CS 2623`); `EN 1223` and `CO 1223` list each other as prerequisites; `EN 3143` needs
a course the program page never mentions; and the major's minimum grade is assumed to be C.
