# Visor: Login and roles (design, v0.1)

Status: **draft for approval**. Replaces the stopgap write token (KAN-46) for people, and is the
base for saved chats and the conversation log (spec 09) and for reviewing Claude's proposals.

## Why

Advisor edits, approvals, flagging, Claude-proposal review and transcript uploads only work locally,
because the live site can't tell a registrar from a visitor. The browser can't send the write token
(and shouldn't hold it). Visor needs accounts and roles.

## Decisions (Nathanael, 2026-11-12)

| Question | Decision |
|---|---|
| How do people sign in? | **Clerk**, installed through the Vercel Marketplace (email code, Google, Microsoft). It can move to Lipscomb's Microsoft SSO later, once IT registers an app. |
| Who gets which role? | **Admins by email** (`VISOR_ADMIN_EMAILS`). Everyone else starts as a **student**; an admin page promotes people to **advisor** or **registrar** and assigns advisees. |
| What does signing in unlock? | **Staff features only.** Advisors, registrars and admins can save plan edits, approve, flag, review proposals and upload transcripts. Students keep using fictional demo records; signed-out visitors keep today's demo. |

## User stories

### US-8.1 Anyone: sign in and out

1. **Given** the site, **then** a **Sign in** button opens Clerk's sign-in, and a signed-in person sees
   their name and role in the header with **Sign out**. [frontend test of the header state]
2. **Given** a signed-out visitor, **then** everything works exactly as today's public demo: fictional
   students, the role switcher, the shared Ask Visor key and its limits. [`test_signed_out_is_the_demo`]

### US-8.2 Admin: give people roles

1. **Given** an email in `VISOR_ADMIN_EMAILS`, **then** that person is an **admin** when signed in, and
   can't be demoted from the page. [`test_admins_come_from_the_env`]
2. **Given** the admin page, **then** an admin lists everyone who has signed in, sets a role (student,
   advisor, registrar), and assigns advisees to an advisor. Every change records who made it and when.
   [`test_admin_sets_roles_and_advisees`, `test_only_admins_change_roles`]

### US-8.3 Staff: do staff things on the live site

1. **Given** a signed-in **advisor**, **then** they can save edits and approve plans for **their**
   advisees only (spec 06); other students' plans are read-only to them. [`test_advisor_edits_own_advisees_only`]
2. **Given** a signed-in **registrar**, **then** they can flag courses and confirm or reject equivalencies,
   including Claude's proposals (`decided_by` = their name). [`test_registrar_decides_equivalencies`]
3. **Given** advisor, registrar or admin, **then** `uploads_open` is true and the transcript file
   picker appears (page and 📎). Students never see it on the public site. [`test_uploads_open_for_staff_only`]
4. **Given** an **admin**, **then** they can do all of the above.
5. **Given** the write token (`X-Visor-Token`), **then** it still works for scripts and seeding, and is
   never needed in the browser. [`test_token_still_works_for_scripts`]

### US-8.4 Everyone: the server decides, not the browser

1. **Given** any request, **then** the role comes from a verified Clerk session token (`Authorization:
   Bearer`), checked against Clerk's published keys, issuer and authorized party (our own site). A
   role sent by the browser is ignored. [`test_forged_or_expired_tokens_are_refused`]
2. **Given** no token or a bad one, **then** the request is treated as a signed-out visitor (reads
   work; staff writes answer `401`/`403` as today).

## Design

### Clerk

- `vercel integration add clerk` provisions the Clerk app and its env vars. The publishable key
  reaches Vite as `VITE_CLERK_PUBLISHABLE_KEY`; `CLERK_SECRET_KEY` stays on the server.
- **Frontend:** Clerk's React SDK: `ClerkProvider`, `SignInButton`, `UserButton`, `useAuth().getToken()`.
  `lib.js` `api()` adds `Authorization: Bearer <token>` when signed in.
- **Backend:** `backend/visor/accounts.py` verifies the JWT with PyJWT against Clerk's JWKS (cached),
  checking `iss`, `exp`, `nbf` and `azp` (our origins), then loads or creates the `app_user` row.

### Storage

| Table | Columns |
|---|---|
| `app_user` | `id`, `clerk_id` (unique), `email`, `name`, `role` (student/advisor/registrar/admin), `created_at`, `role_set_by`, `role_set_at` |
| `advisee` | `advisor_id` → `app_user`, `student_key` (student number), `assigned_by`, `assigned_at` |

### API

| Route | What | Who |
|---|---|---|
| `GET /api/me` | Name, email, role, advisee keys (`null` when signed out) | anyone |
| `GET /api/admin/users` | Everyone who has signed in | admin |
| `PUT /api/admin/users/<id>` | Set role | admin |
| `PUT /api/admin/users/<id>/advisees` | Set advisees | admin |

Existing write routes switch from `write_guard()` to `require_role(...)`, which accepts a staff session
**or** the write token.

### What stays the same

- Fictional data only on the public site. A real student record is never stored (that needs IT
  sign-off from Brett Hanson, as before).
- Ask Visor conversations are still not stored. Saved chats and the log come in spec 09, built on
  these accounts (decided: readable by admins and the student's advisor, kept one academic year).

## Open questions

- Should Lipscomb email addresses become staff-capable automatically? Not now (decision: admins grant
  roles).
- Moving to Lipscomb Microsoft SSO needs an app registration from IT.
