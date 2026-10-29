# Judgment calls made converting catalog prose into rules

Each line is a decision a person should confirm. Source: 2026-2027 Undergraduate Catalog, read 2026-09-27.

1. Catalog page states: total 127 hours = Core (Journey) 38 + major 69 + electives 9, plus '6 hours of additional electives to meet the minimum university requirement of 126'. The groups below cover 120 hours (the page's own '69 hours' major list sums to 71, and the four Core-specific courses add 13). The remaining credits toward totalCredits are free electives, which the engine reports in credits.remaining but does not plan.
2. ENGR 1000 Professional Development and Networking (0 credits, 'must be taken every semester') is not modeled as a requirement group; advisors should remind students.
3. Major groups carry minGrade C because every CS/SENG/IT prerequisite chain in the catalog requires a C or higher; the program page itself states no major minimum grade. CONFIRM with the department.
4. Core groups already satisfied by major/specific courses are omitted: Quantitative Inquiry (MA 1314), Scientific Inquiry (PH 2414), POWERS (EN 3143 + CO 1223 per the program page), Great Ideas in Politics/Philosophy and Virtue/Flourishing/Vocation (ENGR 3993 per the program page). The B.S. 15-hour math/science requirement is covered by the major.
5. Artistic Inquiry alternative '3 semesters of ensembles (for non-CEA majors)' is not modeled.
6. Christianity & Society menu: the Core page lists BI 1003 as an option 'taken prior to the Story classes'; it is included as a third option.
7. Literature: 'EN 2103 Literary Inquiry or a Survey Literature course'; survey courses EN 2113–2163 are included as options. EN 2103 sections tagged DP also satisfy Diverse Perspectives.
8. Diverse Perspectives is shareable: a DP-tagged course taken for another requirement also counts here (Core page).
9. Elective pool = 3000/4000-level CS, SENG, SEC, IT courses that are regularly offered, in a recommendation order chosen by the team; 'or an elective approved by the department' is not modeled. Excluded: CS 3243 (offered on demand); CS 3333 (offered on demand); CS 4013 (offered on demand); CS 350V (special topics, on demand); IT 350V (special topics, on demand); SEC 350V (special topics, on demand); SENG 350V (special topics, on demand); IT 3121 (master's-program applicants only); IT 3131 (master's-program applicants only); SEC 4053 (information-security seniors only); SEC 4193 (optional travel course).
10. CS 1213 prerequisite is 'MA 1113 or higher' (math placement); modeled as none.
11. MA 1314 prerequisite is MA 1123/MA 1135 with C or ACT/SAT placement; modeled as none (CS students typically place into Calculus I).
12. MA 2103 prerequisite is MA 1113/MA 1135 with C or ACT 23 / SAT 560; modeled as none.
13. MA 2183 prerequisite is MA 1113/MA 1135 with C or ACT placement; modeled as none.
14. MA 2314 also accepts AP Calculus AB ≥ 3; modeled as MA 1314 only.
15. CCT 395V requires junior standing + program director permission; approximated as 'after CS 2233'. Advisor should confirm timing.
16. CCT 405V requires senior standing + 30 hours of CS; approximated as 'after CS 2623 and CS 3123'.
17. CS 3633 lists prerequisite 'CS 3623', which no longer exists in the 2026-27 catalog; Design and Analysis of Algorithms is now CS 2623. Modeled as CS 2623 — CONFIRM with the department.
18. CS 3523 alternative prerequisite '(EECE 3624 and CS 2233)' dropped: EECE 3624 is not in the 2026-27 catalog.
19. SENG 3233 prerequisite text 'CS 1013 or CS 1213 and SENG 2513' read as (CS 1013 or CS 1213) and SENG 2513.
20. IT 4423 'junior standing' dropped; IT 3413 kept.
21. LU 1013 prerequisite is an ACT/SAT writing score or EN 1113 with C; modeled as none.
22. EN 1223 prerequisite (placement/EN 1113) modeled as none.
23. Catalog lists EN 1223 as a prerequisite of CO 1223 AND CO 1223 as a prerequisite of EN 1223 (a cycle; they are the POWERS substitutes). Both modeled as prerequisite-free. CONFIRM with the advising office.
24. EN 3143 requires EN 1223 or LU 1013, neither of which the program page lists; the forecast will plan one of them (3 hours, absorbed by the 6 hours of additional electives). CONFIRM.
25. IT 3223 'instructor approval' alternative dropped.
26. EC 3603 removed from menu options: prerequisite chain reaches FI 3503, which is outside the prefixes read.
27. NURS 4054 removed from menu options: prerequisite chain reaches CHEM 1024, which is outside the prefixes read.
28. PS 4613: prerequisite 'senior standing.' names no course; modeled as none.
29. ITA 1124: prerequisite 'Elementary Italian I or equivalent with a grade of 'C' or higher.' names no course; modeled as none.
30. ENGR 3613: non-course clause in prerequisite 'PH 2414 and Consent of Instructor' dropped.
31. ED 3343: prerequisite 'Admission to the program.' names no course; modeled as none.
32. BY 3553: catalog says 'SP offered in alternate years' (parity unknown); modeled as every year.
33. CCT 395V: variable credit '1-3' modeled as 3; advisor can adjust in feature 002.
34. CS 1013: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
35. CS 3463: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
36. CS 3843: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
37. CS 4323: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
38. CS 4333: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
39. FS 2013: catalog gives no regular term ('Offered on demand'); modeled as fall+spring. CONFIRM.
40. GL 110V: variable credit '1-3' modeled as 3; advisor can adjust in feature 002.
41. GL 110V: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
42. LJS 3533: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
43. PO 3153: catalog gives no regular term (''); modeled as fall+spring. CONFIRM.
44. SO 3023: catalog gives no regular term ('Offered on demand'); modeled as fall+spring. CONFIRM.
45. Every prerequisite carries min_grade C: the catalog's CS/MA/SEC/IT prerequisite text says 'with a grade of C or higher' almost everywhere. Placement-only prerequisites were already modeled as none.
46. Class standing ("junior standing", "senior standing", "taken junior or senior year") is modeled in `course_standing.csv` as a minimum number of completed + planned hours before the course can be planned: junior = 60, senior = 90. CONFIRM the thresholds with the registrar.
47. Major-elective recommendation order (the order the forecast picks in) was chosen by the team, not the department: AI and theory first, then security, IT, software engineering. Courses with no regular term in the catalog are last within their area.
