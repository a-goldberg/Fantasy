#!/usr/bin/env python3
"""Fail-fast checks for the generated draft assistant payload and static app."""

import json
import re
from collections import Counter
from pathlib import Path

from player_names import normalize_player_name

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
    normalized_names = [normalize_player_name(name) for name in names]
    assert len(normalized_names) == len(set(normalized_names)), "Duplicate aliased player identities"
    assert len(payload["teams"]) == 32, "Expected 32 NFL team sheets"
    assert all(player["position"] in {"QB", "RB", "WR", "TE", "K", "DST"} for player in players)
    assert not any(player["position_conflict"] for player in players), "Unresolved position conflict"
    assert sum(player["adp"] is not None for player in players) >= 220, "Public ADP match rate regressed"
    assert sum(player.get("models", {}).get("injury") is not None for player in players) >= 200, "Injury-model match rate regressed"
    assert sum(player.get("models", {}).get("early_sos") is not None for player in players) >= 200, "Early-SOS match rate regressed"
    assert sum(bool(player.get("depth_chart")) for player in players) >= 180, "Depth-chart match rate regressed"
    assert sum(player.get("draftsheets_position_tier") not in (None, "") for player in players) >= 230, "DraftSheets positional-tier coverage regressed"
    assert sum(player.get("rotoballer_rank") not in (None, "") for player in players) >= 390, "RotoBaller Superflex rank coverage regressed"
    expert_meta = payload["source_freshness"]["expert_rankings"]
    assert expert_meta["rank_horizon"] == 200, "Expert ranks must use the fixed 200-player horizon"
    assert "rotoballer_superflex_rank" in expert_meta["weights"], "RotoBaller weight missing from runtime metadata"
    assert sum(bool((player.get("team_qb_context") or {}).get("qb_chart_tier")) for player in players if player["position"] != "QB") >= 150, "Team-QB tier coverage regressed"
    qb_context_names = [(player.get("team_qb_context") or {}).get("player", "") for player in players]
    assert not any(re.search(r"\b(?:\d{2}/\d{1,2}|[A-Z]{1,3}/[A-Z]{2,3}|(?:CF|SF)\d{2})\*?\b", name, re.I) for name in qb_context_names), "Ourlads identifiers leaked into displayed QB names"
    pit_contexts = [player.get("team_qb_context") for player in players if player.get("team") == "PIT" and player["position"] != "QB"]
    assert pit_contexts and all(context and context.get("player") == "Aaron Rodgers" and context.get("qb_chart_tier") for context in pit_contexts), "Pittsburgh team-QB context did not reconcile Aaron Rodgers"
    min_contexts = [player.get("team_qb_context") for player in players if player.get("team") == "MIN" and player["position"] != "QB"]
    assert min_contexts and all(context and context.get("player") == "Kyler Murray" and context.get("qb_chart_tier") for context in min_contexts), "Minnesota team-QB context did not reconcile Kyler Murray"
    terrance_ferguson = next(player for player in players if player["player"] == "Terrance Ferguson")
    assert terrance_ferguson.get("team") == "LAR" and terrance_ferguson.get("bye"), "Ourlads depth matching did not enrich Terrance Ferguson's team and bye"
    assert (terrance_ferguson.get("team_qb_context") or {}).get("player") == "Matthew Stafford", "Terrance Ferguson did not inherit the Rams QB context"
    gainwells = [player for player in players if normalize_player_name(player["player"]) == "kennethgainwell"]
    assert len(gainwells) == 1, "Kenny and Kenneth Gainwell must resolve to one player"
    gainwell = gainwells[0]
    assert gainwell["source_count"] >= 3, "Gainwell's expert ranks did not merge"
    assert gainwell.get("adp") is not None, "Gainwell's market ADP did not merge"
    assert gainwell.get("models", {}).get("injury") is not None, "Gainwell's Kenneth-keyed injury model did not merge"
    rb_handcuff_players = [player for player in players if player.get("rb_handcuff")]
    assert len(rb_handcuff_players) >= 28, "FantasyGuru RB handcuff coverage regressed"
    ray_davis = next(player for player in players if player["player"] == "Ray Davis")
    assert ray_davis["rb_handcuff"]["starter"] == "James Cook III", "RB grid did not reconcile James Cook's canonical name"
    assert ray_davis["rb_handcuff"]["source_name"] == "RB-Grid-August", "RB handcuff provenance is missing"
    for player_name in ("Denzel Boston", "KC Concepcion", "Terrance Ferguson"):
        corrected_player = next(player for player in players if player["player"] == player_name)
        assert corrected_player["source_count"] >= 2, f"{player_name} should have complementary expert coverage"
        if player_name != "Terrance Ferguson":
            assert corrected_player["source_quality"]["market_disagreement"] > 30, f"{player_name} must expose conflicting ADP inputs"
            assert corrected_player["source_quality"]["market"] == "low", f"{player_name} conflicting ADP must not be labeled high confidence"

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
    expected_keepers = {
        32: ("Nalick", "Zay Flowers"),
        56: ("Jeff", "Colston Loveland"),
        58: ("Greenspan", "Bo Nix"),
        59: ("Tompkins", "Brock Bowers"),
        64: ("Goldberg", "Matthew Stafford"),
        66: ("Joshua", "Drake Maye"),
        74: ("Big Leiber", "Ladd McConkey"),
        76: ("Jeff", "Cam Skattebo"),
        81: ("Ori", "Jaxson Dart"),
        94: ("Big Leiber", "Travis Etienne Jr."),
        95: ("Joshua", "Sam Darnold"),
        100: ("Ori", "Jordan Addison"),
        102: ("Tompkins", "Javonte Williams"),
        118: ("Greenspan", "Quinshon Judkins"),
    }
    actual_keepers = {
        item["overall_pick"]: (item["manager"], item["player"])
        for item in payload["draft"]["keepers"]
    }
    assert actual_keepers == expected_keepers, "Keeper declarations or costs do not match the confirmed league list"
    assert not payload["draft"]["unknown_inputs"], "Keeper input should be complete"
    assert all(item["status"] == "confirmed" for item in payload["draft"]["keepers"])
    assert all(owner_at(pick, order, trades) == manager for pick, (manager, _) in expected_keepers.items()), "A keeper was assigned to a pick not owned by its manager"
    assert next(player for player in players if player["player"] == "Matthew Stafford")["position"] == "QB"
    unavailable_on_board = {
        player["player"]: player
        for player in players
        if player["player"] in {"Ricky Pearsall", "Jayden Higgins", "Calvin Austin III"}
    }
    assert "Calvin Austin III" in unavailable_on_board, "Current ranked player Calvin Austin III is missing from the board"
    for unavailable_name, unavailable in unavailable_on_board.items():
        assert unavailable["draft_eligible"] is False, f"{unavailable_name} must be excluded after verified season-ending news"
        assert unavailable["availability_status"]["source_name"] == "NFL.com"

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
        "confirmed_keepers": len(actual_keepers),
        "traded_picks": {"116": owner_at(116, order, trades), "168": owner_at(168, order, trades)},
        "status": "PASS"
    }, indent=2, default=dict))


if __name__ == "__main__":
    main()
