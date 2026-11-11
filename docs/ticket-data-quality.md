# Ticket data quality

Service reports are built from data entered by people under pressure. The measures are only as good as the
fields beneath them. This note lists the usual problems, and shows what this pipeline does about each.

## What goes wrong

| Problem | Effect on the report | What the pipeline does |
| --- | --- | --- |
| Timestamps out of order, for example resolved before opened | Negative durations, impossible results | `timeline_ok` is 0 on the ticket. It stays in the volume counts and is not measured against a target. The view `data_quality_checks` counts them. |
| Resolved with no first response recorded | Response cannot be judged | Reported by `data_quality_checks`. The resolution time is used as the response time, so a response is never counted later than the fix. This is generous to the team, which is why the count is shown. |
| Time zones mixed or local time stored as if UTC | Targets are met or missed by hours, near midnight and at daylight saving changes | All timestamps are UTC in the files. The support window for each site is converted to UTC by the generator, including the daylight saving rules for each time zone. |
| Priority changed after the fact, or not matching the matrix | Wrong target applied | `data_quality_checks` lists tickets whose priority does not match impact and urgency. |
| Duplicate ticket references | Double counting | The loader rejects the file and names the line of the duplicate. |
| Unknown site, team or company | Results fall out of the breakdowns | The loader rejects references to a site, company or team that does not exist, with the line. |
| Reopened ticket logged as a new ticket | Reopening is understated, volume overstated | Not detectable in this data. See Limitations in the [README](../README.md). |
| Tickets closed in bulk | Closure dates cluster, and measures that use closure are meaningless | Measures stop at resolution, not closure. |
| Resolved flag set on an open ticket | Satisfaction and first contact figures counted for tickets that are not finished | `data_quality_checks` reports first contact, reopened and satisfaction values on unresolved tickets. |
| Timestamps in the future | Extract problem, or a clock error | Reported as "timestamp after the extract time". |
| Blank category or free text categories | Category tables are unusable | The loader rejects blank categories. Free text is not detected, so keep the category list controlled in the tool. |
| Changes in how fields are used between months | A trend that is really a process change | Keep a note of process changes beside the trend. |

## Two kinds of check

**Hard checks** stop the load: a wrong number of columns, a value that is not a whole number or a timestamp,
a reference to something that does not exist, a duplicate key. The loader reports every problem with its file
and line, not only the first, and writes nothing to the database until the input is clean. The exit status is 2
so that a scheduled job fails loudly.

**Soft checks** are counted and printed but do not stop the load, because real extracts have some bad rows and
the report must still be produced. The counts appear in `data_quality_checks`, which the definitions page of the
report design is meant to show (see [report-layout.md](../powerbi/report-layout.md)).

Hard checks are for data that cannot be loaded. Soft checks are for data that can be loaded and should be
questioned. A good pack says how many tickets were affected, so that readers can judge for themselves.

## Source habits that help

- Make the fields that drive measures mandatory or automatic: priority from the matrix, timestamps from the tool,
  not typed.
- Do not allow a ticket to be resolved without a response being recorded.
- Keep one time zone in the extract and say which.
- Record when a ticket is paused, and why, if pauses are allowed. This pipeline has no pause concept, which is a
  limitation.
- Run the checks every month and keep the results. A rising count is an early warning that process has drifted.

## The data here

The data is generated, and the generator does not produce bad rows by default, so `data_quality_checks` shows
zeros for the committed files. The tests build bad inputs deliberately to prove the checks fire (see
`tests/test_loader.py` and `tests/test_views_fixture.py`).
