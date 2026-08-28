#!/usr/bin/env python3
"""Compare recorded mock-draft rosters using current league-specific data."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOARD_PATH = ROOT / "2026/App/data/draft-board.json"
DRAFTSHEETS_PATH = ROOT / "2026/Analysis/source/draftsheets_2026_2026-08-26.json"
DEFAULT_RESULTS = Path("/Users/adam/Downloads/ mock results")
DEFAULT_OCR = Path("/private/tmp/ocr")
OUTPUT_DIR = ROOT / "2026/Analysis/generated"

OFFENSE = {"QB", "RB", "WR", "TE"}
STARTER_MINIMUMS = {"QB": 2, "RB": 2, "WR": 3, "TE": 1}


def norm(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


def percentile(values: list[float], value: float, higher_is_better: bool = True) -> float:
    if len(values) <= 1:
        return 1.0
    ordered = sorted(values)
    below = sum(item < value for item in ordered)
    equal = sum(item == value for item in ordered)
    pct = (below + 0.5 * (equal - 1)) / (len(values) - 1)
    return pct if higher_is_better else 1.0 - pct


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None

    def ranks(items: list[float]) -> list[float]:
        result = [0.0] * len(items)
        for value in sorted(set(items)):
            indexes = [i for i, item in enumerate(items) if item == value]
            rank = statistics.mean(i + 1 for i, item in enumerate(sorted(items)) if item == value)
            for index in indexes:
                result[index] = rank
        return result

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    numerator = sum((x - mx) * (y - my) for x, y in zip(rx, ry))
    denominator = math.sqrt(sum((x - mx) ** 2 for x in rx) * sum((y - my) ** 2 for y in ry))
    return numerator / denominator if denominator else None


@dataclass(frozen=True)
class OcrLine:
    x: float
    y: float
    width: float
    height: float
    text: str


def run_ocr(ocr_binary: Path, image: Path) -> list[OcrLine]:
    completed = subprocess.run(
        [str(ocr_binary), str(image)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines: list[OcrLine] = []
    for raw in completed.stdout.splitlines():
        parts = raw.split("\t", 4)
        if len(parts) != 5:
            continue
        lines.append(OcrLine(*(float(value) for value in parts[:4]), parts[4]))
    return lines


def player_match(line: str, players: list[dict]) -> tuple[dict | None, float]:
    line_norm = norm(line)
    if len(line_norm) < 5:
        return None, 0.0
    best_player, best_score = None, 0.0
    for player in players:
        name_norm = norm(player["player"])
        if not name_norm:
            continue
        if name_norm in line_norm:
            score = 1.0
        elif line_norm in name_norm and len(line_norm) >= 7:
            score = 0.94
        else:
            score = SequenceMatcher(None, line_norm, name_norm).ratio()
        if score > best_score:
            best_player, best_score = player, score
    return (best_player, best_score) if best_score >= 0.72 else (None, best_score)


def extract_roster(lines: list[OcrLine], players: list[dict]) -> tuple[list[dict], list[dict]]:
    boundary = None
    for line in lines:
        if "optimizedpicks" in norm(line.text):
            boundary = line.y + line.height + 0.025
            break

    candidates: dict[str, dict] = {}
    evidence: list[dict] = []
    for line in lines:
        if boundary is not None and line.y < boundary:
            continue
        player, confidence = player_match(line.text, players)
        if player is None:
            continue
        name = player["player"]
        existing = candidates.get(name)
        match = {
            "player": name,
            "position": player["position"],
            "ocr_text": line.text,
            "confidence": round(confidence, 3),
            "x": line.x,
            "y": line.y,
        }
        if existing is None or confidence > existing["confidence"]:
            candidates[name] = match

    roster = sorted(candidates.values(), key=lambda item: (-item["y"], item["x"]))
    evidence.extend(roster)
    return roster, evidence


def load_projections() -> dict[str, float]:
    values = json.loads(DRAFTSHEETS_PATH.read_text())["values"]
    projections: dict[str, float] = {}

    def add_rows(start: int, stop: int, name_col: int, points_col: int) -> None:
        for row in values[start:stop]:
            if len(row) <= max(name_col, points_col):
                continue
            name, points = str(row[name_col]).strip(), str(row[points_col]).strip()
            if not name or not re.fullmatch(r"-?\d+(?:\.\d+)?", points):
                continue
            projections[norm(name)] = float(points)

    add_rows(4, 45, 2, 4)     # QB
    add_rows(4, len(values), 12, 14)  # RB
    add_rows(4, len(values), 22, 24)  # WR
    add_rows(47, len(values), 2, 4)   # TE
    return projections


def projection_for(player: dict, projections: dict[str, float]) -> float | None:
    key = norm(player["player"])
    if key in projections:
        return projections[key]
    nearest = sorted(
        ((SequenceMatcher(None, key, candidate).ratio(), points) for candidate, points in projections.items()),
        reverse=True,
    )
    return nearest[0][1] if nearest and nearest[0][0] >= 0.9 else None


def choose_starters(roster: list[dict]) -> list[dict]:
    available = [player for player in roster if player["position"] in OFFENSE and player.get("projection") is not None]
    starters: list[dict] = []
    for position, count in STARTER_MINIMUMS.items():
        choices = sorted(
            (player for player in available if player["position"] == position),
            key=lambda player: player["projection"],
            reverse=True,
        )[:count]
        starters.extend(choices)
    used = {player["player"] for player in starters}
    flex = sorted(
        (player for player in available if player["position"] in {"RB", "WR", "TE"} and player["player"] not in used),
        key=lambda player: player["projection"],
        reverse=True,
    )
    if flex:
        starters.append(flex[0])
    return starters


def bye_failures(roster: list[dict]) -> int:
    failures = 0
    for bye in range(5, 15):
        active = [player for player in roster if str(player.get("bye")) != str(bye)]
        counts = Counter(player["position"] for player in active)
        required = all(counts[position] >= count for position, count in STARTER_MINIMUMS.items())
        flex_pool = sum(counts[position] - STARTER_MINIMUMS.get(position, 0) for position in ("RB", "WR", "TE"))
        if not required or flex_pool < 1:
            failures += 1
    return failures


def score_roster(roster: list[dict], projections: dict[str, float], board_by_name: dict[str, dict]) -> dict:
    enriched: list[dict] = []
    for match in roster:
        board_player = board_by_name[match["player"]]
        projection = projection_for(board_player, projections)
        injury = (board_player.get("models", {}).get("injury") or {}).get("risk_percentile_at_position")
        enriched.append({
            **match,
            "team": board_player.get("team"),
            "bye": board_player.get("bye"),
            "adp": board_player.get("adp"),
            "projection": projection,
            "injury_risk": injury,
        })

    starters = choose_starters(enriched)
    starter_names = {player["player"] for player in starters}
    offense = [player for player in enriched if player["position"] in OFFENSE]
    bench = sorted(
        (player for player in offense if player["player"] not in starter_names and player.get("projection") is not None),
        key=lambda player: player["projection"],
        reverse=True,
    )
    adp_values = sorted(player["adp"] for player in offense if isinstance(player.get("adp"), (int, float)))[:14]
    injury_values = [player["injury_risk"] for player in starters if isinstance(player.get("injury_risk"), (int, float))]
    return {
        "players": enriched,
        "starters": starters,
        "roster_size": len(enriched),
        "offense_count": len(offense),
        "projected_starter_points": round(sum(player["projection"] for player in starters), 1),
        "starter_projection_coverage": len(starters),
        "top3_bench_points": round(sum(player["projection"] for player in bench[:3]), 1),
        "normalized_adp_sum": round(sum(adp_values), 1) if adp_values else None,
        "normalized_adp_count": len(adp_values),
        "starter_injury_risk": round(statistics.mean(injury_values), 1) if injury_values else None,
        "bye_failure_weeks": bye_failures(enriched),
        "position_counts": dict(sorted(Counter(player["position"] for player in enriched).items())),
    }


def simulator_for(path: Path) -> str:
    lower = path.name.lower()
    if "draftkick" in lower:
        return "DraftKick"
    if "fantasyguru" in lower:
        return "FantasyGuru"
    return "Unlabeled"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--ocr", type=Path, default=DEFAULT_OCR)
    args = parser.parse_args()

    board = json.loads(BOARD_PATH.read_text())
    players = board["players"]
    board_by_name = {player["player"]: player for player in players}
    projections = load_projections()
    images = sorted(
        (path for path in args.results_dir.glob("*.png") if "partial" not in path.name.lower()),
        key=lambda path: path.stat().st_mtime,
    )

    results: list[dict] = []
    for sequence, image in enumerate(images, 1):
        lines = run_ocr(args.ocr, image)
        roster, evidence = extract_roster(lines, players)
        scored = score_roster(roster, projections, board_by_name)
        results.append({
            "sequence": sequence,
            "file": image.name,
            "recorded_at": image.stat().st_mtime,
            "simulator": simulator_for(image),
            "ocr_evidence": evidence,
            **scored,
        })

    seen_rosters: dict[tuple[str, ...], str] = {}
    for result in results:
        signature = tuple(sorted(player["player"] for player in result["players"]))
        result["duplicate_of"] = seen_rosters.get(signature)
        if result["duplicate_of"] is None:
            seen_rosters[signature] = result["file"]

    complete_metrics = [
        result for result in results
        if result["starter_projection_coverage"] == 9 and result["duplicate_of"] is None
    ]
    for result in complete_metrics:
        result["projection_percentile"] = percentile(
            [item["projected_starter_points"] for item in complete_metrics],
            result["projected_starter_points"],
        )
        result["adp_percentile"] = percentile(
            [item["normalized_adp_sum"] for item in complete_metrics if item["normalized_adp_sum"] is not None],
            result["normalized_adp_sum"],
            higher_is_better=False,
        )
        result["injury_percentile"] = percentile(
            [item["starter_injury_risk"] for item in complete_metrics if item["starter_injury_risk"] is not None],
            result["starter_injury_risk"],
            higher_is_better=False,
        )
        result["bye_percentile"] = percentile(
            [item["bye_failure_weeks"] for item in complete_metrics],
            result["bye_failure_weeks"],
            higher_is_better=False,
        )
        result["balanced_score"] = round(100 * (
            0.50 * result["projection_percentile"]
            + 0.30 * result["adp_percentile"]
            + 0.10 * result["injury_percentile"]
            + 0.10 * result["bye_percentile"]
        ), 1)

    score_by_file = {result["file"]: result for result in complete_metrics}
    for result in results:
        if result["duplicate_of"]:
            original = score_by_file[result["duplicate_of"]]
            for field in (
                "projection_percentile", "adp_percentile", "injury_percentile",
                "bye_percentile", "balanced_score",
            ):
                result[field] = original[field]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "mock_draft_comparison.json"
    csv_path = OUTPUT_DIR / "mock_draft_comparison.csv"
    report_path = ROOT / "2026/Analysis/mock-draft-comparison.md"
    json_path.write_text(json.dumps({"source_data_date": board["generated"], "results": results}, indent=2) + "\n")

    fields = [
        "sequence", "file", "simulator", "roster_size", "offense_count", "position_counts",
        "projected_starter_points", "starter_projection_coverage", "top3_bench_points",
        "normalized_adp_sum", "normalized_adp_count", "starter_injury_risk", "bye_failure_weeks",
        "balanced_score",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            writer.writerow({**result, "position_counts": json.dumps(result["position_counts"], sort_keys=True)})

    ranked = sorted(complete_metrics, key=lambda item: item.get("balanced_score", -1), reverse=True)
    projected = sorted(complete_metrics, key=lambda item: item["projected_starter_points"], reverse=True)
    market = sorted(complete_metrics, key=lambda item: item["normalized_adp_sum"])
    pre_change = complete_metrics[:8]
    post_change = complete_metrics[8:]
    projection_trend = spearman(
        [float(item["sequence"]) for item in complete_metrics],
        [item["projected_starter_points"] for item in complete_metrics],
    )
    balanced_trend = spearman(
        [float(item["sequence"]) for item in complete_metrics],
        [item["balanced_score"] for item in complete_metrics],
    )

    lines = [
        "# Mock draft comparison",
        "",
        f"Generated from {len(results)} nonpartial screenshots, representing {len(complete_metrics)} unique rosters, and the current {board['generated']} Draft Room data.",
        "",
        "## Method",
        "",
        "- Projected-points score: best legal offensive lineup (2 QB, 2 RB, 3 WR, 1 TE, 1 RB/WR/TE flex) using the league-specific DraftSheets PTS column.",
        "- Projection source: the Aug. 26 DraftSheets sheet configured for this league's 10-team, non-PPR, two-QB scoring.",
        "- Market score: sum of the 14 best current consensus two-QB ADPs on each offensive roster. The current board combines Fantasy Football Calculator and FantasyPros market data. Lower is better. Fourteen normalizes the one early 15-of-17 screenshot.",
        "- Illustrative balanced index: 50% projected-points percentile, 30% ADP percentile, 10% lower starter injury risk, and 10% bye-week coverage. These weights are useful, not objectively correct.",
        "- Kicker and defense are excluded from projected-points and ADP comparisons because they are not covered comparably by the offensive projection source.",
        "- `mock_results2.png` is a 15-of-17 screenshot, but it contains a complete nine-player offensive starting lineup and 14 offensive players, so it remains comparable under the normalized measures.",
        "- `mock_results15-draftkick-20260827.png` duplicates the roster in `mock_results11-draftkick-20260827.png`; it is retained in the audit but counted once in rankings and trends.",
        "",
        "## Overall ranking",
        "",
        "| Rank | Mock | Simulator | Starter pts | ADP sum | Injury risk | Bye failures | Index |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for rank, item in enumerate(ranked, 1):
        lines.append(
            f"| {rank} | {item['file']} | {item['simulator']} | {item['projected_starter_points']:.1f} | "
            f"{item['normalized_adp_sum']:.1f} | {item['starter_injury_risk']:.1f} | "
            f"{item['bye_failure_weeks']} | {item['balanced_score']:.1f} |"
        )

    lines.extend([
        "",
        "## Metric leaders",
        "",
        f"- Highest projected starting lineup: **{projected[0]['file']}** ({projected[0]['projected_starter_points']:.1f} points).",
        f"- Strongest current ADP roster: **{market[0]['file']}** (normalized ADP sum {market[0]['normalized_adp_sum']:.1f}).",
        f"- Best illustrative balanced index: **{ranked[0]['file']}** ({ranked[0]['balanced_score']:.1f}).",
        "",
        "## Change over time",
        "",
    ])
    lines.extend([
        f"- Earlier set ({len(pre_change)} unique rosters, through {pre_change[-1]['file']}): "
        f"{statistics.mean(item['projected_starter_points'] for item in pre_change):.1f} average starter points; "
        f"{statistics.mean(item['normalized_adp_sum'] for item in pre_change):.1f} average ADP sum; "
        f"{statistics.mean(item['balanced_score'] for item in pre_change):.1f} average index.",
        f"- Aug. 27 QA set ({len(post_change)} unique rosters): "
        f"{statistics.mean(item['projected_starter_points'] for item in post_change):.1f} average starter points; "
        f"{statistics.mean(item['normalized_adp_sum'] for item in post_change):.1f} average ADP sum; "
        f"{statistics.mean(item['balanced_score'] for item in post_change):.1f} average index.",
        f"- Change: {statistics.mean(item['projected_starter_points'] for item in post_change) - statistics.mean(item['projected_starter_points'] for item in pre_change):+.1f} starter points; "
        f"{statistics.mean(item['normalized_adp_sum'] for item in post_change) - statistics.mean(item['normalized_adp_sum'] for item in pre_change):+.1f} ADP sum (lower is better); "
        f"{statistics.mean(item['balanced_score'] for item in post_change) - statistics.mean(item['balanced_score'] for item in pre_change):+.1f} index points.",
    ])
    lines.extend([
        f"- Spearman time correlation: projected points {projection_trend:.2f}; balanced score {balanced_trend:.2f}.",
        "",
        "A positive correlation suggests later mocks improved; a value near zero suggests randomness; a negative value suggests later mocks weakened on that measure. With only 14 unique rosters, treat this as directional evidence, not proof.",
        "",
        "## Simulator averages (unique rosters)",
        "",
        "| Simulator | N | Starter pts | ADP sum | Index |",
        "|---|---:|---:|---:|---:|",
    ])
    for simulator in ("DraftKick", "FantasyGuru", "Unlabeled"):
        group = [item for item in complete_metrics if item["simulator"] == simulator]
        if group:
            lines.append(
                f"| {simulator} | {len(group)} | "
                f"{statistics.mean(item['projected_starter_points'] for item in group):.1f} | "
                f"{statistics.mean(item['normalized_adp_sum'] for item in group):.1f} | "
                f"{statistics.mean(item['balanced_score'] for item in group):.1f} |"
            )
    lines.extend([
        "",
        "## Extraction audit",
        "",
        "| Mock | Roster | Offense | Positions | Projection coverage | Note |",
        "|---|---:|---:|---|---:|---|",
    ])
    for item in results:
        lines.append(
            f"| {item['file']} | {item['roster_size']} | {item['offense_count']} | "
            f"{', '.join(f'{key} {value}' for key, value in item['position_counts'].items())} | "
            f"{item['starter_projection_coverage']}/9 | "
            f"{('Duplicate of ' + item['duplicate_of']) if item['duplicate_of'] else ('15-of-17 snapshot' if item['roster_size'] < 17 else '')} |"
        )
    report_path.write_text("\n".join(lines) + "\n")

    print(report_path)
    print(csv_path)
    print(json_path)
    for result in results:
        print(
            f"{result['sequence']:02d} {result['file']}: roster={result['roster_size']} "
            f"positions={result['position_counts']} starters={result['starter_projection_coverage']}/9"
        )


if __name__ == "__main__":
    main()
