#!/usr/bin/env python3
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "past_draft_results_corrected.json"
PLAYERS = Path("/private/tmp/nflverse_players.csv")
OUT = ROOT / "generated"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = [str(y) for y in range(2018, 2026)]
MANAGERS = ["Ori", "Tompkins", "Greenspan", "Goldberg", "Jeff", "Danziger", "Joshua", "Big Leiber", "Barry", "Nalick", "Abe"]
DEF_NAMES = {
    "arizona","atlanta","baltimore","buffalo","carolina","chicago","cincinnati","cleveland",
    "dallas","denver","detroit","green bay","houston","indianapolis","jacksonville","kansas city",
    "las vegas","los angeles","miami","minnesota","new england","new orleans","new york",
    "philadelphia","pittsburgh","san francisco","seattle","tampa bay","tennessee","washington",
    "broncos","steelers","texans","eagles","vikings","ravens","chiefs","bills","commanders","packers"
}
POSITION_ALIASES = {
    "hollywoodbrown": "WR",
    "nyheimmillerhines": "RB",
    "joshuapalmer": "WR",
    "travishunter": "WR",
}

def norm(value):
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = value.lower().replace("’", "'")
    value = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value

def load_positions():
    by_name = defaultdict(Counter)
    with PLAYERS.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = norm(row.get("display_name"))
            group = (row.get("position_group") or "").upper()
            detail = (row.get("position") or "").upper()
            pos = group if group in {"QB","RB","WR","TE","K"} else detail
            if pos in {"QB","RB","WR","TE","K"} and name:
                by_name[name][pos] += 1
    return {name: counts.most_common(1)[0][0] for name, counts in by_name.items()}

def classify(name, positions):
    if name == "--empty--":
        return "EMPTY"
    if name.lower() in DEF_NAMES:
        return "DST"
    key = norm(name)
    return POSITION_ALIASES.get(key, positions.get(key, "UNKNOWN"))

def infer_home_slots(rows):
    # Transform each physical board position back to its nominal snake slot.
    counts = defaultdict(Counter)
    for r in rows:
        slot = r["pick_in_round"] if r["round"] % 2 else 11 - r["pick_in_round"]
        counts[r["manager"]][slot] += 1
    managers = sorted(counts)
    # Small exact assignment: dynamic programming over 10 slots.
    states = {0: (0, {})}
    for manager in managers:
        nxt = {}
        for mask, (score, assign) in states.items():
            for slot in range(1, 11):
                bit = 1 << (slot - 1)
                if mask & bit:
                    continue
                cand = score + counts[manager][slot]
                newmask = mask | bit
                if newmask not in nxt or cand > nxt[newmask][0]:
                    nxt[newmask] = (cand, {**assign, manager: slot})
        states = nxt
    return max(states.values(), key=lambda x: x[0])[1]

raw = json.loads(SOURCE.read_text())
positions = load_positions()
rows = []
for year in YEARS:
    current_round = None
    for cells in raw["sheets"][year]:
        first = str(cells[0] if cells else "")
        match = re.fullmatch(r"Round\s+(\d+)", first)
        if match:
            current_round = int(match.group(1))
            continue
        if current_round is None or len(cells) < 3:
            continue
        try:
            pick = int(cells[0])
        except (TypeError, ValueError):
            continue
        raw_player = str(cells[1]).strip()
        manager = str(cells[2]).strip()
        keeper = raw_player.endswith(" (K)")
        player = raw_player[:-4] if keeper else raw_player
        rows.append({
            "season": int(year),
            "round": current_round,
            "pick_in_round": pick,
            "overall_pick": (current_round - 1) * 10 + pick,
            "manager": manager,
            "player": player,
            "keeper_flag": keeper,
            "position": classify(player, positions),
        })

# Inferred home slots and deviations.
home_slots = {}
for year in YEARS:
    yr = [r for r in rows if r["season"] == int(year)]
    assignment = infer_home_slots(yr)
    home_slots[year] = assignment
    for r in yr:
        nominal_slot = r["pick_in_round"] if r["round"] % 2 else 11 - r["pick_in_round"]
        r["nominal_slot"] = nominal_slot
        r["home_slot"] = assignment.get(r["manager"])
        r["slot_deviation"] = nominal_slot != r["home_slot"]
        r["anomaly_type"] = "confirmed-traded-pick" if r["slot_deviation"] else ""

