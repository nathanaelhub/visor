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
   turned on, and reports the last planned term as the projected graduation term.
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
3. **Given** a request to change the plan, **then** the answer says it can't and explains why the
   planner placed the course there (system prompt; no write tool exists).
4. **Given** a rejected key, rate limiting, or an API outage, **then** the response is one of the
   designed states (`invalid_key` 401, `rate_limited` 429 with retry-after, `api_down` 503).
   [`test_errors_map_to_the_designed_states`]
5. **Given** any chat, **then** nothing is stored — not the key, not the conversation, not unknown
   transfer courses. [`test_chat_stores_nothing`]

Models: Claude Opus 5.5 (default), Sonnet 5.5, Haiku 5.5. Opus and Sonnet requests opt into
server-side refusal fallbacks (`fallbacks: "default"`). A deployment may set
`VISOR_ANTHROPIC_API_KEY` to use one shared key instead of per-user keys. [`test_shared_key_mode`]

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
