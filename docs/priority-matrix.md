# Priority matrix

Priority decides which targets apply to a ticket, so it decides how the service level is measured. It is worth
a short, written rule.

## The matrix in this repository

Priority follows from two judgements, impact and urgency, each on a three point scale. The matrix is in
[`data/priority_matrix.csv`](../data/priority_matrix.csv).

| | Urgency 1 (work stopped, no workaround) | Urgency 2 (work slowed) | Urgency 3 (can wait) |
| --- | --- | --- | --- |
| **Impact 1** (site wide or many users) | P1 Critical | P2 High | P3 Medium |
| **Impact 2** (a team) | P2 High | P3 Medium | P4 Low |
| **Impact 3** (one person) | P3 Medium | P4 Low | P4 Low |

The shape is a common one in IT service management. Two inputs are easier to judge consistently than one
overall priority, and the matrix makes the result repeatable. The values in the cells are a choice for each
organisation.

## Who decides

- **Impact** describes the business effect and is set from the facts: how many people, which service.
- **Urgency** describes how soon the effect must end. A requester may state it, and the service desk may
  adjust it with a reason.
- **Priority** is calculated, not typed. A priority that anyone can overwrite becomes the lever that people pull
  to get attention, and the service level for the highest priority then measures lobbying.

## Protecting the top priority

A short list of P1 criteria, agreed with the managing directors in advance, is more useful than any amount of
judgement at 2 a.m. Typical elements: a service that many sites depend on is down, there is a safety or legal
exposure, or revenue is stopping. When a P1 is declared, the priority also decides who is woken up, so
the measurement should follow the same rule as the escalation.

In the example data, P1 is the only priority with a 24 hour, 7 day clock. The target is four hours to resolve.
A P1 raised at 3 a.m. at a site with a support window of 08:00 to 18:00 therefore still counts against the
target, as it would in an agreement that includes out-of-hours cover.

## Service requests

Service requests (a new starter's laptop, an access request) are planned work and do not have an urgent end.
In the example targets they carry priorities P2 to P4 only. Incidents and requests share the matrix, but the
data does not create P1 requests, because an emergency is an incident.

## Checking the matrix

Two cheap checks belong in every report pipeline:

1. Every ticket's priority agrees with the matrix for its impact and urgency. The view
   `data_quality_checks` reports tickets that do not (see [ticket-data-quality.md](ticket-data-quality.md)).
2. The mix of priorities is plausible. A group where a third of tickets are P1 has a definition problem, and a
   group with none may have a reporting one. In the example data, P4 is the largest share of incidents, and P1 the
   smallest.

## Changing the matrix

Changing the cells changes history if old tickets are re-scored. Store the priority on the ticket when it is
set and keep the matrix version in the report notes. A recalculation should be a decision, announced in the pack,
not a quiet fix.
