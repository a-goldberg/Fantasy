# NFL fantasy team one-sheet specification

Each team sheet is a decision aid, not a general season preview.  The current application generates all 32 shells and their ranked player maps.  Research notes are added only when sourced.

## At-a-glance fields

- Team, bye, offensive coordinator/play-caller, quarterback, and projected scoring environment.
- Draftable players by position, composite rank, market ADP, tier, and role.
- Expected 11/12/21 personnel usage when it materially affects routes, targets, or backfield roles.
- Offensive-line direction and the specific fantasy positions it affects.
- Open targets/carries, red-zone roles, and credible paths to a larger workload.
- Confirmed injuries and meaningful recovery or recurrence risk.
- Handcuff/contingency hierarchy and whether the reserve has standalone value.
- Coaching, scheme, quarterback, and major teammate changes.
- Confidence, recency, and a source link on every interpretive note.

## What stays out

- Defensive analysis that does not affect the offense or DST value.
- Generic team narratives, win-loss predictions, and camp praise without role evidence.
- Duplicated facts already reflected in the expert consensus unless they explain a disagreement.
- Long article summaries.  The sheet stores a concise decision implication and a link back to the source.

## Interface behavior

The draft card shows no more than two useful pros and two useful cons.  The modal shows the full player map, verified team context, and research links.  Missing research is labeled as missing; it is never filled with a guess.
