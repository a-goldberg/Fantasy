const STORAGE_KEY = "fantasy-draft-manager-2026-v1";
const DEFAULT_WEIGHTS = {
  availability: 1,
  roster: 1,
  bye: 1,
  history: 0.7,
  tiers: 0.8,
  context: 0.7,
  injuryRisk: 0.8,
  rookieUpside: 0.4,
  earlySchedule: 0.4,
  draftSharks: 0.35,
  newsContext: 0.3,
  roomTrend: 1,
  personalPriority: 1,
};
const state = {
  data: null,
  picks: [],
  history: [],
  weights: { ...DEFAULT_WEIGHTS },
  personalPriorities: {},
};
const ROSTER_POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"];

const $ = (selector) => document.querySelector(selector);
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const normalizePlayerName = (value) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\b(jr|sr|ii|iii|iv|v)\b/g, "")
    .replace(/[^a-z0-9]+/g, "");
const normalCdf = (x) => {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const p =
    1 -
    d *
      t *
      (0.3193815 +
        t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x >= 0 ? p : 1 - p;
};

function ownerAt(overall) {
  const trade = state.data.draft.traded_picks.find(
    (item) => item.overall_pick === overall,
  );
  if (trade) return trade.new_manager;
  const { draft_order: order } = state.data.draft;
  const round = Math.floor((overall - 1) / order.length) + 1;
  const slot = (overall - 1) % order.length;
  return round % 2 ? order[slot] : [...order].reverse()[slot];
}

function roundAt(overall) {
  return Math.floor((overall - 1) / 10) + 1;
}
function selectedNames() {
  return new Set(state.picks.map((pick) => pick.player));
}
function currentOverall() {
  for (let pick = 1; pick <= 170; pick += 1)
    if (!state.picks.some((item) => item.overall === pick)) return pick;
  return 171;
}
function userPicks() {
  return state.picks.filter(
    (pick) => pick.manager === state.data.draft.user_manager,
  );
}
function availablePlayers() {
  const gone = selectedNames();
  return state.data.players.filter(
    (p) => p.draft_eligible !== false && !gone.has(p.player),
  );
}
function nextUserOverall(from = currentOverall()) {
  for (let pick = from; pick <= 170; pick += 1) {
    if (
      ownerAt(pick) === state.data.draft.user_manager &&
      !state.picks.some((item) => item.overall === pick)
    )
      return pick;
  }
  return null;
}
function followingUserOverall(target) {
  return target ? nextUserOverall(target + 1) : null;
}

function rosterCounts() {
  return userPicks().reduce((counts, pick) => {
    const player = state.data.players.find((p) => p.player === pick.player);
    const position = player?.position || pick.position;
    if (position) counts[position] = (counts[position] || 0) + 1;
    return counts;
  }, {});
}

function draftRoomTrendDecision({ position, recentPositions, counts, policy }) {
  const window = recentPositions.slice(-6);
  const runCount = window.filter((item) => item === position).length;
  if (runCount < 3)
    return { score: 0, count: runCount, window: window.length, label: null };
  const format = policy?.league_format || {};
  const hard = policy?.hard_constraints || {};
  const construction = policy?.roster_constructions?.three_qb_wr_depth || {};
  const targets = {
    QB: Math.max(Number(hard.minimum_qb || 3), Number(format.starting_qb || 0)),
    RB: Math.max(Number(format.starting_rb || 2), Number(construction.RB || 0)),
    WR: Math.max(Number(hard.minimum_wr || 5), Number(format.starting_wr || 0)),
    TE: Math.max(Number(format.starting_te || 1), Number(construction.TE || 0)),
    K: 1,
    DST: 1,
  };
  const target = Math.max(1, targets[position] || 1);
  const deficitRatio = clamp(
    (target - Number(counts[position] || 0)) / target,
    0,
    1,
  );
  const recency =
    window.slice(-3).filter((item) => item === position).length >= 2 ? 1 : 0;
  const score = clamp(
    ((runCount - 2) * 3 + recency) * (0.5 + deficitRatio),
    0,
    8,
  );
  return {
    score,
    count: runCount,
    window: window.length,
    label: `${position} run: ${runCount} of the last ${window.length} picks`,
  };
}

function draftRoomTrend(player) {
  const current = currentOverall();
  const recentPositions = state.picks
    .filter((pick) => pick.overall < current)
    .sort((a, b) => a.overall - b.overall)
    .map(
      (pick) =>
        state.data.players.find((item) => item.player === pick.player)
          ?.position || pick.position,
    )
    .filter(Boolean);
  return draftRoomTrendDecision({
    position: player.position,
    recentPositions,
    counts: rosterCounts(),
    policy: state.data.policy,
  });
}

function personalPriorityDecision({
  score = 0,
  avoid = false,
  column = "optimized",
  weight = 1,
}) {
  const normalizedScore = clamp(Number(score) || 0, -10, 10);
  return {
    eligible: !avoid,
    adjustment:
      column === "consensus" ? 0 : normalizedScore * (Number(weight) || 0),
  };
}

function personalPriority(player) {
  const saved =
    state.personalPriorities[normalizePlayerName(player.player)] || {};
  return {
    score: clamp(Number(saved.score) || 0, -10, 10),
    avoid: Boolean(saved.avoid),
  };
}

function recommendationPolicyDecision({
  position,
  counts,
  rosterSize,
  round,
  policy,
  column,
}) {
  const hard = policy?.hard_constraints || {};
  const format = policy?.league_format || {};
  const fourthQb = policy?.soft_targets?.fourth_qb || {};
  const count = Number(counts[position] || 0);
  if (position === "QB") {
    const maximum = Number(hard.maximum_qb || 4);
    if (count >= maximum)
      return {
        eligible: false,
        reason: `The ${maximum}-QB maximum is already filled`,
      };
    if (count >= 3) {
      if (!fourthQb.allowed)
        return {
          eligible: false,
          reason: "The configured roster does not allow a fourth QB",
        };
      const earliest = Number(fourthQb.earliest_round || 10);
      if (round < earliest)
        return {
          eligible: false,
          reason: `A fourth QB is not considered before Round ${earliest}`,
        };
      const missing = Object.entries(
        fourthQb.required_roster_before || {},
      ).filter(
        ([neededPosition, required]) =>
          Number(counts[neededPosition] || 0) < Number(required),
      );
      if (missing.length)
        return {
          eligible: false,
          reason: `A fourth QB must wait until core RB, WR, and TE depth is filled`,
        };
      const columns = fourthQb.recommendation_columns || ["wildcard"];
      if (!columns.includes(column))
        return {
          eligible: false,
          reason:
            "A fourth QB is a speculative option, not an optimized or consensus pick",
        };
    }
  }
  if (position === "TE" && count >= 2)
    return {
      eligible: false,
      reason: "Two tight ends already fill the supported roster constructions",
    };
  if (position === "K" && count >= Number(hard.kickers || 1))
    return { eligible: false, reason: "The kicker slot is already filled" };
  if (position === "DST" && count >= Number(hard.defenses || 1))
    return { eligible: false, reason: "The defense slot is already filled" };

  const minimums = {
    QB: Math.max(Number(hard.minimum_qb || 3), Number(format.starting_qb || 0)),
    RB: Number(format.starting_rb || 2),
    WR: Math.max(Number(hard.minimum_wr || 5), Number(format.starting_wr || 0)),
    TE: Number(format.starting_te || 1),
    K: Number(hard.kickers || 1),
    DST: Number(hard.defenses || 1),
  };
  const after = { ...counts, [position]: count + 1 };
  const remainingSlots =
    Number(format.rounds || policy?.draft_rounds || 17) - rosterSize - 1;
  const minimumSlotsStillNeeded = Object.entries(minimums).reduce(
    (total, [neededPosition, required]) =>
      total + Math.max(0, required - Number(after[neededPosition] || 0)),
    0,
  );
  if (minimumSlotsStillNeeded > remainingSlots) {
    return {
      eligible: false,
      reason:
        "This pick would make the minimum viable roster impossible to complete",
    };
  }
  return { eligible: true, reason: null };
}

function recommendationEligibility(player, targetPick, column) {
  return recommendationPolicyDecision({
    position: player.position,
    counts: rosterCounts(),
    rosterSize: userPicks().length,
    round: roundAt(targetPick),
    policy: state.data.policy,
    column,
  });
}

function availability(player, nextPick) {
  if (!player.adp || !nextPick) return 0.45;
  const deviations = Object.values(player.adp_sources || {})
    .map((row) => Number(row.stdev))
    .filter(Number.isFinite);
  const spread = Math.max(
    4,
    deviations.length
      ? deviations.reduce((a, b) => a + b, 0) / deviations.length
      : 10,
  );
  return clamp(normalCdf((nextPick - player.adp) / spread), 0.02, 0.99);
}

function byeConflict(player) {
  const samePosition = userPicks()
    .map((pick) => state.data.players.find((p) => p.player === pick.player))
    .filter(Boolean)
    .filter(
      (p) =>
        p.position === player.position && String(p.bye) === String(player.bye),
    );
  if (player.position === "QB" && samePosition.length) return 12;
  const limits = { WR: 3, RB: 2, TE: 1 };
  return samePosition.length >= (limits[player.position] || 3)
    ? 7
    : samePosition.length * 1.5;
}

function contextAdjustment(player) {
  const rules = state.data.context_rules || {};
  const minimumConfidence = Number(
    rules.minimum_confidence_for_ranking_adjustment ?? 0.6,
  );
  const singleCap = Number(rules.maximum_single_context_adjustment ?? 4);
  const totalCap = Number(rules.maximum_total_context_adjustment ?? 8);
  const components = (player.classified_context?.applied || [])
    .filter(
      (item) =>
        item.active &&
        item.score_eligible &&
        Number(item.confidence) >= minimumConfidence,
    )
    .map((item) => ({
      summary: item.summary,
      source_name: item.source_name,
      source_url: item.source_url,
      mechanism: item.mechanism,
      direction: item.direction,
      confidence: Number(item.confidence),
      expires_at: item.expires_at,
      contribution: clamp(
        Number(item.capped_adjustment || 0),
        -singleCap,
        singleCap,
      ),
    }));
  const uncapped = components.reduce((sum, item) => sum + item.contribution, 0);
  return { total: clamp(uncapped, -totalCap, totalCap), uncapped, components };
}

function injuryAdjustment(player) {
  const percentile = Number(player.models?.injury?.risk_percentile_at_position);
  if (!Number.isFinite(percentile) || percentile <= 50) return 0;
  return -clamp(((percentile - 50) / 50) * 3, 0, 3);
}

function rookieAdjustment(player, targetPick) {
  const percentile = Number(player.models?.rookie?.overall_percentile);
  if (!Number.isFinite(percentile) || percentile < 75) return 0;
  const roundFactor = clamp((roundAt(targetPick) - 3) / 8, 0, 1);
  return clamp(((percentile - 75) / 25) * 4, 0, 4) * roundFactor;
}

function earlyScheduleAdjustment(player) {
  const average = Number(player.models?.early_sos?.weeks_1_6_average);
  return Number.isFinite(average) ? clamp(average * 12, -2.5, 2.5) : 0;
}

function draftSharksAdjustment(player) {
  const rank = Number(player.models?.draftsharks_superflex?.rank);
  if (!Number.isFinite(rank)) return 0;
  return clamp((player.base_composite_rank - rank) * 0.15, -3, 3);
}

function newsAdjustment(player) {
  return clamp(
    (player.recent_news || []).reduce(
      (sum, item) => sum + Number(item.ranking_adjustment || 0),
      0,
    ),
    -3,
    3,
  );
}

function historicalPressure(player, targetPick, nextPick) {
  if (player.position !== "QB" || !nextPick) return 0;
  const managers = new Set();
  for (let pick = targetPick + 1; pick < nextPick; pick += 1)
    managers.add(ownerAt(pick));
  managers.delete(state.data.draft.user_manager);
  const round = roundAt(targetPick);
  let pressure = 0;
  managers.forEach((manager) => {
    const tendency = state.data.league_history.manager_tendencies[manager];
    if (!tendency) return;
    const first = Number(tendency.avg_first_live_qb_round);
    const volume = Number(tendency.avg_live_qbs);
    if (round >= first - 1) pressure += clamp((volume - 2.1) * 0.45, 0.15, 0.7);
  });
  return clamp(pressure, 0, 3);
}

function tierCliff(player) {
  const nextAtPosition = availablePlayers()
    .filter(
      (p) =>
        p.position === player.position &&
        p.base_composite_rank > player.base_composite_rank,
    )
    .sort((a, b) => a.base_composite_rank - b.base_composite_rank)[0];
  if (!nextAtPosition) return 0;
  return clamp(
    (player.base_quality_score - nextAtPosition.base_quality_score) * 0.75,
    0,
    4,
  );
}

function positionNeed(player, targetPick) {
  const counts = rosterCounts();
  const round = roundAt(targetPick);
  const count = counts[player.position] || 0;
  let score = 0;
  if (player.position === "QB") {
    if (count < 2) score += round <= 6 ? 8 : 14;
    else if (count < 3) score += round >= 7 ? 9 : 3;
    else if (count === 3) score -= 10;
    else score -= 40;
  }
  if (player.position === "WR") {
    if (count === 0 && round >= 3) score += 12;
    if (count < 2 && round >= 4) score += 5;
    if (count < 3 && round >= 5) score += 8;
    if (count < 5 && round >= 9) score += 10;
    if (count < 3 && Number(counts.RB || 0) >= 4) score += 6;
  }
  if (player.position === "RB") {
    if (count === 0 && round >= 3) score += 8;
    if (count < 2 && round >= 5) score += 6;
  }
  if (player.position === "TE" && count === 0 && round >= 8) score += 5;
  if (["K", "DST"].includes(player.position))
    score += round < 15 ? -28 : count ? -20 : 5;
  return score;
}

function scorePlayer(player, targetPick, nextPick) {
  const goneChance = availability(player, nextPick);
  const rankValue = 101 - Math.min(100, player.base_composite_rank * 0.55);
  const marketValue = player.adp
    ? clamp((targetPick - player.adp) * 0.35, -8, 9)
    : -2;
  const need = positionNeed(player, targetPick);
  const bye = byeConflict(player);
  const contextResult = contextAdjustment(player);
  const context = contextResult.total;
  const history = historicalPressure(player, targetPick, nextPick);
  const tiers = tierCliff(player);
  const injury = injuryAdjustment(player);
  const rookie = rookieAdjustment(player, targetPick);
  const earlySchedule = earlyScheduleAdjustment(player);
  const draftSharks = draftSharksAdjustment(player);
  const news = newsAdjustment(player);
  const roomTrend = draftRoomTrend(player);
  const personal = personalPriority(player);
  const personalAdjustment = personalPriorityDecision({
    ...personal,
    weight: state.weights.personalPriority,
  }).adjustment;
  return {
    optimized:
      player.base_quality_score * 0.72 +
      rankValue * 0.18 +
      goneChance * 8 * state.weights.availability +
      marketValue +
      need * state.weights.roster +
      roomTrend.score * state.weights.roomTrend +
      context * state.weights.context -
      bye * state.weights.bye +
      history * state.weights.history +
      tiers * state.weights.tiers +
      injury * state.weights.injuryRisk +
      rookie * state.weights.rookieUpside +
      earlySchedule * state.weights.earlySchedule +
      draftSharks * state.weights.draftSharks +
      news * state.weights.newsContext +
      personalAdjustment,
    consensus:
      player.base_quality_score * 0.78 + rankValue * 0.17 + marketValue * 0.5,
    wildcard:
      player.base_quality_score * 0.55 +
      goneChance * 12 * state.weights.availability +
      Math.max(0, (player.adp || 240) - player.base_composite_rank) * 0.24 +
      Math.max(0, need) * 0.5 * state.weights.roster +
      roomTrend.score * 0.8 * state.weights.roomTrend +
      context * state.weights.context -
      bye * state.weights.bye +
      tiers * state.weights.tiers +
      injury * state.weights.injuryRisk +
      rookie * state.weights.rookieUpside * 1.5 +
      earlySchedule * state.weights.earlySchedule +
      draftSharks * state.weights.draftSharks +
      news * state.weights.newsContext +
      personalAdjustment,
    goneChance,
    need,
    bye,
    context,
    contextComponents: contextResult.components,
    contextUncapped: contextResult.uncapped,
    history,
    tiers,
    injury,
    rookie,
    earlySchedule,
    draftSharks,
    news,
    roomTrend,
    personal,
    personalAdjustment,
  };
}

function recommendations() {
  const target = nextUserOverall();
  const next = followingUserOverall(target);
  if (!target)
    return { target, next, optimized: [], consensus: [], wildcard: [] };
  const scored = availablePlayers().map((player) => ({
    player,
    ...scorePlayer(player, target, next),
  }));
  const eligible = (entry, column) =>
    personalPriorityDecision({ ...entry.personal, column }).eligible &&
    recommendationEligibility(entry.player, target, column).eligible;
  const optimized = [...scored]
    .filter((entry) => eligible(entry, "optimized"))
    .sort((a, b) => b.optimized - a.optimized)
    .slice(0, 3);
  const consensus = [...scored]
    .filter((entry) => eligible(entry, "consensus"))
    .sort((a, b) => b.consensus - a.consensus)
    .slice(0, 3);
  const defaultNames = new Set(
    [...optimized, ...consensus].map((x) => x.player.player),
  );
  let wildcard = [...scored]
    .filter((entry) => eligible(entry, "wildcard"))
    .filter((x) => !defaultNames.has(x.player.player))
    .filter(
      (x) =>
        x.player.base_composite_rank <= target + 45 ||
        (x.player.adp && x.player.adp <= (next || target + 20)),
    )
    .filter(
      (x) => !["K", "DST"].includes(x.player.position) || roundAt(target) >= 15,
    )
    .sort((a, b) => b.wildcard - a.wildcard)
    .slice(0, 3);
  if (wildcard.length < 3)
    wildcard = [...scored]
      .filter((entry) => eligible(entry, "wildcard"))
      .filter((x) => !defaultNames.has(x.player.player))
      .sort((a, b) => b.wildcard - a.wildcard)
      .slice(0, 3);
  return { target, next, optimized, consensus, wildcard };
}

function describe(entry, kind, target, next) {
  const { player } = entry;
  const targetRound = roundAt(target);
  const pct = Math.round(entry.goneChance * 100);
  const market = player.adp
    ? `Market ADP ${player.adp.toFixed(1)}`
    : "No matched public ADP";
  const source = `${player.source_count} ranking source${player.source_count === 1 ? "" : "s"}`;
  const cases = {
    optimized: `${player.position} value adjusted for your current roster, bye coverage, and the ${next ? next - target : 0}-pick wait after this selection.`,
    consensus: `Composite rank No. ${player.base_composite_rank}, using the current expert inputs as the neutral baseline.`,
    wildcard: `A defensible departure from the top of the board: the quality-versus-market gap creates upside without reaching blindly.`,
  };
  const pros = [market, source];
  if (entry.personal?.score > 0)
    pros.unshift(`Personal priority +${entry.personal.score}`);
  if (entry.need >= 6)
    pros.unshift(`Addresses a roster need by Round ${targetRound}`);
  if (entry.roomTrend?.score >= 2) pros.unshift(entry.roomTrend.label);
  if (player.adp && player.base_composite_rank + 8 < player.adp)
    pros.unshift("Experts rate him materially above his market cost");
  const positiveSignal = (entry.contextComponents || [])
    .filter((item) => item.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)[0];
  const negativeSignal = (entry.contextComponents || [])
    .filter((item) => item.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution)[0];
  if (positiveSignal)
    pros.unshift(`${positiveSignal.summary} (${positiveSignal.source_name})`);
  if (entry.rookie >= 2)
    pros.unshift(
      `Rookie model: ${player.models.rookie.prospect_label}, ${player.models.rookie.overall_percentile}th percentile`,
    );
  if (entry.earlySchedule >= 1)
    pros.unshift("Favorable Weeks 1–6 positional schedule");
  if (entry.draftSharks >= 1)
    pros.unshift(
      `DraftSharks Superflex rank No. ${player.models.draftsharks_superflex.rank}`,
    );
  const cons = [];
  if (entry.personal?.score < 0)
    cons.push(`Personal fade ${entry.personal.score}`);
  if (entry.bye >= 7) cons.push("Creates a positional bye-coverage problem");
  else if (entry.bye > 0)
    cons.push("Adds another same-position player on this bye");
  if (!player.adp) cons.push("Public 2QB availability data is missing");
  if (entry.injury <= -1)
    cons.push(
      `Injury-risk percentile ${player.models.injury.risk_percentile_at_position} at ${player.position}`,
    );
  if (negativeSignal)
    cons.unshift(`${negativeSignal.summary} (${negativeSignal.source_name})`);
  if (entry.earlySchedule <= -1)
    cons.push("Difficult Weeks 1–6 positional schedule");
  if (
    !(player.classified_context?.applied || []).length &&
    !(player.classified_context?.research_only || []).length &&
    !player.recent_news.length
  )
    cons.push("No additional qualitative finding is attached");
  if (player.source_count < 2) cons.push("Thin expert-source coverage");
  if (!cons.length)
    cons.push(`About ${pct}% likely to be drafted before pick ${next || "—"}`);
  const selectedPros = pros.slice(0, 2);
  if (positiveSignal) {
    const citedSignal = `${positiveSignal.summary} (${positiveSignal.source_name})`;
    if (!selectedPros.includes(citedSignal))
      selectedPros.splice(0, 1, citedSignal);
  }
  if (entry.personal?.score > 0) {
    const personalText = `Personal priority +${entry.personal.score}`;
    if (!selectedPros.includes(personalText))
      selectedPros.splice(Math.min(1, selectedPros.length), 1, personalText);
  }
  return {
    caseText: cases[kind],
    pros: selectedPros.join(" · "),
    cons: cons.slice(0, 2).join(" · "),
  };
}

function renderCandidate(entry, kind, target, next) {
  const node = $("#candidate-template").content.firstElementChild.cloneNode(
    true,
  );
  const player = entry.player;
  const copy = describe(entry, kind, target, next);
  node.querySelector("h3").textContent = player.player;
  node.querySelector(".player-meta").textContent =
    `${player.position} · ${player.team || "FA"} · Bye ${player.bye || "—"} · Composite ${player.base_composite_rank}`;
  node.querySelector(".availability").textContent = next
    ? `${Math.round(entry.goneChance * 100)}% gone by ${next}`
    : "Last pick";
  node.querySelector(".case").textContent = copy.caseText;
  node.querySelector(".pros").textContent = copy.pros;
  node.querySelector(".cons").textContent = copy.cons;
  const draftButton = node.querySelector(".draft-button");
  draftButton.textContent =
    currentOverall() === target ? "Draft this player" : "Record as next pick";
  draftButton.addEventListener("click", () => recordPlayer(player.player));
  node
    .querySelector(".research-button")
    .addEventListener("click", () => openPlayer(player));
  node
    .querySelector(".team-button")
    .addEventListener("click", () => openTeam(player.team));
  return node;
}

function renderList(selector, entries, kind, target, next) {
  const host = $(selector);
  host.replaceChildren();
  if (!entries.length) {
    host.innerHTML =
      '<p class="empty-state">No recommendation is available.</p>';
    return;
  }
  entries.forEach((entry) =>
    host.append(renderCandidate(entry, kind, target, next)),
  );
}

function recordPlayer(playerName, position = null, type = "live") {
  const overall = currentOverall();
  if (overall > 170) return;
  state.history.push(JSON.stringify(state.picks));
  state.picks.push({
    overall,
    round: roundAt(overall),
    manager: ownerAt(overall),
    player: playerName,
    position,
    type,
  });
  autoApplyKeepers();
  persist();
  $("#board-dialog").close();
  render();
}

function recordPlaceholder(position) {
  recordPlayer(`Other ${position}`, position, "placeholder");
}

function autoApplyKeepers() {
  state.data.draft.keepers.forEach((keeper) => {
    if (!state.picks.some((pick) => pick.overall === keeper.overall_pick)) {
      state.picks.push({
        overall: keeper.overall_pick,
        round: keeper.round,
        manager: keeper.manager,
        player: keeper.player,
        type: "keeper",
        status: keeper.status,
      });
    }
  });
  state.picks.sort((a, b) => a.overall - b.overall);
}

function persist() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      picks: state.picks,
      history: state.history,
      weights: state.weights,
      personalPriorities: state.personalPriorities,
    }),
  );
}
function restore() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  if (saved) {
    state.picks = saved.picks || [];
    state.history = saved.history || [];
    state.weights = { ...DEFAULT_WEIGHTS, ...(saved.weights || {}) };
    state.personalPriorities = saved.personalPriorities || {};
  }
  autoApplyKeepers();
}

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>'"]/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      })[character],
  );
}

