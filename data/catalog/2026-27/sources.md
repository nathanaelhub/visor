# Sources — catalog year 2026–2027

All data in this folder was transcribed from the **2026-2027 Undergraduate Catalog** on
catalog.lipscomb.edu (Modern Campus Catalog) on 2026-09-27. The site sits behind a JavaScript
challenge, so the pages were read with a headless browser and the expanded course listings were
parsed by script; every judgment call made while converting catalog prose into rules is listed
under `notes:` in the program file.

| What                                                                                                                                              | URL                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Computer Science, B.S. — program of study requirements                                                                                            | https://catalog.lipscomb.edu/preview_program.php?catoid=33&poid=11188 |
| The Core, Journey (general education, 46 hours; menus for Social Inquiry, Diverse Perspectives, Virtue/Flourishing/Vocation; transfer guidelines) | https://catalog.lipscomb.edu/content.php?catoid=33&navoid=2779        |
| Course descriptions (filtered by prefix, expanded)                                                                                                | https://catalog.lipscomb.edu/content.php?catoid=33&navoid=2729        |
| Academic departments (program index)                                                                                                              | https://catalog.lipscomb.edu/content.php?catoid=33&navoid=2731        |

Prefixes read for course data: CS, CCT, IT, SENG, SEC, DS, MA, PH, ENGR, EN, CO, BI, LU, HI, PO,
PL, ARTS, SCI, EC, ED, FS, GL, LJS, PS, SO, SW, BY, KIN, FR, GE, ITA, ML, NURS, SN.

## Open questions for the advising office / department

See `notes:` in `programs/bs-computer-science.yaml`. The ones that change forecasts:

1. **CS 3633 Advanced Algorithms** lists prerequisite _CS 3623_, which does not exist in this
   catalog (Design and Analysis of Algorithms is CS 2623). Modeled as CS 2623.
2. **EN 1223 ↔ CO 1223** list each other as prerequisites. Modeled as neither.
3. **EN 3143 Technical Writing** requires EN 1223 or LU 1013; the program page lists neither.
4. **Major minimum grade**: the program page states none; prerequisite chains require C.
   Modeled as minGrade C on the major groups.
5. **Junior/senior standing** prerequisites (CCT 395V, CCT 405V, IT 4423) are approximated by
   course prerequisites.

## Not yet covered

- The archived **2025-2026** catalog (students who declared before Fall 2026 may be on it).
- The department's advising sheet / recommended semester sequence, if one exists — it would
  refine the elective recommendation order.
