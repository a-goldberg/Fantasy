# Context classification pipeline

`Pipeline/classify_context.py` converts the current research snapshot into `Analysis/generated/classified_context.json`.  It is deliberately conservative: a source being credible does not make every inference drawn from it credible.

## Status meanings

- `approved`: A reviewed adjustment passes the configured threshold, or an attributed RotoWire report states a concrete, non-speculative participation, absence, release, or won-job event at confidence 0.70 or higher.  It is eligible for the qualitative score until it expires.  Automatically approved news expires after 21 days and is capped at 1.5 points (availability signals at 1 point).
- `candidate`: The source supports a factual availability, role, newcomer, or depth-chart observation.  It is visible and auditable, but is not automatically a qualitative ranking adjustment.
- `research_only`: Potentially useful context that lacks sufficient certainty or direction.  Its capped adjustment is always zero.

## Source rules

- DraftSharks injury risk, rookie model, early schedule, and Superflex composite remain structured model inputs.  This pipeline counts them for its audit summary but does not create duplicate qualitative signals.
- A RotoWire item is classified only when its text explicitly supports a practice/availability direction or a concrete roster-role event.  Concrete, attributed, non-hedged reports may be approved under the narrow threshold above.  Hedged status reports remain candidates.  Repeated same-player, same-status reports on the same date are collapsed to the newest item.  Speculative committee projections and workload predictions remain research-only, while generic practice praise and highlights are rejected from classification.
- Ourlads markers are limited to fantasy positions, the first two listed depth spots, and players on the current draft board.  They record the listed fact with zero directional adjustment because a depth-chart marker does not establish performance, injury severity, or workload.
- ESPN headlines stay in the discovery feed.  They are rejected from automatic classification until a human reviews the article and records a supported mechanism.
- The latest authenticated FantasyGuru qualitative snapshot is imported as human-reviewed expert context.  Every finding must include a source link, explicit mechanism, direction, confidence, and expiration, and this adapter caps a single adjustment at 1.5 points.  Unmatched players and malformed findings are rejected.  These findings are separate from FantasyGuru rankings and projections already represented in the consensus board.

## Adding a reviewed adjustment

Add an object to `player_adjustments` or `team_adjustments` in `Config/context_adjustments.json`.  Required fields are `entity` (or `player`/`team`), `summary`, `mechanism`, `signal_class`, `source_name`, `source_url`, `published_at`, `confidence`, and `adjustment`.  Team entries should include `affected_positions`.  Optional fields include `expires_at`, `evidence_type`, and `status`.

The classifier enforces the configured per-signal cap, turns below-threshold or non-approved manual entries into zero-point research notes, sorts output deterministically, rejects duplicate signals, and validates the complete signal contract on every run.  Use:

```sh
python3 2026/Pipeline/classify_context.py
python3 2026/Pipeline/classify_context.py --validate-only
```

The classifier does not claim that a factual candidate should change a ranking.  A later review or explicit recommendation-engine policy must decide which candidate classes qualify, while still respecting the total-context cap.
