# Translating the views to SQL Server (T-SQL)

> **Not executed here.** The views in this repository were written for SQLite and tested only on SQLite
> (see [`sql/views`](views)). No SQL Server, Azure SQL or Fabric instance was available. This note explains
> what has to change and why, based on Microsoft documentation for each function, but none of the T-SQL
> below has been run. Treat it as a checklist for a developer, and test every view against your own data.

Function behaviour was checked against Microsoft Learn on 2026-11-11. Where a page did not state something
(for example, CTEs inside views), the note below says so.

## 1. Differences that affect every view

| Topic | SQLite (as written) | SQL Server (T-SQL) |
| --- | --- | --- |
| Timestamp type | UTC text, `YYYY-MM-DD HH:MM:SS` | `datetime2(0)`. Compare and subtract as dates, not text. |
| Elapsed seconds | `strftime('%s', x)` gives epoch seconds | `DATEDIFF(SECOND, start, end)`. It returns `int` and fails for gaps over about 68 years, so use `DATEDIFF_BIG` only if your data could reach that. |
| Integer division | `/` on two integers truncates | The same: Microsoft documents that integer divided by integer truncates. Use `1.0 *` to force decimals, as the views already do. |
| Two-argument `MIN(a, b)` and `MAX(a, b)` | Scalar functions | Not available. Use `LEAST` and `GREATEST` (SQL Server 2022 and later, Azure SQL), or a `CASE` expression on older versions. |
| `AVG` of an integer | Returns a decimal | Returns `int` and truncates. Write `AVG(1.0 * x)`. The `top_categories` view already does. |
| Month text from a timestamp | `substr(x, 1, 7)` | `CONVERT(char(7), x, 120)`. Style 120 is `yyyy-MM-dd HH:mm:ss`, so the first seven characters are the month. `FORMAT(x, 'yyyy-MM')` also works but is slower. |
| Add one month | `datetime(d, '+1 month')` | `DATEADD(MONTH, 1, d)`. At month ends the result is clamped to the last day of the target month. |
| `GROUP BY` an alias | Allowed in SQLite | Not allowed. The views group by real columns or by columns of a CTE, so this is already safe. |
| `CREATE VIEW` | Any place in a script | Must be the first statement in a batch. Separate views with `GO`. |
| `ORDER BY` inside a view | Allowed | Not allowed without `TOP` or `OFFSET`. The views only use `ORDER BY` inside window functions, which is allowed. Sort in the query that reads the view. |
| Reserved or risky column names | `date`, `year`, `month` are fine | Wrap in square brackets, for example `[date]`, `[month]`, to be safe. |
| Collation | Text comparison is case-sensitive by default | SQL Server defaults are usually case-insensitive. Category names that differ only by case would merge. |
| Schema prefix | None | Use `dbo.` (or your schema) on every table and view name. |
| Flags | `INTEGER` 0 or 1 | `bit` or `tinyint`. If you use `bit`, cast to `int` before `SUM`. |

## 2. Data types for `schema.sql`

| Column kind | SQLite | Suggested T-SQL |
| --- | --- | --- |
| IDs and codes | `TEXT` | `varchar(20)` |
| Names, categories | `TEXT` | `nvarchar(100)` |
| Whole numbers, flags | `INTEGER` | `int`, `smallint` or `bit` |
| Full time (FTE) | `REAL` | `decimal(4,1)` |
| Timestamps (UTC) | `TEXT` | `datetime2(0)` |
| Calendar dates | `TEXT` | `date` |

`PRAGMA foreign_keys` has no equivalent: SQL Server enforces declared foreign keys. `CHECK` constraints,
`PRIMARY KEY` and `CREATE INDEX` translate directly. Load order matters because of foreign keys, so keep the
order used in `sql/loader.py`.

## 3. View by view

### `fact_ticket`

The only view with real rewriting. Everything else reads from it.

- Replace the `strftime('%s', ...)` arithmetic with `DATEDIFF(SECOND, ...)`.
- Replace two-argument `MIN` and `MAX` in the support-hours subquery. A version that works on every supported
  release uses `CASE`:

```sql
-- Not executed here. Support minutes between opened_at and response_clock_end.
COALESCE((
    SELECT SUM(DATEDIFF(SECOND,
               CASE WHEN w.open_utc  > b.opened_at         THEN w.open_utc  ELSE b.opened_at         END,
               CASE WHEN w.close_utc < b.response_clock_end THEN w.close_utc ELSE b.response_clock_end END))
    FROM dbo.support_windows AS w
    WHERE w.calendar_code = b.calendar_code
      AND w.close_utc > b.opened_at
      AND w.open_utc  < b.response_clock_end
), 0) / 60 AS response_support_minutes
```

  On SQL Server 2022 or later you can write `LEAST(w.close_utc, b.response_clock_end)` and
  `GREATEST(w.open_utc, b.opened_at)` instead. Microsoft documents that these ignore NULL arguments when at
  least one argument is not NULL, which does not matter here because neither argument can be NULL.
