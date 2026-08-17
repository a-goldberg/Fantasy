#!/usr/bin/env python3
"""Combine rankings, market ADP, league history, and explicit context into app data."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "Analysis" / "generated"
APP_DATA = ROOT / "App" / "data"
APP_DATA.mkdir(parents=True, exist_ok=True)

TEAM_NAMES = {
    "ARI":"Arizona Cardinals", "ATL":"Atlanta Falcons", "BAL":"Baltimore Ravens", "BUF":"Buffalo Bills",
    "CAR":"Carolina Panthers", "CHI":"Chicago Bears", "CIN":"Cincinnati Bengals", "CLE":"Cleveland Browns",
    "DAL":"Dallas Cowboys", "DEN":"Denver Broncos", "DET":"Detroit Lions", "GB":"Green Bay Packers",
    "HOU":"Houston Texans", "IND":"Indianapolis Colts", "JAX":"Jacksonville Jaguars", "KC":"Kansas City Chiefs",
    "LAC":"Los Angeles Chargers", "LAR":"Los Angeles Rams", "LV":"Las Vegas Raiders", "MIA":"Miami Dolphins",
    "MIN":"Minnesota Vikings", "NE":"New England Patriots", "NO":"New Orleans Saints", "NYG":"New York Giants",
    "NYJ":"New York Jets", "PHI":"Philadelphia Eagles", "PIT":"Pittsburgh Steelers", "SEA":"Seattle Seahawks",
    "SF":"San Francisco 49ers", "TB":"Tampa Bay Buccaneers", "TEN":"Tennessee Titans", "WAS":"Washington Commanders"
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def main() -> None:
    board = json.loads((GENERATED / "base_composite_board.json").read_text())
    public_adp = json.loads((GENERATED / "public_2qb_adp.json").read_text())
    draft = json.loads((ROOT / "Config" / "current_draft.json").read_text())
    policy = json.loads((ROOT / "Config" / "draft_policy.json").read_text())
    context = json.loads((ROOT / "Config" / "context_adjustments.json").read_text())
    history = json.loads((GENERATED / "historical_draft_analysis.json").read_text())

    adp_by_name = defaultdict(list)
    adp_detail = defaultdict(dict)
    for row in public_adp["players"]:
        key = normalize(row["player"])
        if row.get("adp") is not None:
            adp_by_name[key].append(float(row["adp"]))
        adp_detail[key][row["provider"]] = row

    adjustments = defaultdict(list)
    for item in context["player_adjustments"]:
        adjustments[normalize(item["player"])].append(item)

    players = []
    for raw in board["players"]:
        player = dict(raw)
        key = normalize(player["player"])
        player["adp"] = median(adp_by_name[key])
        player["adp_sources"] = adp_detail[key]
        player["market_source_count"] = len(adp_by_name[key])
        provider_adps = adp_by_name[key]
        player["source_quality"] = {
            "expert": "high" if player["source_count"] >= 3 else ("medium" if player["source_count"] == 2 else "low"),
            "market": "high" if len(provider_adps) >= 2 else ("medium" if len(provider_adps) == 1 else "missing"),
            "market_disagreement": round(max(provider_adps) - min(provider_adps), 1) if len(provider_adps) >= 2 else None,
            "context": "not loaded" if not adjustments[key] else "source dependent"
        }
        player["context"] = adjustments[key]
        player["research_links"] = {
            "fantasypros": adp_detail[key].get("fantasypros", {}).get("player_url"),
            "fantasyguru_projections": "https://www.fantasyguru.com/nfl-projections-offense",
        }
        players.append(player)

    by_team = defaultdict(list)
    for player in players:
        if player.get("team") in TEAM_NAMES:
            by_team[player["team"]].append(player)
    teams = []
    for abbreviation, full_name in TEAM_NAMES.items():
        team_players = sorted(by_team[abbreviation], key=lambda p: p["base_composite_rank"])
        bye_values = [str(p["bye"]) for p in team_players if str(p.get("bye", "")).isdigit()]
        teams.append({
            "abbreviation": abbreviation,
            "name": full_name,
            "bye": int(max(set(bye_values), key=bye_values.count)) if bye_values else None,
            "players": [{"player": p["player"], "position": p["position"], "rank": p["base_composite_rank"]} for p in team_players],
            "verified_notes": [],
            "source_links": {
                "coaching": "https://www.fantasyguru.com/2026-nfl-coaching-system-breakdowns",
                "personnel": "https://www.fantasyguru.com/nfl-personnel-tendencies-2026",
                "offensive_line": "https://www.fantasyguru.com/2026-offensive-line-breakdown"
            }
        })

    manager_tendencies = {}
    with (GENERATED / "manager_tendencies.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            manager_tendencies[row["manager"]] = row

    payload = {
        "generated": date.today().isoformat(),
        "status": "pre-draft; keeper and traded-pick inputs incomplete",
        "draft": draft,
        "policy": policy,
        "context_rules": context["rules"],
        "source_freshness": public_adp["sources"],
        "players": players,
        "teams": teams,
        "league_history": {
            "qb_scarcity": history["qb_scarcity"],
            "manager_tendencies": manager_tendencies,
            "limitations": history["limitations"]
        }
    }
    (APP_DATA / "draft-board.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(players)} players and {len(teams)} team sheets.")


if __name__ == "__main__":
    main()