function sourceLink(signal) {
  const label = escapeHtml(signal.source_name || "Source");
  try {
    const url = new URL(signal.source_url);
    if (!["http:", "https:"].includes(url.protocol)) return label;
    return `<a href="${escapeHtml(url.href)}" target="_blank" rel="noreferrer">${label}</a>`;
  } catch (_) {
    return label;
  }
}

function renderSignals(signals, applied) {
  if (!signals?.length) {
    const message = applied
      ? "No additional reviewed qualitative adjustment applies.  Structured injury, rookie, schedule, and ranking models are scored separately."
      : "No additional research-only qualitative findings are attached.";
    return `<li>${message}</li>`;
  }
  return signals
    .map((signal) => {
      const adjustment = Number(signal.capped_adjustment || 0);
      const signed =
        adjustment > 0 ? `+${adjustment.toFixed(1)}` : adjustment.toFixed(1);
      const expiry = signal.expires_at
        ? ` · expires ${escapeHtml(String(signal.expires_at).slice(0, 10))}`
        : "";
      const reason =
        !applied && signal.exclusion_reason
          ? `<br><span class="note-reason">${escapeHtml(signal.exclusion_reason)}</span>`
          : "";
      return `<li class="context-note ${applied ? "applied-note" : "research-note"}">
      <div><strong>${escapeHtml(signal.summary || "Reviewed finding")}</strong>${applied ? `<span class="adjustment-badge">${signed}</span>` : ""}</div>
      <div>${escapeHtml(signal.mechanism || "No mechanism stated")}</div>
      <small>${sourceLink(signal)} · ${Math.round(Number(signal.confidence || 0) * 100)}% confidence${expiry}</small>${reason}
    </li>`;
    })
    .join("");
}

