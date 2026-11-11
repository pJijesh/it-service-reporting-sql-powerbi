# Power BI design

A report design for the service level data in this repository: a star schema, Power Query for loading it, DAX
measures, a page layout and a data dictionary. It is a specification that follows documented syntax. It is not a
built report.

| File | What it is |
| --- | --- |
| [data-model.md](data-model.md) | Star schema diagram (source [`data-model.mmd`](data-model.mmd), rendered [`data-model.svg`](data-model.svg)), relationships and design choices. |
| [load-csvs.pq](load-csvs.pq) | Power Query M for every table: loading the CSV files, parsing UTC timestamps, building the model tables. |
| [measures.dax](measures.dax) | 46 DAX measures, each with a header saying what question it answers and how to format it. |
| [measures.md](measures.md) | The same measures as a reference table, grouped, with cohort and the SQL view each one mirrors. |
| [report-layout.md](report-layout.md) | Seven pages, their visuals and fields, filters, and what a board member and a managing director each need. |
| [data-dictionary.md](data-dictionary.md) | Every column in every CSV and in the Power BI fact table. |

## Why the logic sits in SQL

The service level clock counts minutes inside each site's support window. That is date arithmetic across time
zones and holidays, and it is written once, in SQL, and tested against hand worked answers. Power BI loads the
result (`model/fact_ticket.csv`) and its measures only count and divide. This keeps one definition of a breach
and makes the Power BI numbers checkable against the SQL output.

## Verification status

What was checked, and what was not.

**Not done.** No `.pbix` file is included. Nothing in this folder has been opened or run in Power BI Desktop, the
Power BI service or any DAX engine. The DAX measures and the Power Query M were not evaluated. They may need small
corrections on first use.

**Done.**

- **Function names and syntax.** Each DAX function used (`CALCULATE`, `COUNTROWS`, `COUNT`, `SUM`, `MAX`, `MIN`,
  `DIVIDE`, `EOMONTH`, `FILTER`, `REMOVEFILTERS`, `USERELATIONSHIP`, `ISBLANK`, `IF`, `BLANK`, `TRUE`, `SWITCH`,
  `SELECTEDVALUE`) and the `VAR` and `RETURN` syntax was checked against its reference page on Microsoft Learn,
  using the web, in November 2026. The M functions used (`Csv.Document`, `File.Contents`, `Table.PromoteHeaders`,
  `Table.TransformColumnTypes`, `Table.TransformColumns`, `Table.AddColumn`, `Table.NestedJoin`,
  `Table.ExpandTableColumn`, `Table.ReplaceValue`, `Replacer.ReplaceValue`, `Table.SelectColumns`, `Table.Distinct`,
  `Table.ColumnNames`, `#date`, `#datetime`, `#table`, `Text.Range`, `Number.FromText`, `DateTime.Date`) were checked the same way.
- **Modelling guidance.** The star schema and date table points were checked against Microsoft's pages on star
  schema design and on date tables. The row-level security notes were checked against Microsoft's page on
  row-level security in the service.
- **Static checks.** `tests/test_powerbi_spec.py` checks that the measures file has balanced brackets, uses only
  an allowed list of function names, and gives every measure a documentation header; that every measure appears
  in [measures.md](measures.md); that every column of every CSV appears in the data dictionary; and that every
  query in the M file is listed. These tests do not execute DAX or M.
- **The numbers underneath.** The SQL views that the measures mirror are tested against hand worked values and an
  independent Python calculation. The DAX restates those sums and ratios. If the DAX is wrong, it will most
  likely differ from the SQL output, which is why the layout's build order starts with three numbers to compare.

**Points to treat with care.**

- `DateTimeZone.FromText` is documented as accepting ISO 8601 text, but the pages checked did not say that a
  trailing `Z` is accepted in every culture. The M file therefore parses the UTC timestamps by hand with
  `Text.Range` and `Number.FromText`, and builds the value with `#datetime`. This avoids the question. It was not
  run.
- Blank handling in the M file replaces empty text with null using `Replacer.ReplaceValue`. Its Microsoft
  page does not say whether it matches whole values only, as the single example suggests. If empty cells do not
  become null in your copy, check that step first.
- Month and date arithmetic in the DAX uses `EOMONTH` on a date and compares dates with Boolean filter
  arguments inside `CALCULATE`. Microsoft's `EOMONTH` and `CALCULATE` pages were checked. Date values as numbers
  were confirmed only on the third party reference dax.guide, not on a Microsoft page.
- The `USERELATIONSHIP` and row-level security combination is limited in Microsoft's documentation. See
  [data-model.md](data-model.md) for the fallback.
- The report layout is a design. No one has used it with a real audience.

## Using it

1. Build the tables with [load-csvs.pq](load-csvs.pq). Create the `DataFolder` and `ModelFolder` parameters described at the top of the
   file, pointing at the `data` and `model` folders.
2. Create the relationships listed in [data-model.md](data-model.md) and mark `DimDate` as the date table.
3. Add the measures from [measures.dax](measures.dax) to an empty table named `_Measures`.
4. Compare resolution service level, MTTR and backlog for one month with
   [`reports/board-pack-2025-11.md`](../reports/board-pack-2025-11.md).
5. Build the pages from [report-layout.md](report-layout.md).
