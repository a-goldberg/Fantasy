# Fantasy Draft Manager

Fantasy Draft Manager is a local draft-day decision system for Goldberg's 2026 fantasy football league. The project combines a consensus player board with league-specific draft history, two-QB scarcity, current roster construction, market availability, live positional runs, bye coverage, injuries, depth charts, schedule context, and reviewed qualitative research.

The goal is not to predict the season perfectly or automate the final pick. The goal is to make the best available evidence easy to use while preventing avoidable draft-day mistakes.

## 2026 league context

- 10 teams
- 17 rounds
- non-PPR scoring
- 2 starting QBs
- 2 starting RBs
- 3 starting WRs
- 1 starting TE
- 1 RB/WR/TE flex
- 6 bench spots
- keepers cost a pick three rounds earlier than the prior year
- undrafted keepers cost a sixth-round pick
- traded picks are allowed

The 2026 draft order is Ori, Tompkins, Greenspan, Goldberg, Jeff, Joshua, Big Leiber, Barry, Nalick, and Abe. Matthew Stafford is Goldberg's confirmed seventh-round keeper at overall pick 64. Barry owns Jeff's Round 12 pick, and Jeff owns Barry's Round 17 pick. Other managers' keeper declarations are still incomplete and remain a clearly labeled input gap.

## Draft-room interface

Start the local app from the repository root:

```sh
python3 2026/App/serve.py
```

Then open `http://127.0.0.1:8765`.

The page provides three recommendation columns:

1. **Optimized picks** account for player quality, the current roster, positional scarcity, likely availability, bye coverage, tier cliffs, live draft behavior, injuries, schedule, and reviewed context.
2. **Consensus picks** show the neutral expert-board alternatives.
3. **Wildcard picks** surface defensible upside and market gaps without bypassing hard roster rules.

Unknown market data is treated as unknown rather than as hidden value. Missing ADP contributes neither an availability estimate nor a market-gap bonus. Market-gap bonuses shrink when expert coverage is thin or ADP sources disagree, with a five-point cap for one-source expert rankings. Before Round 11, a thin-data player needs at least two independent upside signals, including trusted analyst or ranking support, to appear as a Wildcard. Structured-model-only speculation is reserved for the final four rounds, while Personal Priority remains a deliberate override. Low-confidence source coverage and buried skill-position depth roles also reduce Optimized and Wildcard scores.

The roster panel groups Goldberg's players by position with NFL team, bye week, keeper status, and same-position bye conflicts.

Live picks can be entered by player search. When a player is outside the local pool, **Other QB/RB/WR/TE/K/DST** placeholders advance the draft without incorrectly removing a known player. **Undo** remains visible. Personal Priorities, Tuning, Refresh & Rebuild, and Reset Draft are kept in the **Admin** menu to reduce accidental clicks.

**Personal priorities** is a separate subjective layer for players Goldberg wants to boost or fade despite the evidence-based ranking. A −10 to +10 preference changes Optimized and Wildcard scoring but leaves Consensus neutral. A **Do not recommend** setting is a hard exclusion from every recommendation column. These preferences are stored with the local app state and survive rankings rebuilds and draft resets until explicitly cleared.

See [the app guide](2026/App/README.md) for the complete workflow and control behavior.

## Recommendation policy

Eligibility is enforced separately from weighted scoring. Tuning cannot override these rules.

- Carry at least three QBs.
- Never recommend a fifth QB.
- Do not recommend a fourth QB before Round 10.
- A fourth QB requires at least four RBs, five WRs, and one TE, and may appear only as a wildcard.
- Preserve enough remaining picks to complete the required QB, RB, WR, TE, K, and DST roster.
- Do not recommend duplicate kickers or defenses.
- Do not recommend a third TE.
- Treat the first three QB bye weeks as a hard coverage concern.
- Protect the minimum WR depth needed for a league that starts three or four receivers every week.

