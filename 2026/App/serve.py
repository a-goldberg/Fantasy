#!/usr/bin/env python3
"""Serve the draft room and expose one explicit local rebuild operation."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
sys.path.insert(0, str(ROOT / "2026" / "Pipeline"))
from player_names import normalize_player_name

LOCK = threading.Lock()
SCRIPTS = [
    ROOT / "2026" / "Pipeline" / "refresh_public_adp.py",
    ROOT / "2026" / "Pipeline" / "refresh_public_rankings.py",
    ROOT / "2026" / "Pipeline" / "refresh_context_sources.py",
    ROOT / "2026" / "Pipeline" / "parse_draftsheets.py",
    ROOT / "2026" / "Pipeline" / "test_composite_rank_normalization.py",
    ROOT / "2026" / "Pipeline" / "test_player_names.py",
    ROOT / "2026" / "Pipeline" / "build_composite_board.py",
    ROOT / "2026" / "Pipeline" / "classify_context.py",
    ROOT / "2026" / "Pipeline" / "build_app_data.py",
    ROOT / "2026" / "Pipeline" / "validate_draft_app.py",
]

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP), **kwargs)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/refresh-rebuild":
            self.send_json(404, {"error": "Unknown operation"})
            return
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            self.send_json(403, {"error": "Rebuild requests must come from the local draft room"})
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self.send_json(415, {"error": "Rebuild requests must use JSON"})
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 100_000)
            request_data = json.loads(self.rfile.read(length) or b"{}")
            drafted_players = request_data.get("drafted_players", [])
            if not isinstance(drafted_players, list) or not all(isinstance(name, str) for name in drafted_players):
                raise ValueError("drafted_players must be a list of names")
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
            return
        if not LOCK.acquire(blocking=False):
            self.send_json(409, {"error": "A rebuild is already running"})
            return
        try:
            board_path = ROOT / "2026" / "App" / "data" / "draft-board.json"
            previous_board = board_path.read_bytes() if board_path.exists() else None
            logs = []
            for script in SCRIPTS:
                completed = subprocess.run(
                    [sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, timeout=120
                )
                logs.append({"step": script.name, "status": completed.returncode, "output": completed.stdout[-1200:]})
                if completed.returncode:
                    if previous_board is not None:
                        board_path.write_bytes(previous_board)
                    self.send_json(500, {"error": f"{script.name} failed", "details": completed.stderr[-1200:], "steps": logs})
                    return
            refreshed_board = json.loads(board_path.read_text())
            refreshed_names = {normalize_player_name(player["player"]) for player in refreshed_board["players"]}
            missing = sorted(name for name in set(drafted_players) if normalize_player_name(name) not in refreshed_names)
            if missing:
                if previous_board is not None:
                    board_path.write_bytes(previous_board)
                self.send_json(409, {"error": f"Refreshed data could not reconcile recorded players: {', '.join(missing)}", "steps": logs})
                return
            context = json.loads((ROOT / "2026" / "Analysis" / "generated" / "current_context.json").read_text())
            self.send_json(200, {
                "ok": True,
                "steps": logs,
                "warnings": context.get("warnings", []) + [
                    "Connected Google Sheets use the latest locally imported snapshots; this local service cannot authenticate to Drive.",
                    "Authenticated FantasyGuru research uses the latest locally imported reviewed snapshot; refresh that source through an authenticated agent session before rebuilding when newer paid content is available.",
                ],
            })
        except subprocess.TimeoutExpired as error:
            if 'previous_board' in locals() and previous_board is not None:
                board_path.write_bytes(previous_board)
            self.send_json(504, {"error": f"{Path(error.cmd[-1]).name} timed out; the active draft was not changed"})
        except Exception as error:
            if 'previous_board' in locals() and previous_board is not None:
                board_path.write_bytes(previous_board)
            self.send_json(500, {"error": str(error)})
        finally:
            LOCK.release()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Draft room: http://127.0.0.1:8765")
    server.serve_forever()
