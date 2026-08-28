#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const policy = require("../Config/draft_policy.json");
const board = require("../App/data/draft-board.json");
const {
  recommendationPolicyDecision, draftRoomTrendDecision, personalPriorityDecision,
  marketAvailabilityDecision, wildcardMarketGapDecision, wildcardMarketGap, evidenceQualityAdjustment, wildcardEvidenceDecision,
  handcuffBoostDecision, handcuffRelationshipDecision, endgameSpecialistAdjustment,
  displayedNextUserOverall, softTargetUrgencyDecision, marginalLineupRoleDecision,
  expectedNextPickValueDecision, baselineCoreValue,
} = require("../App/app.js");

assert.equal(displayedNextUserOverall({ current: 124, target: 124, next: 137, currentOwner: "Goldberg", userManager: "Goldberg" }), 137, "While Goldberg is on the clock, the header shows the pick after the current selection");
assert.equal(displayedNextUserOverall({ current: 57, target: 57, next: 77, currentOwner: "Goldberg", userManager: "Goldberg" }), 77, "The header skips Stafford's occupied Round 7 keeper slot");
assert.equal(displayedNextUserOverall({ current: 10, target: 17, next: 24, currentOwner: "Abe", userManager: "Goldberg" }), 17, "While another manager is on the clock, the header shows Goldberg's upcoming selection");

function eligible(position, counts, rosterSize, round, column) {
  return recommendationPolicyDecision({ position, counts, rosterSize, round, policy, column }).eligible;
}

const threeQbsNoSkillPlayers = { QB: 3, RB: 0, WR: 0, TE: 0, K: 0, DST: 0 };
for (const column of ["optimized", "consensus", "wildcard"]) {
  assert.equal(eligible("QB", threeQbsNoSkillPlayers, 3, 3, column), false, `Round 3 ${column} must exclude a fourth QB`);
  assert.equal(eligible("WR", threeQbsNoSkillPlayers, 3, 3, column), true, `Round 3 ${column} must retain WRs`);
  assert.equal(eligible("RB", threeQbsNoSkillPlayers, 3, 3, column), true, `Round 3 ${column} must retain RBs`);
}

const staffordAndEliteQb = { QB: 2, RB: 0, WR: 0, TE: 0, K: 0, DST: 0 };
const qb3Role = marginalLineupRoleDecision({ position: "QB", counts: staffordAndEliteQb, policy });
const rb1Role = marginalLineupRoleDecision({ position: "RB", counts: staffordAndEliteQb, policy });
const wr1Role = marginalLineupRoleDecision({ position: "WR", counts: staffordAndEliteQb, policy });
assert.equal(qb3Role.role, "reserve", "Stafford plus an elite QB makes QB3 a reserve, not a third starter");
assert.equal(qb3Role.multiplier, 0.28, "QB3 receives only expected reserve-use value");
assert.equal(rb1Role.role, "starter", "The first RB still fills a weekly starting slot");
assert.equal(wr1Role.role, "starter", "The first WR still fills a weekly starting slot");
assert.ok(rb1Role.multiplier > qb3Role.multiplier && wr1Role.multiplier > qb3Role.multiplier, "Open RB/WR starter slots carry more marginal lineup value than QB3");

assert.equal(
  softTargetUrgencyDecision({ position: "QB", counts: staffordAndEliteQb, rosterSize: 2, policy }),
  0,
  "The preferred third QB does not create early-draft urgency while core starters remain open",
);
assert.ok(
  softTargetUrgencyDecision({ position: "QB", counts: { QB: 2, RB: 5, WR: 5, TE: 1, K: 1, DST: 0 }, rosterSize: 15, policy }) > 0,
  "QB3 depth becomes useful when the draft is closing and the core roster is built",
);

const reserveWait = expectedNextPickValueDecision({
  currentValue: 20,
  alternatives: [{ value: 18, goneChance: 0.2 }],
  share: 0.35,
});
const starterWait = expectedNextPickValueDecision({
  currentValue: 55,
  alternatives: [{ value: 42, goneChance: 0.8 }],
  share: 0.35,
});
assert.ok(starterWait.waitCost > reserveWait.waitCost, "Waiting costs more when a starter tier is likely to disappear than when reserve QB value remains");

const jaydenDaniels = board.players.find((player) => player.player === "Jayden Daniels");
const derrickHenry = board.players.find((player) => player.player === "Derrick Henry");
assert.ok(jaydenDaniels && derrickHenry, "The early-QB regression players remain on the generated board");
assert.ok(
  baselineCoreValue(derrickHenry) * rb1Role.multiplier > baselineCoreValue(jaydenDaniels) * qb3Role.multiplier,
  "A starter-level RB's marginal core value beats QB3 after Stafford and a first-round passer are rostered",
);

