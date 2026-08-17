# Refresh workflow

## Normal refresh

1. Read the latest values from the three stable Drive file IDs.
2. Save dated raw snapshots without overwriting the previous ones.
3. Rebuild the DraftSheets name/value board.
4. Rebuild the base composite.
5. Refresh public 10-team 2QB ADP.
6. If the authenticated FantasyGuru session is available, refresh projections, rankings, injuries, outlook tags, handcuffs, and contextual signals.
7. Validate player-name joins, positions, teams, byes, row counts, source dates, and conflicts.
8. Publish a new board only if validation passes.

## Draft-session refresh

Run one mandatory full refresh immediately before the draft operation begins.  Freeze the resulting source version for the session.  Live recommendations then recalculate after every pick from the frozen player board plus:

- players drafted or kept;
- current team construction;
- bye coverage;
- positional tier cliffs and runs;
- estimated availability before Goldberg's next selection;
- remaining managers' historical tendencies.

Breaking injury or role news can trigger a manual source refresh, but normal pick processing does not repeatedly re-ingest every file.

## Failure behavior

- Keep the last valid snapshot when a source cannot be reached.
- Label its age and reduce its confidence.
- Do not publish a newly merged board when player identity, position, or row validation fails.
- Do not infer values for missing players or silently repair ambiguous names.
