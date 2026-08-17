#!/usr/bin/env python3
"""Merge the current source snapshots into a transparent base-quality board."""

import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Analysis" / "source"
GENERATED = ROOT / "Analysis" / "generated"
WEIGHTS = json.loads((ROOT / "Config" / "composite_weights.json").read_text())["quality_weights"]


def norm(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = value.lower()
    value = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def latest(pattern):
    matches = sorted(SOURCE.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No source snapshot matches {pattern}")
    return matches[-1]


def percentile(rank, count):
    if count <= 1:
        return 1.0
    return 1 - ((rank - 1) / (count - 1))


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
            "draftsheets_overall_value_rank": rank,
            "draftsheets_score": percentile(rank, len(ordered)),
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
            "jeff_mans_score": percentile(rank, len(valid)),
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
            "qb_chart_score": percentile(rank, len(valid)),
        }
    return result


def main():
    draftsheets = load_draftsheets()
    jeff = load_jeff_mans()
    qb_chart = load_qb_chart()
    keys = sorted(set(draftsheets) | set(jeff) | set(qb_chart))
    board = []

    for key in keys:
        ds = draftsheets.get(key, {})
        jm = jeff.get(key, {})
        qb = qb_chart.get(key, {})
        name = jm.get("player") or ds.get("player") or qb.get("player")
        positions = {p for p in [ds.get("position"), jm.get("position")] if p}
        position = jm.get("position") or ds.get("position") or ("QB" if qb else "")
        components = []
        if "draftsheets_score" in ds:
            components.append((WEIGHTS["draftsheets_scoring_value"], ds["draftsheets_score"]))
        if "jeff_mans_score" in jm:
            components.append((WEIGHTS["jeff_mans_superflex_rank"], jm["jeff_mans_score"]))
        if position == "QB" and "qb_chart_score" in qb:
            components.append((WEIGHTS["fantasyguru_qb_chart_rank"], qb["qb_chart_score"]))
        total_weight = sum(weight for weight, _ in components)
        score = sum(weight * value for weight, value in components) / total_weight if total_weight else 0
        board.append({
            "player": name,
            "position": position,
            "team": jm.get("team", ""),
            "bye": jm.get("bye", ""),
            "base_quality_score": round(score * 100, 3),
            "source_count": len(components),
            "position_conflict": len(positions) > 1,
            "draftsheets_value": ds.get("draftsheets_value", ""),
            "draftsheets_overall_value_rank": ds.get("draftsheets_overall_value_rank", ""),
            "jeff_mans_rank": jm.get("jeff_mans_rank", ""),
            "qb_chart_rank": qb.get("qb_chart_rank", ""),
            "qb_chart_tier": qb.get("qb_chart_tier", ""),
            "qb_chart_2qb_adp": qb.get("qb_chart_2qb_adp", ""),
        })

    board.sort(key=lambda p: (-p["base_quality_score"], p["player"]))
    for rank, player in enumerate(board, 1):
        player["base_composite_rank"] = rank

    fields = [
        "base_composite_rank", "player", "position", "team", "bye",
        "base_quality_score", "source_count", "position_conflict",
        "draftsheets_value", "draftsheets_overall_value_rank",
        "jeff_mans_rank", "qb_chart_rank", "qb_chart_tier", "qb_chart_2qb_adp"
    ]
    with (GENERATED / "base_composite_board.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(board)
    (GENERATED / "base_composite_board.json").write_text(json.dumps({
        "weights": WEIGHTS,
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
