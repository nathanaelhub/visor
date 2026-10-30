# Claude Design prompt — Visor landing page, nav, and "Ask Visor" chat

Paste everything below the line into Claude Design.

---

Design the web app shell for **Visor**, a course-planning and transfer-advising tool for Lipscomb University (Nashville, TN). Deliver three things: a **landing page**, the **app navigation** with only the tabs listed below, and an **"Ask Visor" chat panel** that runs on the user's own Anthropic API key. Show desktop (1440×900) and phone (390×844) for each.

## What Visor does (so the design reflects it)

- **Students** see their degree progress, a semester-by-semester plan to graduation, and what to take next term — and *why* each course is there ("Unlocks 6 later courses", "Offered Spring only", "Retake: earned D+, needs C"). Students view; they don't edit.
- **Advisors** open any student, see the same plan plus warnings ("Needs advisor review: CS 3633 could not be placed"), and adjust it.
- **Registrar's office** looks up a transfer course from another school and sees what it counts as at Lipscomb: **Confirmed**, **Proposed** (a person must confirm), or **Unknown** (flag for a professor).
- The plan is built by a deterministic rules engine from the real catalog. AI never decides a plan; it only explains and answers questions about it.

## 1. Landing page

- **Hero:** product name, a one-line promise (e.g. "Know your path to graduation — and why every course is on it"), and three entry buttons: **I'm a student**, **I'm an advisor**, **Registrar's office**.
- **How it works** (3 steps): your courses + transfer credit → degree audit against the catalog → a term-by-term plan with reasons.
- **Proof strip:** a small, real-looking preview of a plan card (term name, 4–5 courses, reason chips) and a transfer lookup result with a Confirmed badge.
- **Trust notes:** "Built on Lipscomb's published 2026–27 catalog", "Advisors approve every plan", "Demo uses fictional students only".
- Footer: catalog source, privacy note (student records follow FERPA), contact.

## 2. Navigation — only these tabs

| Tab | Who | Contents |
|---|---|---|
| **My Plan** | student | progress summary (hours done / in progress / required, projected graduation), requirement groups (Met / In progress / Needed), semester plan cards with reason chips |
| **Students** | advisor | searchable student list with flags (needs review, retake, transfer pending) → opens that student's plan |
| **Transfer** | registrar, advisor | school + course lookup, result card (Confirmed / Proposed / Unknown), "Flag for review" action |
| **Ask Visor** | everyone | the chat panel below (also available as a slide-out drawer from any tab) |

Role switcher in the header (demo mode: "Viewing as: Student / Advisor / Registrar"). No other tabs: schedule conflicts and prerequisite checks live *inside* My Plan, not as separate tabs.

## 3. "Ask Visor" chat panel (bring your own API key)

A chat wrapper that connects to Claude with the user's own key and answers questions grounded in Visor's data.

**Connect state (before a key):**
- Card titled "Connect your Anthropic API key" with a masked input, a **Connect** button, a model picker (Claude Opus 5 / Claude Sonnet 5 / Claude Haiku 4.5), and a link "Where do I get a key?".
- Plain-language security note: "Your key stays in this browser session and is sent only to Visor's server to relay your request. It is never stored or shown again." Show a **Disconnect** control once connected and a status pill (Connected · model name).
- Admin variant: "This deployment uses a shared key configured by your administrator" (no input shown).

**Chat state:**
- Suggested prompts tied to Visor: "Why is CS 3633 in Spring 2028?", "What if I fail Data Structures?", "What does my Nashville State credit count as?", "Which requirements am I still missing?"
- Messages can show **tool-call cards** when the assistant uses Visor data — e.g. "Looked up CISP 1020 at Nashville State → CS 2233 · Confirmed", "Ran your degree audit · 3 groups still needed" — each expandable to show the underlying result.
- Answers cite their source with small chips ("Catalog 2026–27", "Your plan", "Equivalency table").
- A persistent footer line: "Visor's planner decides the plan; Ask Visor explains it. Check with your advisor before registering."
- States to design: connecting, invalid key, rate-limited, offline/API down, empty conversation, long answer with a table, the assistant declining to change a plan ("I can't edit your plan — ask your advisor").
- Layout: full-page in the Ask Visor tab; a right-side drawer (desktop) or bottom sheet (phone) from other tabs, keeping the student's current plan in context.

## Visual direction

- Calm, trustworthy, academic, and modern — not a generic SaaS template. Lipscomb purple (#331E54) and gold (#F4AA00) as accents on a light neutral base; provide a dark mode.
- Status colors must be distinguishable without color alone (icon + label): Met/Confirmed, In progress/Proposed, Needed/Unknown, Needs review.
- Readable at a glance: plan cards scannable in under 10 seconds; reason chips small but legible.
- WCAG 2.2 AA contrast, full keyboard navigation, visible focus states, 44px touch targets on phone, no horizontal scrolling at 390px.

## Deliverables

1. Landing page (desktop + phone).
2. App shell with the four tabs and role switcher, showing **My Plan** filled with realistic fictional data.
3. Ask Visor: connect state, connected chat with a tool-call card and citation chips, and the error states listed above; drawer/bottom-sheet variant.
4. A short component list (buttons, pills/badges, plan card, reason chip, tool-call card, chat bubble, key-connect card) with their states.
