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

## Added 2026-11-12: Biology, Management (B.B.A.), Nursing (BSN), Psychology (spec 07)

- Biology: elective menu 'five courses selected from' modeled as choose 5 of the listed courses; the 'BY 2213 or (BY 3514 and BY 3524)' and 'BY 2424 or BY 3214' pairs are listed as separate options, and variable-credit BY 450V/460V (chair approval) are left out. CONFIRM.
- Biology: courses offered 'in alternate years' are modeled as every year (parity not stated).
- Biology: Scientific Inquiry is met by the major (BY, CM); Quantitative Inquiry by MA 1113. Total 126 hours is the university minimum (College of Business page); the program page states only the 56-hour major. Free electives fill the rest.
- Psychology: electives 'choose 9 hours' modeled as 9 hours from the listed courses that are regularly offered; on-demand courses and variable-credit topics/internships are left out of the planner's picks (they still count if taken).
- Psychology: minimum grade C in the major is assumed (prerequisite chains require C); the page states none. Scientific Inquiry modeled as SCI 2304 or one foundational science course (BY 1134, BY 2213, CM 1024); the Core page says '4 hours of foundational science coursework'. CONFIRM.
- Nursing: BI 3213 (Christianity & Society) and PS 1113 (Social Inquiry) are in the nursing course list, so those Core groups are not repeated. The medical-terminology certificate (non-credit) is not modeled. Admission to the upper-division program is shown as a warning on every nursing plan, never decided by the planner.
- Nursing: the program page's Core list has no Great Ideas in Politics/Philosophy course; none is required here. NURS 3993 is the Virtue, Flourishing & Vocation course and the sciences cover Scientific Inquiry. CONFIRM.
- Nursing: minimum grade C assumed for nursing and science courses; CONFIRM with the School of Nursing.
- Management: the B.B.A. business core is from the College of Business page (navoid 2700). EC 2403 meets Social Inquiry and MA 2183 meets Quantitative Inquiry (both in the business core), so those Core groups are not repeated.
- Management: the concentration (9 h) is modeled as the Integrated Management concentration (any upper-division business), combined with the major's 'one upper-division COB course' and the business core's 'any 3000/4000 business course' into one 15-hour group. A student choosing Healthcare, Data Analytics or Supply Chain needs those courses named by an advisor (spec 06 pins). CONFIRM.
- Management: BA 3993 (Business Values: Virtue, Flourishing and Vocation) in the business core meets the Core's Virtue, Flourishing & Vocation requirement.
- Biology and Psychology have no discipline Virtue, Flourishing & Vocation course in the pages read, so the Core's alternative BI 3433 Practices for Spiritual Formation is used. CONFIRM.
- Lipscomb has no 'Business Administration' major; Management, B.B.A. (the general management degree) stands in for it (decision 2026-11-12).
- BI 3433 Practices for Spiritual Formation: course row added from the Core page (credits 3, fall and spring assumed; junior standing); its description page was not read. CONFIRM.
- SCI 2304 Scientific Inquiry: The Practice of Progress: course row added from the Core page (credits 4, fall and spring assumed); its description page was not read. CONFIRM.
- BY 2133: offered in alternate years (parity not stated); modeled as every year.
- BY 3524: prerequisite text not modeled: 'Physiology I'.
- BY 3123: offered in alternate years (parity not stated); modeled as every year.
- BY 2623: offered in alternate years (parity not stated); modeled as every year.
- BY 3413: offered in alternate years (parity not stated); modeled as every year.
- BY 3903: prerequisite text not modeled: 'permission of the academic chair'.
- BY 4413: offered in alternate years (parity not stated); modeled as every year.
- NURS 2103: prerequisite text not modeled: '(Anatomy & Physiology I)'.
- NURS 3553: offered in alternate years (parity not stated); modeled as every year.
- NURS 3003: offered in alternate years (parity not stated); modeled as every year.
- BA 390V: variable credit '0-10' modeled as 10.
- BA 3993: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- DS 2503: prerequisite text not modeled: 'successful completion of the college of business spreadsheet pre-test'.
- FI 3503: prerequisite text not modeled: 'successful completion of the college of business spreadsheet pre-test'.
- BA 2601: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- AC 4803: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- FI 4803: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- MG 4803: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- MK 4803: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
- MG 4253: catalog gives no regular term (none); modeled as fall+spring. CONFIRM.
