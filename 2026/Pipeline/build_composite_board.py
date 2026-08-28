#!/usr/bin/env python3
"""Merge the current source snapshots into a transparent base-quality board."""

import csv
import json
import re
from pathlib import Path

from player_names import normalize_player_name

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Analysis" / "source"
GENERATED = ROOT / "Analysis" / "generated"
CONFIG = json.loads((ROOT / "Config" / "composite_weights.json").read_text())
WEIGHTS = CONFIG["quality_weights"]
RANK_HORIZON = int(CONFIG["rank_horizon"])


def norm(value):
    return normalize_player_name(value)


def latest(pattern):
    matches = sorted(SOURCE.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No source snapshot matches {pattern}")
    return matches[-1]


def fixed_rank_score(rank, horizon=RANK_HORIZON):
    """Score an absolute rank on a fixed horizon, independent of source length."""
    if rank < 1:
        raise ValueError("Rank must be positive")
    return max(0.0, (horizon + 1 - rank) / horizon)


def combine_quality_scores(primary_components, supplemental_components):
    """Combine source scores without letting supplemental data establish quality.

    Overall ranking sources may establish a player's baseline on their own. A
    positional chart or other supplemental source may refine that baseline, but
    it cannot be renormalized into a full-strength overall-player opinion when
    no primary source ranks the player.
    """
    applied_supplemental = supplemental_components if primary_components else []
    components = primary_components + applied_supplemental
    total_weight = sum(weight for weight, _ in components)
    score = sum(weight * value for weight, value in components) / total_weight if total_weight else 0
    return {
        "score": score,
        "source_count": len(components),
        "primary_source_count": len(primary_components),
        "supplemental_source_count": len(supplemental_components),
        "supplemental_applied_count": len(applied_supplemental),
        "expert_weight_coverage": total_weight,
        "supplemental_only": not primary_components and bool(supplemental_components),
    }


def load_draftsheets():
    payload = json.loads((GENERATED / "draftsheets_value_board.json").read_text())
    players = payload["players"]
    ordered = sorted(players, key=lambda p: (-float(p["displayed_value"]), p["player"]))
    rank_by_key = {norm(p["player"]): rank for rank, p in enumerate(ordered, 1)}
    result = {}
    for item in players:
        key = norm(item["player"])
        rank = rank_by_key[key]
        result[key] = {
            "player": item["player"],
            "position": item["position"],
            "draftsheets_value": item["displayed_value"],
            "draftsheets_position_tier": item.get("position_tier"),
            "draftsheets_overall_value_rank": rank,
            "draftsheets_score": fixed_rank_score(rank),
        }
    return result


def load_jeff_mans():
    raw = json.loads(latest("jeff_mans_superflex_*.json").read_text())
    values = raw["values"]
    result = {}
    valid = [r for r in values[1:] if len(r) >= 5 and str(r[0]).isdigit()]
    for row in valid:
        rank = int(row[0])
        depth = str(row[4])
        match = re.match(r"([A-Z]+)", depth)
        result[norm(row[1])] = {
            "player": row[1],
            "team": row[2],
            "bye": row[3],
            "position": match.group(1) if match else "",
            "jeff_mans_rank": rank,
            "jeff_mans_score": fixed_rank_score(rank),
        }
    return result


def load_qb_chart():
    raw = json.loads(latest("fantasyguru_2qb_chart_*.json").read_text())
    valid = [r for r in raw["values"][1:] if len(r) >= 2 and str(r[0]).isdigit()]
    result = {}
    current_tier = None
    for row in raw["values"][1:]:
        if row and str(row[0]).upper().startswith("TIER"):
            current_tier = row[0]
            continue
        if len(row) < 2 or not str(row[0]).isdigit():
            continue
        rank = int(row[0])
        result[norm(row[1])] = {
            "player": row[1],
            "qb_chart_rank": rank,
            "qb_chart_tier": current_tier,
            "qb_chart_2qb_adp": row[5] if len(row) > 5 else "",
            "qb_chart_score": fixed_rank_score(rank),
        }
    return result


def load_rotoballer():
    raw = json.loads(latest("rotoballer_superflex_rankings_*.json").read_text())
    result = {}
    for row in raw["players"]:
        rank = int(row["rank"])
        result[norm(row["player"])] = {
            "player": row["player"],
            "team": row.get("team", ""),
            "bye": row.get("bye", ""),
            "position": row.get("position", ""),
            "rotoballer_rank": rank,
            "rotoballer_tier": row.get("tier", ""),
            "rotoballer_player_url": row.get("player_url", ""),
            "rotoballer_score": fixed_rank_score(rank),
        }
    return result


def main():
    draftsheets = load_draftsheets()
    jeff = load_jeff_mans()
    qb_chart = load_qb_chart()
    rotoballer = load_rotoballer()
    keys = sorted(set(draftsheets) | set(jeff) | set(qb_chart) | set(rotoballer))
    board = []

    for key in keys:
        ds = draftsheets.get(key, {})
        jm = jeff.get(key, {})
        qb = qb_chart.get(key, {})
        rb = rotoballer.get(key, {})
        name = jm.get("player") or ds.get("player") or rb.get("player") or qb.get("player")
        positions = {p for p in [ds.get("position"), jm.get("position"), rb.get("position")] if p}
        position = jm.get("position") or ds.get("position") or rb.get("position") or ("QB" if qb else "")
        primary_components = []
        if "draftsheets_score" in ds:
            primary_components.append((WEIGHTS["draftsheets_scoring_value"], ds["draftsheets_score"]))
        if "jeff_mans_score" in jm:
            primary_components.append((WEIGHTS["jeff_mans_superflex_rank"], jm["jeff_mans_score"]))
        if "rotoballer_score" in rb:
            primary_components.append((WEIGHTS["rotoballer_superflex_rank"], rb["rotoballer_score"]))
        supplemental_components = []
        if position == "QB" and "qb_chart_score" in qb:
            supplemental_components.append((WEIGHTS["fantasyguru_qb_chart_rank"], qb["qb_chart_score"]))
        quality = combine_quality_scores(primary_components, supplemental_components)
        board.append({
            "player": name,
            "position": position,
            "team": jm.get("team") or rb.get("team", ""),
            "bye": jm.get("bye") or rb.get("bye", ""),
            "base_quality_score": round(quality["score"] * 100, 3),
            "source_count": quality["source_count"],
            "primary_source_count": quality["primary_source_count"],
            "supplemental_source_count": quality["supplemental_source_count"],
            "supplemental_applied_count": quality["supplemental_applied_count"],
            "supplemental_only": quality["supplemental_only"],
            "expert_weight_coverage": round(quality["expert_weight_coverage"], 3),
            "position_conflict": len(positions) > 1,
            "draftsheets_value": ds.get("draftsheets_value", ""),
            "draftsheets_position_tier": ds.get("draftsheets_position_tier", ""),
            "draftsheets_overall_value_rank": ds.get("draftsheets_overall_value_rank", ""),
            "jeff_mans_rank": jm.get("jeff_mans_rank", ""),
            "rotoballer_rank": rb.get("rotoballer_rank", ""),
            "rotoballer_tier": rb.get("rotoballer_tier", ""),
            "rotoballer_player_url": rb.get("rotoballer_player_url", ""),
            "qb_chart_rank": qb.get("qb_chart_rank", ""),
            "qb_chart_tier": qb.get("qb_chart_tier", ""),
            "qb_chart_2qb_adp": qb.get("qb_chart_2qb_adp", ""),
        })

    board.sort(key=lambda p: (-p["base_quality_score"], p["player"]))
    for rank, player in enumerate(board, 1):
        player["base_composite_rank"] = rank

    fields = [
        "base_composite_rank", "player", "position", "team", "bye",
        "base_quality_score", "source_count", "primary_source_count",
        "supplemental_source_count", "supplemental_applied_count", "supplemental_only",
        "expert_weight_coverage", "position_conflict",
        "draftsheets_value", "draftsheets_position_tier", "draftsheets_overall_value_rank",
        "jeff_mans_rank", "rotoballer_rank", "rotoballer_tier", "rotoballer_player_url",
        "qb_chart_rank", "qb_chart_tier", "qb_chart_2qb_adp"
    ]
    with (GENERATED / "base_composite_board.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(board)
    (GENERATED / "base_composite_board.json").write_text(json.dumps({
        "weights": WEIGHTS,
        "rank_horizon": RANK_HORIZON,
        "source_roles": CONFIG.get("source_roles", {}),
        "note": "Base player quality only. ADP availability and draft-state policy are applied later.",
        "players": board,
    }, indent=2) + "\n")
    print(json.dumps({"players": len(board), "top_20": [
        {"rank": p["base_composite_rank"], "player": p["player"],
         "position": p["position"], "score": p["base_quality_score"]}
        for p in board[:20]
    ]}, indent=2))


if __name__ == "__main__":
    main()
