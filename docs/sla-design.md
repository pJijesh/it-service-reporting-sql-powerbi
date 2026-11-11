# Designing a service level

A service level is a promise with a measurement attached. It is useful only if the promise is clear to the
people who receive it, the measurement is the same every month, and a missed month leads to a decision.

## The parts of a definition

Every target in [`data/sla_targets.csv`](../data/sla_targets.csv) has the same parts, and a target that lacks one
of them cannot be measured consistently.

| Part | Question | Example in this repository |
| --- | --- | --- |
| Scope | Which tickets does it cover? | Incidents and service requests. Problems and changes are managed with other measures. |
| Priority | Does the target depend on how serious the ticket is? | Four priorities, P1 to P4. See [priority-matrix.md](priority-matrix.md). |
| Start | When does the clock start? | When the ticket is logged. |
| Stop | When does it stop? | Response: first reply by a person. Resolution: the first time the ticket is marked resolved. |
| Clock | Which minutes count? | P1 counts every minute. Other priorities count minutes inside the site's support hours. |
| Target | How long is allowed? | For example P2 incident: 30 minutes to respond, 480 support minutes to resolve. |
| Attainment | What share of tickets must meet it, over what period? | 92% of tickets opened in a calendar month, in the example report. |
| Exclusions | What pauses or removes a ticket? | Stated rules only. This repository applies none, which is a limitation. |

## Decisions that change the result

**The clock.** Counting every minute is simple to explain and unfair to a ticket raised on Friday evening.
Counting only support hours is fairer and needs a calendar for each site, with holidays and daylight saving
changes. The generated data includes sites in three time zones, so the pipeline has to do this properly: see
[`sql/views/01_fact_ticket.sql`](../sql/views/01_fact_ticket.sql). The cost is explanation. Say which clock a
number uses wherever it appears, because 8 support hours and 8 elapsed hours are different promises.

**Resolved or closed.** Measure resolution at the moment the fix is offered, not at closure. Closure often
happens automatically some days later, and a measure that stops at closure rewards slow closing rules.

**The cohort.** A month's service level can describe tickets opened in the month or tickets resolved in the month.
Opened cohorts make the month's promise testable against the demand that arrived. Resolved cohorts reflect the
work done, and suit speed and quality measures. This repository uses opened for service levels and resolved for
time to resolve, first time fix, reopening and satisfaction, and states which at every use.

**Open tickets already late.** A ticket that is still open and past its target has already failed. Leaving it out
until it is resolved flatters the month. Counting it as a breach straight away is more honest. A ticket still open
and inside its target has no outcome yet and is shown as in flight.

**Ratios of sums.** Combine months and teams by adding the numerators and denominators, then dividing. Averaging
the monthly percentages weights a quiet month the same as a peak.

## Setting the level

- Start from what the business needs, ask what an hour of delay costs, and work back. A target that nobody
  asked for is a number to defend, not a service to deliver.
- Check it against capacity. The example teams are small (between two and four full-time equivalents), and a
  target that needs permanent spare capacity is a target that will fail in a bad month.
- Set attainment below 100%. A 100% target makes every late ticket a failure and teaches people to stop
  reporting honestly. A target near 90 to 95% leaves room for the unusual ticket.
- Agree the definition in writing before the first report, not after the first miss.
- Review yearly, and record when a target changed. A past month is judged against the targets in force then, which
  is why the fact table stores the target on each ticket.

## When the target is missed

A report that shows red without a cause invites blame. Each missed month in the board pack carries a short
explanation, the actions, and a decision requested or "none". The example commentary in
[`reports/commentary-2025-11.md`](../reports/commentary-2025-11.md) shows the form. The facts and figures in it
are fictional.
