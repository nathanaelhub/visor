# Catalog year 2026-27 (real, public data)

Five programs from Lipscomb's public 2026-2027 Undergraduate Catalog: **Computer Science, B.S.** (read
2026-09-27), and **Biology, B.S.**, **Management, B.B.A.**, **Nursing (BSN)** and **Psychology, B.S.**
(read 2026-11-12, spec 07). This is public catalog data, not student data, so it is safe in git.

| File | What |
|---|---|
| `courses.csv`, `prereqs.csv`, `terms.csv`, `sections.csv` | Same format as `data/sample/`, so `flask seed` loads them. `prereqs.csv` adds `min_grade`. |
| `course_terms.csv` | When each course is usually offered (season + every/even/odd year) |
| `course_tags.csv` | Which courses carry `DP` (Diverse Perspectives) and `SOCIAL_INQUIRY` |
| `course_standing.csv` | Courses that need junior (60) or senior (90) hours first |
| `programs.csv`, `req_groups.csv`, `req_items.csv` | The five programs and their requirement groups (spec 04's tables, as files) |
| `program_gates.csv` | Admission gates shown as warnings, never enforced (Nursing's upper-division program) |
| `sources.md` | The exact catalog pages and the open questions for the department |
| `notes.md` | **Every judgment call** made turning catalog prose into rules. Read this before trusting a plan. |
