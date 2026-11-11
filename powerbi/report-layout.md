# Report layout specification

A design for a Power BI report built on the model in [data-model.md](data-model.md) with the measures in
[measures.md](measures.md). It is a specification, not a finished file: no `.pbix` is included and the report has
not been built in Power BI Desktop. The numbers quoted in the examples come from the committed board pack for
November 2025 ([`reports/board-pack-2025-11.md`](../reports/board-pack-2025-11.md)), which is generated from the
SQL views on fictional data.

## Who reads it, and what each needs

| Reader | Question | Needs | Does not need |
| --- | --- | --- | --- |
| Group board | Is IT delivering the service we pay for, and is anything getting worse? | One page. Three or four numbers against target, a trend, one or two sentences of explanation. | Ticket counts by category, team workload, definitions of every measure. |
| Managing director of a company | How is my company served, and what do my people experience? | Their company against the group, by site, with the open tickets that affect them. | Other companies in detail, unless the group shares them. |
| Head of IT and service managers | Where is the problem, which team, which category, what do we do on Monday? | Drill down to team, category, priority and individual tickets. | Executive summaries. |

The pages below run from the board view to the operating view. The first page is the only one the board needs.

## Global settings

- **Month slicer.** One slicer on `DimDate[year_month]`, single select, synced across all pages. Default to the latest
  complete month. A page that reads "this month" must say which month: bind a title to `Report Title`.
- **Company and site slicers** on `DimSite`. On the board page, hide them so the board view is always the whole group.
- **Fixed definitions.** Every percentage on every page uses the measures in [measures.md](measures.md). Do not drag
  a column into a visual and let Power BI summarise it, because averaging a flag column is not the same as a
  ratio of sums.
- **Colour.** Do not rely on colour alone to show status. Each status card pairs the colour with a word from
  `Resolution Status` and a sign on the change measure. Use a palette that is distinguishable with colour vision
  deficiency, and test the report in greyscale.
- **Visual interactions.** Turn cross-filtering off between the trend chart and the headline cards, so a click on a
  month changes the detail and not the headline.
- **Alt text** on every visual, and a sensible tab order.

## Page 1: Executive summary (board)

Purpose: answer "is the service healthy" in under a minute.

| Visual | Fields | Notes |
| --- | --- | --- |
| Title | `Report Title` | Names the month. |
| Card: resolution service level | `Resolution Met %`, `Resolution Met % MoM Change (pts)` | Reference value `Resolution Target %`. Add `Resolution Status` as text beside it. |
| Card: P1 resolution | `P1 Resolution Met %` | A single number for the incidents the board would hear about anyway. |
| Card: backlog | `Backlog at Period End`, `Backlog MoM Change` | |
| Card: satisfaction | `CSAT Average`, `CSAT Response Rate` | Show the response rate next to the score so a high score from few responses is visible. |
| Line chart, 12 months | x `DimDate[year_month]`, y `Resolution Met %`, line `Resolution Target %` | The shape of the year in one picture. |
| Text box | Written commentary | Two or three sentences by the IT leader: what changed, why, what is being done. A number without a reason is not a report. |

What the board should not see on this page: ticket volume, MTTR, category lists, team names. They invite questions
about the mechanism before the outcome is understood. They are on later pages for anyone who asks.

## Page 2: Service levels

Purpose: where the service level is won or lost.

| Visual | Fields |
| --- | --- |
| Clustered column: response and resolution by month | `Response Met %`, `Resolution Met %` by `DimDate[year_month]` |
| Matrix: company by priority | rows `DimSite[company_name]`, columns `DimPriority[priority]`, values `Resolution Met %`, `Resolution Measured` |
| Bar: team | `DimTeam[team_name]` by `Resolution Met %`, with `Resolution Target %` line |
| Table: breach counts | `Resolution Missed`, `Resolution In Flight` by team |
| Slicers | Ticket type, priority |

Always show the count beside the percentage (`Resolution Measured`). A 50% result on four tickets and on four hundred
tickets are different findings.

In the example data this page is where the November 2025 dip shows: one team (business applications) falls to
61.5%, against 92.7% the month before, while the other teams stay close to normal. A group average alone hides that.

## Page 3: Backlog and ageing

Purpose: how much is waiting, and how old.

