# FantasyGuru research map

Authenticated access was verified in Chrome on Aug. 16, 2026.

## Highest-value feeds

| Resource | Use in the model |
|---|---|
| NFL offensive projections | Scoring-matched statistical projections and non-PPR points; page showed an Aug. 16 update |
| Jeff Mans superflex top 200 | Expert overall rank and positional scarcity view |
| 2QB/Superflex chart | QB tiers, pairings, and 2QB ADP |
| WR outlooks | Individual outlook tags and ten useful receiver tiers, including ceiling, rebound, surprise, bye-week, and stash profiles |
| RB/handcuff grid | Backfield order and contingency-upside tags |

## Contextual modifiers

| Resource | Structured signals to extract |
|---|---|
| Same Faces in New Places | New team, expected role change, opportunity gain/loss, uncertainty |
| Personnel Tendencies | 11/12/21 personnel rates and which WR/TE/RB roles benefit |
| Coaching System Breakdowns | Pace, pass/rush tendency, play-caller change, role concentration |
| Offensive Line Breakdown | Run blocking, pass protection, continuity, injuries |
| The Red Zone | High-value touch and target opportunity |
| Dynasty/rookie rankings | Rookie upside and long-term talent; low weight for immediate redraft value |
| NewsGuru and injury reporting | Current health, depth-chart, and role changes with timestamps |

## Two-QB strategy signals

The FantasyGuru strategy article recommends:

- targeting one top-10-to-12 quarterback as QB1;
- rostering three quarterbacks in true 2QB leagues;
- using different bye weeks for those quarterbacks;
- avoiding the assumption that two elite quarterbacks are necessary;
- exploiting RB/WR values when the room becomes overly aggressive at QB;
- remaining responsive to the actual draft room.

Those recommendations are treated as expert inputs, not absolute rules.  This league's corrected history remains the stronger source for when its own QB runs occur.

## Content handling

The application should store compact player tags, ranks, projections, source dates, and article URLs.  It should not reproduce full paid articles.  A refresh re-extracts the current structured observations from the authenticated session and preserves the previous snapshot for comparison.