The user has historically drafted WR poorly and wants meaningful WR depth plus late breakout candidates. The app therefore increases WR urgency when the roster is RB-heavy and has fewer than three receivers.

## Availability and in-draft trends

Two different systems cover two different questions:

- **Availability risk** uses public two-QB ADP and source spread to estimate whether a specific player will survive until Goldberg's next pick.
- **Draft-room trends** watches the six most recent completed picks. Three or more picks at the same position creates run pressure. The pressure is roster-aware, so a WR run matters much more when Goldberg has one WR than when he already has five.

League-history pressure remains a separate, lower-weight signal. Historical drafts are used for manager tendencies and league-specific scarcity, not as a claim that an opponent will repeat an exact pick.

## Late-round handcuffs

In Rounds 14–17, the app boosts verified Ourlads backups to Goldberg's two highest-ranked rostered RBs and two highest-ranked rostered QBs. The reminder grows later in the draft and receives an additional bump when the protected starter has a high injury-risk percentile. It remains subordinate to roster rules: a fourth QB is still late-Wildcard-only after core depth is complete, and a fifth QB is never eligible.

Kicker and defense become viable beginning in Round 14, with urgency rising through the final pick. Roster-feasibility gates preserve the required slots, leaving the other late selections available for handcuffs or explicitly sourced upside candidates rather than manufactured sleeper scores.

## Player data hierarchy

The base board uses weighted expert sources rather than an original projection model. Current source groups include:

- DraftSheets scoring values and positional tiers;
- Jeff Mans/FantasyGuru Superflex rankings;
- RotoBaller public Superflex expert rankings;
- FantasyGuru two-QB chart and QB tiers;
- public 10-team two-QB ADP from Fantasy Football Calculator and FantasyPros;
- partial public DraftSharks Superflex rankings;
- DraftSharks injury, rookie, and early-schedule models;
- RotoWire player news;
- ESPN NFL RSS;
- Ourlads offensive depth charts; and
- authenticated FantasyGuru coaching, personnel, offensive-line, player-outlook, and related draft research.

Overall expert ranks use a fixed 200-player scoring horizon. Rank No. 100 therefore contributes the same base value whether a source publishes 150 players or 400. Ranks beyond 200 contribute no additional base-quality credit, though kicker and defense needs can still surface those positions through the endgame roster policy. A longer list cannot make its middle ranks look artificially stronger.

Expert rankings and market ADP remain separate. RotoBaller is an expert-consensus input; its generic industry-average field is not treated as two-QB market ADP. The public FantasyPros Superflex ECR page currently exposes only a short public table, so it is not imported as a full-board source. DraftSharks market data will be added only when its league format and component provenance can be captured cleanly without double-counting a consensus and its underlying feeds.

Connected Google Sheets and authenticated browser sources must be imported through Codex. The local server cannot authenticate to Drive or paid sites itself.

DraftSheets names and displayed values remain the trusted ranking fields. Positional tiers are also trusted because the current tier cells use player-name-keyed `VLOOKUP` formulas. Team, bye, points, PS, and ECR fields from the displayed row remain excluded because the workbook's prior manual-sort behavior could detach those cells from the player name.

Ourlads roster identifiers are parsed separately from player names. Codes such as `CC/NYJ`, `U/SF`, draft rounds, and free-agent markers remain available as source metadata, but cannot enter cross-source name matching or UI labels. A single unambiguous Ourlads match can also restore a missing team, bye, schedule, and team-QB context.

Player identity uses a small explicit alias registry rather than fuzzy nickname matching. For example, `Kenny Gainwell` and `Kenneth Gainwell` resolve to one canonical identity while the UI retains the name used by the primary rankings sources. The same alias key is used by the composite, context classifier, app-data joins, validation, and active-draft rebuild reconciliation.

## Context and source quality

Qualitative findings require a source, mechanism, direction, confidence, retrieval date, and expiration. Adjustments are capped so one narrative cannot overpower the expert baseline.

