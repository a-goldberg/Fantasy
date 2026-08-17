# 2026 Draft Room

This is a dependency-free local draft assistant.  From the project root, run:

```sh
python3 2026/App/serve.py
```

Then open `http://127.0.0.1:8765`.

The page saves live draft picks in the browser, automatically places confirmed keeper Matthew Stafford at pick 64, and recalculates all three recommendation columns after every recorded pick.  Use **Undo** to reverse live entries.

**Refresh & Rebuild** refreshes public market/context sources, rebuilds all generated boards from the latest verified snapshots, and validates the result without clearing recorded picks or tuning settings.  It also refuses to install a refreshed board if an already drafted player can no longer be reconciled.

**Reset Draft** has a separate confirmation and clears recorded live picks only.  Confirmed keepers and tuning settings remain.  Connected Google Sheets cannot be authenticated by the local server, so Refresh & Rebuild reuses their latest imported snapshots and reports this limitation.

Before the real draft, refresh the data and rebuild the app payload:

```sh
python3 2026/Pipeline/refresh_public_adp.py
python3 2026/Pipeline/refresh_context_sources.py
python3 2026/Pipeline/parse_draftsheets.py
python3 2026/Pipeline/build_composite_board.py
python3 2026/Pipeline/build_app_data.py
```

The remaining league keeper list and any traded-pick changes belong in `2026/Config/current_draft.json`.  Contextual player and team observations belong in `2026/Config/context_adjustments.json`; unsourced narrative is intentionally ignored.
