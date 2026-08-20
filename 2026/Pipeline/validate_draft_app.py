#!/usr/bin/env python3
"""Fail-fast checks for the generated draft assistant payload and static app."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "App" / "data" / "draft-board.json"
CLASSIFIED = ROOT / "Analysis" / "generated" / "classified_context.json"
SIGNAL_FIELDS = {
    "entity_type", "entity", "affected_positions", "signal_class", "summary", "mechanism",
    "direction", "capped_adjustment", "confidence", "source_name", "source_url",
    "published_at", "retrieved_at", "expires_at", "evidence_type", "status",
}


def owner_at(overall, order, trades=()):
    trade = next((item for item in trades if item["overall_pick"] == overall), None)
    if trade:
        return trade["new_manager"]
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
    assert sum(player.get("models", {}).get("injury") is not None for player in players) >= 200, "Injury-model match rate regressed"
    assert sum(player.get("models", {}).get("early_sos") is not None for player in players) >= 200, "Early-SOS match rate regressed"
    assert sum(bool(player.get("depth_chart")) for player in players) >= 180, "Depth-chart match rate regressed"
    assert sum(player.get("draftsheets_position_tier") not in (None, "") for player in players) >= 230, "DraftSheets positional-tier coverage regressed"
    assert sum(bool((player.get("team_qb_context") or {}).get("qb_chart_tier")) for player in players if player["position"] != "QB") >= 150, "Team-QB tier coverage regressed"

    rules = payload["context_rules"]
    policy = payload["policy"]
    assert int(policy["hard_constraints"]["maximum_qb"]) == 4, "Recommendation policy must prohibit a fifth QB"
    fourth_qb = policy["soft_targets"]["fourth_qb"]
    assert int(fourth_qb["earliest_round"]) >= 10, "Fourth-QB recommendations must remain late-round options"
    assert fourth_qb["recommendation_columns"] == ["wildcard"], "A fourth QB should be a wildcard only"
    assert int(fourth_qb["required_roster_before"]["WR"]) >= 5, "Fourth QB cannot displace required WR depth"
    single_cap = float(rules["maximum_single_context_adjustment"])
    total_cap = float(rules["maximum_total_context_adjustment"])
    applied_count = 0
    research_only_count = 0
    for player in players:
        classified_context = player.get("classified_context")
        assert isinstance(classified_context, dict), f"Missing classified context container for {player['player']}"
        applied = classified_context.get("applied", [])
        research_only = classified_context.get("research_only", [])
        applied_count += len(applied)
        research_only_count += len(research_only)
        assert all(item.get("active") and item.get("score_eligible") for item in applied), "Non-scoreable signal in applied context"
        assert all(not item.get("score_eligible") for item in research_only), "Scoreable signal incorrectly labeled research-only"
        assert all(abs(float(item["capped_adjustment"])) <= single_cap for item in applied + research_only), "Single context cap exceeded"
        raw_total = sum(float(item["capped_adjustment"]) for item in applied)
        expected_total = max(-total_cap, min(total_cap, raw_total))
        assert abs(float(classified_context["score_total"]) - expected_total) < 1e-6, "Total context cap mismatch"
        assert abs(float(classified_context["score_total"])) <= total_cap, "Total context cap exceeded"

    team_note_count = 0
    teams_with_context = 0
    for team in payload["teams"]:
        notes = team.get("verified_notes", []) + team.get("research_only_notes", [])
        if notes:
            teams_with_context += 1
        team_note_count += len(notes)
        assert all(abs(float(item["capped_adjustment"])) <= single_cap for item in notes), "Team-sheet context cap exceeded"
        assert all(item.get("score_eligible") for item in team.get("verified_notes", [])), "Unscored note shown as applied on a team sheet"
        assert all(not item.get("score_eligible") for item in team.get("research_only_notes", [])), "Scoreable note shown as research-only on a team sheet"

    if CLASSIFIED.exists():
        classified = json.loads(CLASSIFIED.read_text())
        assert isinstance(classified.get("player_signals"), list) and isinstance(classified.get("team_signals"), list)
        for signal in classified["player_signals"] + classified["team_signals"]:
            assert SIGNAL_FIELDS <= signal.keys(), f"Classified signal is missing fields: {SIGNAL_FIELDS - signal.keys()}"
            assert signal["entity_type"] in {"player", "team"}
            assert isinstance(signal["affected_positions"], list)
            assert 0 <= float(signal["confidence"]) <= 1
            assert abs(float(signal["capped_adjustment"])) <= single_cap, "Classifier emitted an adjustment above the configured cap"

    order = payload["draft"]["draft_order"]
    trades = payload["draft"]["traded_picks"]
    goldberg_picks = [pick for pick in range(1, 171) if owner_at(pick, order, trades) == "Goldberg"]
    assert goldberg_picks == [4,17,24,37,44,57,64,77,84,97,104,117,124,137,144,157,164]
    assert owner_at(116, order, trades) == "Barry", "Barry should own Jeff's round 12 pick"
    assert owner_at(168, order, trades) == "Jeff", "Jeff should own Barry's round 17 pick"
    assert Counter(item["new_manager"] for item in trades) == Counter({"Barry": 1, "Jeff": 1})
    stafford = next(player for player in players if player["player"] == "Matthew Stafford")
    pearsall = next(player for player in players if player["player"] == "Ricky Pearsall")
    keeper = payload["draft"]["keepers"][0]
    assert keeper["player"] == "Matthew Stafford" and keeper["overall_pick"] == 64
    assert keeper["status"] == "confirmed"
    assert stafford["position"] == "QB"
    assert pearsall["draft_eligible"] is False, "Ricky Pearsall must be excluded after verified season-ending IR"
    assert pearsall["availability_status"]["source_name"] == "NFL.com"

    positions = Counter(player["position"] for player in players)
    print(json.dumps({
        "players": len(players),
        "adp_matches": sum(player["adp"] is not None for player in players),
        "injury_model_matches": sum(player.get("models", {}).get("injury") is not None for player in players),
        "early_sos_matches": sum(player.get("models", {}).get("early_sos") is not None for player in players),
        "depth_chart_matches": sum(bool(player.get("depth_chart")) for player in players),
        "draftsheets_tier_matches": sum(player.get("draftsheets_position_tier") not in (None, "") for player in players),
        "team_qb_tier_matches": sum(bool((player.get("team_qb_context") or {}).get("qb_chart_tier")) for player in players if player["position"] != "QB"),
        "classified_context": {
            "source_available": CLASSIFIED.exists(),
            "applied_signal_matches": applied_count,
            "research_only_signal_matches": research_only_count,
            "team_sheet_note_matches": team_note_count,
            "teams_with_context": teams_with_context,
        },
        "teams": len(payload["teams"]),
        "positions": positions,
        "goldberg_picks": goldberg_picks,
        "confirmed_keeper": f"{keeper['player']} at {keeper['overall_pick']}",
        "traded_picks": {"116": owner_at(116, order, trades), "168": owner_at(168, order, trades)},
        "status": "PASS"
    }, indent=2, default=dict))


if __name__ == "__main__":
    main()
