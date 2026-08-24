#!/usr/bin/env python3
"""Refresh public expert-ranking snapshots used by the base-quality composite."""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "Analysis" / "source"
ROTOBALLER_URL = (
    "https://www.rotoballer.com/wp-json/rb/v1/rankings"
    "?league=Overall&perPage=600&spreadsheet=superflex"
)
USER_AGENT = "Mozilla/5.0 (compatible; FantasyDraftManager/2026; personal research)"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    raw = fetch_json(ROTOBALLER_URL)
    players = []
    for row in raw.get("data", []):
        player = row.get("player") or {}
        name = player.get("name")
        rank = row.get("rank") or row.get("resolved_rank") or row.get("overall_rank")
        if not name or not isinstance(rank, int):
            continue
        players.append({
            "rank": rank,
            "player": name,
            "position": row.get("position"),
            "team": row.get("team"),
            "bye": row.get("bye_week"),
            "tier": row.get("tier") or row.get("display_tier_number"),
            "target_round": row.get("target_round"),
            "updated_at": row.get("updated_at"),
            "player_url": player.get("rotoballer_link"),
        })
    players.sort(key=lambda item: (item["rank"], item["player"]))
    snapshot = {
        "source": "RotoBaller",
        "source_url": ROTOBALLER_URL,
        "retrieved": stamp,
        "format": "Overall Superflex expert rankings",
        "purpose": "base_quality",
        "coverage": len(players),
        "players": players,
    }
    output = SOURCE_DIR / f"rotoballer_superflex_rankings_{stamp}.json"
    output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(players)} RotoBaller Superflex expert ranks to {output.name}.")


if __name__ == "__main__":
    main()
