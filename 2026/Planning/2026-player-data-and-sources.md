# 2026 player data and source plan

## Design principle

Keep three concepts separate:

1. **Player quality**: projections, expert ranks, role, health, and uncertainty.
2. **Market availability**: exact-format ADP and the league's historical behavior.
3. **Draft decision value**: player quality adjusted for keepers, roster construction, pick gaps, positional scarcity, and opponent tendencies.

Combining all three into one unexplained rank would make the application harder to audit and easier to mislead.

## Canonical player record

| Group | Fields |
|---|---|
| Identity | player_id, canonical_name, aliases, position, NFL team, bye week, rookie flag |
| Source observation | source_id, source_version, source_player_name, retrieved_at, effective_at, scoring_format, league_size, roster_format |
| Ranking/market | overall_rank, position_rank, tier, ADP, ADP_low, ADP_high, sample_size |
| Projection | pass/rush/receiving projections, projected fantasy points, value over baseline |
| Team context | depth-chart slot, role, snap/target/carry expectation, competition, offensive environment |
| Health/news | status, injury, practice participation, report time, expected impact, source URL |
| Consensus | normalized rank score, normalized ADP score, projection score, source dispersion |
| Draft context | keeper status/cost, drafted status, manager, pick availability probability, position-run risk |
| Modifiers | league QB premium, roster need, tier cliff, replacement value, bye interaction, user adjustment |
| Confidence | provenance class, recency score, format-fit score, sample score, completeness score, conflict flag |

Source observations should be append-only snapshots.  The canonical player record is rebuilt from the latest valid observations so source corrections do not erase provenance.

## Source hierarchy

1. **League authority**: Yahoo settings, final 2026 draft order, keeper declarations, traded-pick board, and live draft state.
2. **Exact-format market data**: 10-team 2QB/non-PPR ADP.  Use this primarily to estimate availability, not player quality.
3. **Scoring-matched expert projections/rankings**: the Drive workbooks, FantasyGuru material, Draft Sharks, and other expert sources that clearly state format and update time.
4. **Broad consensus rankings**: useful for stabilizing an outlier expert view, but down-weighted when format fit is poor.
5. **Team/depth-chart context**: official transactions and injury reports first; current depth-chart and beat reporting second.
6. **Historical league behavior**: a modest contextual adjustment, never a substitute for current player data.

## Current Drive inventory

| File | File ID | Modified (UTC) | Initial assessment |
|---|---|---|---|
| Fantasy Guru 2QB-Superflex-Chart-2026 | 1MWb7IXa4gB3Li74w83wv9w-EhRLqkIokOzgLwQQaH8w | 2026-08-15 23:52 | Directly useful QB tiers and 2QB ADP |
| Jeff Mans Superflex Rankings | 1GFljIw0L3CVLVJ3OnBrLSb81drDoND9D4rgeeVPVozk | 2026-08-15 23:50 | Directly useful overall superflex ranking |
| DraftSheets_2026 | 1PBGqN-gs8w7nq2_LheYAytHoywH-6wwit_CNanHQvbg | 2026-08-15 23:21 | Scoring is configured correctly; requires reconciliation before ingest |

The DraftSheets workbook is set to 10 teams, two QBs, non-PPR, four-point passing touchdowns, and minus-one interceptions.  However, its visible DraftSheet contains player/team conflicts with the other two files (for example, Drake Maye and Jayden Daniels have swapped team/bye values, as do Jonathan Taylor and Christian McCaffrey).  The ingestion process must reject or quarantine inconsistent team/bye fields rather than silently accepting them.

## Current public-source assessment

- Fantasy Football Calculator exposes a current 10-team, 2QB JSON feed.  The Aug. 16 snapshot contains 224 players and is based on 3,993 drafts from July 17 through Aug. 16.  This is the best initial availability feed of the sources reviewed.
- FantasyPros Draft Wizard exposes a parseable 10-team, 2QB, standard mock-ADP table with average, high, low, standard deviation, and drafted percentage.
- Draft Sharks exposes only part of the table without an Insider login, and the public page does not expose player names reliably in its text representation.  It should be ingested through an authenticated browser session or an authorized export, not guessed from team logos and ranks.
- FantasyGuru premium rankings and articles can inform expert-quality and strategy components.  Store concise structured observations and citations for personal use; do not copy full paid articles into the project.

## Refresh and validation

- Discover the three Drive files by stable file ID, not only by title.
- Record Drive modified time and retrieval time on every import.
- Refresh source snapshots before the application starts; the live draft uses one frozen, validated snapshot so a source change cannot move the board mid-pick.
- Run another forced refresh shortly before the draft.
- Fail closed if a required tab/header disappears, player identifiers become ambiguous, duplicate files are found, or row counts change unexpectedly.
- Reconcile names through aliases, but never auto-merge ambiguous players.
- Compare team, position, and bye across sources.  Preserve conflicts and choose a canonical value only from a higher-authority current source.
- Store raw source observations separately from the composite.

## Composite method

Do not average raw ordinal ranks, ADP, and projected points together.  Normalize within source and position, then calculate separate components:

- expert-quality score;
- scoring-adjusted projection/value score;
- market-availability score;
- role/health risk score;
- league-context score.

Weights remain configurable and should not be finalized until the accessible sources pass validation.  The application should display the component scores, source count, last-updated time, and disagreement level alongside the composite.
