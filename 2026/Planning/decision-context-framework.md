# Decision context and intangibles framework

## Purpose

Context may move a player within a tier or break a close decision.  It should not overpower multiple current expert rankings unless the underlying change is concrete, material, and well supported.

## Signal test

A note can affect the optimized score only when it has all of the following:

- a player or team it clearly applies to;
- a dated source link;
- a signal class (role, health, environment, scheme, or development);
- a direction and bounded adjustment;
- confidence of at least 0.60;
- a short explanation of the fantasy mechanism, not merely the event.

Narrative-only notes remain visible for research if useful, but their ranking adjustment is zero.  Examples include generic coach praise, an isolated practice highlight, or “best shape of his life” reporting without evidence of a changed role.

## Guardrails

- One context item may move the score by no more than four points.
- All context combined may move the score by no more than eight points.
- Correlated reports about the same event count as one signal, not several.
- Injury effects distinguish confirmed availability, workload limitation, recurrence risk, and speculation.
- A coaching or scheme change needs a plausible volume, efficiency, personnel, or scoring-path effect.
- Old reports expire or receive a recency penalty.  A newer official depth-chart, transaction, or injury report supersedes older commentary.
- Conflicts are shown rather than silently averaged away.

## Source-quality order

1. Official transactions, injury reports, and direct team announcements.
2. Current projections, depth charts, and well-sourced reporting from established fantasy or NFL analysts.
3. Multiple credible beat reports that agree on a role change.
4. A single attributed beat report.
5. Unattributed aggregation, social chatter, and narrative claims (display-only or ignored).

The empty adjustment arrays in `Config/context_adjustments.json` are intentional.  They prevent the interface from manufacturing persuasive-sounding pros and cons before the research is actually captured.
