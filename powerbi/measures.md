# Measure reference

Every measure in [`measures.dax`](measures.dax), in the order they appear there. The names below match the
file exactly, and `tests/test_powerbi_spec.py` fails if a measure is missing from this page or from the file.

> **Not run in Power BI Desktop.** The measures follow documented DAX syntax. None has been evaluated by a DAX
> engine. The SQL views they mirror are tested; see [README.md](README.md) for what that does and does not prove.

## Conventions

- **Cohorts.** Service level and volume measures count a ticket in the month it was opened. Time to resolve,
  first time fix, reopening and satisfaction count it in the month it was resolved. Both cohorts match the SQL
  views, which is why Power BI and SQL should agree on the same data.
- **Ratios are ratios of sums.** Every percentage is `DIVIDE ( sum, sum )`. Averaging monthly percentages is wrong
  when months differ in size, so no measure does it. Totals, rolling windows and filtered views stay correct.
- **Blank, not zero.** `DIVIDE` returns blank when the denominator is zero, so empty months show as gaps
  rather than as 0% or 100%.
- **Month grain.** Prior month, rolling three months and period end measures read the last date in the filter
  context and work from its calendar month. Use them in visuals or slicers at month grain.
- **Format.** Set the format shown in the table when adding each measure.

## Volume

Cohort: Month opened (resolved count uses month resolved). SQL counterpart: `volume_trend`.

Tests: `tests/test_views_fixture.py`, `tests/test_views_generated.py` check the SQL counts. The DAX is a one-line COUNTROWS.

| Measure | Answers | Format |
| --- | --- | --- |
| `Tickets Opened` | how much demand arrived? Counts tickets of every type, by the date they were opened. | whole number |
| `Tickets Resolved` | how much work was finished? Counts tickets by the date they were resolved. Tickets with no resolution time are excluded by the is_open test. | whole number |
| `Tickets Opened Prior Month` | what was demand last month? Uses the calendar month before the last date in context. | whole number |
| `Tickets Opened MoM %` | is demand rising or falling against last month? Blank when there is no prior month. | 0.0% |
| `Tickets Opened Rolling 3M Average` | what is the underlying monthly demand once one-off months are smoothed out? Total opened in the three calendar months ending with the current month, divided by three. Blank until three months exist. | 0.0 |

## Service levels

Cohort: Month opened. SQL counterpart: `sla_compliance`, `sla_compliance_team`.

The SQL view is checked against hand worked fixture answers and an independent Python oracle. The DAX restates the same sums of flags and is not run.

| Measure | Answers | Format |
| --- | --- | --- |
| `Response Measured` | how many tickets have a response outcome? Counts incidents and service requests that were either answered, or are unanswered and already past target. Tickets still inside target are not counted. The flag is worked out in the SQL view fact_ticket. | whole number |
| `Response Met` | how many of those were answered within target? A response exactly on target counts as met. | whole number |
| `Response Met %` | what share of tickets got a response within target? This is the response service level. | 0.0% |
| `Resolution Measured` | how many tickets have a resolution outcome? Resolved tickets, plus open tickets already past target. Open tickets still inside target ("in flight") are left out until they have an outcome. | whole number |
| `Resolution Met` | how many of those were resolved within target? | whole number |
| `Resolution Met %` | what share of tickets were resolved within target? This is the headline service level. | 0.0% |
| `Resolution Missed` | how many tickets breached their resolution target? Useful as a count beside the percentage, because a small percentage move on a large volume is many tickets. | whole number |
| `Resolution In Flight` | how many tickets are still open and still inside target, so cannot be judged yet? Show this beside the percentage for the most recent month, where it is largest. | whole number |
| `P1 Resolution Met %` | how did the most serious incidents do? Resolution service level for P1 incidents only. The number of P1 tickets is small, so show the count (Resolution Measured) next to it. | 0.0% |
| `Resolution Met % Prior Month` | what was the resolution service level last month? Calendar month before the last date in context. | 0.0% |
| `Resolution Met % MoM Change (pts)` | did the service level improve or worsen since last month, in percentage points? Not a percentage change: 90% to 92% is +2.0 points. Blank if either month has no data. | +0.0;-0.0;0.0 |
| `Resolution Met % Rolling 3M` | what is the service level over the last three months, smoothing one-off dips? It adds up the counts for three calendar months and divides once. It is not the average of three monthly percentages. Blank until three months of data exist. | 0.0% |
| `Response Met % Prior Month` | what was the response service level last month? | 0.0% |
| `Response Met % MoM Change (pts)` | did response performance improve or worsen since last month, in percentage points? | +0.0;-0.0;0.0 |
| `Response Met % Rolling 3M` | what is the response service level over the last three months? Ratio of summed counts. | 0.0% |

## Targets and status

Cohort: Not applicable. SQL counterpart: Targets in `sla_targets.csv`.

The target lines are constants for the example. Replace them with agreed values, ideally from a table.

