#!/usr/bin/env python3
"""Refresh structured context from DraftSharks, RotoWire, ESPN, and Ourlads."""

from __future__ import annotations

import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from ourlads_names import parse_ourlads_name

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Analysis" / "source"
GENERATED = ROOT / "Analysis" / "generated"
STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
DAY = STAMP[:10]
UA = "Mozilla/5.0 (compatible; FantasyDraftManager/2026; personal research)"

URLS = {
    "injury": "https://www.draftsharks.com/injury-predictor",
    "rookie": "https://www.draftsharks.com/nfl-rookie-model",
    "superflex": "https://www.draftsharks.com/rankings/superflex",
    "rotowire": "https://www.rotowire.com/football/news.php",
    "espn": "https://www.espn.com/espn/rss/nfl/news",
    "ourlads": "https://www.ourlads.com/nfldepthcharts/depthcharts.aspx",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def embedded_vue(source: str) -> dict:
    marker = "var vueAppData = "
    start = source.find(marker)
    if start < 0:
        raise ValueError("vueAppData was not present")
    result, _ = json.JSONDecoder().raw_decode(source, start + len(marker))
    return result


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def parse_injury(source: str) -> dict:
    data = embedded_vue(source)
    players = []
    for row in data["playerData"]:
        profile = row.get("sipPlayerProfile") or {}
        if not profile:
            continue
        players.append({
            "player": f"{row['first_name']} {row['last_name']}",
            "position": row.get("fantasy_position") or row.get("position"),
            "team": (row.get("team") or {}).get("abbr"),
            "injury_probability": float(profile["injury_prob"]),
            "projected_games_missed": float(profile["proj_games_missed"]),
            "durability": float(profile["durability"]),
            "risk_group": profile.get("positional_risk_group"),
            "model_updated": profile.get("update_time"),
            "recorded_injuries": len(row.get("sipInjuries") or []),
        })
    if len(players) < 300:
        raise ValueError(f"injury model returned only {len(players)} players")
    return {"source_url": URLS["injury"], "source_updated": data.get("lastUpdateTime"), "players": players}


def parse_rookies(source: str) -> dict:
    data = embedded_vue(source)
    players = []
    for row in data["projections"]:
        if row.get("draft_year") != 2026:
            continue
        player = row["player"]
        players.append({
            "player": f"{player['first_name']} {player['last_name']}",
            "position": player.get("fantasy_position"),
            "team": (player.get("team") or {}).get("abbr"),
            "overall_score": float(row["overall_score"]),
            "model_output": float(row["model_output"]),
            "prospect_label": row.get("fantasy_prospect"),
            "overall_percentile": row.get("overall_percentile"),
            "film_percentile": row.get("film_percentile"),
            "production_percentile": row.get("production_percentile"),
            "athleticism_percentile": row.get("athleticism_percentile"),
            "position_model_rank": row.get("rankFantasyPositionDsValue"),
            "model_updated": row.get("update_time"),
        })
    if len(players) < 75:
        raise ValueError(f"rookie model returned only {len(players)} 2026 players")
    return {"source_url": URLS["rookie"], "draft_year": 2026, "players": players}


def parse_sos(position_sources: dict[str, str]) -> dict:
    teams = {}
    for position, source in position_sources.items():
        data = embedded_vue(source)
        if len(data["teamData"]) != 32:
            raise ValueError(f"{position} schedule returned {len(data['teamData'])} teams")
        for row in data["teamData"]:
            weeks = []
            for game in row["schedule"]:
                if not 1 <= int(game["week"]) <= 6:
                    continue
                opponent = game.get("opponent") or {}
                allowed = opponent.get("currentSosFpa") or {}
                raw = allowed.get(f"against_{position.lower()}_percent_diff")
                weeks.append({
                    "week": int(game["week"]),
                    "opponent": opponent.get("abbr"),
                    "home": bool(game.get("home")),
                    "percent_difference": float(raw) if raw is not None else None,
                })
            values = [week["percent_difference"] for week in weeks if week["percent_difference"] is not None]
            teams.setdefault(row["abbr"], {"team": row["abbr"], "bye": row.get("bye"), "positions": {}})
            teams[row["abbr"]]["positions"][position] = {
                "weeks_1_6_average": round(sum(values) / len(values), 4) if values else None,
                "weeks": weeks,
            }
    return {
        "source_url_pattern": "https://www.draftsharks.com/strength-of-schedule/{position}",
        "interpretation": "Positive is easier; negative is harder. Values are opponent fantasy points allowed versus expectation.",
        "teams": sorted(teams.values(), key=lambda row: row["team"]),
    }


def parse_superflex(source: str) -> dict:
    players = []
    pattern = re.compile(r"<tbody\s+data-player-row(?P<attrs>.*?)>(?P<body>.*?)</tbody>", re.S | re.I)
    for match in pattern.finditer(source):
        attrs, body = match.group("attrs"), match.group("body")
        def attr(name):
            found = re.search(rf'data-{re.escape(name)}="([^"]*)"', attrs)
            return html.unescape(found.group(1)) if found else None
        values = dict(re.findall(r'data-value="([^"]*)"\s+data-attribute="([^"]+)"', body))
        rank_match = re.search(r'class="column-title rank-index">\s*<span>(\d+)</span>', body)
        team_match = re.search(r'class="player-details-group__team-name">([^<]+)</span>', body)
        name = attr("player-name")
        if not name or not rank_match:
            continue
        by_attribute = {attribute: value for value, attribute in values.items()}
        players.append({
            "rank": int(rank_match.group(1)),
            "player": name,
            "position": attr("fantasy-position"),
            "team": clean_text(team_match.group(1)) if team_match else None,
            "rookie": attr("is-rookie") == "true",
            "adp": by_attribute.get("adp"),
            "sos": by_attribute.get("strength_of_schedule"),
            "injury_probability": by_attribute.get("player.sipPlayerProfile.injury_prob"),
            "floor": by_attribute.get("floor_points"),
            "projection": by_attribute.get("fantasy_points"),
            "ceiling": by_attribute.get("ceiling_points"),
            "three_d_value": by_attribute.get("dsValue"),
        })
    if len(players) < 20:
        raise ValueError(f"public superflex table returned only {len(players)} players")
    return {"source_url": URLS["superflex"], "coverage": "partial public table", "players": players}


def parse_rotowire(source: str) -> dict:
    players = []
    blocks = re.split(r'<div class="news-update(?: [^"]*)?">', source)[1:]
    for block in blocks:
        name = re.search(r'class="news-update__player-link" href="([^"]+)">([^<]+)</a>', block)
        headline = re.search(r'class="news-update__headline" href="([^"]+)">([^<]+)</a>', block)
        team = re.search(r'class="news-update__logo"[^>]+alt="([^"]+)"', block)
        position = re.search(r'class="news-update__pos">([^<]+)</b>', block)
        timestamp = re.search(r'class="news-update__timestamp">([^<]+)</div>', block)
        update = re.search(r'class="news-update__news">(.*?)</div>', block, re.S)
        injury = re.search(r'class="news-update__inj">([^<]+)</div>', block)
        if not name or not headline:
            continue
        players.append({
            "player": clean_text(name.group(2)),
            "player_url": "https://www.rotowire.com" + name.group(1),
            "headline": clean_text(headline.group(2)),
            "headline_url": "https://www.rotowire.com" + headline.group(1),
            "team": team.group(1) if team else None,
            "position": clean_text(position.group(1)) if position else None,
            "date": clean_text(timestamp.group(1)) if timestamp else None,
            "injury": clean_text(injury.group(1)) if injury else None,
            "update": clean_text(update.group(1)) if update else None,
            "ranking_adjustment": 0,
            "adjustment_note": "News is research context until a concrete fantasy impact is verified."
        })
    return {"source_url": URLS["rotowire"], "items": players}


def merge_rotowire_history(current: dict, snapshot_limit: int = 21) -> dict:
    """Retain a rolling set of dated news snapshots instead of only today's top page."""
    items = []
    seen = set()
    paths = sorted(SOURCE.glob("rotowire_news_*.json"))[-snapshot_limit:]
    for payload in [current] + [json.loads(path.read_text()) for path in reversed(paths)]:
        for item in payload.get("items", []):
            identity = item.get("headline_url") or (item.get("player"), item.get("headline"), item.get("date"))
            identity = tuple(identity) if isinstance(identity, tuple) else identity
            if identity in seen:
                continue
            seen.add(identity)
            items.append(item)
    return {
        **current,
        "items": items,
        "retention": f"Current page plus up to {snapshot_limit} dated local snapshots; duplicate headlines removed.",
    }


def parse_espn(source: str) -> dict:
    root = ET.fromstring(source)
    channel = root.find("channel")
    items = []
    for item in channel.findall("item") if channel is not None else []:
        items.append({
            "title": item.findtext("title"),
            "link": item.findtext("link"),
            "published": item.findtext("pubDate"),
        })
    return {"source_url": URLS["espn"], "last_build": channel.findtext("lastBuildDate") if channel is not None else None, "items": items}


def parse_ourlads(source: str) -> dict:
    sections = list(re.finditer(r"<h2 Class='([^']+)'>(.*?)<small>Updated:\s*([^<]+)</small></h2>", source, re.S | re.I))
    teams = []
    status_map = {"lc_purple": "2026 draft pick", "lc_aqua": "2026 undrafted free agent", "lc_gold": "2026 acquisition", "lc_red": "injured/inactive"}
    for index, section in enumerate(sections):
        abbreviation = section.group(1)
        if abbreviation == "ARZ": abbreviation = "ARI"
        start = section.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(source)
        content = source[start:end].split("Defense -", 1)[0]
        rows = []
        for row_match in re.finditer(r"<tr class='row-dc-(?:wht|grey)'>(.*?)</tr>", content, re.S | re.I):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_match.group(1), re.S | re.I)
            if len(cells) < 4:
                continue
            position = clean_text(cells[1])
            if position not in {"QB", "RB", "FB", "LWR", "RWR", "SWR", "WR", "TE", "LT", "LG", "C", "RG", "RT"}:
                continue
            depth = []
            for depth_index, cell_index in enumerate(range(3, min(len(cells), 12), 2), 1):
                anchor = re.search(r"<a href='([^']+)' class='([^']*)'>(.*?)</a>", cells[cell_index], re.S | re.I)
                if not anchor or not clean_text(anchor.group(3)):
                    continue
                raw_name = clean_text(anchor.group(3))
                parsed_name = parse_ourlads_name(raw_name)
                depth.append({
                    "depth": depth_index,
                    "raw_name": raw_name,
                    "player": parsed_name["player"],
                    "ourlads_identifier": parsed_name["identifier"],
                    "status": status_map.get(anchor.group(2), "returning/other"),
                    "player_url": anchor.group(1),
                })
            if depth:
                rows.append({"position": position, "depth": depth})
        teams.append({"team": abbreviation, "updated": clean_text(section.group(3)), "offense": rows})
    if len(teams) != 32:
        raise ValueError(f"Ourlads returned {len(teams)} team sections")
    return {"source_url": URLS["ourlads"], "legend": status_map, "teams": teams}


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)
    previous_path = GENERATED / "current_context.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    output = {"retrieved": STAMP, "sources": {}, "warnings": []}

    jobs = {
        "draftsharks_injury": lambda: parse_injury(fetch(URLS["injury"])),
        "draftsharks_rookies": lambda: parse_rookies(fetch(URLS["rookie"])),
        "draftsharks_early_sos": lambda: parse_sos({pos: fetch(f"https://www.draftsharks.com/strength-of-schedule/{pos.lower()}") for pos in ("QB", "RB", "WR", "TE")}),
        "draftsharks_superflex": lambda: parse_superflex(fetch(URLS["superflex"])),
        "rotowire_news": lambda: parse_rotowire(fetch(URLS["rotowire"])),
        "espn_news": lambda: parse_espn(fetch(URLS["espn"])),
        "ourlads_depth_charts": lambda: parse_ourlads(fetch(URLS["ourlads"])),
    }
    for key, job in jobs.items():
        try:
            value = job()
            if key == "rotowire_news":
                value = merge_rotowire_history(value)
            value["retrieved"] = STAMP
            output["sources"][key] = value
            (SOURCE / f"{key}_{DAY}.json").write_text(json.dumps(value, indent=2) + "\n")
        except Exception as error:
            if previous.get("sources", {}).get(key):
                output["sources"][key] = previous["sources"][key]
                output["warnings"].append(f"{key} refresh failed; retained prior snapshot: {error}")
            else:
                output["warnings"].append(f"{key} unavailable with no prior snapshot: {error}")

    previous_path.write_text(json.dumps(output, indent=2) + "\n")
    counts = {key: len(value.get("players", value.get("items", value.get("teams", [])))) for key, value in output["sources"].items()}
    print(json.dumps({"retrieved": STAMP, "counts": counts, "warnings": output["warnings"]}, indent=2))


if __name__ == "__main__":
    main()
