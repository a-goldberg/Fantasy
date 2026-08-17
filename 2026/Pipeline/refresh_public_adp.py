#!/usr/bin/env python3
"""Refresh public 10-team 2QB ADP snapshots without third-party packages."""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "Analysis" / "source"
GENERATED_DIR = ROOT / "Analysis" / "generated"
FFC_URL = "https://fantasyfootballcalculator.com/api/v1/adp/2qb?teams=10&year=2026&position=all"
FP_URL = "https://draftwizard.fantasypros.com/football/adp/mock-drafts/overall/2qb-std-10-teams"
USER_AGENT = "Mozilla/5.0 (compatible; FantasyDraftManager/2026; personal research)"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def pick_to_number(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    if re.fullmatch(r"\d+\.\d{2}", value):
        round_number, slot = (int(part) for part in value.split("."))
        return float((round_number - 1) * 10 + slot)
    try:
        return float(value)
    except ValueError:
        return None


class FantasyProsTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_body = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []
        self.player_url = ""
        self.row_player_url = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == "adpTable":
            self.in_table = True
        elif self.in_table and tag == "tbody":
            self.in_body = True
        elif self.in_body and tag == "tr":
            self.in_row = True
            self.row = []
            self.row_player_url = ""
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.cell_parts = []
        elif self.in_cell and tag == "a" and "fantasypros.com/nfl/players/" in attrs.get("href", ""):
            self.row_player_url = attrs["href"]

    def handle_data(self, data):
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.in_cell:
            self.row.append(" ".join("".join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row + [self.row_player_url])
            self.in_row = False
        elif tag == "tbody" and self.in_body:
            self.in_body = False
        elif tag == "table" and self.in_table:
            self.in_table = False


def parse_team_bye(value: str) -> tuple[str, int | None]:
    match = re.match(r"([A-Z]+).*?\((\d+)\)", value)
    if not match:
        return value.strip(), None
    return match.group(1), int(match.group(2))


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()

    ffc_raw = json.loads(fetch(FFC_URL))
    (SOURCE_DIR / f"ffc_2qb_adp_2026_{stamp}.json").write_text(
        json.dumps(ffc_raw, indent=2) + "\n", encoding="utf-8"
    )

    fp_html = fetch(FP_URL).decode("utf-8", errors="replace")
    parser = FantasyProsTable()
    parser.feed(fp_html)
    fp_players = []
    for row in parser.rows:
        if len(row) < 10:
            continue
        pos_label, overall, name, team_bye, avg, high, low, stdev, drafted, url = row[:10]
        team, bye = parse_team_bye(team_bye)
        fp_players.append({
            "name": name,
            "position": re.sub(r"\d+$", "", pos_label),
            "position_rank": int(re.sub(r"^\D+", "", pos_label)),
            "overall_rank": int(overall),
            "team": team,
            "bye": bye,
            "adp": pick_to_number(avg),
            "high": pick_to_number(high),
            "low": pick_to_number(low),
            "stdev": float(stdev),
            "percent_drafted": float(drafted.rstrip("%")),
            "player_url": url,
        })
    fp_snapshot = {
        "source_url": FP_URL,
        "retrieved": stamp,
        "format": "10-team 2QB standard mock drafts",
        "players": fp_players,
    }
    (SOURCE_DIR / f"fantasypros_2qb_adp_2026_{stamp}.json").write_text(
        json.dumps(fp_snapshot, indent=2) + "\n", encoding="utf-8"
    )

    normalized = []
    for provider, players in (("ffc", ffc_raw["players"]), ("fantasypros", fp_players)):
        for player in players:
            normalized.append({
                "provider": provider,
                "player": player.get("name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "bye": player.get("bye"),
                "adp": player.get("adp"),
                "high": player.get("high"),
                "low": player.get("low"),
                "stdev": player.get("stdev"),
                "sample_size": player.get("times_drafted"),
                "player_url": player.get("player_url"),
            })
    fields = list(normalized[0])
    with (GENERATED_DIR / "public_2qb_adp.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalized)
    (GENERATED_DIR / "public_2qb_adp.json").write_text(json.dumps({
        "retrieved": stamp,
        "sources": {
            "ffc": {"url": FFC_URL, "meta": ffc_raw.get("meta")},
            "fantasypros": {"url": FP_URL, "players": len(fp_players)},
        },
        "players": normalized,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(normalized)} provider-player ADP rows ({len(fp_players)} FantasyPros).")


if __name__ == "__main__":
    main()
