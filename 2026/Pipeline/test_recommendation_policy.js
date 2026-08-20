#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const policy = require("../Config/draft_policy.json");
const { recommendationPolicyDecision, draftRoomTrendDecision, personalPriorityDecision } = require("../App/app.js");

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

console.log("Recommendation-policy regression scenarios: PASS");
