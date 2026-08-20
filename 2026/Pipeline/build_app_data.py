#!/usr/bin/env python3
"""Combine rankings, market ADP, league history, and explicit context into app data."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "Analysis" / "generated"
SOURCE = ROOT / "Analysis" / "source"
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
TEAM_ALIASES = {"ARZ": "ARI", "JAC": "JAX", "LVR": "LV", "RAM": "LAR"}


def parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def team_key(value):
    """Resolve a team abbreviation or full team name to the canonical abbreviation."""
    raw = str(value or "").strip()
    upper = TEAM_ALIASES.get(raw.upper(), raw.upper())
    if upper in TEAM_NAMES:
        return upper
    normalized = normalize(raw)
    return next((abbr for abbr, name in TEAM_NAMES.items() if normalize(name) == normalized), upper)


def is_structured_model_duplicate(signal):
    """Keep qualitative evidence visible without scoring a model already scored elsewhere."""
    source = normalize(signal.get("source_name", ""))
    url = str(signal.get("source_url", "")).lower()
    evidence = normalize(signal.get("evidence_type", ""))
    mechanism = normalize(signal.get("mechanism", ""))
    combined = " ".join((source, url, evidence, mechanism))
    duplicate_markers = (
        "injurypredictor", "injury-predictor", "rookiemodel", "nfl-rookie-model",
        "strengthofschedule", "strength-of-schedule", "superflexranking", "rankings/superflex",
    )
    return any(marker in combined for marker in duplicate_markers)


def prepare_signal(signal, rules, today):
    """Normalize classifier output and explain why a finding is or is not scoreable."""
    item = dict(signal)
    try:
        raw_adjustment = float(item.get("capped_adjustment", 0) or 0)
    except (TypeError, ValueError):
        raw_adjustment = 0.0
    single_cap = float(rules["maximum_single_context_adjustment"])
    item["capped_adjustment"] = round(max(-single_cap, min(single_cap, raw_adjustment)), 3)
    try:
        item["confidence"] = float(item.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        item["confidence"] = 0.0
    positions = item.get("affected_positions") or []
    item["affected_positions"] = [str(position).upper() for position in positions]
    status = str(item.get("status", "research_only")).lower()
    expiry = parse_datetime(item.get("expires_at"))
    expired = bool(expiry and expiry.date() < today)
    duplicate = is_structured_model_duplicate(item)
    below_threshold = item["confidence"] < float(rules["minimum_confidence_for_ranking_adjustment"])
    item["active"] = status == "approved" and not expired
    item["score_eligible"] = item["active"] and not duplicate and not below_threshold
    if expired:
        item["exclusion_reason"] = "expired"
    elif status != "approved":
        item["exclusion_reason"] = "research only; not approved for scoring"
    elif duplicate:
        item["exclusion_reason"] = "shown for research; already represented by a structured model"
    elif below_threshold:
        item["exclusion_reason"] = "research only; confidence is below the scoring threshold"
    else:
        item["exclusion_reason"] = None
    return item


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


def unique_signals(items):
    seen = set()
    result = []
    for item in items:
        identity = (item.get("entity_type"), item.get("entity"), item.get("source_url"), item.get("summary"))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def ourlads_name(raw_name: str) -> str:
    value = re.sub(r"\s+(?:\d{2}/\d|[UWTPC]/[A-Za-z]+|[SC]F\d+\*?)$", "", raw_name).strip()
    if "," in value:
        last, first = (part.strip() for part in value.split(",", 1))
        value = f"{first} {last}"
    return value.title()


def main() -> None:
    board = json.loads((GENERATED / "base_composite_board.json").read_text())
    public_adp = json.loads((GENERATED / "public_2qb_adp.json").read_text())
    draft = json.loads((ROOT / "Config" / "current_draft.json").read_text())
    policy = json.loads((ROOT / "Config" / "draft_policy.json").read_text())
    context = json.loads((ROOT / "Config" / "context_adjustments.json").read_text())
    classified_path = GENERATED / "classified_context.json"
    classified = json.loads(classified_path.read_text()) if classified_path.exists() else {"player_signals": [], "team_signals": []}
    history = json.loads((GENERATED / "historical_draft_analysis.json").read_text())
    current_context_path = GENERATED / "current_context.json"
    current_context = json.loads(current_context_path.read_text()) if current_context_path.exists() else {"sources": {}, "warnings": ["Context sources have not been refreshed."]}
    context_sources = current_context.get("sources", {})
    availability_paths = sorted(SOURCE.glob("verified_player_availability_*.json"))
    verified_availability = json.loads(availability_paths[-1].read_text()) if availability_paths else {"source": {}, "players": []}
    availability_by_name = {normalize(item["player"]): item for item in verified_availability.get("players", [])}
    rules = context["rules"]
    today = date.today()

    classified_players = defaultdict(list)
    classified_teams = defaultdict(list)
    for raw_signal in classified.get("player_signals", []):
        signal = prepare_signal(raw_signal, rules, today)
        classified_players[normalize(signal.get("entity", ""))].append(signal)
    for raw_signal in classified.get("team_signals", []):
        signal = prepare_signal(raw_signal, rules, today)
        classified_teams[team_key(signal.get("entity", ""))].append(signal)

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
    team_adjustments = defaultdict(list)
    for item in context["team_adjustments"]:
        team_adjustments[TEAM_ALIASES.get(item["team"], item["team"])].append(item)

    injury_by_name = {normalize(row["player"]): row for row in context_sources.get("draftsharks_injury", {}).get("players", [])}
    rookie_by_name = {normalize(row["player"]): row for row in context_sources.get("draftsharks_rookies", {}).get("players", [])}
    ds_by_name = {normalize(row["player"]): row for row in context_sources.get("draftsharks_superflex", {}).get("players", [])}
    news_by_name = defaultdict(list)
    for row in context_sources.get("rotowire_news", {}).get("items", []):
        news_by_name[normalize(row["player"])].append(row)
    sos_by_team = {TEAM_ALIASES.get(row["team"], row["team"]): row for row in context_sources.get("draftsharks_early_sos", {}).get("teams", [])}
    depth_by_name = defaultdict(list)
    depth_by_team = {}
    for team in context_sources.get("ourlads_depth_charts", {}).get("teams", []):
        team_abbr = TEAM_ALIASES.get(team["team"], team["team"])
        depth_by_team[team_abbr] = team
        for row in team["offense"]:
            for item in row["depth"]:
                depth_by_name[normalize(ourlads_name(item["raw_name"]))].append({
                    "team": team_abbr, "position": row["position"], **item
                })

    injury_groups = defaultdict(list)
    for row in injury_by_name.values():
        injury_groups[row["position"]].append(row["injury_probability"])
    for values in injury_groups.values():
        values.sort()

    def injury_percentile(row):
        if not row:
            return None
        values = injury_groups[row["position"]]
        below = sum(value <= row["injury_probability"] for value in values)
        return round(100 * below / len(values))

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
            "context": "not loaded"
        }
        injury = injury_by_name.get(key)
        if injury and not player.get("team"):
            player["team"] = TEAM_ALIASES.get(injury.get("team"), injury.get("team"))
        applicable_team_context = [item for item in team_adjustments.get(player.get("team"), [])
                                   if not item.get("positions") or player["position"] in item["positions"]]
        player["context"] = adjustments[key] + applicable_team_context
        team = team_key(player.get("team"))
        classified_matches = list(classified_players.get(key, []))
        classified_matches.extend(
            item for item in classified_teams.get(team, [])
            if not item.get("affected_positions") or player["position"] in item["affected_positions"]
        )
        applied_signals = [item for item in classified_matches if item["score_eligible"]]
        uncapped_context_total = sum(item["capped_adjustment"] for item in applied_signals)
        total_cap = float(rules["maximum_total_context_adjustment"])
        player["classified_context"] = {
            "applied": applied_signals,
            "research_only": [item for item in classified_matches if not item["score_eligible"]],
            "uncapped_total": round(uncapped_context_total, 3),
            "score_total": round(max(-total_cap, min(total_cap, uncapped_context_total)), 3),
            "was_total_capped": abs(uncapped_context_total) > total_cap,
        }
        classified_count = len(classified_matches)
        player["source_quality"]["context"] = "reviewed" if classified_count else "no additional reviewed notes"
        team_sos = sos_by_team.get(TEAM_ALIASES.get(player.get("team"), player.get("team")), {})
        if (player.get("bye") in (None, "")) and team_sos.get("bye"):
            player["bye"] = str(team_sos["bye"])
        player["models"] = {
            "injury": ({**injury, "risk_percentile_at_position": injury_percentile(injury)} if injury else None),
            "rookie": rookie_by_name.get(key),
            "early_sos": team_sos.get("positions", {}).get(player["position"]),
            "draftsharks_superflex": ds_by_name.get(key),
        }
        player["recent_news"] = news_by_name.get(key, [])[:3]
        availability_status = availability_by_name.get(key)
        player["availability_status"] = availability_status
        player["draft_eligible"] = availability_status.get("draft_eligible", True) if availability_status else True
        player["depth_chart"] = depth_by_name.get(key, [])
        player["research_links"] = {
            "fantasypros": adp_detail[key].get("fantasypros", {}).get("player_url"),
            "fantasyguru_projections": "https://www.fantasyguru.com/nfl-projections-offense",
            "draftsharks_injury": "https://www.draftsharks.com/injury-predictor",
            "draftsharks_rookie": "https://www.draftsharks.com/nfl-rookie-model",
            "draftsharks_sos": f"https://www.draftsharks.com/strength-of-schedule/{player['position'].lower()}",
            "draftsharks_superflex": "https://www.draftsharks.com/rankings/superflex",
        }
        players.append(player)

    players_by_name = {normalize(player["player"]): player for player in players}
    starting_qb_by_team = {}
    for abbreviation, depth in depth_by_team.items():
        qb_row = next((row for row in depth.get("offense", []) if row.get("position") == "QB"), None)
        if not qb_row or not qb_row.get("depth"):
            continue
        starter_name = ourlads_name(qb_row["depth"][0]["raw_name"])
        matched_qb = players_by_name.get(normalize(starter_name))
        starting_qb_by_team[abbreviation] = {
            "player": matched_qb["player"] if matched_qb else starter_name,
            "qb_chart_tier": matched_qb.get("qb_chart_tier") if matched_qb else None,
            "depth_chart_updated": depth.get("updated"),
            "source_name": "Ourlads depth chart + FantasyGuru 2QB chart",
            "source_url": "https://www.ourlads.com/nfldepthcharts/depthcharts.aspx",
        }
    for player in players:
        player["team_qb_context"] = starting_qb_by_team.get(player.get("team"))

    by_team = defaultdict(list)
    for player in players:
        if player.get("team") in TEAM_NAMES:
            by_team[player["team"]].append(player)
    teams = []
    for abbreviation, full_name in TEAM_NAMES.items():
        team_players = sorted(by_team[abbreviation], key=lambda p: p["base_composite_rank"])
        bye_values = [str(p["bye"]) for p in team_players if str(p.get("bye", "")).isdigit()]
        depth = depth_by_team.get(abbreviation)
        depth_rows = depth.get("offense", []) if depth else []
        starter_statuses = [row["depth"][0]["status"] for row in depth_rows if row.get("depth")]
        team_level_signals = classified_teams.get(abbreviation, [])
        player_level_signals = [
            {**item, "summary": f"{player['player']}: {item['summary']}"}
            for player in team_players
            for item in classified_players.get(normalize(player["player"]), [])
        ]
        sheet_signals = unique_signals(list(team_level_signals) + player_level_signals)
        teams.append({
            "abbreviation": abbreviation,
            "name": full_name,
            "bye": int(max(set(bye_values), key=bye_values.count)) if bye_values else None,
            "players": [{"player": p["player"], "position": p["position"], "rank": p["base_composite_rank"]} for p in team_players],
            "verified_notes": [item for item in sheet_signals if item["score_eligible"]],
            "research_only_notes": [item for item in sheet_signals if not item["score_eligible"]],
            "early_sos": sos_by_team.get(abbreviation, {}).get("positions", {}),
            "depth_chart": depth_rows,
            "depth_chart_updated": depth.get("updated") if depth else None,
            "offensive_starter_context": {
                "2026_acquisitions": starter_statuses.count("2026 acquisition"),
                "2026_draft_picks": starter_statuses.count("2026 draft pick"),
                "2026_undrafted_free_agents": starter_statuses.count("2026 undrafted free agent"),
                "injured_inactive": starter_statuses.count("injured/inactive"),
            },
            "source_links": {
                "coaching": "https://www.fantasyguru.com/2026-nfl-coaching-system-breakdowns",
                "personnel": "https://www.fantasyguru.com/nfl-personnel-tendencies-2026",
                "offensive_line": "https://www.fantasyguru.com/2026-offensive-line-breakdown",
                "depth_chart": "https://www.ourlads.com/nfldepthcharts/depthcharts.aspx"
            }
        })

    manager_tendencies = {}
    with (GENERATED / "manager_tendencies.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            manager_tendencies[row["manager"]] = row

    payload = {
        "generated": date.today().isoformat(),
        "status": "pre-draft; Stafford confirmed; other managers' keepers incomplete",
        "draft": draft,
        "policy": policy,
        "context_rules": rules,
        "classified_context": {
            "available": classified_path.exists(),
            "generated_at": classified.get("generated_at") or classified.get("generated"),
            "player_signal_count": len(classified.get("player_signals", [])),
            "team_signal_count": len(classified.get("team_signals", [])),
            "status_counts": classified.get("summary", {}).get("status_counts", {}),
            "authenticated_research_snapshot": classified.get("summary", {}).get("authenticated_research_snapshot", {}),
        },
        "source_freshness": {
            "market": public_adp["sources"],
            "context_retrieved": current_context.get("retrieved"),
            "context_warnings": current_context.get("warnings", []),
            "verified_availability": verified_availability.get("source", {}),
        },
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
