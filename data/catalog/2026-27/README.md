# Catalog year 2026-27 (real, public data)

The **Computer Science, B.S.** program from Lipscomb's public 2026-2027 Undergraduate Catalog,
read on 2026-09-27. This is public catalog data, not student data, so it is safe in git.

| File | What |
|---|---|
| `courses.csv`, `prereqs.csv`, `terms.csv`, `sections.csv` | Same format as `data/sample/`, so `flask seed` loads them. `prereqs.csv` adds `min_grade`. |
| `course_terms.csv` | When each course is usually offered (season + every/even/odd year) |
| `course_tags.csv` | Which courses carry `DP` (Diverse Perspectives) and `SOCIAL_INQUIRY` |
| `course_standing.csv` | Courses that need junior (60) or senior (90) hours first |
| `programs.csv`, `req_groups.csv`, `req_items.csv` | The program and its 11 requirement groups (spec 04's tables, as files) |
| `sources.md` | The exact catalog pages and the open questions for the department |
| `notes.md` | **Every judgment call** made turning catalog prose into rules. Read this before trusting a plan. |
