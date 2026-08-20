# Refresh workflow

## Normal refresh

1. Read the latest values from the three stable Drive file IDs.
2. Save dated raw snapshots without overwriting the previous ones.
3. Rebuild the DraftSheets name/value board.
4. Rebuild the base composite.
5. Refresh public 10-team 2QB ADP.
6. Refresh DraftSharks injury, rookie, Weeks 1–6 schedule, and visible Superflex data.
7. Refresh current RotoWire/ESPN news and Ourlads depth charts.
8. If the authenticated FantasyGuru session is available, refresh the dated qualitative tracks.  The current implemented tracks are targeted player/personnel findings, all 32 coaching-system breakdowns, and all 32 offensive-line breakdowns.  Newer track-specific findings supersede older selective notes from the same article/entity/class.
9. Classify refreshed context into approved, candidate, research-only, and rejected findings.  Apply only explicit, current facts that pass the confidence, expiration, deduplication, and adjustment-cap gates.
10. Validate player-name joins, positions, teams, byes, row counts, source dates, signal eligibility, and conflicts.
11. Publish a new board only if validation passes.

The application’s **Refresh & Rebuild** button performs steps 3–7 and 9–11 through the local service while preserving recorded picks and tuning settings.  It refuses to install a refreshed board when an already drafted player cannot be reconciled.  It cannot authenticate to Google Drive or premium browser sessions, so it reuses their latest imported snapshots and reports that limitation.

**Reset Draft** is a separate confirmed action.  It clears recorded live selections, preserves tuning settings, and reapplies every confirmed keeper from the current configuration.

## Draft-session refresh

Run one mandatory full refresh immediately before the draft operation begins.  Freeze the resulting source version for the session.  Live recommendations then recalculate after every pick from the frozen player board plus:

- players drafted or kept;
- current team construction;
- bye coverage;
- positional tier cliffs and runs;
- estimated availability before Goldberg's next selection;
- remaining managers' historical tendencies.
- bounded injury risk, rookie upside, early schedule, and corroborating composite modifiers.

Breaking injury or role news can trigger a manual source refresh, but normal pick processing does not repeatedly re-ingest every file.

## Failure behavior

- Keep the last valid snapshot when a source cannot be reached.
- Label its age and reduce its confidence.
- Do not publish a newly merged board when player identity, position, or row validation fails.
- Do not infer values for missing players or silently repair ambiguous names.
- Treat a preseason rest report as neutral, not as an injury downgrade.  For repeated reports about the same player/injury, retain the newest explicit availability direction rather than stacking daily blurbs.
