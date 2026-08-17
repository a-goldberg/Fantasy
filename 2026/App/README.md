# 2026 Draft Room

This is a dependency-free local draft assistant.  From the project root, run:

```sh
python3 -m http.server 8765 --directory 2026/App
```

Then open `http://127.0.0.1:8765`.

The page saves live draft picks in the browser, automatically reserves Matthew Stafford at pick 64 under the current working assumption, and recalculates all three recommendation columns after every recorded pick.  Use **Undo** to reverse live entries.  The app does not alter the generated source snapshot.

Before the real draft, refresh the data and rebuild the app payload:

```sh
python3 2026/Pipeline/refresh_public_adp.py
python3 2026/Pipeline/parse_draftsheets.py
python3 2026/Pipeline/build_composite_board.py
python3 2026/Pipeline/build_app_data.py
```

The final league keeper list and traded-pick map belong in `2026/Config/current_draft.json`.  Contextual player and team observations belong in `2026/Config/context_adjustments.json`; unsourced narrative is intentionally ignored.
