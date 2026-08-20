#!/usr/bin/env python3
"""Classify context snapshots into conservative, auditable fantasy signals.

This stage does not reinterpret the structured DraftSharks models, which are
already scored elsewhere.  It promotes only explicit news/depth-chart facts to
candidate signals and accepts human-reviewed config entries as approved.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "Analysis" / "generated" / "current_context.json"
ADJUSTMENTS_PATH = ROOT / "Config" / "context_adjustments.json"
BOARD_PATH = ROOT / "Analysis" / "generated" / "base_composite_board.json"
OUTPUT_PATH = ROOT / "Analysis" / "generated" / "classified_context.json"
SOURCE_DIR = ROOT / "Analysis" / "source"

REQUIRED_SIGNAL_FIELDS = {
    "entity_type", "entity", "affected_positions", "signal_class", "summary",
    "mechanism", "direction", "raw_adjustment", "capped_adjustment",
    "confidence", "source_name", "source_url", "published_at", "retrieved_at",
    "expires_at", "evidence_type", "status",
}
VALID_CLASSES = {"role", "health", "environment", "scheme", "development", "narrative"}
VALID_STATUSES = {"approved", "candidate", "research_only"}
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}
POSITION_MAP = {"LWR": "WR", "RWR": "WR", "SWR": "WR"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any, fallback: str) -> datetime:
    if not value:
        value = fallback
    text = str(value).strip()
    for pattern in ("%B %d, %Y", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%m/%d/%Y %I:%M%p"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return datetime.fromisoformat(fallback.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower().replace("’", "'")
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


def ourlads_name(raw: str) -> str:
    value = re.sub(r"\s+(?:\d{2}/\d|[A-Z]{1,3}/[^ ]+|[A-Z]{1,3}\d{2})\*?$", "", raw.strip(), flags=re.I)
    if "," not in value:
        return value.title()
    surname, given = (part.strip() for part in value.split(",", 1))
    return f"{given.title()} {surname.title()}"


def player_index() -> dict[str, dict[str, Any]]:
    board = json.loads(BOARD_PATH.read_text())
    return {normalized_name(row["player"]): row for row in board["players"]}


def signal(
    *, entity_type: str, entity: str, affected_positions: list[str], signal_class: str,
    summary: str, mechanism: str, direction: int, raw_adjustment: float,
    confidence: float, source_name: str, source_url: str, published_at: str,
    retrieved_at: str, expires_at: str, evidence_type: str, status: str,
    cap: float = 4.0,
) -> dict[str, Any]:
    capped = max(-cap, min(cap, raw_adjustment)) if status != "research_only" else 0.0
    return {
        "entity_type": entity_type,
        "entity": entity,
        "affected_positions": sorted(set(affected_positions)),
        "signal_class": signal_class,
        "summary": summary,
        "mechanism": mechanism,
        "direction": direction,
        "raw_adjustment": round(float(raw_adjustment), 3),
        "capped_adjustment": round(float(capped), 3),
        "confidence": round(float(confidence), 3),
        "source_name": source_name,
        "source_url": source_url,
        "published_at": published_at,
        "retrieved_at": retrieved_at,
        "expires_at": expires_at,
        "evidence_type": evidence_type,
        "status": status,
    }


def rejection(source: str, entity: str | None, summary: str, reason: str, url: str | None = None) -> dict[str, Any]:
    return {"source_name": source, "entity": entity, "summary": summary, "reason": reason, "source_url": url}


def classify_rotowire(source: dict[str, Any], players: dict[str, dict[str, Any]], snapshot: str):
    signals, rejected = [], []
    seen_health_events: set[tuple[str, str]] = set()
    positive = re.compile(r"\b(return(?:s|ed)?|participat(?:e|ed|es)|takes? part|works? in (?:team|7-on-7|11-on-11) drills|full practice)\b", re.I)
    negative = re.compile(r"\b(sidelined|sits? out|sitting out|held out|won't practice|will not practice|won't participate|will not participate|not participating|will miss|miss(?:es|ing)? practice|wasn't spotted|not spotted|may not practice|unsure if .* play)\b", re.I)
    role = re.compile(r"\b(claimed .+ job|wins? .+ competition|will be released|cutting|share .+ work|50-50.+split)\b", re.I)
    speculative = re.compile(r"\b(predicts?|seem likely|could|may|expected)\b", re.I)
    uncertain_status = re.compile(r"\b(could|may|unsure|not spotted|wasn't spotted|own pace|side field|in attendance|suited up|appears prepared)\b", re.I)
    for item in source.get("items", []):
        player = players.get(normalized_name(item.get("player", "")))
        combined = f"{item.get('headline', '')}. {item.get('update', '')}"
        url = item.get("headline_url") or source.get("source_url")
        if not player:
            rejected.append(rejection("RotoWire", item.get("player"), item.get("headline", ""), "Player is not on the current draft board.", url))
            continue
        if re.search(r"\bpreseason\b", combined, re.I) and re.search(r"\b(rest(?:ed|ing)?|key starters?|sit(?:s|ting)? out)\b", combined, re.I):
            rejected.append(rejection("RotoWire", player["player"], item.get("headline", ""), "Preseason rest is not a regular-season availability downgrade.", url))
            continue
        event = parse_date(item.get("date"), snapshot)
        published = iso(event)
        expires = iso(event + timedelta(days=21))
        position = player["position"]
        if role.search(combined):
            is_speculative = bool(speculative.search(combined))
            direction = -1 if re.search(r"released|cutting", combined, re.I) else (0 if "share" in combined.lower() or "split" in combined.lower() else 1)
            raw = -1.5 if direction < 0 else (0 if direction == 0 else 1.25)
            confidence = 0.55 if is_speculative else 0.78
            status = "research_only" if is_speculative or direction == 0 else "approved"
            signals.append(signal(
                entity_type="player", entity=player["player"], affected_positions=[position], signal_class="role",
                summary=item["headline"], mechanism="The report directly addresses roster status or workload, but downstream fantasy volume is not assumed.",
                direction=direction, raw_adjustment=raw, confidence=confidence, source_name="RotoWire", source_url=url,
                published_at=published, retrieved_at=source.get("retrieved", snapshot), expires_at=expires,
                evidence_type="attributed_report", status=status, cap=1.5,
            ))
        elif item.get("injury") or positive.search(combined) or negative.search(combined):
            neg = bool(negative.search(combined))
            # Negated participation phrases contain the positive token
            # "participate". An explicit absence takes precedence.
            pos = bool(positive.search(combined)) and not neg
            if pos == neg:
                rejected.append(rejection("RotoWire", player["player"], item.get("headline", ""), "Injury/status wording does not establish a clear availability direction.", url))
                continue
            # The feed often publishes several incremental practice blurbs about
            # the same injury on the same day. Keep the first (newest) explicit
            # direction so one underlying event cannot be counted repeatedly.
            injury_key = re.sub(r"[^a-z0-9]", "", (item.get("injury") or "status").lower())
            event_key = (normalized_name(player["player"]), injury_key)
            if event_key in seen_health_events:
                rejected.append(rejection("RotoWire", player["player"], item.get("headline", ""), "Duplicate same-player, same-status event from the same day.", url))
                continue
            seen_health_events.add(event_key)
            non_contact = bool(re.search(r"non-contact", combined, re.I))
            confidence = 0.68 if non_contact else 0.72
            raw = (0.5 if non_contact else 0.75) * (1 if pos else -1)
            # Auto-approval is intentionally narrow: an attributed report must
            # state an actual participation/absence direction without hedging.
            # The signal expires quickly and never exceeds one point.
            status = "approved" if confidence >= 0.70 and not uncertain_status.search(combined) else "candidate"
            signals.append(signal(
                entity_type="player", entity=player["player"], affected_positions=[position], signal_class="health",
                summary=item["headline"], mechanism="Practice participation or absence is an availability signal; it does not establish a regular-season workload or recovery timetable.",
                direction=1 if pos else -1, raw_adjustment=raw, confidence=confidence, source_name="RotoWire", source_url=url,
                published_at=published, retrieved_at=source.get("retrieved", snapshot), expires_at=expires,
                evidence_type="attributed_practice_or_injury_report", status=status, cap=1.0,
            ))
        else:
            rejected.append(rejection("RotoWire", player["player"], item.get("headline", ""), "General news has no explicit, supported availability or role effect.", url))
    return signals, rejected


def classify_ourlads(source: dict[str, Any], players: dict[str, dict[str, Any]], snapshot: str):
    signals, rejected = [], []
    relevant_statuses = {"injured/inactive", "2026 draft pick", "2026 undrafted free agent", "2026 acquisition"}
    for team in source.get("teams", []):
        event = parse_date(team.get("updated"), snapshot)
        for group in team.get("offense", []):
            position = POSITION_MAP.get(group.get("position"), group.get("position"))
            if position not in FANTASY_POSITIONS:
                continue
            for row in group.get("depth", []):
                if row.get("depth", 99) > 2 or row.get("status") not in relevant_statuses:
                    continue
                parsed = ourlads_name(row.get("raw_name", ""))
                player = players.get(normalized_name(parsed))
                if not player:
                    rejected.append(rejection("Ourlads", parsed, f"{team['team']} {group['position']} depth {row.get('depth')}: {row.get('status')}", "Depth-chart player is not on the current draft board.", row.get("player_url")))
                    continue
                status = row["status"]
                is_health = status == "injured/inactive"
                signals.append(signal(
                    entity_type="player", entity=player["player"], affected_positions=[player["position"]],
                    signal_class="health" if is_health else ("development" if "draft pick" in status or "undrafted" in status else "role"),
                    summary=f"Listed at {group['position']} depth {row['depth']} and marked {status}.",
                    mechanism="This is a factual depth-chart marker. It does not by itself establish severity, workload, efficiency, or fantasy direction.",
                    direction=0, raw_adjustment=0, confidence=0.66 if is_health else 0.62,
                    source_name="Ourlads", source_url=row.get("player_url") or source.get("source_url"),
                    published_at=iso(event), retrieved_at=source.get("retrieved", snapshot),
                    expires_at=iso(event + timedelta(days=14)), evidence_type="depth_chart_marker", status="candidate",
                ))
    return signals, rejected


def classify_manual(config: dict[str, Any], snapshot: str):
    signals, rejected = [], []
    cap = float(config.get("rules", {}).get("maximum_single_context_adjustment", 4))
    threshold = float(config.get("rules", {}).get("minimum_confidence_for_ranking_adjustment", 0.6))
    for entity_type, key in (("player", "player_adjustments"), ("team", "team_adjustments")):
        for item in config.get(key, []):
            entity = item.get("entity") or item.get("player") or item.get("team")
            missing = [field for field in ("summary", "mechanism", "signal_class", "source_name", "source_url", "published_at", "confidence", "adjustment") if item.get(field) is None]
            if not entity or missing:
                rejected.append(rejection("Manual adjustment", entity, item.get("summary", "Invalid manual adjustment"), f"Missing required fields: {', '.join(missing) if missing else 'entity'}", item.get("source_url")))
                continue
            confidence = float(item["confidence"])
            raw = float(item["adjustment"])
            approved = confidence >= threshold and item.get("status", "approved") == "approved"
            published = parse_date(item["published_at"], snapshot)
            expires = parse_date(item.get("expires_at"), iso(published + timedelta(days=30)))
            signals.append(signal(
                entity_type=entity_type, entity=entity,
                affected_positions=item.get("affected_positions", [item.get("position")] if item.get("position") else []),
                signal_class=item["signal_class"], summary=item["summary"], mechanism=item["mechanism"],
                direction=0 if raw == 0 else (1 if raw > 0 else -1), raw_adjustment=raw,
                confidence=confidence, source_name=item["source_name"], source_url=item["source_url"],
                published_at=iso(published), retrieved_at=item.get("retrieved_at", snapshot), expires_at=iso(expires),
                evidence_type=item.get("evidence_type", "human_reviewed_source"), status="approved" if approved else "research_only", cap=cap,
            ))
    return signals, rejected


def latest_source(pattern: str) -> Path | None:
    matches = sorted(SOURCE_DIR.glob(pattern))
    return matches[-1] if matches else None


def latest_fantasyguru_sources() -> list[Path]:
    """Return the newest snapshot from each authenticated research track."""
    paths = []
    for pattern in ("fantasyguru_qualitative_context_*.json", "fantasyguru_coaching_context_*.json", "fantasyguru_oline_context_*.json"):
        path = latest_source(pattern)
        if path:
            paths.append(path)
    return paths


def classify_reviewed_fantasyguru(players: dict[str, dict[str, Any]], snapshot: str):
    """Import the newest authenticated snapshot from every research track."""
    signals, rejected = [], []
    paths = latest_fantasyguru_sources()
    if not paths:
        return signals, [rejection("FantasyGuru authenticated research", None, "No qualitative snapshot found.", "Authenticated research has not been imported.")]
    direction_map = {"positive": 1, "negative": -1, "neutral": 0, 1: 1, -1: -1, 0: 0}
    items = []
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get("status") != "available":
            rejected.append(rejection("FantasyGuru authenticated research", None, f"Snapshot unavailable: {path.name}", payload.get("method_note", "Authenticated research was unavailable.")))
            continue
        items.extend(payload.get("signals", []))
    # A newer dedicated research track supersedes an older selective note from
    # the same article for the same entity/class. Do not let a rewritten
    # summary count the same evidence twice.
    deduped_items = {}
    for item in items:
        key = (
            item.get("entity_type"), normalized_name(str(item.get("entity", ""))),
            item.get("source_url"), item.get("signal_class"),
        )
        previous = deduped_items.get(key)
        if not previous or str(item.get("retrieved_at") or "") >= str(previous.get("retrieved_at") or ""):
            deduped_items[key] = item
    items = list(deduped_items.values())
    for item in items:
        entity_type = item.get("entity_type")
        entity = item.get("entity")
        missing = [field for field in (
            "entity_type", "entity", "signal_class", "summary", "mechanism", "direction",
            "raw_adjustment", "confidence", "source_name", "source_url", "retrieved_at", "expires_at",
            "evidence_type", "status",
        ) if item.get(field) is None]
        if missing:
            rejected.append(rejection("FantasyGuru authenticated research", entity, item.get("summary", "Invalid reviewed finding"), f"Missing required fields: {', '.join(missing)}", item.get("source_url")))
            continue
        if entity_type == "player" and normalized_name(entity) not in players:
            rejected.append(rejection(item["source_name"], entity, item["summary"], "Player is not on the current draft board.", item["source_url"]))
            continue
        if entity_type not in {"player", "team"}:
            rejected.append(rejection(item["source_name"], entity, item["summary"], "Unsupported entity type.", item["source_url"]))
            continue
        direction = direction_map.get(item["direction"])
        raw = float(item["raw_adjustment"])
        confidence = float(item["confidence"])
        if direction is None or (raw != 0 and direction != (1 if raw > 0 else -1)):
            rejected.append(rejection(item["source_name"], entity, item["summary"], "Direction and adjustment disagree.", item["source_url"]))
            continue
        approved = item["status"] == "reviewed" and confidence >= 0.6 and direction != 0
        signals.append(signal(
            entity_type=entity_type, entity=entity,
            affected_positions=item.get("affected_positions", []), signal_class=item["signal_class"],
            summary=item["summary"], mechanism=item["mechanism"], direction=direction,
            raw_adjustment=raw, confidence=confidence, source_name=item["source_name"],
            source_url=item["source_url"], published_at=item.get("published_at"),
            retrieved_at=item.get("retrieved_at", snapshot), expires_at=item["expires_at"],
            evidence_type=item["evidence_type"], status="approved" if approved else "research_only",
            cap=1.5,
        ))
    return signals, rejected


def validate(output: dict[str, Any]) -> None:
    for key in ("generated_at", "source_snapshot_retrieved", "player_signals", "team_signals", "rejected_signals", "summary"):
        assert key in output, f"missing top-level field: {key}"
    identities = set()
    for row in output["player_signals"] + output["team_signals"]:
        missing = REQUIRED_SIGNAL_FIELDS - row.keys()
        assert not missing, f"{row.get('entity')} missing {sorted(missing)}"
        assert row["entity_type"] in {"player", "team"}
        assert row["signal_class"] in VALID_CLASSES
        assert row["status"] in VALID_STATUSES
        assert row["direction"] in {-1, 0, 1}
        assert 0 <= row["confidence"] <= 1
        assert abs(row["capped_adjustment"]) <= 4
        if row["status"] == "research_only":
            assert row["capped_adjustment"] == 0
        identity = (row["entity_type"], row["entity"], row["source_url"], row["summary"])
        assert identity not in identities, f"duplicate signal: {identity}"
        identities.add(identity)
    assert output["player_signals"] == sorted(output["player_signals"], key=sort_key)
    assert output["team_signals"] == sorted(output["team_signals"], key=sort_key)


def sort_key(row: dict[str, Any]):
    return (row["entity"].casefold(), row["signal_class"], row["source_name"], row.get("published_at") or "", row["summary"])


def build() -> dict[str, Any]:
    context = json.loads(CONTEXT_PATH.read_text())
    config = json.loads(ADJUSTMENTS_PATH.read_text())
    players = player_index()
    snapshot = context["retrieved"]
    all_signals, rejected = [], []

    rw_signals, rw_rejected = classify_rotowire(context.get("sources", {}).get("rotowire_news", {}), players, snapshot)
    ol_signals, ol_rejected = classify_ourlads(context.get("sources", {}).get("ourlads_depth_charts", {}), players, snapshot)
    manual_signals, manual_rejected = classify_manual(config, snapshot)
    guru_signals, guru_rejected = classify_reviewed_fantasyguru(players, snapshot)
    guru_paths = latest_fantasyguru_sources()
    guru_snapshots = [json.loads(path.read_text()) for path in guru_paths]
    all_signals.extend(rw_signals + ol_signals + manual_signals + guru_signals)
    rejected.extend(rw_rejected + ol_rejected + manual_rejected + guru_rejected)

    # ESPN's general NFL feed is retained for research discovery, never converted
    # into player/team causality without a later human-reviewed adjustment.
    espn = context.get("sources", {}).get("espn_news", {})
    for item in espn.get("items", []):
        rejected.append(rejection("ESPN NFL News", None, item.get("title", ""), "General headline is research-only; no explicit player/position mechanism was reviewed.", item.get("link")))

    player_signals = sorted((row for row in all_signals if row["entity_type"] == "player"), key=sort_key)
    team_signals = sorted((row for row in all_signals if row["entity_type"] == "team"), key=sort_key)
    rejected.sort(key=lambda row: ((row.get("source_name") or "").casefold(), (row.get("entity") or "").casefold(), row.get("summary") or ""))
    status_counts = {status: sum(row["status"] == status for row in all_signals) for status in sorted(VALID_STATUSES)}
    output = {
        "generated_at": utc_now(),
        "source_snapshot_retrieved": snapshot,
        "player_signals": player_signals,
        "team_signals": team_signals,
        "rejected_signals": rejected,
        "summary": {
            "player_signal_count": len(player_signals),
            "team_signal_count": len(team_signals),
            "status_counts": status_counts,
            "rejected_count": len(rejected),
            "structured_models_not_duplicated": {
                key: len(context.get("sources", {}).get(key, {}).get(collection, []))
                for key, collection in (("draftsharks_injury", "players"), ("draftsharks_rookies", "players"), ("draftsharks_early_sos", "teams"), ("draftsharks_superflex", "players"))
            },
            "authenticated_research_snapshot": {
                "files": [path.name for path in guru_paths],
                "status": "available" if guru_snapshots and all(row.get("status") == "available" for row in guru_snapshots) else "missing_or_partial",
                "retrieved_at": max((row.get("retrieved_at") or "" for row in guru_snapshots), default=None),
                "signal_count": sum(len(row.get("signals", [])) for row in guru_snapshots),
            },
            "automatic_scoring_policy": "Approved manual signals, authenticated human-reviewed FantasyGuru findings, and concrete non-speculative RotoWire availability/job facts are ranking-ready. Candidate depth-chart or hedged news facts require review; research_only signals score zero.",
        },
    }
    validate(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        output = json.loads(OUTPUT_PATH.read_text())
    else:
        output = build()
        OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n")
    validate(output)
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