- `CASE`, `COALESCE` with three arguments, `CROSS JOIN` and `LEFT JOIN` are unchanged.
- `substr(opened_at, 1, 7)` becomes `CONVERT(char(7), opened_at, 120)`.
- Every CTE in the view is standard T-SQL. Microsoft's `CREATE VIEW` page shows a leading `WITH` clause only
  in the Azure Synapse and Fabric syntax, so on SQL Server and Azure SQL confirm that your version accepts a
  CTE in a view. If it does not, move the CTE chain into inline table-valued functions or nested subqueries.
- The correlated subquery in the select list is supported. If performance matters at scale, rewrite it as an
  `OUTER APPLY` and add an index on `support_windows (calendar_code, close_utc)` (already in `schema.sql`).

### `sla_compliance` and `sla_compliance_team`

Unchanged apart from schema prefixes and bracketing `[month]`. `ROUND`, `NULLIF`, `SUM(CASE ...)` and
`GROUP BY` all behave the same. Percentages use `100.0 *`, so there is no integer truncation.

### `backlog_ageing`

Unchanged. The bucket labels are computed in a CTE and the outer query groups by those columns, which avoids
the alias restriction.

### `backlog_month_end`

Replace `datetime(month_start, '+1 month')` with `DATEADD(MONTH, 1, month_start)`. The join condition compares
timestamps, so with `datetime2` columns it works as written. Alternatively derive the month list from
`EOMONTH` if you do not keep a date dimension.

### `mttr` and `mttr_percentiles`

`mttr` is unchanged. `mttr_percentiles` uses `ROW_NUMBER()` and `COUNT(*) OVER`, both available in SQL Server.
SQL Server also has `PERCENTILE_CONT` and `PERCENTILE_DISC`, used with `OVER (PARTITION BY ...)`. Microsoft
documents `PERCENTILE_DISC` as returning the smallest value in the group whose cumulative distribution is at
least the requested percentile, which is the same idea as the nearest-rank method used here. Microsoft also
notes that the aggregate form without `OVER` is not supported on SQL Server, so use the window form.
`PERCENTILE_CONT` interpolates and can return a value that no ticket had. Keep the method the same in every
tool, or the SQL and Power BI numbers will differ.

### `first_time_fix_rate`, `reopen_rate`, `csat_summary`

Unchanged. They use `COUNT`, `SUM`, `ROUND` and `NULLIF`. In `csat_summary`, `COUNT(f.csat)` counts non-NULL
values in both systems.

### `volume_trend` and `volume_by_weekday`

`LAG(x) OVER (PARTITION BY ... ORDER BY ...)` is the same syntax. Microsoft documents that `LAG` returns NULL
when there is no previous row and no default is supplied, which is what the view relies on. In
`volume_by_weekday`, replace `substr(t.opened_at, 1, 10)` with `CAST(t.opened_at AS date)` and join on
`[date]`.

### `top_categories`

`RANK()` and `SUM(...) OVER (PARTITION BY ...)` are unchanged. The `1.0 *` inside `AVG` is required in T-SQL.

### `team_load`

`CROSS JOIN` of months and teams, and the four `LEFT JOIN`s, are unchanged. `fte` must be a decimal type so
that `assigned_tickets / fte` is not an integer division.

### `data_quality_checks`

Unchanged. The `UNION ALL` takes its column names from the first `SELECT`.

## 4. Building the support windows in SQL Server

`support_windows` is a table, not a calculation, so the views never need time zone logic. This repository
builds the rows in Python. In SQL Server you could build them with `AT TIME ZONE`, which Microsoft documents
for SQL Server 2016 and later. Time zone names come from `sys.time_zone_info` (Windows names such as
`GMT Standard Time` for the United Kingdom, not IANA names such as `Europe/London`), so check the names exist
on your server before relying on them. Convert the opening time on each local date to UTC, one row per working
day and calendar, and exclude your own holiday list.

## 5. Suggested test plan on SQL Server

1. Load the CSV files in `data/` with `bcp`, `BULK INSERT` or your ETL tool into tables with the types above.
2. Create the views in order, comparing each against the SQLite result for the same month.
3. Reproduce the checks in `tests/test_views_fixture.py`: load `fixture_builder.TICKETS` and compare to the hand
   worked answers in that file. Those answers are independent of any database.
4. Compare `sla_compliance` row counts and sums with the SQLite output for the full data set.