const fourQbs = { QB: 4, RB: 4, WR: 5, TE: 1, K: 0, DST: 0 };
for (const column of ["optimized", "consensus", "wildcard"]) {
  assert.equal(eligible("QB", fourQbs, 14, 12, column), false, `A fifth QB must never appear in ${column}`);
}

const fourthQbReady = { QB: 3, RB: 4, WR: 5, TE: 1, K: 0, DST: 0 };
assert.equal(eligible("QB", fourthQbReady, 13, 10, "optimized"), false, "A fourth QB is not an optimized pick");
assert.equal(eligible("QB", fourthQbReady, 13, 10, "consensus"), false, "A fourth QB is not a consensus pick");
assert.equal(eligible("QB", fourthQbReady, 13, 10, "wildcard"), true, "A late fourth QB may appear as a wildcard");

assert.equal(eligible("K", { K: 1 }, 16, 17, "optimized"), false, "A second kicker must be excluded");
assert.equal(eligible("DST", { DST: 1 }, 16, 17, "wildcard"), false, "A second defense must be excluded");
assert.equal(eligible("TE", { TE: 2 }, 10, 11, "consensus"), false, "A third tight end must be excluded");

const receiverRun = ["RB", "WR", "WR", "QB", "WR", "TE"];
const needyWrTrend = draftRoomTrendDecision({ position: "WR", recentPositions: receiverRun, counts: { RB: 4, WR: 1 }, policy });
const filledWrTrend = draftRoomTrendDecision({ position: "WR", recentPositions: receiverRun, counts: { RB: 4, WR: 5 }, policy });
assert.ok(needyWrTrend.score >= 3.5, "A three-WR run must materially raise WR urgency for a WR-thin roster");
assert.ok(needyWrTrend.score > filledWrTrend.score, "Room-trend pressure must be roster-aware rather than blindly chasing a run");
assert.equal(draftRoomTrendDecision({ position: "RB", recentPositions: receiverRun, counts: { RB: 1 }, policy }).score, 0, "A position without a run gets no room-trend bump");

assert.equal(personalPriorityDecision({ score: 7, column: "optimized", weight: 1 }).adjustment, 7, "A boost changes optimized scoring");
assert.equal(personalPriorityDecision({ score: -4, column: "wildcard", weight: .5 }).adjustment, -2, "A fade changes wildcard scoring at the configured weight");
assert.equal(personalPriorityDecision({ score: 10, column: "consensus", weight: 1 }).adjustment, 0, "Personal priority never changes consensus scoring");
assert.equal(personalPriorityDecision({ score: 0, avoid: true, column: "consensus" }).eligible, false, "A hard avoid suppresses every recommendation column");