| Visual | Fields |
| --- | --- |
| Column by month end | `Backlog at Period End` by month |
| Cards | `Open Tickets Now`, `Open Over 30 Days`, `Open Past Target` |
| Stacked bar: age bands by team | Age band columns from the `backlog_ageing` logic. In Power BI add a calculated column on `FactTicket` for the band, or load the view. |
| Table: oldest open tickets | `ticket_id`, `category`, `priority`, `assignee_team`, `open_age_days` sorted by age |

`Open Tickets Now` ignores the month slicer by design: it is the position at the extract time.

## Page 4: Demand

Purpose: what people ask for, and when.

| Visual | Fields |
| --- | --- |
| Column: tickets opened per month | `Tickets Opened` with `Tickets Opened Rolling 3M Average` as a line |
| Column: by weekday | `DimDate[day_name]` sorted by `day_of_week` |
| Bar: top categories | `FactTicket[category]` by `Tickets Opened` |
| Table: month on month | `Tickets Opened`, `Tickets Opened Prior Month`, `Tickets Opened MoM %` |

Use this page to explain volume driven dips. Peaks at month end and on Mondays are visible in the generated data
and are the reason resolution targets are best read over a month, not a day.

## Page 5: Quality

Purpose: is the fix a fix, and do people notice.

| Visual | Fields |
| --- | --- |
| Line: first time fix | `FTF %` by month |
| Line: reopen | `Reopen %` by month |
| Column: satisfaction | `CSAT Average`, `CSAT Satisfied %` by month |
| Card | `CSAT Response Rate` |
| Table | Category by `FTF %`, `Reopen %`, `Resolved Incidents and Requests` |

First time fix and reopening are reported together on purpose. A team can raise one by hurting the other: closing
tickets quickly to improve resolution time will raise reopening.

## Page 6: Time to resolve

Purpose: the operating view of speed, for service managers.

| Visual | Fields |
| --- | --- |
| Line: MTTR | `MTTR (hours)` by month, with `MTTR (hours) Rolling 3M` |
| Card | `MTTR (hours) MoM Change %` |
| Table by priority | `MTTR (hours)`, `Incidents Resolved` |

The mean hides long tails. The SQL view `mttr_percentiles` gives the median and 90th percentile. Power BI can
show the same with a calculated measure, but none is written here, so for the tail use the SQL output or
add a measure and test it.

## Page 7: Definitions and data quality

Purpose: so that a reader can trust, and challenge, the numbers.

- A text page listing each headline measure in one sentence, which cohort it uses and which clock it uses.
- A card for the count of tickets excluded for a failed timeline check (`timeline_ok = 0`). The SQL view
  `data_quality_checks` lists the checks.
- The extract time (`extract_info.csv`) and the report version.

See [`docs/ticket-data-quality.md`](../docs/ticket-data-quality.md) for the data problems that make this page
necessary.

## Managing director view versus board view

| Aspect | Board | Managing director |
| --- | --- | --- |
| Scope | Whole group | One company, against the group |
| Pages | 1, optionally 2 | 1 to 5 |
| Depth | Outcome and trend | Outcome, site and category |
| Language | Service, risk, money | Service and what users felt |
| Cadence | Quarterly pack, month by exception | Monthly |
| Targets | Shown, with RAG as words | Shown, with the contract wording |

## Row-level security (optional)

To let each managing director see only their own company, define a role in Power BI Desktop that filters
`DimSite[company_name]`, and add users to the role in the Power BI service. Points to check before relying on this,
which come from Microsoft's documentation of row-level security and were not tested here:

- Roles restrict data for people with the Viewer role in a workspace. People with higher roles, including those who
  can edit, see all rows.
- A role filter applies to the table it is defined on and flows to related tables along the relationships.
  Microsoft's page for `USERELATIONSHIP` says the function cannot be used when row-level security is defined on
  the table in which the measure is included, and gives an error as the result. The role here is defined on
  `DimSite`, not on the date or measures tables, but the resolved-date measures use `USERELATIONSHIP`, so test
  them with the role applied before relying on it. [data-model.md](data-model.md) describes the fallback.
- The group-level page 1 would show the filtered company only. If the group view must remain visible to the
  managing directors, publish it as a separate report.

## Build order

1. Load the tables with [`load-csvs.pq`](load-csvs.pq) and set the relationships in
   [data-model.md](data-model.md).
2. Create `_Measures` and add the measures from [`measures.dax`](measures.dax).
3. Check three numbers against the SQL output: resolution service level, MTTR and backlog for one month. The
   committed board pack gives the expected values.
4. Build page 1, then the others.
5. Review with one managing director as a reader, and cut anything they did not use.