| Measure | Answers | Format |
| --- | --- | --- |
| `Resolution Target %` | what is the target line? A constant for reference lines and the status measure. The value is an example from this repository. In a real model, hold targets in a table so that the owner can change them without editing DAX. | 0% |
| `Response Target %` | what is the target line for response? Same caution as above. | 0% |
| `Resolution Status` | is the service level on target, in words? Text is used so that status does not depend on colour alone. "No data" when there are no measured tickets. | text |

## Time to resolve

Cohort: Month resolved. SQL counterpart: `mttr`, `mttr_percentiles`.

The SQL view is tested against a hand worked mean. The DAX divides the same totals and is not run.

| Measure | Answers | Format |
| --- | --- | --- |
| `Incidents Resolved` | how many incidents were finished? Counts resolved incidents with a valid timeline, by the date they were resolved. This is the denominator of MTTR. | whole number |
| `Resolution Clock Minutes of Resolved Incidents` | how much clock time did those incidents use in total? Sum of the resolution clock: elapsed minutes for P1, support-hours minutes for the rest. This is the numerator of MTTR. Kept as a measure so that the totals combine correctly across any filter. | whole number |
| `MTTR (hours)` | on average, how long did incidents take to resolve? Mean time to resolve in clock hours (support hours except P1). A mean is pulled up by a few very slow tickets, so read it with the median in the SQL view mttr_percentiles. | 0.0 |
| `MTTR (hours) Prior Month` | what was MTTR last month? | 0.0 |
| `MTTR (hours) MoM Change %` | did incidents take longer or shorter than last month, as a percentage? Positive means slower. | +0.0%;-0.0%;0.0% |
| `MTTR (hours) Rolling 3M` | what is MTTR over three months? Total clock minutes divided by total incidents across the window, not an average of monthly means. Blank until three months of data exist. | 0.0 |

## Backlog

Cohort: Point in time. SQL counterpart: `backlog_ageing`, `backlog_month_end`.

The SQL view is tested against hand counted month ends. The DAX uses COUNTROWS over a FILTER inside CALCULATE and is not run.

| Measure | Answers | Format |
| --- | --- | --- |
| `Open Tickets Now` | how many tickets are open at the extract time? Ignores the date selection, because a ticket opened in an earlier month is still open now. Backlog means not yet resolved. | whole number |
| `Open Over 30 Days` | how many open tickets are old? Open at the extract time and more than 30 days old (the "Over 30 days" bucket in the SQL view backlog_ageing). | whole number |
| `Open Past Target` | how many open tickets have already breached their resolution target? Problems and changes have no target, so they never appear here. | whole number |
| `Backlog at Period End` | how many tickets were open at the end of the month? A ticket is open at that moment if it was opened before it and not resolved before it. Uses the last date in context, so use it at month grain. DimDate is cleared inside CALCULATE so that tickets opened in earlier months are included. Other filters (company, team, type) still apply. | whole number |
| `Backlog at Prior Month End` | how many tickets were open at the end of the previous month? | whole number |
| `Backlog MoM Change` | is the backlog growing? Open tickets at this month end minus open tickets at the last month end. Positive means growth. Blank for the first month, where the prior position is not in the data. | +0;-0;0 |

## Quality

Cohort: Month resolved. SQL counterpart: `first_time_fix_rate`, `reopen_rate`, `csat_summary`.

The SQL views are tested. The DAX is not run.

| Measure | Answers | Format |
| --- | --- | --- |
| `Resolved Incidents and Requests` | how many tickets does each quality measure divide by? Resolved incidents and service requests with a valid timeline, by resolution date. Problems and changes are left out. | whole number |
| `Fixed at First Contact` | how many of those were resolved by first-line staff at the first interaction, with no hand-off? The flag comes from the ticketing tool, so its definition is the tool's. | whole number |
| `FTF %` | what share of resolved tickets were fixed at first contact? First time fix rate. | 0.0% |
| `Reopened Tickets` | how many resolved tickets came back? Counts the reopened flag on tickets resolved in the period. The latest month is provisional because recent tickets have had less time to be reopened. | whole number |
| `Reopen %` | how often is a fix not a fix? Share of resolved tickets that were reopened. | 0.0% |
| `CSAT Responses` | how many people answered the survey? COUNT ignores blanks, so tickets with no response are not counted. Always show this beside the score: a score from few responses is not a trend. | whole number |
| `CSAT Average` | how satisfied were the people who answered? Mean score from 1 to 5 across responses. | 0.00 |
| `CSAT Satisfied %` | what share of responses were positive? Responses scoring 4 or 5, divided by all responses. Often easier for a board to read than an average. | 0.0% |
| `CSAT Response Rate` | how representative is the score? Responses divided by resolved tickets. | 0.0% |

## Labels

Cohort: Not applicable. SQL counterpart: None.

Presentation only.

| Measure | Answers | Format |
| --- | --- | --- |
| `Selected Month Label` | which month is on the page? The single month selected in a slicer, or "All months". | text |
| `Report Title` | nothing by itself. Use it as a dynamic visual title so that the page names the month shown. | text |