- Concrete and current facts may be approved for a small scoring adjustment.
- Speculation, generic camp praise, unsupported narratives, and unresolved projections stay visible as research-only findings and score zero.
- DraftSharks injury, rookie, schedule, and Superflex models are scored separately and are not duplicated as qualitative adjustments.
- Newer findings can supersede older notes from the same source/entity/class.

Player cards distinguish the player's own DraftSheets tier from the quality of the passing environment. QBs show their FantasyGuru QB tier. RBs, WRs, and TEs show the current Ourlads starting QB and that QB's FantasyGuru tier when both sources can be reconciled.

## Injury and current availability

The DraftSharks Injury Predictor is a risk model, not an active/inactive feed. RotoWire provides current player news, ESPN provides general league headlines, and Ourlads supplies depth-chart/inactive context.

RotoWire refreshes retain the current page plus up to 21 dated local snapshots. This prevents an important update from disappearing as soon as it falls off the latest-news page.

Explicit season-long unavailability is handled as a hard, source-backed eligibility override rather than a modest injury penalty. Ricky Pearsall, Jayden Higgins, and Calvin Austin III are currently excluded from all recommendations and search results based on verified NFL.com reports that they will miss the 2026 season.

## Historical draft data

Historical results are normalized from explicit pick and round fields. Snake order is not inferred from manager order because the source contains keepers, traded picks, multiple manager picks within a round, and empty Yahoo artifacts.

The historical analysis supports:

- league positional timing;
- QB scarcity and run behavior;
- manager QB volume and first-QB timing;
- position preferences;
- keeper and traded-pick anomalies; and
- opponent demand between Goldberg's picks.

Historical results are descriptive evidence, not a deterministic opponent-prediction model.

## Refresh and rebuild

The Admin **Refresh & Rebuild** operation refreshes accessible public sources, merges rolling news history, rebuilds all generated boards, reclassifies context, and validates the result. Recorded picks, placeholders, keepers, tuning settings, and personal priorities are preserved.

A connected-data refresh is still required through Codex after DraftSheets, Drive rankings, or authenticated FantasyGuru sources change. Once those snapshots are local, the Admin rebuild incorporates them.

Manual pipeline sequence:

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
node 2026/Pipeline/test_recommendation_policy.js
```

## Repository map

- `2026/App/`: local draft-room UI and server
- `2026/App/data/draft-board.json`: generated runtime payload
- `2026/Analysis/source/`: dated source snapshots
- `2026/Analysis/generated/`: normalized boards, historical analysis, and classified context
- `2026/Config/current_draft.json`: draft order, keepers, traded picks, and unresolved inputs
- `2026/Config/draft_policy.json`: roster constructions and hard recommendation policy
- `2026/Config/composite_weights.json`: baseline expert-source weights
- `2026/Config/context_adjustments.json`: manually reviewed context rules and adjustments
- `2026/Pipeline/`: refresh, normalization, classification, build, and validation scripts
- `2026/Planning/`: league settings, decision policy, research plans, and review artifacts

## Current known gaps

- The 14 reported keeper declarations are loaded, including two managers who declared none. Future changes still need to be entered explicitly.
- Google Sheets and authenticated FantasyGuru content require an external connected-data refresh before the local rebuild.
- News feeds are not complete historical archives. Rolling local retention reduces that risk, while verified season-long availability overrides cover confirmed high-impact absences.
- Superflex sources are an approximation for this league's true two-QB plus three-WR structure, so roster policy and DraftSheets scoring remain important corrections.

## Future Enhancements

- Publish it as a self-hosted web app that I can access from anywhere
- Include API functionality so that picks can be made programmatically (as in an automated mock draft)
- Chron job or other scheduled task to automatically fetch news and other updates and rebuild recommendation metrics accordingly
- More admin tools, like edit team names, league/scoring settings, roster composition, etc.
- Multi-user accounts with authentication and server-side data store
- Choose from multiple trusted data sources or bring in your own, with configurable tuning for the influence of each
