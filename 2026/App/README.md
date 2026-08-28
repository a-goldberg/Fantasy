# 2026 Fantasy Draft Manager

This is a local, dependency-free draft assistant built for Goldberg's 10-team, two-QB, non-PPR league.  It combines expert rankings, two-QB market data, league history, roster construction, current draft behavior, injuries, schedule context, depth charts, and reviewed qualitative research.  It is decision support, not an automatic drafter.

## Start the draft room

From the project root, run:

```sh
python3 2026/App/serve.py
```

Then open `http://127.0.0.1:8765`.

Do not open `index.html` directly or use a static preview server.  Those approaches can display the interface, but they cannot handle the rebuild API.

## Draft-day workflow

The app records picks in browser storage and recalculates all recommendations after each entry.  All 14 reported league keepers are automatically placed at their confirmed round costs, including Matthew Stafford at pick 64.  The current draft order and the Barry/Jeff pick trade come from `2026/Config/current_draft.json`.

Use **Record another pick** to search for a player.  If someone selects a player outside the local pool, use **Other QB**, **Other RB**, **Other WR**, **Other TE**, **Other K**, or **Other DST**.  A placeholder advances the draft without falsely removing a known player.  If the placeholder belongs to Goldberg, its position still counts toward roster construction.

The roster panel groups Goldberg's players by position and shows NFL team, bye week, keeper cost, and same-position bye conflicts.  **Undo** reverses the latest live entry.

The header's **Your next pick** value shows Goldberg's upcoming selection while another manager is on the clock.  While Goldberg is currently picking, it advances to the following open Goldberg selection and skips any intervening keeper-occupied round.

## Local draft-state API

The local server also maintains a small, validated pick ledger at `2026/App/data/live-draft-state.json`.  It is loopback-only and is intended for this draft room, not for public deployment.  The browser syncs its recorded picks after each change, while an automation can reconcile a numbered mock-draft board without replaying every click.

- `GET /api/draft-state` returns the current ledger and configured keepers.
- `POST /api/draft-state/picks` atomically records the exact next open pick, canonicalizes the player, derives round and manager ownership, and rejects stale or out-of-sequence writes.
- `POST /api/draft-state/sync` accepts `{ expected_version, picks }` and rejects stale versions, duplicate pick numbers, duplicate players, malformed entries, and unknown players.
- `POST /api/draft-state/reconcile` merges a numbered source-board sequence, preserves matching keepers and existing picks, and stops on gaps or conflicts.
- `POST /api/draft-state/undo` removes only the latest non-keeper selection and requires the current version.
- `POST /api/draft-state/reset` requires the current version plus `{ "confirm": true }`.

The API does not contain a second recommendation engine.  The browser remains responsible for scoring and display; the API is the durable draft-entry boundary.  When served locally, the browser reads the API ledger on startup and uses API mutations for picks, undo, and reset.

### Future public-app direction

If this becomes a shared hosted app, retain the versioned event-ledger contract and replace the local JSON file with a database.  Add league and user identifiers, authentication, source-specific player aliases, and audit metadata before exposing it beyond the loopback server.  Keep paid-source credentials and refresh jobs separate from public draft-state endpoints.

## Recommendation columns

- **Optimized picks** combine marginal lineup value with roster need, the cost of waiting until the next pick, bye coverage, positional tier cliffs, current draft-room trends, league history, structured models, and reviewed context.
- **Consensus picks** stay close to the neutral expert board and market value, but discount players whose likely role is reserve depth.  Tuning controls do not change this column.
- **Wildcard picks** surface defensible upside and market gaps.  Hard roster rules still apply, so this column cannot recommend an otherwise prohibited fifth QB or an impossible roster construction.

Missing market data is neutral, not upside: it contributes no availability probability and no expert-versus-market gap.  Market-gap bonuses are reduced when the expert board has thin coverage or public ADP sources disagree, and a one-source expert gap is capped at five points.  Before Round 11, a player supported by fewer than two baseline ranking sources needs at least two independent upside signals, including approved analyst or ranking support, to enter Wildcards.  Rounds 11–13 loosen that requirement, while a qualified structured model alone is reserved for Rounds 14–17.  A Personal Priority boost remains a deliberate override.  Thin source coverage and buried RB/WR/TE depth-chart roles also receive small reliability adjustments in Optimized and Wildcard scoring.  Consensus remains the unmodified baseline comparison.

Overall rankings and supplemental position charts have different authority.  DraftSheets, Jeff Mans Superflex, or RotoBaller Superflex may establish a player's baseline quality.  The FantasyGuru QB chart can refine an already-ranked QB, but cannot create an overall composite rank by itself.  Supplemental-only players remain searchable with their chart context, but receive zero baseline-quality credit until an overall source ranks them.