assert.equal(marketAvailabilityDecision({ adp: null, nextPick: 117 }).probability, null, "Missing ADP must remain unknown");
assert.equal(marketAvailabilityDecision({ adp: null, nextPick: 117 }).contributionBasis, 0, "Missing ADP must add no availability score");
assert.equal(wildcardMarketGap({ adp: null, baseCompositeRank: 145 }), 0, "Missing ADP must not create a fake market gap");
assert.equal(wildcardMarketGap({ adp: 151.3, baseCompositeRank: 98, sourceCount: 3, adpSources: { a: { adp: 151.3 }, b: { adp: 151.3 } } }).toFixed(2), "12.79", "Well-supported and aligned market data retains the full measured gap");
const thinConflictedGap = wildcardMarketGapDecision({
  adp: 163,
  baseCompositeRank: 97,
  sourceCount: 1,
  adpSources: { ffc: { adp: 135 }, fantasypros: { adp: 191 } },
});
assert.ok(thinConflictedGap.adjustment <= 5, "A one-source expert gap is capped at five points");
assert.ok(thinConflictedGap.adjustment < thinConflictedGap.rawAdjustment / 3, "Conflicting ADP sources materially shrink a thin-data market gap");
assert.deepEqual(evidenceQualityAdjustment({ sourceCount: 1, depth: 3, position: "TE" }), { source: -5, depthRole: -4, total: -9 }, "A one-source TE3 receives a reliability adjustment");
assert.equal(wildcardEvidenceDecision({ sourceCount: 1 }).eligible, false, "A thin-data player without an upside signal is not a wildcard");
assert.equal(wildcardEvidenceDecision({ sourceCount: 3 }).eligible, false, "Multiple baseline ranks alone do not constitute a Wildcard thesis");
assert.equal(wildcardEvidenceDecision({ sourceCount: 3, draftSharksRank: 80 }).eligible, false, "A generic DraftSharks rank alone does not constitute a sleeper signal");
assert.equal(wildcardEvidenceDecision({ round: 9, sourceCount: 1, rookiePercentile: 88 }).eligible, false, "A rookie model alone cannot support a thin-data early Wildcard");
assert.equal(wildcardEvidenceDecision({ round: 9, sourceCount: 1, rookiePercentile: 88, positiveContext: 0.5 }).eligible, true, "Independent analyst support plus a rookie model can support a thin-data early Wildcard");
assert.equal(wildcardEvidenceDecision({ round: 14, sourceCount: 1, rookiePercentile: 88 }).eligible, true, "A qualified rookie model can support an endgame Wildcard");
assert.equal(wildcardEvidenceDecision({ sourceCount: 1, personalScore: 2 }).eligible, true, "A deliberate personal boost can support a thin-data wildcard");
assert.equal(handcuffBoostDecision({ round: 13, position: "RB", candidateDepth: 2, starterInjuryPercentile: 95 }).score, 0, "Handcuffs are not boosted before the final four rounds");
const ordinaryHandcuff = handcuffBoostDecision({ round: 15, position: "RB", candidateDepth: 2, starterInjuryPercentile: 40 });
const highRiskHandcuff = handcuffBoostDecision({ round: 15, position: "RB", candidateDepth: 2, starterInjuryPercentile: 90 });
assert.ok(highRiskHandcuff.score > ordinaryHandcuff.score, "A high-risk starter materially increases the backup's handcuff score");
assert.ok(handcuffBoostDecision({ round: 17, position: "QB", candidateDepth: 2, starterInjuryPercentile: 90 }).score > highRiskHandcuff.score, "Handcuff reminders strengthen as the draft closes");
assert.equal(wildcardEvidenceDecision({ sourceCount: 1, handcuffScore: 4 }).eligible, true, "A verified handcuff can qualify a thin-data Wildcard");
assert.equal(endgameSpecialistAdjustment({ position: "K", count: 0, round: 13 }), -28, "Kickers remain suppressed before the endgame");
assert.ok(endgameSpecialistAdjustment({ position: "K", count: 0, round: 14 }) > 0, "A missing kicker can enter recommendations in Round 14");
assert.ok(endgameSpecialistAdjustment({ position: "DST", count: 0, round: 17 }) > endgameSpecialistAdjustment({ position: "DST", count: 0, round: 14 }), "K/DST urgency rises through the final four rounds");

const christianMcCaffrey = board.players.find((player) => player.player === "Christian McCaffrey");
const jordanJames = board.players.find((player) => player.player === "Jordan James");
const cmcHandcuff = handcuffRelationshipDecision({ player: jordanJames, rosteredPlayers: [christianMcCaffrey], targetPick: 137 });
assert.equal(cmcHandcuff.starter, "Christian McCaffrey", "The live handcuff matcher links the verified primary handcuff to the rostered starter");
assert.ok(cmcHandcuff.score > 0 && cmcHandcuff.starterInjuryPercentile >= 90, "The matched handcuff carries the starter's high injury-risk signal");
assert.equal(cmcHandcuff.sourceName, "RB-Grid-August", "The supplemental RB handcuff grid takes precedence over generic depth order");

const jamesCook = board.players.find((player) => player.player === "James Cook III");
const rayDavis = board.players.find((player) => player.player === "Ray Davis");
const cookHandcuff = handcuffRelationshipDecision({ player: rayDavis, rosteredPlayers: [jamesCook], targetPick: 147 });
assert.equal(cookHandcuff.starter, "James Cook III", "Suffix-normalized RB grid names link to the canonical starter");
assert.ok(cookHandcuff.score > 0, "A verified primary RB handcuff receives an endgame reminder");

for (const playerName of ["Denzel Boston", "KC Concepcion"]) {
  const player = board.players.find((item) => item.player === playerName);
  assert.ok(player, `${playerName} must remain available for the rank-normalization regression`);
  assert.ok(player.source_count >= 2, `${playerName} must carry the complementary Superflex expert rank`);
  assert.equal(player.source_quality.market, "low", `${playerName} conflicting market inputs must remain low confidence`);
}

const treyLance = board.players.find((player) => player.player === "Trey Lance");
assert.ok(treyLance, "Trey Lance must remain searchable as supplemental QB-chart context");
assert.equal(treyLance.qb_chart_rank, 40, "Trey Lance's positional QB-chart context must remain visible");
assert.equal(treyLance.primary_source_count, 0, "Trey Lance must not acquire an invented overall-ranking source");
assert.equal(treyLance.supplemental_source_count, 1, "Trey Lance's supplemental source must be retained");
assert.equal(treyLance.supplemental_applied_count, 0, "Supplemental-only evidence must not affect base quality");
assert.equal(treyLance.base_quality_score, 0, "Supplemental-only evidence must not create base quality");
assert.ok(treyLance.base_composite_rank > 200, "A supplemental-only player must remain outside the meaningful overall board");

console.log("Recommendation-policy regression scenarios: PASS");
