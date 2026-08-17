#!/usr/bin/env python3
"""Fail-fast checks for the generated draft assistant payload and static app."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "App" / "data" / "draft-board.json"


def owner_at(overall, order):
    round_number = (overall - 1) // len(order) + 1
    slot = (overall - 1) % len(order)
    return order[slot] if round_number % 2 else list(reversed(order))[slot]


def main():
    payload = json.loads(DATA.read_text())
    players = payload["players"]
    names = [player["player"] for player in players]
    assert len(players) >= 250, "Player pool unexpectedly small"
    assert len(names) == len(set(names)), "Duplicate canonical player names"
    assert len(payload["teams"]) == 32, "Expected 32 NFL team sheets"
    assert all(player["position"] in {"QB", "RB", "WR", "TE", "K", "DST"} for player in players)
    assert not any(player["position_conflict"] for player in players), "Unresolved position conflict"
    assert sum(player["adp"] is not None for player in players) >= 220, "Public ADP match rate regressed"

    order = payload["draft"]["draft_order"]
    goldberg_picks = [pick for pick in range(1, 171) if owner_at(pick, order) == "Goldberg"]
    assert goldberg_picks == [4,17,24,37,44,57,64,77,84,97,104,117,124,137,144,157,164]
    stafford = next(player for player in players if player["player"] == "Matthew Stafford")
    keeper = payload["draft"]["keepers"][0]
    assert keeper["player"] == "Matthew Stafford" and keeper["overall_pick"] == 64
    assert stafford["position"] == "QB"

    positions = Counter(player["position"] for player in players)
    print(json.dumps({
        "players": len(players),
        "adp_matches": sum(player["adp"] is not None for player in players),
        "teams": len(payload["teams"]),
        "positions": positions,
        "goldberg_picks": goldberg_picks,
        "keeper_assumption": f"{keeper['player']} at {keeper['overall_pick']}",
        "status": "PASS"
    }, indent=2, default=dict))


if __name__ == "__main__":
    main()