Recommendation eligibility is separate from scoring.  Two QBs are the hard starter requirement; a third QB is a preferred end-state reserve, not a third starter.  Once three QBs are rostered, another QB is excluded until the late-draft fourth-QB conditions are satisfied.  A fourth QB may then appear only as a wildcard.  A fifth QB is never recommended.  The same feasibility gate prevents extra K/DST selections, prevents a third TE, and preserves enough remaining picks to complete the league's required roster.

Candidate quality is converted to marginal lineup value before ranking.  A player filling an open weekly starter receives full baseline credit, a likely flex receives partial credit, and reserve players receive only their expected-use share.  In particular, after Stafford and another starting QB are rostered, QB3 is valued as bye/injury depth.  The model also estimates the best same-position value likely to survive until Goldberg's next pick.  Urgency comes from the expected drop between now and then, so an early QB3 can still win when the tier loss truly justifies it, but it is not promoted simply because the final roster prefers three quarterbacks.

## Availability and live draft trends

These are separate signals:

- **Availability risk** estimates which same-position alternatives are likely to survive until Goldberg's next pick.  It uses public two-QB ADP and source spread to measure the cost of waiting, rather than awarding every likely-to-disappear player the same generic bonus.  The Availability tuning control changes this opportunity-cost influence.
- **Draft-room trends** watches the positions selected in the six most recent completed picks.  Three or more picks at one position creates run pressure.  The pressure is larger when Goldberg is still thin at that position, so the app can react to a WR run without blindly chasing every run.  The Draft-room trends tuning control changes this influence.
- **Roster need** handles Goldberg's own construction independently.  For example, a roster with four RBs and fewer than three WRs receives additional WR urgency because the league starts three receivers.

Candidate cards call out a detected run when it materially affects the optimized or wildcard score.

## Late-round handcuffs and endgame

Rounds 14–17 add a roster-specific handcuff signal for Goldberg's two highest-ranked rostered RBs and two highest-ranked rostered QBs.  RB relationships use the current FantasyGuru RB Handcuff Grid when available, with Ourlads as the fallback; QB relationships use Ourlads.  The boost grows as the draft closes and increases further when the rostered starter has a high DraftSharks injury-risk percentile.  A direct backup relationship can qualify an otherwise thin-data player for Wildcard consideration, and candidate cards identify the starter being protected.

Handcuff scoring does not bypass roster feasibility.  A fourth QB still requires the configured RB/WR/TE depth and can appear only as a late Wildcard; a fifth QB remains prohibited.  The shared bye with the protected starter is not treated as a bye-coverage mistake because the backup is an injury contingency, though conflicts with other same-position players still count.

Kicker and defense suppression now ends in Round 14.  Their urgency rises through Round 17, while the feasibility gate reserves enough remaining picks to fill both positions.  This supports an endgame of K, DST, and approximately two handcuff or sourced-upside selections without forcing a fixed order when clearly better value remains.

## Player and team research

Player research cards use directional colors: green supports the outlook, red weighs against it, and gray is neutral or informational.  Each scored structured input shows its current weighted effect.

Research cards include:

- composite rank and quality score;
- public two-QB ADP and cross-source disagreement;
- DraftSheets value rank and the player's own positional tier;
- the FantasyGuru QB tier for quarterbacks;
- the Ourlads starting quarterback and that quarterback's FantasyGuru tier for RBs, WRs, and TEs;
- injury probability and projected games missed;
- Weeks 1–6 positional strength of schedule;
- rookie-model and DraftSharks Superflex comparisons;
- depth-chart role;
- reviewed qualitative adjustments and research-only findings; and
- matching recent news with links.

DraftSheets positional tiers are safe to associate with names because the current tier cells use name-keyed `VLOOKUP` formulas.  Other workbook row fields remain excluded from the importer because the prior manual-sort problem could detach them from the displayed player name.

Team sheets combine player maps, early schedule data, Ourlads depth-chart markers, and reviewed FantasyGuru coaching, personnel, and offensive-line findings.  Player and team dialogs close with the close button or a click on the backdrop.

## Injury and availability sources

The injury/news layer is intentionally split by purpose:

