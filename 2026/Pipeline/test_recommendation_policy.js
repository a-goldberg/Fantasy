#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const policy = require("../Config/draft_policy.json");
const board = require("../App/data/draft-board.json");
const {
  recommendationPolicyDecision, draftRoomTrendDecision, personalPriorityDecision,
  marketAvailabilityDecision, wildcardMarketGapDecision, wildcardMarketGap, evidenceQualityAdjustment, wildcardEvidenceDecision,
  handcuffBoostDecision, handcuffRelationshipDecision, endgameSpecialistAdjustment,
} = require("../App/app.js");

function eligible(position, counts, rosterSize, round, column) {
  return recommendationPolicyDecision({ position, counts, rosterSize, round, policy, column }).eligible;
}

const threeQbsNoSkillPlayers = { QB: 3, RB: 0, WR: 0, TE: 0, K: 0, DST: 0 };
for (const column of ["optimized", "consensus", "wildcard"]) {
  assert.equal(eligible("QB", threeQbsNoSkillPlayers, 3, 3, column), false, `Round 3 ${column} must exclude a fourth QB`);
  assert.equal(eligible("WR", threeQbsNoSkillPlayers, 3, 3, column), true, `Round 3 ${column} must retain WRs`);
  assert.equal(eligible("RB", threeQbsNoSkillPlayers, 3, 3, column), true, `Round 3 ${column} must retain RBs`);
}

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
assert.equal(cmcHandcuff.starter, "Christian McCaffrey", "The live handcuff matcher links an Ourlads RB2 to the rostered RB1");
assert.ok(cmcHandcuff.score > 0 && cmcHandcuff.starterInjuryPercentile >= 90, "The matched handcuff carries the starter's high injury-risk signal");

for (const playerName of ["Denzel Boston", "KC Concepcion"]) {
  const player = board.players.find((item) => item.player === playerName);
  assert.ok(player, `${playerName} must remain available for the rank-normalization regression`);
  assert.ok(player.source_count >= 2, `${playerName} must carry the complementary Superflex expert rank`);
  assert.equal(player.source_quality.market, "low", `${playerName} conflicting market inputs must remain low confidence`);
}

console.log("Recommendation-policy regression scenarios: PASS");
