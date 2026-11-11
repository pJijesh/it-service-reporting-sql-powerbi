# Response targets and resolution targets

Most service level agreements set two targets per priority. They answer different questions and fail for
different reasons.

| | Response | Resolution |
| --- | --- | --- |
| Question | Did someone pick it up? | Did the problem go away? |
| Stops when | A person first replies or starts work | The ticket is marked resolved |
| What it protects | The requester's confidence that the ticket was received | The business outcome |
| Typical failure | Triage backlog, no one watching the queue, out-of-hours gaps | Capacity, skills, third party delays, wrong team |
| Gaming risk | An automatic reply that stops the clock | Resolving early and reopening later |

## Why both

A fast response with a slow resolution describes a service desk that is polite and unhelpful. A fast resolution
with a poor response describes one that goes quiet and then delivers. A single combined number hides which one
is happening, and the remedies differ: response problems are usually about queue handling and staffing at the
front, resolution problems about skills, escalation and dependencies.

## Rules that keep response honest

- Count a human reply or an assignment to a named person doing the work. Do not count an automatic
  acknowledgement.
- State the stop event in the data, because tools differ. In this repository the stop is the field
  `first_response_at`, set when a person first responds.
- Report response for every priority, not only the serious ones. Low priority tickets are where queues hide.

## Rules that keep resolution honest

- Stop at the first resolution, not at closure.
- Report reopening beside it (`Reopen %` in [measures.md](../powerbi/measures.md)). If resolution improves and
  reopening worsens, tickets are being closed to stop the clock.
- Show the count of tickets measured beside the percentage.

## Proportion between the two

In the example targets, response is a small fraction of resolution: 30 minutes against 480 for a P2 incident.
A response target close to the resolution target is almost meaningless, since by the time the response is
late the ticket is also nearly breached. A response target that is a tiny fraction of resolution protects the
requester against silence. Choose the response target first, as a statement of how long anyone should wait to be
told that someone is working on it, and then the resolution target, as a statement of the outcome.

## What the board pack does

The headline table in the board pack shows both: resolution within target and response within target. In November
2025 in the example data, both fell, resolution from 94.3% to 87.9% and response from 94.3% to 89.1%. The next
table breaks them down by priority, because a group figure can hide a poor result for a small and serious
population such as P1.