- **DraftSharks Injury Predictor** supplies modeled injury probability and projected games missed.  This is a risk model, not a current active/inactive list.
- **RotoWire** supplies current player news.  Refreshes now merge the current page with up to 21 dated local snapshots so an important update does not disappear merely because it falls off the latest-news page.
- **ESPN NFL RSS** supplies broader league headlines.
- **Ourlads** supplies current offensive depth-chart and injured/inactive context.
- **Verified availability overrides** store explicit season-long statuses supported by an attributable source.  These are hard eligibility gates, not small ranking penalties.

Ourlads appends roster metadata such as `CC/NYJ`, `U/SF`, draft round, and free-agent codes to its displayed names.  The importer preserves that token as a separate source identifier, while all matching and UI labels use the cleaned player name.  When a ranked player lacks a team but has one unambiguous Ourlads depth-chart match, that team is used to restore bye, schedule, and team-QB context with explicit provenance.

Ricky Pearsall, Jayden Higgins, and Calvin Austin III are currently marked out for the 2026 season from verified NFL.com reports.  They remain in the research database for provenance, but they are excluded from search results and every recommendation column.  Trey Benson's current injured-reserve status is treated as a negative, expiring health signal rather than a season-long exclusion because the available report does not establish that timetable.

The previous rebuild missed Pearsall because the RotoWire importer retained only the most recent page of updates, while his season-ending news was already older.  The rolling snapshot retention and verified hard-status layer address the two distinct failure modes: disappearing news history and known season-long unavailability.

## Tuning and administration

**Undo** remains visible during the draft.  Less-frequent and higher-risk controls are under the **Admin** menu:

- **Personal priorities** provides a searchable list of the current player pool.  Give a player a subjective −10 to +10 fade/boost to change Optimized and Wildcard scoring, or mark **Do not recommend** to suppress him from all three recommendation columns.  Consensus ignores the numeric preference so it remains a neutral comparison.  Preferences apply immediately and persist through rebuilds and draft resets until cleared.
- **Tuning** changes optimized and wildcard weights only.  It cannot override hard roster or availability gates.
- **Refresh & Rebuild** refreshes accessible public sources, rebuilds the boards, and validates the result without clearing recorded picks, placeholders, or tuning settings.
- **Reset Draft** clears recorded live picks and placeholders after confirmation.  Confirmed keepers, tuning settings, and personal priorities remain.

Connected Google Sheets and authenticated FantasyGuru pages cannot be refreshed directly by the local server.  A local rebuild therefore uses the latest imported snapshots for those sources.  Request a connected-data refresh through Codex before rebuilding when DraftSheets, Drive rankings, or paid FantasyGuru content has changed.

## Data and scoring safeguards

- Base projections come from weighted expert inputs.  Context is deliberately capped so a single narrative cannot dominate the ranking.
- Explicit current availability or roster-role facts may receive a small, expiring qualitative adjustment.
- Speculation, generic camp praise, unsupported narratives, and signals already represented by a structured model remain visible for research but score zero.
- Season-long unavailability is a hard exclusion and requires a verified source.
- Missing data stays labeled as missing.  The pipeline does not infer a tier, injury, role, or team relationship that it cannot reconcile.
- Known cross-source name variants use explicit aliases across rankings, context, and rebuild reconciliation.  `Kenny Gainwell` and `Kenneth Gainwell` are one player; ambiguous nicknames are not fuzzy-merged.
- Missing ADP never becomes a synthetic late ADP, a made-up availability percentage, or a positive Wildcard market gap.
- Analyst sleeper recommendations should enter as attributable ranking or reviewed-context sources.  The app does not manufacture a sleeper score from missing information.
- Overall expert ranks are normalized against a fixed 200-player horizon.  Source list length does not change the value of a given absolute rank, and ranks beyond 200 add no base-quality credit.

## Manual rebuild sequence

The Admin rebuild performs the equivalent of:

```sh
python3 2026/Pipeline/refresh_public_adp.py
python3 2026/Pipeline/refresh_public_rankings.py
python3 2026/Pipeline/refresh_context_sources.py
python3 2026/Pipeline/parse_draftsheets.py
python3 2026/Pipeline/test_composite_rank_normalization.py
python3 2026/Pipeline/build_composite_board.py
python3 2026/Pipeline/classify_context.py
python3 2026/Pipeline/build_app_data.py
python3 2026/Pipeline/validate_draft_app.py
```

Recommendation-policy regressions can be run separately with:

```sh
node 2026/Pipeline/test_recommendation_policy.js
```

Future keeper changes and traded-pick changes belong in `2026/Config/current_draft.json`.  Manually reviewed player and team observations belong in `2026/Config/context_adjustments.json`.  Authenticated FantasyGuru research and connected spreadsheet imports are stored as dated source snapshots under `2026/Analysis/source/`.
