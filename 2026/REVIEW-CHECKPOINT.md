# Fantasy Draft Manager — review checkpoint

Date: Aug. 16, 2026

## Completed

- Rebuilt the historical dataset from the corrected Google Sheet.
- Preserved the Danziger-to-Joshua transition without merging their records.
- Recomputed manager tendencies, QB scarcity, positional runs, and pick-slot anomalies.
- Recorded the 2026 order and Goldberg's expected snake picks.
- Inventoried the three new 2026 Drive workbooks.
- Defined the 2026 player/source schema, hierarchy, refresh rules, and validation gates.
- Prepared a provisional Herbert/Stafford keeper comparison.
- Added a safe DraftSheets parser that uses only displayed player names and values.
- Generated the first reproducible 272-player base composite from the Aug. 16 snapshots.
- Added refresh rules and explicit roster, bye-week, WR-depth, fourth-QB, and RB-handcuff policies.
- Verified authenticated FantasyGuru access and mapped the useful projection, outlook, analytics, coaching, rookie, injury, and handcuff resources.
- Added reproducible 10-team 2QB ADP ingestion for Fantasy Football Calculator and FantasyPros (454 provider-player rows in the current snapshot).
- Built a dependency-free, responsive draft-room application with optimized, consensus, and wildcard recommendation columns.
- Added live pick entry, undo, automatic Stafford reservation at pick 64, roster tracking, recalculation after every pick, player research cards, and 32 NFL team-sheet foundations.
- Separated market availability from player quality and capped sourced context adjustments; unsourced narrative has exactly zero ranking effect.
- Added a validation gate covering player-pool size, duplicate names, positions, ADP match rate, all 32 team sheets, Goldberg's snake picks, and the Stafford keeper slot.
- Added the reported 2026 pick swap: Barry owns Jeff's Round 12 selection (pick 116), and Jeff owns Barry's Round 17 selection (pick 168).  Live pick ownership now follows the trade map.
- Marked Matthew Stafford as Goldberg's confirmed Round 7 keeper at pick 64.
- Added current DraftSharks injury risk, 2026 rookie scores, Weeks 1–6 positional schedules, and the partial public Superflex composite as separately tunable inputs.
- Added current RotoWire and ESPN news snapshots plus all-team Ourlads offensive depth charts.  Unreviewed news remains zero-weight until its fantasy mechanism is verified.
- Split maintenance into **Refresh & Rebuild**, which preserves picks and tuning while refreshing and validating the board, and **Reset Draft**, which clears live selections only after confirmation and reapplies confirmed keepers.

## Superseded

Any prior manager-level analysis derived from the incorrectly renamed draft workbook is invalid.  Use the generated files under [Analysis](Analysis/) and the planning documents under [Planning](Planning/) instead.

## Waiting on user/external state

1. The league-wide keeper declarations.
2. Confirmation that the Barry/Jeff swap is the complete 2026 traded-pick list.
3. Confirmation that Stafford has been formally declared as Goldberg's seventh-round keeper.
4. Final keeper and traded-pick state before a live draft board is frozen.

Stafford is implemented as a clearly labeled working assumption.  No final draft simulation should be locked before items 1–3 are available.

## Current generated boards

- [DraftSheets name/value board](Analysis/generated/draftsheets_value_board.csv)
- [Base composite board](Analysis/generated/base_composite_board.csv)
- [Public 2QB ADP](Analysis/generated/public_2qb_adp.csv)
- [Draft-room application](App/index.html)
