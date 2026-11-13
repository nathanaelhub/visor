# Visor: Saved chats and the conversation log (design, v0.1)

Status: **draft for approval**. Builds on spec 08 (accounts and roles) and the Ask Visor relay (spec 05).

## Why

Students can't come back to an earlier conversation, and staff can't check what Ask Visor actually told
someone ("the AI said I could skip MA 2183"). Today Visor deliberately stores no chat text. This spec
stores conversations for signed-in people, with a clear notice, limited readers and a fixed retention.

## Decisions

| Question | Decision |
|---|---|
| Who can read a student's chats? (Nathanael, 2026-11-12) | **The person themselves, their advisor, and Visor admins.** |
| How long are chats kept? (Nathanael, 2026-11-12) | **One academic year (365 days)**, then deleted automatically. |
| Before real students use it | **IT sign-off (Brett Hanson)**: once saved, a real student's chats are part of their education record (FERPA). Until then the public site has fictional records only (spec 08). |
| Whose chats are saved? (proposed) | **Signed-in people only.** Signed-out demo chats stay unsaved and anonymous, as today. |
| What is stored? (proposed) | Every question and the exact answer, the model, the time, and each tool Claude used with its input and one-line summary. The full tool results are not stored; the planner can recompute them from the record. |
| Can it be edited? (proposed) | **No.** Rows are only added. Each message carries a hash of the previous one, so a changed or missing message shows up as a broken chain. Only the retention job deletes, whole conversations at a time. |

## User stories

### US-9.1 Signed-in person: see and return to my chats

1. **Given** a signed-in person in Ask Visor, **then** the chat shows **"Saved for one year. Your advisor
   and Visor admins can read it."** A signed-out visitor sees **"Not saved."** [frontend test]
2. **Given** a signed-in person's chat, **then** each question and answer is saved as it happens, under
   one conversation (who, which student record, model, start time). [`test_signed_in_chat_is_saved`,
   `test_signed_out_chat_is_not_saved`]
3. **Given** **History** in Ask Visor, **then** the person sees their own conversations, newest first, and
   can open one to read it. [`test_people_see_only_their_own_history`]

### US-9.2 Advisor / admin: check what Ask Visor said

1. **Given** an admin, **then** a **Conversations** page lists every saved conversation (person, student
   record, date, first question) and opens the full transcript with the tools Claude used.
   [`test_admin_reads_any_conversation`]
2. **Given** an advisor, **then** they see conversations about **their advisees'** records only.
   [`test_advisor_reads_advisees_conversations_only`]
3. **Given** a student or a signed-out visitor, **then** the log routes answer `403`.
   [`test_students_cannot_read_others`]
4. **Given** any conversation, **then** it shows **"Log verified"** when the hash chain is intact, and
   names the first broken message otherwise. [`test_tampering_breaks_the_chain`]
5. **Given** a reader opens someone else's conversation, **then** that access is itself recorded (who,
   when) and shown on the conversation. [`test_reading_is_recorded`]

### US-9.3 Everyone: chats don't outlive the retention period

1. **Given** a conversation older than 365 days, **then** the daily job deletes it and its messages.
   [`test_old_conversations_are_purged`]
2. **Given** the purge route, **then** only Vercel Cron (with `CRON_SECRET`) or the write token can call it.
   [`test_purge_needs_the_cron_secret`]

## Design

### Storage

| Table | Columns |
|---|---|
| `conversation` | `id`, `user_id` → `app_user`, `student_key` (student number, or `transcript:<id>` for a record read from a transcript), `student_name`, `model`, `started_at`, `last_at` |
| `chat_message` | `id`, `conversation_id`, `seq`, `role` (user/assistant), `text`, `tools` JSON (`[{tool, input, summary, status}]`), `model`, `created_at`, `prev_hash`, `hash` (SHA-256 of `prev_hash` and the row's content) |
| `log_access` | `id`, `conversation_id`, `reader_id` → `app_user`, `read_at` |

### API

| Route | What | Who |
|---|---|---|
| `POST /api/chat` | Unchanged for signed-out visitors. Signed in: accepts `conversation_id` (or starts one) and returns it; saves the question and the answer | anyone |
| `GET /api/chats` | My conversations | signed in |
| `GET /api/chats/<id>` | One conversation with its messages and `verified` | owner, the record's advisor, admin |
| `GET /api/admin/conversations` | All conversations (admins) or advisees' (advisors) | advisor, admin |
| `POST /api/cron/purge-chats` | Delete conversations older than 365 days | Vercel Cron (`CRON_SECRET`) or the write token |

A cron entry in `vercel.json` runs the purge daily.

### What stays the same

- Ask Visor's limits (US-5.6) and its read-only tools.
- Signed-out visitors: nothing stored.
- No real student records on the public site until IT signs off.
