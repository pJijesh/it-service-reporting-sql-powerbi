# Board and managing director reporting

The same data serves two readers with different questions. A single report for both usually serves neither.

## What each reader is deciding

| | Group board | Managing director |
| --- | --- | --- |
| Responsibility | The group's risk, spend and strategy | One company's operations and its people |
| Typical question | Is IT delivering, and do we need to act? | Is my company served well, and what do I tell my managers? |
| Time available | Minutes, and not every month | A monthly review |
| Needs | Outcome, trend, one reason, one decision | Outcome, site and category, open items that affect them |
| Wants less of | Mechanism, team detail, definitions | Other companies' detail, jargon |

## The board view

A board page answers four things. These are the figures in section 1 of the [board
pack](../reports/board-pack-2025-11.md).

1. **Outcome.** The headline service level, against target, with the previous month. Use a fixed set of six or
   fewer measures so that each month is comparable.
2. **Direction.** A twelve month line. The board cares more about drift than about a single month.
3. **Reason.** Two or three sentences of plain language: what changed and why. A figure without a reason makes
   directors guess.
4. **Decision.** What the board is asked to do, or the words "none this month". An item that needs no decision
   still has a reason to be there: it records that the board was told.

What to leave out of the board page: ticket counts by category, team workload, individual tickets and technical
terms. They are available on request. A board that has to read a detailed table to find the message will stop
reading the pack.

## The managing director view

A managing director needs to answer their own people. The layout in
[report-layout.md](../powerbi/report-layout.md) gives the company in context: its result, the group result beside
it, a split by site, the categories that cause tickets, and the open tickets still affecting them. Targets are shown
the same way for every company, so that a difference is a finding and not a different yardstick.

Open tickets matter more to this reader than to the board. A single unresolved P2 for a plant manager is the whole
service for that week, whatever the monthly percentage says.

## Rules both views share

- **One definition.** The same measure has the same meaning in every view. A target of 92% that means tickets
  opened in the month on the board page cannot mean tickets resolved in the month on another.
- **Counts beside percentages.** A percentage on a small number is noise. Show the number of tickets.
- **Words as well as colour.** Status is written ("Met", "Not met"), not only coloured, so that it survives black
  and white printing and colour vision differences.
- **Fixed timing.** Publish on the same working day each month, from a data extract with a stated time.
- **Honest ranges.** Say when the number is provisional, when a team was part staffed, or when a data problem
  affected the month.

## The commentary is the report

The tables can be generated. The reasoning cannot, and it is what the reader came for. In this repository the
commentary is a separate hand-written file, [`reports/commentary-2025-11.md`](../reports/commentary-2025-11.md),
merged into the generated pack by `reports/build_report.py`. A test checks that the figures it quotes agree with the
tables, so that the story and the numbers cannot drift apart.

## Cadence

Monthly for managing directors. Quarterly for the board, with a month by exception: a miss that the board should
not hear about first from someone else. Agree the exception rule in advance, for example "any month where P1
resolution or overall resolution is below target for the second month running."
