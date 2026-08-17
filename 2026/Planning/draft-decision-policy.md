# Draft decision policy

## DraftSheets handling

The workbook will not be sorted or repaired in place.  On refresh, the pipeline reads only the displayed **NAME** and **VALUE** cells for QB, RB, WR, and TE.  It pairs each name with the value shown beside it, sorts those pairs by value within position, and ignores the detached team, bye, points, tier, PS, and ECR fields.

Team, bye, position, and current role must come from reconciled external sources.  This prevents the workbook's independent column sorting from contaminating the player record.

## Refresh behavior

- A refresh can be requested manually at any time.
- During active preseason work, use no more than one normal refresh per day.
- Force a complete refresh before opening a real draft session.
- Freeze that source snapshot during the draft.  Do not re-ingest before every pick unless requested or major breaking news makes the snapshot unsafe.
- Every recommendation displays the source time and flags stale or conflicting data.

## Roster construction

Three default 17-player shapes are supported:

- 3 QB, 5 RB, 6 WR, 1 TE, 1 K, 1 DST.
- 4 QB, 5 RB, 5 WR, 1 TE, 1 K, 1 DST.
- 3 QB, 5 RB, 5 WR, 2 TE, 1 K, 1 DST.

The six-WR construction is the default because the league starts three WRs and can start a fourth in the flex.  The four-QB construction is available when a speculative quarterback has real starting upside, but it cannot eliminate the fifth WR or required bye coverage.

## Bye-week controls

Bye checks operate on positional coverage, not merely total players sharing a week.

- The first three quarterbacks must have three different bye weeks.
- A completed roster must still field two QBs, two RBs, three WRs, and one TE during every bye week.
- Same-bye exposure receives an increasing penalty before it becomes a hard coverage failure.
- K and DST byes do not influence early draft recommendations.

## Wide receiver correction

- Prefer at least one WR by the end of round 4 and three by the end of round 8, while allowing exceptional values to override those checkpoints.
- Finish with at least five WRs; six is preferred in the three-QB build.
- Reserve one or two late WR selections for breakout profiles rather than low-ceiling veteran depth.
- Use FantasyGuru's WR outlook tiers, personnel tendencies, coaching changes, role/target opportunity, and expert-versus-market gaps to identify breakouts.

## Quarterbacks

- Three is the minimum, with distinct bye weeks.
- The target is one top-12-caliber QB, one reliable QB2, and one playable QB3.
- A fourth QB should be a rookie, an uncertain current starter, or a backup with a credible path to starts.  It should not simply be a fourth low-ceiling veteran.
- Two premium QBs are not required.  If the room overpays for QBs, the board should surface the WR/RB value created by the run.

## Running-back contingencies

Drafting a handcuff without owning the starter is allowed.  The late-round target is one or two contingency backs with a clear promotion path and meaningful upside.  This preference remains subordinate to QB minimums, WR depth, and bye coverage.
