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
- Do not recommend a fourth QB before Round 10 or before the roster has at least four RBs, five WRs, and one TE.  When eligible, show that fourth QB only as a wildcard.
- Never recommend a fifth QB.  This is a roster-eligibility rule, so the tuning controls cannot override it.
- Two premium QBs are not required.  If the room overpays for QBs, the board should surface the WR/RB value created by the run.

## Running-back contingencies

Drafting a handcuff without owning the starter is allowed.  The late-round target is one or two contingency players with a clear promotion path and meaningful upside.  This preference remains subordinate to QB minimums, WR depth, and bye coverage.

Beginning in Round 14, verified Ourlads backups to the two highest-ranked RBs and two highest-ranked QBs on Goldberg's roster receive a handcuff boost.  The boost grows through Round 17 and increases with the protected starter's DraftSharks injury-risk percentile.  A shared bye with the protected starter is expected for a handcuff and is not penalized, although conflicts with other same-position players still apply.

The handcuff signal cannot override the fourth- and fifth-QB rules.  The intended final-four-round mix is one kicker, one defense, and roughly two handcuff or attributable upside selections, in whichever order best fits the remaining board.  Missing data alone is never treated as sleeper evidence.

## Thin-data and Wildcard evidence

Missing or sparse rankings do not create sleeper value by themselves.  Expert-versus-market bonuses are confidence-weighted using both the number of baseline ranking sources and the agreement among public ADP sources.  A one-source expert gap cannot contribute more than five points.

Before Round 11, a player with fewer than two baseline ranking sources needs at least two independent upside signals, one of which must be trusted analyst context, approved news, or an additional ranking source.  Rounds 11–13 allow either trusted support or two structured signals.  In Rounds 14–17, one qualified rookie model, verified handcuff relationship, or other explicit signal may support an endgame Wildcard.  Personal Priority is an intentional user override at every stage.
