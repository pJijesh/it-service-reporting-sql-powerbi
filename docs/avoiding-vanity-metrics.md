# Avoiding vanity metrics

A vanity metric is a number that looks like performance and cannot lead to a decision. Service desk tools produce
many of them, because they are easy to count.

## Common ones, and what to use instead

| Number | Why it misleads | Better |
| --- | --- | --- |
| Tickets closed | Rises when work is split, auto-closed or closed prematurely. Says nothing about whether problems were fixed. | Resolution within target, with reopening beside it. |
| Total tickets opened | Is a measure of demand and population, not performance. A rise can mean a release, a new site or better reporting. | Tickets opened per head, with the reason for movements, read as demand. |
| Average response time | A few very fast automatic replies hide slow human ones. A mean hides the tail. | Response within target, and the 90th percentile of resolution. |
| Average resolution time alone | A mean is pulled by a few very long tickets and ignores the priority mix. | Mean and median together, by priority (`mttr` and `mttr_percentiles`). |
| Uptime of one system | Ignores the experience of the people who could not work for a measured but "allowed" outage. | Business hours availability, and P1 count and duration. |
| Satisfaction score alone | Rises when only happy people answer. | Score with the response rate beside it. |
| Percent of tickets resolved | Ignores when. A ticket solved after a month counts the same as one solved in an hour. | Resolution within target. |
| Number of knowledge base entries | Counts effort. | Share of tickets resolved at first contact, and reopen rate. |

## Tests for a good measure

1. **Decision.** Name the decision someone would take if the number moved. No decision, no measure.
2. **Gaming.** Ask how a team would raise it cheaply, and whether that helps the business. If not, pair it with
   a counter measure. Resolution within target pairs with reopen rate. First contact fix pairs with
   satisfaction.
3. **Denominator.** Is the count of things measured shown? A percentage with a small denominator is not a finding.
4. **Stability.** Does the definition stay the same month to month, and is a change announced?
5. **Reader.** Can the person it is for explain it back to a colleague in one sentence?

## Pairs used in this repository

| Measure | Counter measure |
| --- | --- |
| Resolution within target | Reopened after resolution |
| First time fix rate | Customer satisfaction |
| Satisfaction average | Survey response rate |
| Tickets opened | Backlog at month end |
| Mean time to resolve | Median and 90th percentile |

## Averages and percentages

Two rules prevent most arithmetic errors in reports.

- Combine percentages by adding counts and dividing again. A three month service level is the sum of met tickets
  divided by the sum of measured tickets, not the average of three percentages.
- Do not average a mean. The mean of monthly mean resolution times is not the mean of the tickets.

Both are applied in the SQL views and the DAX measures, and the fixture tests check them against hand worked
values.

## Context a number needs

Every figure in a pack should be able to answer: against what (target or last period), out of how many (the
count), over which tickets (cohort and clock), and why it moved. The example pack follows that order in each
section.