fields = list(rows[0])
with (OUT / "historical_draft_normalized.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

sanity = {}
for year in YEARS:
    yr = [r for r in rows if r["season"] == int(year)]
    counts = Counter(r["manager"] for r in yr)
    pos_counts = Counter(r["position"] for r in yr)
    sanity[year] = {
        "slots": len(yr),
        "rounds": sorted(set(r["round"] for r in yr)),
        "unique_managers": len(counts),
        "manager_pick_counts": dict(sorted(counts.items())),
        "position_counts": dict(sorted(pos_counts.items())),
        "keepers": sum(r["keeper_flag"] for r in yr),
        "empty_slots": sum(r["position"] == "EMPTY" for r in yr),
        "unknown_positions": sorted({r["player"] for r in yr if r["position"] == "UNKNOWN"}),
        "inferred_home_slots": dict(sorted(home_slots[year].items(), key=lambda kv: kv[1])),
        "slot_deviations": sum(r["slot_deviation"] for r in yr),
        "nonkeeper_slot_deviations": sum(r["slot_deviation"] and not r["keeper_flag"] for r in yr),
    }

manager_summary = []
active_managers = ["Ori","Tompkins","Greenspan","Goldberg","Jeff","Joshua","Big Leiber","Barry","Nalick","Abe"]
for manager in active_managers + ["Danziger"]:
    mr = [r for r in rows if r["manager"] == manager]
    seasons = sorted(set(r["season"] for r in mr))
    qbs = [r for r in mr if r["position"] == "QB"]
    first_qb_rounds, second_qb_rounds, qb_counts = [], [], []
    first_live_qb_rounds, live_qb_counts = [], []
    for season in seasons:
        sq = sorted((r for r in qbs if r["season"] == season), key=lambda r:r["overall_pick"])
        qb_counts.append(len(sq))
        if sq: first_qb_rounds.append(sq[0]["round"])
        if len(sq) > 1: second_qb_rounds.append(sq[1]["round"])
        live_sq = [r for r in sq if not r["keeper_flag"]]
        live_qb_counts.append(len(live_sq))
        if live_sq: first_live_qb_rounds.append(live_sq[0]["round"])
    pos = Counter(r["position"] for r in mr)
    manager_summary.append({
        "manager": manager,
        "seasons": ",".join(map(str,seasons)),
        "drafts": len(seasons),
        "picks": len(mr),
        "keepers": sum(r["keeper_flag"] for r in mr),
        "avg_qbs": round(sum(qb_counts)/len(qb_counts),2) if qb_counts else None,
        "avg_live_qbs": round(sum(live_qb_counts)/len(live_qb_counts),2) if live_qb_counts else None,
        "avg_first_qb_round": round(sum(first_qb_rounds)/len(first_qb_rounds),2) if first_qb_rounds else None,
        "avg_first_live_qb_round": round(sum(first_live_qb_rounds)/len(first_live_qb_rounds),2) if first_live_qb_rounds else None,
        "avg_second_qb_round": round(sum(second_qb_rounds)/len(second_qb_rounds),2) if second_qb_rounds else None,
        "qb_keepers": sum(r["keeper_flag"] for r in qbs),
        "qb": pos["QB"], "rb": pos["RB"], "wr": pos["WR"], "te": pos["TE"], "dst": pos["DST"], "k": pos["K"],
        "confirmed_traded_picks": sum(r["anomaly_type"] == "confirmed-traded-pick" for r in mr),
    })

with (OUT / "manager_tendencies.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(manager_summary[0]))
    w.writeheader(); w.writerows(manager_summary)

anomalies = [r for r in rows if r["slot_deviation"]]
with (OUT / "pick_slot_anomalies.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(anomalies)

qb_scarcity = {}
for year in YEARS:
    yrq = sorted((r for r in rows if r["season"] == int(year) and r["position"] == "QB"), key=lambda r:r["overall_pick"])
    live_yrq = [r for r in yrq if not r["keeper_flag"]]
    qb_scarcity[year] = {
        "total_qbs": len(yrq),
        "live_qbs": len(live_yrq),
        **{f"qb{n}_overall": (yrq[n-1]["overall_pick"] if len(yrq) >= n else None) for n in (5,10,15,20,25)},
        **{f"live_qb{n}_overall": (live_yrq[n-1]["overall_pick"] if len(live_yrq) >= n else None) for n in (5,10,15,20,25)},
        "qbs_by_round": dict(sorted(Counter(r["round"] for r in yrq).items())),
    }

runs = []
for year in YEARS:
    yr = sorted((r for r in rows if r["season"] == int(year) and r["position"] not in {"EMPTY","UNKNOWN"}), key=lambda r:r["overall_pick"])
    start = 0
    for i in range(1, len(yr)+1):
        if i == len(yr) or yr[i]["position"] != yr[start]["position"] or yr[i]["overall_pick"] != yr[i-1]["overall_pick"]+1:
            if i-start >= 3:
                runs.append({"season":int(year),"position":yr[start]["position"],"length":i-start,
                             "start_pick":yr[start]["overall_pick"],"end_pick":yr[i-1]["overall_pick"],
                             "players":" | ".join(r["player"] for r in yr[start:i])})
            start = i
with (OUT / "positional_runs.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["season","position","length","start_pick","end_pick","players"])
    w.writeheader(); w.writerows(runs)

analysis = {
    "source": raw["source"],
    "sanity": sanity,
    "manager_summary": manager_summary,
    "qb_scarcity": qb_scarcity,
    "positional_runs": runs,
    "limitations": [
        "Home draft slots are inferred from the corrected manager labels by maximum-consistency assignment.",
        "The league owner confirmed that every slot deviation represents a pick traded during the prior season; the sheet does not contain the underlying transaction details.",
        "Positions are reconciled against nflverse player history plus explicit defense-name handling; unresolved names remain UNKNOWN and are not guessed."
    ]
}
(OUT / "historical_draft_analysis.json").write_text(json.dumps(analysis, indent=2)+"\n")
print(json.dumps(analysis, indent=2))