function metricTone(value, thresholds = {}) {
  if (!Number.isFinite(value)) return "unavailable";
  if (value >= (thresholds.strongPositive ?? Infinity))
    return "strong-positive";
  if (value >= (thresholds.positive ?? Infinity)) return "positive";
  if (value <= (thresholds.strongNegative ?? -Infinity))
    return "strong-negative";
  if (value <= (thresholds.negative ?? -Infinity)) return "negative";
  return "neutral";
}

function renderMetric({
  label,
  value,
  tone = "neutral",
  impact = "Context",
  detail = "",
}) {
  return `<div class="detail-stat metric-${tone}">
    <div class="metric-label-row"><span>${escapeHtml(label)}</span><em>${escapeHtml(impact)}</em></div>
    <strong>${escapeHtml(value)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}
  </div>`;
}

function signedNumber(value) {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${number.toFixed(1)}`;
}

function openPlayer(player) {
  const adps = Object.values(player.adp_sources || {});
  const appliedNotes = renderSignals(player.classified_context?.applied, true);
  const researchNotes = renderSignals(
    player.classified_context?.research_only,
    false,
  );
  const target = nextUserOverall() || currentOverall();
  const qualitative = contextAdjustment(player).total * state.weights.context;
  const injury = injuryAdjustment(player) * state.weights.injuryRisk;
  const schedule =
    earlyScheduleAdjustment(player) * state.weights.earlySchedule;
  const rookie = rookieAdjustment(player, target) * state.weights.rookieUpside;
  const draftSharks = draftSharksAdjustment(player) * state.weights.draftSharks;
  const injuryModel = player.models.injury;
  const injuryPercentile = Number(injuryModel?.risk_percentile_at_position);
  const projectedMissed = Number(injuryModel?.projected_games_missed);
  const injuryTone = Number.isFinite(injuryPercentile)
    ? injuryPercentile <= 25
      ? "strong-positive"
      : injuryPercentile <= 50
        ? "positive"
        : injuryPercentile >= 80
          ? "strong-negative"
          : "negative"
    : "unavailable";
  const earlySos = Number(player.models.early_sos?.weeks_1_6_average);
  const earlySosTone = metricTone(earlySos, {
    strongPositive: 0.08,
    positive: 0.02,
    negative: -0.02,
    strongNegative: -0.08,
  });
  const qualitativeTone = metricTone(qualitative, {
    strongPositive: 1,
    positive: 0.05,
    negative: -0.05,
    strongNegative: -1,
  });
  const marketGap = player.adp
    ? Number(player.adp) - Number(player.base_composite_rank)
    : NaN;
  const marketGapTone = metricTone(marketGap, {
    strongPositive: 15,
    positive: 6,
    negative: -6,
    strongNegative: -15,
  });
  const disagreement = Number(player.source_quality.market_disagreement);
  const disagreementTone = Number.isFinite(disagreement)
    ? disagreement >= 30
      ? "strong-negative"
      : disagreement >= 15
        ? "negative"
        : disagreement <= 7
          ? "positive"
          : "neutral"
    : "unavailable";
  const rookiePercentile = Number(player.models.rookie?.overall_percentile);
  const rookieTone = Number.isFinite(rookiePercentile)
    ? rookiePercentile >= 90
      ? "strong-positive"
      : rookiePercentile >= 75
        ? "positive"
        : "neutral"
    : "unavailable";
  const depth = Number(player.depth_chart[0]?.depth);
  const depthTone = Number.isFinite(depth)
    ? depth === 1
      ? "positive"
      : depth >= 3
        ? "negative"
        : "neutral"
    : "unavailable";
  const dsGap = Number.isFinite(
    Number(player.models.draftsharks_superflex?.rank),
  )
    ? Number(player.base_composite_rank) -
      Number(player.models.draftsharks_superflex.rank)
    : NaN;
  const dsTone = metricTone(dsGap, {
    strongPositive: 15,
    positive: 6,
    negative: -6,
    strongNegative: -15,
  });
  const qualitativeDetail = player.classified_context?.applied?.length
    ? `${player.classified_context.applied.length} reviewed finding${player.classified_context.applied.length === 1 ? "" : "s"}`
    : "No applied qualitative finding";
  const positionalTier = Number(player.draftsheets_position_tier);
  const positionalTierTone = Number.isFinite(positionalTier)
    ? positionalTier <= 1
      ? "strong-positive"
      : positionalTier <= 3
        ? "positive"
        : positionalTier >= 8
          ? "negative"
          : "neutral"
    : "unavailable";
  const qbContext =
    player.position === "QB"
      ? { player: player.player, qb_chart_tier: player.qb_chart_tier }
      : player.team_qb_context;
  const availabilityStatus = player.availability_status;
  const personal = personalPriority(player);
  const personalTone = personal.avoid
    ? "strong-negative"
    : metricTone(personal.score, {
        strongPositive: 6,
        positive: 1,
        negative: -1,
        strongNegative: -6,
      });
  const personalValue = personal.avoid
    ? "Do not recommend"
    : personal.score
      ? `${personal.score > 0 ? "+" : ""}${personal.score}`
      : "Neutral";
  $("#dialog-content").innerHTML = `
    <p class="eyebrow">Player research card</p><h2>${player.player}</h2><p>${player.position} · ${player.team || "FA"} · Bye ${player.bye || "—"}</p>
    <div class="metric-legend"><span><i class="legend-positive"></i>Supports outlook</span><span><i class="legend-negative"></i>Weighs against</span><span><i class="legend-neutral"></i>Context / near neutral</span></div>
    <div class="detail-grid">
      ${renderMetric({ label: "Composite", value: `No. ${player.base_composite_rank}`, impact: "Baseline", detail: "Weighted expert rank" })}
      ${renderMetric({ label: "Quality score", value: player.base_quality_score.toFixed(1), impact: "Baseline", detail: "Cross-source consensus" })}
      ${renderMetric({ label: "Market ADP", value: player.adp ? player.adp.toFixed(1) : "Missing", tone: marketGapTone, impact: Number.isFinite(marketGap) ? (marketGap >= 6 ? "Possible value" : marketGap <= -6 ? "Market premium" : "Near consensus") : "Missing", detail: Number.isFinite(marketGap) ? `${Math.abs(marketGap).toFixed(1)} picks from composite` : "No matched 2QB ADP" })}
      ${renderMetric({ label: "Expert confidence", value: player.source_quality.expert, tone: player.source_quality.expert === "high" ? "positive" : player.source_quality.expert === "low" ? "negative" : "neutral", impact: "Source quality" })}
      ${renderMetric({ label: "Market confidence", value: player.source_quality.market, tone: player.source_quality.market === "high" ? "positive" : player.source_quality.market === "missing" ? "negative" : "neutral", impact: "Source quality" })}
      ${renderMetric({ label: "ADP disagreement", value: player.source_quality.market_disagreement ?? "—", tone: disagreementTone, impact: disagreementTone.includes("negative") ? "Uncertain market" : disagreementTone === "positive" ? "Good agreement" : "Context", detail: "Spread across matched ADP sources" })}
      ${renderMetric({ label: "Reviewed context", value: signedNumber(player.classified_context?.score_total), tone: qualitativeTone, impact: qualitative ? `Weighted ${signedNumber(qualitative)}` : "No current effect", detail: qualitativeDetail })}
      ${renderMetric({ label: "Injury probability", value: injuryModel ? `${Math.round(injuryModel.injury_probability * 100)}%` : "—", tone: injuryTone, impact: injury < 0 ? `Weighted ${signedNumber(injury)}` : injuryModel ? "No risk penalty" : "Missing", detail: Number.isFinite(injuryPercentile) ? `${injuryPercentile}th percentile risk at ${player.position}` : "No injury model match" })}
      ${renderMetric({ label: "Projected missed", value: injuryModel?.projected_games_missed ?? "—", tone: Number.isFinite(projectedMissed) ? (projectedMissed <= 0.5 ? "positive" : projectedMissed >= 2.5 ? "strong-negative" : projectedMissed > 1 ? "negative" : "neutral") : "unavailable", impact: "Same injury model", detail: "Shown for context; not scored twice" })}
      ${renderMetric({ label: "Early SOS", value: Number.isFinite(earlySos) ? `${earlySos > 0 ? "+" : ""}${(earlySos * 100).toFixed(1)}%` : "—", tone: earlySosTone, impact: schedule ? `Weighted ${signedNumber(schedule)}` : Number.isFinite(earlySos) ? "Near neutral" : "Missing", detail: "Weeks 1–6; positive means easier" })}
      ${renderMetric({ label: "Rookie model", value: player.models.rookie ? `${player.models.rookie.overall_score} · ${player.models.rookie.prospect_label}` : "—", tone: rookieTone, impact: rookie ? `Weighted +${rookie.toFixed(1)}` : Number.isFinite(rookiePercentile) ? "No current bump" : "Not applicable", detail: Number.isFinite(rookiePercentile) ? `${rookiePercentile}th percentile; upside grows later` : "" })}
      ${renderMetric({ label: "DS Superflex", value: player.models.draftsharks_superflex ? `No. ${player.models.draftsharks_superflex.rank}` : "—", tone: dsTone, impact: draftSharks ? `Weighted ${signedNumber(draftSharks)}` : Number.isFinite(dsGap) ? "Near composite" : "Missing", detail: Number.isFinite(dsGap) ? `${Math.abs(dsGap)} ranks ${dsGap > 0 ? "ahead of" : "behind"} composite` : "" })}
      ${renderMetric({ label: "Depth role", value: player.depth_chart[0] ? `${player.depth_chart[0].position}${player.depth_chart[0].depth}` : "—", tone: depthTone, impact: depth === 1 ? "Projected starter" : depth === 2 ? "Secondary role" : Number.isFinite(depth) ? "Buried role" : "Missing", detail: "Informational; verified notes drive adjustments" })}
      ${renderMetric({ label: "DraftSheets", value: player.draftsheets_overall_value_rank ? `No. ${player.draftsheets_overall_value_rank}` : "—", impact: "Baseline source" })}
      ${renderMetric({ label: "Overall Tier", value: Number.isFinite(positionalTier) ? `Tier ${positionalTier}` : "—", tone: positionalTierTone, impact: Number.isFinite(positionalTier) ? "DraftSheets tier" : "Missing", detail: "Name-keyed workbook formula" })}
      ${renderMetric({ label: "Mans rank", value: player.jeff_mans_rank ? `No. ${player.jeff_mans_rank}` : "—", impact: "Baseline source" })}
      ${renderMetric({ label: player.position === "QB" ? "QB tier" : "Team QB tier", value: qbContext?.qb_chart_tier || "—", tone: qbContext?.qb_chart_tier ? "neutral" : "unavailable", impact: qbContext?.qb_chart_tier ? "Passing environment" : "Missing", detail: qbContext?.player ? `${qbContext.player} · Ourlads starter` : "No matched starting-QB tier" })}
      ${renderMetric({ label: "Availability", value: availabilityStatus ? availabilityStatus.status.replaceAll("_", " ") : "Active / no override", tone: availabilityStatus?.draft_eligible === false ? "strong-negative" : "neutral", impact: availabilityStatus?.draft_eligible === false ? "Excluded" : "No hard exclusion", detail: availabilityStatus?.summary || "Current news still affects reviewed context separately" })}
      ${renderMetric({ label: "Personal priority", value: personalValue, tone: personalTone, impact: personal.avoid ? "Hard avoid" : personal.score ? `Weighted ${signedNumber(personal.score * state.weights.personalPriority)}` : "No current effect", detail: "Subjective Admin preference; not evidence-based" })}
    </div>
    <h3>How to read these influences</h3><p class="model-context-note">The colored cards show direction at the current tuning settings.  Injury probability, rookie upside, Weeks 1–6 schedule, and the DraftSharks comparison are structured inputs.  <strong>Reviewed context</strong> is the separate total from the cited qualitative findings below, so the same evidence is not counted twice.</p>
    <h3>Applied qualitative context</h3><ul class="source-list context-list">${appliedNotes}</ul>
    <details class="research-details"><summary>Research-only findings</summary><ul class="source-list context-list">${researchNotes}</ul></details>
    <h3>Recent news</h3><ul class="source-list">${player.recent_news.length ? player.recent_news.map((item) => `<li><a href="${item.headline_url}" target="_blank" rel="noreferrer">${item.headline}</a>${item.injury ? ` · ${item.injury}` : ""}<br>${item.update || ""}</li>`).join("") : "<li>No matching item in the latest RotoWire snapshot.</li>"}</ul>
    <h3>Market sources</h3><ul class="source-list">${adps.length ? adps.map((row) => `<li>${row.player_url ? `<a href="${row.player_url}" target="_blank" rel="noreferrer">${row.provider}</a>` : row.provider}: ADP ${Number(row.adp).toFixed(1)}${row.stdev ? `, spread ${row.stdev}` : ""}</li>`).join("") : "<li>No matched 2QB market record.</li>"}</ul>
    <h3>Further research</h3><ul class="source-list"><li><a href="${player.research_links.draftsharks_injury}" target="_blank" rel="noreferrer">DraftSharks injury model</a></li>${player.models.rookie ? `<li><a href="${player.research_links.draftsharks_rookie}" target="_blank" rel="noreferrer">DraftSharks rookie model</a></li>` : ""}<li><a href="${player.research_links.draftsharks_sos}" target="_blank" rel="noreferrer">DraftSharks positional schedule</a></li><li><a href="${player.research_links.draftsharks_superflex}" target="_blank" rel="noreferrer">DraftSharks Superflex ranking</a></li><li><a href="${player.research_links.fantasyguru_projections}" target="_blank" rel="noreferrer">FantasyGuru projections</a></li></ul>`;
  $("#detail-dialog").showModal();
}

function openTeam(abbreviation) {
  const team = state.data.teams.find(
    (item) => item.abbreviation === abbreviation,
  );
  if (!team) return;
  const notes = renderSignals(team.verified_notes, true);
  const researchNotes = renderSignals(team.research_only_notes, false);
  const context = team.offensive_starter_context;
  const sos = Object.entries(team.early_sos || {})
    .map(
      ([position, value]) =>
        `${position} ${(value.weeks_1_6_average * 100).toFixed(1)}%`,
    )
    .join(" · ");
  $("#dialog-content").innerHTML = `
    <p class="eyebrow">Fantasy team one-sheet</p><h2>${team.name}</h2><p>Bye ${team.bye || "—"}</p>
    <h3>Draftable player map</h3><ul class="team-player-list">${team.players
      .slice(0, 12)
      .map(
        (p) =>
          `<li><strong>${p.player}</strong> · ${p.position} · composite ${p.rank}</li>`,
      )
      .join("")}</ul>
    <h3>Structured model inputs</h3><p><strong>Early schedule:</strong> ${sos || "No current schedule snapshot."} <small>(positive is easier)</small></p>
    <p><strong>Depth-chart change markers:</strong> ${context["2026_acquisitions"]} projected offensive starters acquired in 2026 · ${context["2026_draft_picks"]} rookie starters · ${context.injured_inactive} injured/inactive starters</p>
    <h3>Applied qualitative context</h3><ul class="source-list context-list">${notes}</ul>
    <details class="research-details"><summary>Research-only findings</summary><ul class="source-list context-list">${researchNotes}</ul></details>
    <h3>Research paths</h3><ul class="source-list">${Object.entries(
      team.source_links,
    )
      .map(
        ([name, url]) =>
          `<li><a href="${url}" target="_blank" rel="noreferrer">${name.replaceAll("_", " ")}</a></li>`,
      )
      .join("")}</ul>`;
  $("#detail-dialog").showModal();
}

function openSearch() {
  $("#player-search").value = "";
  renderSearch("");
  $("#board-dialog").showModal();
  $("#player-search").focus();
}

function openTuning() {
  $("#admin-menu")?.removeAttribute("open");
  const labels = {
    availability: "Availability risk",
    roster: "Roster need",
    bye: "Bye protection",
    history: "League history",
    tiers: "Tier cliffs",
    context: "Verified context",
    injuryRisk: "Injury model",
    rookieUpside: "Rookie upside",
    earlySchedule: "Weeks 1–6 SOS",
    draftSharks: "DS composite",
    newsContext: "Reviewed news",
    roomTrend: "Draft-room trends",
    personalPriority: "Personal priority",
  };
  $("#tuning-controls").replaceChildren(
    ...Object.entries(labels).map(([key, label]) => {
      const wrapper = document.createElement("label");
      wrapper.className = "tuning-control";
      wrapper.innerHTML = `<span>${label}</span><input type="range" min="0" max="1.5" step="0.1" value="${state.weights[key]}" data-weight="${key}"><output>${Number(state.weights[key]).toFixed(1)}×</output>`;
      wrapper.querySelector("input").addEventListener("input", (event) => {
        wrapper.querySelector("output").textContent =
          `${Number(event.target.value).toFixed(1)}×`;
      });
      return wrapper;
    }),
  );
  $("#tuning-dialog").showModal();
}

function setPersonalPriority(player, next) {
  const key = normalizePlayerName(player.player);
  const score = clamp(Number(next.score) || 0, -10, 10);
  const avoid = Boolean(next.avoid);
  if (!score && !avoid) delete state.personalPriorities[key];
  else state.personalPriorities[key] = { score, avoid };
  persist();
  render();
}

function renderPersonalPriorities() {
  const query = $("#personal-priority-search").value.trim().toLowerCase();
  const modifiedOnly = $("#personal-modified-only").checked;
  const adjusted = Object.values(state.personalPriorities).filter((item) =>
    Number(item.score),
  ).length;
  const avoided = Object.values(state.personalPriorities).filter(
    (item) => item.avoid,
  ).length;
  $("#personal-priority-summary").textContent =
    `${adjusted} adjusted · ${avoided} hard avoided`;
  const players = state.data.players
    .filter(
      (player) =>
        !query ||
        `${player.player} ${player.position} ${player.team || ""}`
          .toLowerCase()
          .includes(query),
    )
    .filter(
      (player) =>
        !modifiedOnly ||
        personalPriority(player).score ||
        personalPriority(player).avoid,
    )
    .sort((a, b) => {
      const aModified =
        personalPriority(a).score || personalPriority(a).avoid ? 1 : 0;
      const bModified =
        personalPriority(b).score || personalPriority(b).avoid ? 1 : 0;
      return (
        bModified - aModified || a.base_composite_rank - b.base_composite_rank
      );
    });
  const rows = players.map((player) => {
    const setting = personalPriority(player);
    const row = document.createElement("div");
    row.className = "personal-priority-row";
    row.innerHTML = `<div class="personal-player"><strong>${escapeHtml(player.player)}</strong><span>${escapeHtml(player.position)} · ${escapeHtml(player.team || "FA")} · composite ${escapeHtml(player.base_composite_rank)}${player.draft_eligible === false ? " · unavailable" : ""}</span></div>
      <div class="priority-stepper">
        <button type="button" aria-label="Lower ${escapeHtml(player.player)}">−</button>
        <output class="${setting.score > 0 ? "priority-positive" : setting.score < 0 ? "priority-negative" : ""}">${setting.score > 0 ? "+" : ""}${setting.score}</output>
        <button type="button" aria-label="Raise ${escapeHtml(player.player)}">+</button>
      </div>
      <label class="avoid-toggle"><input type="checkbox" ${setting.avoid ? "checked" : ""}> Do not recommend</label>`;
    const [lower, raise] = row.querySelectorAll(".priority-stepper button");
    lower.addEventListener("click", () => {
      setPersonalPriority(player, {
        ...personalPriority(player),
        score: setting.score - 1,
      });
      renderPersonalPriorities();
    });
    raise.addEventListener("click", () => {
      setPersonalPriority(player, {
        ...personalPriority(player),
        score: setting.score + 1,
      });
      renderPersonalPriorities();
    });
    row
      .querySelector(".avoid-toggle input")
      .addEventListener("change", (event) => {
        setPersonalPriority(player, {
          ...personalPriority(player),
          avoid: event.target.checked,
        });
        renderPersonalPriorities();
      });
    return row;
  });
  if (rows.length) $("#personal-priority-list").replaceChildren(...rows);
  else
    $("#personal-priority-list").innerHTML =
      '<p class="empty-state">No matching players.</p>';
}

function openPersonalPriorities() {
  $("#admin-menu")?.removeAttribute("open");
  $("#personal-priority-search").value = "";
  $("#personal-modified-only").checked = false;
  renderPersonalPriorities();
  $("#personal-priority-dialog").showModal();
  $("#personal-priority-search").focus();
}

function saveTuning() {
  document.querySelectorAll("[data-weight]").forEach((input) => {
    state.weights[input.dataset.weight] = Number(input.value);
  });
  persist();
  $("#tuning-dialog").close();
  render();
}

function closeDialogFromBackdrop(event) {
  const dialog = event.currentTarget;
  const bounds = dialog.getBoundingClientRect();
  const outside =
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom;
  if (outside) dialog.close();
}

const DRAFT_SERVER_ORIGINS = new Set([
  "http://127.0.0.1:8765",
  "http://localhost:8765",
]);

async function readJsonResponse(response, operation) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    const body = await response.text();
    const looksLikeHtml =
      body.trimStart().startsWith("<!DOCTYPE") ||
      body.trimStart().startsWith("<html");
    if (response.status === 501 || looksLikeHtml) {
      throw new Error(
        "Refresh & Rebuild needs the Fantasy Draft Manager server.  From the project root, run: python3 2026/App/serve.py  Then open http://127.0.0.1:8765.",
      );
    }
    throw new Error(
      `${operation} returned ${response.status} ${response.statusText || "without JSON"}.`,
    );
  }
  try {
    return await response.json();
  } catch (_) {
    throw new Error(`${operation} returned an invalid JSON response.`);
  }
}

async function refreshAndRebuild() {
  $("#admin-menu")?.removeAttribute("open");
  const button = $("#refresh-rebuild");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Rebuilding…";
  try {
    if (!DRAFT_SERVER_ORIGINS.has(window.location.origin)) {
      throw new Error(
        "Refresh & Rebuild needs the Fantasy Draft Manager server.  From the project root, run: python3 2026/App/serve.py  Then open http://127.0.0.1:8765.",
      );
    }
    const draftedPlayers = state.picks
      .filter((pick) => !["keeper", "placeholder"].includes(pick.type))
      .map((pick) => pick.player);
    const response = await fetch("/api/refresh-rebuild", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drafted_players: draftedPlayers }),
    });
    const result = await readJsonResponse(response, "The rebuild service");
    if (!response.ok) throw new Error(result.error || "Rebuild failed");
    const boardResponse = await fetch(
      `data/draft-board.json?refresh=${Date.now()}`,
    );
    const refreshedData = await readJsonResponse(
      boardResponse,
      "The refreshed draft board",
    );
    if (!boardResponse.ok)
      throw new Error(
        refreshedData.error || "The refreshed draft board could not be loaded",
      );
    const refreshedNames = new Map(
      refreshedData.players.map((player) => [
        normalizePlayerName(player.player),
        player.player,
      ]),
    );
    const missingDraftedPlayers = state.picks.filter(
      (pick) =>
        !["keeper", "placeholder"].includes(pick.type) &&
        !refreshedNames.has(normalizePlayerName(pick.player)),
    );
    if (missingDraftedPlayers.length) {
      throw new Error(
        `The refreshed board could not reconcile: ${missingDraftedPlayers.map((pick) => pick.player).join(", ")}.  Recorded picks were preserved.`,
      );
    }
    state.data = refreshedData;
    state.picks = state.picks
      .filter((pick) => pick.type !== "keeper")
      .map((pick) => ({
        ...pick,
        player:
          refreshedNames.get(normalizePlayerName(pick.player)) || pick.player,
      }));
    state.history = state.history.map((snapshot) =>
      JSON.stringify(
        JSON.parse(snapshot)
          .filter((pick) => pick.type !== "keeper")
          .map((pick) => ({
            ...pick,
            player:
              refreshedNames.get(normalizePlayerName(pick.player)) ||
              pick.player,
          })),
      ),
    );
    autoApplyKeepers();
    persist();
    render();
    const warnings = result.warnings?.length
      ? `  ${result.warnings.join(" ")}`
      : "";
    window.alert(
      `Rankings rebuilt successfully.  Recorded picks, tuning settings, and personal priorities were preserved.${warnings}`,
    );
  } catch (error) {
    window.alert(`The active draft was not changed.  ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function resetDraft() {
  $("#admin-menu")?.removeAttribute("open");
  if (
    !window.confirm(
      "Clear every recorded live pick and begin a new draft?  Confirmed keepers, tuning settings, and personal priorities will remain.",
    )
  )
    return;
  state.picks = [];
  state.history = [];
  autoApplyKeepers();
  persist();
  render();
}

function renderSearch(query) {
  const words = query.trim().toLowerCase();
  const players = availablePlayers()
    .filter((p) => !words || p.player.toLowerCase().includes(words))
    .slice(0, 20);
  $("#search-results").replaceChildren(
    ...players.map((player) => {
      const button = document.createElement("button");
      button.className = "search-result";
      button.innerHTML = `<strong>${player.player}</strong><span>${player.position} · ${player.team} · rank ${player.base_composite_rank}</span>`;
      button.addEventListener("click", () => recordPlayer(player.player));
      return button;
    }),
  );
}

function renderPlaceholderPicks() {
  $("#other-picks").replaceChildren(
    ...ROSTER_POSITIONS.map((position) => {
      const button = document.createElement("button");
      button.className = "other-pick-button";
      button.type = "button";
      button.textContent = `Other ${position}`;
      button.addEventListener("click", () => recordPlaceholder(position));
      return button;
    }),
  );
}

function renderRoster() {
  const roster = userPicks().sort((a, b) => a.overall - b.overall);
  $("#roster-summary").textContent =
    `${roster.length} of ${state.data.draft.rounds} spots filled`;
  const target =
    state.data.policy?.roster_constructions?.three_qb_wr_depth || {};
  const groups = Object.fromEntries(
    ROSTER_POSITIONS.map((position) => [position, []]),
  );
  roster.forEach((pick) => {
    const player =
      state.data.players.find((item) => item.player === pick.player) ||
      (pick.position
        ? { player: pick.player, position: pick.position, team: "", bye: null }
        : null);
    if (player && groups[player.position])
      groups[player.position].push({ pick, player });
  });
  const columns = ROSTER_POSITIONS.map((position) => {
    const column = document.createElement("section");
    column.className = "roster-position";
    const entries = groups[position];
    const targetText = target[position]
      ? `${entries.length} / ${target[position]}`
      : String(entries.length);
    const byeCounts = entries.reduce((counts, { player }) => {
      const bye = String(player.bye || "");
      if (bye) counts[bye] = (counts[bye] || 0) + 1;
      return counts;
    }, {});
    column.innerHTML = `<header class="roster-position-header"><h3>${position}</h3><span class="roster-position-count">${targetText}</span></header>`;
    const list = document.createElement("div");
    list.className = "roster-player-list";
    if (!entries.length) {
      list.innerHTML = '<div class="roster-empty">No players yet</div>';
    } else {
      entries.forEach(({ pick, player }) => {
        const row = document.createElement("div");
        row.className = "roster-player";
        const keeper =
          pick.type === "keeper"
            ? `<span class="keeper-tag">K${roundAt(pick.overall)}</span>`
            : "";
        const byeConflictClass =
          byeCounts[String(player.bye)] > 1 ? " bye-conflict" : "";
        row.innerHTML = `<div class="roster-player-name" title="${escapeHtml(player.player)}">${escapeHtml(player.player)}${keeper}</div><div class="roster-player-meta${byeConflictClass}">${escapeHtml(player.team || "—")} · Bye ${escapeHtml(player.bye || "—")}</div>`;
        if (byeConflictClass)
          row.title = `Multiple ${position}s share bye ${player.bye}`;
        list.append(row);
      });
    }
    column.append(list);
    return column;
  });
  $("#roster").replaceChildren(...columns);
}

function render() {
  const current = currentOverall();
  const recs = recommendations();
  $("#on-clock").textContent =
    current <= 170 ? `${ownerAt(current)} · Pick ${current}` : "Draft complete";
  $("#next-pick").textContent = recs.target
    ? `No. ${recs.target} · Round ${roundAt(recs.target)}`
    : "Complete";
  renderRoster();
  renderList(
    "#optimized-list",
    recs.optimized,
    "optimized",
    recs.target,
    recs.next,
  );
  renderList(
    "#consensus-list",
    recs.consensus,
    "consensus",
    recs.target,
    recs.next,
  );
  renderList(
    "#wildcard-list",
    recs.wildcard,
    "wildcard",
    recs.target,
    recs.next,
  );
  const unknown = state.data.draft.unknown_inputs;
  $("#data-alert").classList.toggle("visible", unknown.length > 0);
  $("#data-alert").textContent =
    `Stafford is confirmed at pick 64.  Still needed before draft day: ${unknown.slice(0, 2).join("; ").toLowerCase()}.`;
  $("#undo").disabled = !state.history.length;
}

async function init() {
  state.data = await fetch("data/draft-board.json").then((response) =>
    response.json(),
  );
  restore();
  $("#undo").addEventListener("click", () => {
    if (!state.history.length) return;
    state.picks = JSON.parse(state.history.pop());
    autoApplyKeepers();
    persist();
    render();
  });
  $("#open-board").addEventListener("click", openSearch);
  $("#open-personal-priorities").addEventListener(
    "click",
    openPersonalPriorities,
  );
  $("#open-tuning").addEventListener("click", openTuning);
  $("#refresh-rebuild").addEventListener("click", refreshAndRebuild);
  $("#reset-draft").addEventListener("click", resetDraft);
  $("#save-tuning").addEventListener("click", saveTuning);
  $("#reset-tuning").addEventListener("click", () => {
    document.querySelectorAll("[data-weight]").forEach((input) => {
      input.value = DEFAULT_WEIGHTS[input.dataset.weight];
      input.closest(".tuning-control").querySelector("output").textContent =
        `${Number(input.value).toFixed(1)}×`;
    });
  });
  $("#player-search").addEventListener("input", (event) =>
    renderSearch(event.target.value),
  );
  $("#personal-priority-search").addEventListener(
    "input",
    renderPersonalPriorities,
  );
  $("#personal-modified-only").addEventListener(
    "change",
    renderPersonalPriorities,
  );
  $("#clear-personal-priorities").addEventListener("click", () => {
    if (!Object.keys(state.personalPriorities).length) return;
    if (!window.confirm("Clear every personal boost, fade, and hard avoid?"))
      return;
    state.personalPriorities = {};
    persist();
    render();
    renderPersonalPriorities();
  });
  renderPlaceholderPicks();
  document.addEventListener("click", (event) => {
    const menu = $("#admin-menu");
    if (menu?.open && !menu.contains(event.target))
      menu.removeAttribute("open");
  });
  $("#board-dialog").addEventListener("click", closeDialogFromBackdrop);
  $("#detail-dialog").addEventListener("click", closeDialogFromBackdrop);
  $("#personal-priority-dialog").addEventListener(
    "click",
    closeDialogFromBackdrop,
  );
  document
    .querySelectorAll("[data-close]")
    .forEach((button) =>
      button.addEventListener("click", () => button.closest("dialog").close()),
    );
  render();
}

if (typeof module !== "undefined" && module.exports)
  module.exports = {
    recommendationPolicyDecision,
    draftRoomTrendDecision,
    personalPriorityDecision,
  };

if (typeof document !== "undefined") {
  init().catch((error) => {
    $("#data-alert").classList.add("visible");
    $("#data-alert").textContent =
      `The draft data did not load.  Start this folder through the local preview command.  ${error.message}`;
  });
}
