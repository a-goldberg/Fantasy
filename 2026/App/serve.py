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
LIVE_STATE = APP / "data" / "live-draft-state.json"
sys.path.insert(0, str(ROOT / "2026" / "Pipeline"))
from player_names import normalize_player_name

LOCK = threading.Lock()


class DraftConflict(ValueError):
    """The requested mutation is valid JSON but conflicts with current state."""
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

    def read_json_request(self) -> dict:
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("Requests must use JSON")
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 250_000:
            raise ValueError("Request body must be between 1 and 250000 bytes")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Request body must be an object")
        return value

    def local_origin(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin in {"http://127.0.0.1:8765", "http://localhost:8765"}

    def draft_config(self) -> dict:
        return json.loads((ROOT / "2026" / "Config" / "current_draft.json").read_text())

    def board_players(self) -> dict[str, dict]:
        board = json.loads((APP / "data" / "draft-board.json").read_text())
        return {normalize_player_name(item["player"]): item for item in board["players"]}

    def owner_at(self, overall: int) -> str:
        config = self.draft_config()
        trade = next((item for item in config.get("traded_picks", []) if item["overall_pick"] == overall), None)
        if trade:
            return trade["new_manager"]
        order = config["draft_order"]
        round_number = (overall - 1) // len(order) + 1
        slot = (overall - 1) % len(order)
        return order[slot] if round_number % 2 else list(reversed(order))[slot]

    @staticmethod
    def next_open_overall(picks: list[dict]) -> int:
        occupied = {pick["overall"] for pick in picks}
        return next((overall for overall in range(1, 171) if overall not in occupied), 171)

    def canonical_pick(self, request: dict, overall: int | None = None) -> dict:
        pick_overall = overall if overall is not None else request.get("overall")
        if not isinstance(pick_overall, int) or not 1 <= pick_overall <= 170:
            raise ValueError("overall must be an integer from 1 to 170")
        pick_type = request.get("type", "live")
        if pick_type not in {"live", "placeholder"}:
            raise ValueError("type must be live or placeholder")
        player = request.get("player")
        if not isinstance(player, str) or not player.strip():
            raise ValueError("player must be a non-empty string")
        position = request.get("position")
        if pick_type == "placeholder":
            if position not in {"QB", "RB", "WR", "TE", "K", "DST"}:
                raise ValueError("A placeholder needs a valid position")
            canonical_name = f"Other {position}"
        else:
            match = self.board_players().get(normalize_player_name(player))
            if not match:
                raise ValueError(f"Unknown player: {player}")
            canonical_name = match["player"]
            position = match.get("position")
        return {
            "overall": pick_overall,
            "round": (pick_overall - 1) // 10 + 1,
            "manager": self.owner_at(pick_overall),
            "player": canonical_name,
            "position": position,
            "type": pick_type,
            "source": request.get("source", "api"),
        }

    def live_state(self) -> dict:
        keepers = [
            {"overall": item["overall_pick"], "round": item["round"], "manager": item["manager"], "player": item["player"], "type": "keeper", "status": item.get("status")}
            for item in self.draft_config()["keepers"]
        ]
        if not LIVE_STATE.exists():
            state = {"version": 0, "picks": keepers, "history": []}
            state["picks"].sort(key=lambda pick: pick["overall"])
            state["current_overall"] = self.next_open_overall(state["picks"])
            return state
        saved = json.loads(LIVE_STATE.read_text())
        saved["picks"] = [pick for pick in saved.get("picks", []) if pick.get("type") != "keeper"] + keepers
        saved["picks"].sort(key=lambda pick: pick["overall"])
        saved["current_overall"] = self.next_open_overall(saved["picks"])
        return saved

    def save_live_state(self, value: dict) -> None:
        LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = LIVE_STATE.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        temporary.replace(LIVE_STATE)

    def validate_picks(self, picks: list[dict]) -> None:
        seen_overall, seen_players = set(), set()
        known = set(self.board_players())
        for pick in picks:
            if not isinstance(pick, dict) or not isinstance(pick.get("overall"), int) or not 1 <= pick["overall"] <= 170:
                raise ValueError("Every pick needs an overall number from 1 to 170")
            if pick["overall"] in seen_overall: raise ValueError("A pick number may be recorded only once")
            seen_overall.add(pick["overall"])
            if not isinstance(pick.get("player"), str) or not pick["player"].strip(): raise ValueError("Every pick needs a player name")
            if pick.get("type") != "placeholder":
                key = normalize_player_name(pick["player"])
                if key not in known: raise ValueError(f"Unknown player: {pick['player']}")
                if key in seen_players: raise ValueError("A player may be recorded only once")
                seen_players.add(key)

    def do_GET(self):
        if self.path == "/api/draft-state":
            self.send_json(200, self.live_state())
            return
        super().do_GET()

    def do_POST(self):
        if self.path in {"/api/draft-state/sync", "/api/draft-state/reconcile", "/api/draft-state/picks", "/api/draft-state/undo", "/api/draft-state/reset"}:
            if not self.local_origin(): self.send_json(403, {"error": "Draft state requests must come from the local draft room"}); return
            try:
                request = self.read_json_request()
                with LOCK:
                    current = self.live_state()
                    if self.path == "/api/draft-state/reset":
                        if request.get("expected_version") != current.get("version", 0):
                            raise DraftConflict("Draft state changed; reload before writing")
                        if request.get("confirm") is not True: raise ValueError("Reset requires confirm: true")
                        current = {"version": current.get("version", 0) + 1, "picks": [], "history": []}
                    elif self.path == "/api/draft-state/undo":
                        if request.get("expected_version") != current.get("version", 0):
                            raise DraftConflict("Draft state changed; reload before writing")
                        live = [p for p in current["picks"] if p.get("type") != "keeper"]
                        if live: current["picks"].remove(max(live, key=lambda item: item["overall"]))
                        current["version"] = current.get("version", 0) + 1
                    elif self.path == "/api/draft-state/picks":
                        if request.get("expected_version") != current.get("version", 0):
                            raise DraftConflict("Draft state changed; reload before writing")
                        expected = self.next_open_overall(current["picks"])
                        if request.get("overall") != expected:
                            raise DraftConflict(f"Expected overall pick {expected}")
                        current["picks"].append(self.canonical_pick(request))
                        current["version"] = current.get("version", 0) + 1
                    elif self.path == "/api/draft-state/reconcile":
                        if request.get("expected_version") != current.get("version", 0):
                            raise DraftConflict("Draft state changed; reload before writing")
                        incoming = request.get("picks")
                        if not isinstance(incoming, list):
                            raise ValueError("picks must be a list")
                        for item in sorted(incoming, key=lambda value: value.get("overall", 0)):
                            canonical = self.canonical_pick(item)
                            existing = next((pick for pick in current["picks"] if pick["overall"] == canonical["overall"]), None)
                            if existing:
                                if normalize_player_name(existing["player"]) != normalize_player_name(canonical["player"]):
                                    raise DraftConflict(f"Pick {canonical['overall']} conflicts with {existing['player']}")
                                continue
                            expected = self.next_open_overall(current["picks"])
                            if canonical["overall"] != expected:
                                raise DraftConflict(f"Expected overall pick {expected}, received {canonical['overall']}")
                            current["picks"].append(canonical)
                        current["version"] = current.get("version", 0) + 1
                    else:
                        picks = request.get("picks")
                        if not isinstance(picks, list): raise ValueError("picks must be a list")
                        if request.get("expected_version") != current.get("version", 0): raise DraftConflict("Draft state changed; reload before writing")
                        self.validate_picks(picks)
                        current = {"version": current.get("version", 0) + 1, "picks": picks, "history": []}
                    self.validate_picks(current["picks"])
                    self.save_live_state(current)
                    self.send_json(200, self.live_state())
            except DraftConflict as error:
                self.send_json(409, {"error": str(error), "state": self.live_state()})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
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
