# Visor: Advisor edits and plan approval (design, v0.1)

Status: **draft for approval** (issue #8, finding F1 from the user-case report, case A2). Builds on
spec 05. No code until this is approved.

## Why

The original brief says advisors **view and modify** a plan, and the landing page says "Advisors
approve every plan". Today an advisor can only view. This spec adds four things an advisor can do,
says where they are kept, what "approved" means, and how the independent checker re-checks an edited
plan.

## Decisions (Nathanael, 2026-11-10)

| Question | Decision |
|---|---|
| Where are edits kept? | **In the database on a staff deployment** (requests with the write token, KAN-46). On the public demo every edit still works, but it lives in the browser tab and the page says **"Not saved in the demo."** |
| What can an advisor change? | **Plan settings** (summer on/off, target and maximum hours), **pin** a course to a term, **hold** a course back until a term, and **approve** the plan. |
| What happens to an approval when the plan changes? | It is **marked out of date**. Approval belongs to one exact plan; any change to the record, the edits or the catalog shows "Plan changed since approval" to both student and advisor. |

## What stays the same

- **The planner decides; people adjust its inputs.** An advisor never types a plan. Edits are
  inputs to `project()`; the planner still places everything else and gives every course a reason.
- **The checker stays independent.** `rules/verify.py` does not import the planner and gains no
  knowledge of pins. A pin that breaks a rule is caught the same way any planner bug would be.
- **Students can't edit.** The student view shows the advisor's edits and the approval, read-only.
- **Fictional data only** in git and on the public demo.

## User stories

### US-6.1 Advisor: change a student's plan settings

**As** an advisor, **I want** to turn summer terms on or off and set the target and maximum hours per
term for one student, **so that** the plan fits their life (a job, an athletic season, an overload).

1. **Given** an advisor's settings for a student, **when** the plan runs, **then** it uses them in
   place of the defaults (no summer, target 15, max 18). [`test_settings_edits_change_the_plan`]
2. **Given** a maximum above 18 or below 12, **then** it is refused (`400`) unless it is 19–21 and
   the edit carries a note; then the plan shows "Overload approved by advisor: <note>".
   [`test_overload_needs_a_note`]
3. **Given** settings, **then** the checker verifies the plan against the advisor's maximum, not 18.
   [`test_checker_uses_the_advisors_maximum`]

### US-6.2 Advisor: pin a course to a term

**As** an advisor, **I want** to put a course in a specific term, **so that** the plan matches what we
agreed (a course only taught by a professor on sabbatical next year, a study-abroad term).

1. **Given** a pin `{code, term}` for a course the student still needs, **when** the plan runs,
   **then** the course is in that term with the reason **"Pinned by your advisor"**, and the planner
   places everything else around it. [`test_pin_places_the_course`]
2. **Given** a pin that breaks a rule (prerequisite not done by then, course not offered that term,
   or the term goes over the maximum), **then** the pin is kept, the checker reports the violation,
   and the plan is **Needs advisor review** with a warning naming the pin. Nothing silently moves it.
   [`test_bad_pin_is_kept_and_flagged`]
3. **Given** a pin for a course the student doesn't need (done, or not in the program), **then** it
   is ignored with a warning. [`test_pin_for_a_course_not_needed_is_ignored`]
4. **Given** several pins in one term, **then** they are placed in the order given; a pin before the
   plan's start term is refused (`400`).

### US-6.3 Advisor: hold a course back

**As** an advisor, **I want** to say "not before <term>" for a course, **so that** the planner moves
it later (the student needs a lighter first term, or wants a professor who teaches it next year).

1. **Given** a hold `{code, not_before}`, **then** the course is placed in that term or later with
   the reason **"Held until <term> by your advisor"**, and courses that need it move later too.
   [`test_hold_moves_the_course_and_its_dependents`]
2. **Given** a hold that makes a requirement impossible within the planning horizon, **then** it is a
   warning and there is no projected graduation term, the same as any course that can't be placed.
3. **Given** a hold, **then** the checker confirms no held course is placed before its term.
   [`test_checker_enforces_holds`]

### US-6.4 Advisor: approve the plan

**As** an advisor, **I want** to approve a student's plan, **so that** the student knows this is the
plan we agreed on.

1. **Given** a plan with no checker violations and no courses that can't be placed, **when** the
   advisor approves it with their name and an optional note, **then** the approval records who, when,
   the note and a **fingerprint** of the plan. [`test_approve_records_the_fingerprint`]
2. **Given** checker violations or unplaced courses, **then** approve is refused (`409`) with the
   reasons. Fix the pins or holds first. [`test_cannot_approve_a_plan_that_fails_its_checks`]
3. **Given** an approval, **then** the student's My Plan shows **"Approved by <name> on <date>"** and
   the note. [`test_student_sees_the_approval`]
4. **Given** any later change (record, edits, catalog or planner output), **then** the fingerprint no
   longer matches and both views show **"Plan changed since approval · needs re-approval"**. The old
   approval stays in the history. [`test_approval_goes_out_of_date`]

### US-6.5 Everyone: see what was changed and by whom

1. **Given** saved edits, **then** the plan shows an "Advisor changes" list (each pin, hold and
   setting, who made it and when) and each affected course carries its chip.
2. **Given** the public demo, **then** the advisor can try every edit and approval, they apply to
   the plan in that browser tab only, and the panel says **"Not saved in the demo."** Saving answers
   `403` there, as every write does today. [`test_public_demo_does_not_save_edits`]
3. **Given** Ask Visor on a plan with edits, **then** `run_degree_audit` uses the edits, so the chat
   can say "Your advisor pinned CS 3123 to Fall 2027". Ask Visor still cannot change anything.
   [`test_chat_sees_advisor_edits`]

## Design

### Rules (pure, in `backend/visor/rules/`)

```python
@dataclass(frozen=True)
class Pin:  code: str; term: str                 # term code, e.g. "2027FA"
@dataclass(frozen=True)
class Hold: code: str; not_before: str

@dataclass(frozen=True)
class Edits:
    pins: tuple[Pin, ...] = ()
    holds: tuple[Hold, ...] = ()
    overload_note: str | None = None
```

- `project(..., settings, edits=Edits())`: place pins first (in order), then the usual loop with
  holds as an extra "not before" constraint. New reason kinds: `pinned`, `held`.
- `verify(plan, catalog, taken, max_hours, holds=())`: adds a `hold` rule. It still knows nothing
  about pins; a bad pin shows up as an ordinary `prerequisite` / `offering` / `load` violation.
- `fingerprint(plan, record_digest, edits) -> str`: SHA-256 of canonical JSON (sorted keys) of the
  plan's terms and course codes, a digest of the record (program, taken, transfer) and the edits.

### Storage (staff deployments only)

| Table | Columns |
|---|---|
| `plan_edits` | `student_key` (student number), `program_id`, `settings` JSON, `pins` JSON, `holds` JSON, `overload_note`, `updated_by`, `updated_at` |
| `plan_approval` | `id`, `student_key`, `fingerprint`, `approved_by`, `approved_at`, `note` (history: rows are only added) |

`approved_by` / `updated_by` are typed names until real login (KAN-30), the same as `decided_by` on
equivalencies.

### API

| Route | What | Write token |
|---|---|---|
| `POST /api/audit` | Accepts `edits: {settings, pins, holds, overload_note}`. Computes only; never saves. Response adds `fingerprint` and, per course, `pinned` / `held`. | no |
| `GET /api/students/<key>/plan-edits` | Saved edits and the latest approval (or empty) | no |
| `PUT /api/students/<key>/plan-edits` | Save edits | **yes** |
| `POST /api/students/<key>/approval` | `{approved_by, note, fingerprint}`; `409` if the fingerprint isn't the current plan's or the plan fails its checks | **yes** |

### UI

- **Advisor plan view:** an "Adjust plan" panel (summer toggle, target and max hours, overload
  note), a pin / hold menu on each planned course ("Pin to…", "Hold until…"), and an **Approve plan**
  button with name and note. Changes re-run the plan at once. A save button appears on staff
  deployments; the demo shows "Not saved in the demo".
- **Student My Plan:** an approval banner (approved / changed since approval / not yet approved),
  the advisor-change chips, and the "Advisor changes" list. No edit controls.

## Open questions (don't build around these yet)

- Should a student be able to *request* a change (a note to the advisor)? Not in this spec.
- Does the registrar need to see approvals? Ask Ms. Hood.
- Does an approval need a second signature for overloads above 18? Ask the department.
