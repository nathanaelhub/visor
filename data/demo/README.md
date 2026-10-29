# Demo dataset (all fictional)

Seeds the scaled-up demo: the **real** 2026-27 catalog (`data/catalog/2026-27/`, public data) plus
these **made-up** transfer records and students.

- `schools.csv`, `external_courses.csv`, `reviews.csv`: copied from `data/equivalencies/`.
- `equivalencies.csv`: the same rows, with the sample Lipscomb codes moved onto real catalog codes
  (`CS 1113`→`CS 1213`, `CS 1213`/`CS 2113`→`CS 2233`, `CS 3113`→`CS 2323`). Statuses, sources and
  people are unchanged, so confirmed / proposed / rejected / elective / none are all still covered.
- `students/*.json`: invented students for the Degree Progress tab. Never put a real record here.

Load it:

```
cd backend
VISOR_DATA_DIR=../data/catalog/2026-27 VISOR_EQUIV_DATA_DIR=../data/demo flask --app wsgi seed
```
