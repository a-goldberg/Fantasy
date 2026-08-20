#!/usr/bin/env python3
"""Build a position value board from the visible DraftSheets tables.

The source workbook has independent sorts that can detach names from the other
row fields.  Per the owner's instruction, this parser trusts only the displayed
NAME and VALUE cells in each positional table.  Team, bye, points, tier, PS,
and ECR are intentionally ignored and must come from other sources.
"""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "Analysis" / "source"
DEFAULT_OUTPUT_DIR = ROOT / "Analysis" / "generated"

TABLES = {
    "QB": {"name_col": 2, "value_col": 5, "start_row": 4, "end_row": 45},
    "TE": {"name_col": 2, "value_col": 5, "start_row": 47, "end_row": None},
    "RB": {"name_col": 12, "value_col": 15, "start_row": 4, "end_row": None},
    "WR": {"name_col": 22, "value_col": 25, "start_row": 4, "end_row": None},
}


def latest_snapshot(source_dir: Path) -> Path:
    matches = sorted(source_dir.glob("draftsheets_2026_*.json"))
    if not matches:
        raise FileNotFoundError(f"No DraftSheets snapshot found in {source_dir}")
    return matches[-1]


def latest_tier_snapshot(source_dir: Path):
    matches = sorted(source_dir.glob("draftsheets_position_tiers_*.json"))
    return matches[-1] if matches else None


def numeric(value):
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def cell(row, index):
    return row[index] if index < len(row) else ""


def parse(snapshot, tier_snapshot=None):
    source = json.loads(snapshot.read_text())
    rows = source["values"]
    tier_path = tier_snapshot or latest_tier_snapshot(snapshot.parent)
    tiers = {}
    tier_source = None
    if tier_path:
        tier_payload = json.loads(tier_path.read_text())
        tier_source = tier_payload.get("source")
        for item in tier_payload.get("players", []):
            key = (item["position"], item["player"])
            if key in tiers:
                raise ValueError(f"Duplicate positional tier record: {key}")
            tiers[key] = item["position_tier"]
    board = []

    for position, spec in TABLES.items():
        end = spec["end_row"] if spec["end_row"] is not None else len(rows)
        seen = set()
        position_rows = []
        for index in range(spec["start_row"], min(end, len(rows))):
            row = rows[index]
            name = str(cell(row, spec["name_col"])).strip()
            value = numeric(cell(row, spec["value_col"]))
            if not name or value is None or name.upper() == "NAME":
                continue
            if name in seen:
                raise ValueError(f"Duplicate {position} name in displayed table: {name}")
            seen.add(name)
            position_rows.append(
                {
                    "position": position,
                    "player": name,
                    "displayed_value": value,
                    "position_tier": tiers.get((position, name)),
                    "source_row": index + 1,
                }
            )

        position_rows.sort(key=lambda item: (-item["displayed_value"], item["player"]))
        for rank, item in enumerate(position_rows, 1):
            item["value_rank_at_position"] = rank
        board.extend(position_rows)

    source_meta = dict(source["source"])
    if tier_source:
        source_meta["position_tier_source"] = tier_source
    return source_meta, board


def write_outputs(source_meta, board, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "position",
        "value_rank_at_position",
        "player",
        "displayed_value",
        "position_tier",
        "source_row",
    ]
    csv_path = output_dir / "draftsheets_value_board.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(board)

    payload = {
        "source": source_meta,
        "import_rule": "NAME and displayed VALUE only; sorted descending within position",
        "ignored_fields": ["team", "bye", "points", "tier", "PS", "ECR"],
        "players": board,
    }
    json_path = output_dir / "draftsheets_value_board.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    return csv_path, json_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--tier-snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot(DEFAULT_SOURCE_DIR)
    source_meta, board = parse(snapshot, args.tier_snapshot)
    csv_path, json_path = write_outputs(source_meta, board, args.output_dir)
    counts = {}
    for item in board:
        counts[item["position"]] = counts.get(item["position"], 0) + 1
    print(json.dumps({"snapshot": str(snapshot), "counts": counts,
                      "csv": str(csv_path), "json": str(json_path)}, indent=2))


if __name__ == "__main__":
    main()
