# Transfer schools' course lists (public catalogs)

Spec 07, US-7.1. The first five schools on the registrar's "Top Incoming Transfer Schools" list, plus MTSU (8th). Each
`<slug>/courses.csv` is that school's 2026-27 undergraduate course list, read from its public
Acalog catalog by `tools/scrape_external/scrape.py`. This is public catalog data, not student data.

How it was read (2026-11-11 and 12):
- robots.txt was read first and obeyed: no disallowed paths, and the 120-second crawl-delay these
  sites ask of every crawler was kept between requests to the same site.
- Pages that answer plain HTTP with a JavaScript challenge (all but Vol State) were loaded in a
  headless browser, one request per page.
- Raw pages are cached in `data/private/scrape-cache/` (git-ignored), so the CSVs can be rebuilt with
  `python3 tools/scrape_external/scrape.py --parse-only` without asking the sites again.

UT Knoxville writes credits before the description ("<strong>3</strong> Credit Hours") and marks some
course numbers with an asterisk ("CMST 201*"); both are handled.

What is kept: undergraduate, college-credit courses with subject, number, title, credits (the upper
value of a range), the first 400 characters of the description, catalog year and source page.
What is left out: learning-support courses (numbered 0xxx), anything numbered 500+ at a university,
duplicates, and courses whose credits could not be read (never guessed).

| School | Catalog | Pages | Courses | Left out |
| --- | --- | --- | --- | --- |
| Nashville State Community College | 2026-2027 Catalog | 7 | 594 | 21 |
| Volunteer State Community College | 2026-2027 Undergraduate Catalog | 7 | 653 | 25 |
| Columbia State Community College | 2026-2027 Catalog and Student Handbook | 6 | 473 | 11 |
| University of Tennessee at Chattanooga | 2026-2027 Undergraduate Catalog | 26 | 2,467 | 33, plus ESC 1250, INTS 4500 and UHON 3640R (no readable credits) |
| University of Tennessee, Knoxville | 2026-2027 Undergraduate Catalog | 50 | 4,996 | ENGL 263, WGS 425 (no readable credits) |
| Middle Tennessee State University (added 2026-11-13; 8th on the list, and the school of the sample transcript) | 2026-2027 Undergraduate Catalog | 35 | 3,471 | 7, plus ECE 4376, ENGL 3506, FREN 2900, JOUR 3800 (no readable credits) |

Catalog home pages: https://nscc.catalog.acalog.com, https://catalog.volstate.edu,
https://catalog.columbiastate.edu, https://utc.catalog.acalog.com, https://catalog.utk.edu,
https://mtsu.catalog.acalog.com
