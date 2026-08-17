const STORAGE_KEY = "fantasy-draft-manager-2026-v1";
const DEFAULT_WEIGHTS = { availability: 1, roster: 1, bye: 1, history: .7, tiers: .8, context: .7 };
const state = { data: null, picks: [], history: [], weights: { ...DEFAULT_WEIGHTS } };

const $ = (selector) => document.querySelector(selector);
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const normalCdf = (x) => {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp(-x * x / 2);
  const p = 1 - d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x >= 0 ? p : 1 - p;
};

function ownerAt(overall) {
  const { draft_order: order } = state.data.draft;
  const round = Math.floor((overall - 1) / order.length) + 1;
  const slot = (overall - 1) % order.length;
  return round % 2 ? order[slot] : [...order].reverse()[slot];
}

function roundAt(overall) { return Math.floor((overall - 1) / 10) + 1; }
function selectedNames() { return new Set(state.picks.map((pick) => pick.player)); }
function currentOverall() {
  for (let pick = 1; pick <= 170; pick += 1) if (!state.picks.some((item) => item.overall === pick)) return pick;
  return 171;
}
function userPicks() { return state.picks.filter((pick) => pick.manager === state.data.draft.user_manager); }
function availablePlayers() { const gone = selectedNames(); return state.data.players.filter((p) => !gone.has(p.player)); }
function nextUserOverall(from = currentOverall()) {
  for (let pick = from; pick <= 170; pick += 1) {
    if (ownerAt(pick) === state.data.draft.user_manager && !state.picks.some((item) => item.overall === pick)) return pick;
  }
  return null;
}
function followingUserOverall(target) { return target ? nextUserOverall(target + 1) : null; }

function rosterCounts() {
  return userPicks().reduce((counts, pick) => {
    const player = state.data.players.find((p) => p.player === pick.player);
    if (player) counts[player.position] = (counts[player.position] || 0) + 1;
    return counts;
  }, {});
}

function availability(player, nextPick) {
  if (!player.adp || !nextPick) return 0.45;
  const deviations = Object.values(player.adp_sources || {}).map((row) => Number(row.stdev)).filter(Number.isFinite);
  const spread = Math.max(4, deviations.length ? deviations.reduce((a, b) => a + b, 0) / deviations.length : 10);
  return clamp(normalCdf((nextPick - player.adp) / spread), 0.02, 0.99);
}

function byeConflict(player) {
  const samePosition = userPicks().map((pick) => state.data.players.find((p) => p.player === pick.player)).filter(Boolean)
    .filter((p) => p.position === player.position && String(p.bye) === String(player.bye));
  if (player.position === "QB" && samePosition.length) return 12;
  const limits = { WR: 3, RB: 2, TE: 1 };
  return samePosition.length >= (limits[player.position] || 3) ? 7 : samePosition.length * 1.5;
}

function contextAdjustment(player) {
  const total = (player.context || []).filter((item) => Number(item.confidence) >= .6)
    .reduce((sum, item) => sum + Number(item.adjustment || 0), 0);
  return clamp(total, -8, 8);
}

function historicalPressure(player, targetPick, nextPick) {
  if (player.position !== "QB" || !nextPick) return 0;
  const managers = new Set();
  for (let pick = targetPick + 1; pick < nextPick; pick += 1) managers.add(ownerAt(pick));
  managers.delete(state.data.draft.user_manager);
  const round = roundAt(targetPick);
  let pressure = 0;
  managers.forEach((manager) => {
    const tendency = state.data.league_history.manager_tendencies[manager];
    if (!tendency) return;
    const first = Number(tendency.avg_first_live_qb_round);
    const volume = Number(tendency.avg_live_qbs);
    if (round >= first - 1) pressure += clamp((volume - 2.1) * .45, .15, .7);
  });
  return clamp(pressure, 0, 3);
}

function tierCliff(player) {
  const nextAtPosition = availablePlayers().filter((p) => p.position === player.position && p.base_composite_rank > player.base_composite_rank)
    .sort((a, b) => a.base_composite_rank - b.base_composite_rank)[0];
  if (!nextAtPosition) return 0;
  return clamp((player.base_quality_score - nextAtPosition.base_quality_score) * .75, 0, 4);
}

function positionNeed(player, targetPick) {
  const counts = rosterCounts();
  const round = roundAt(targetPick);
  const count = counts[player.position] || 0;
  let score = 0;
  if (player.position === "QB") {
    if (count < 2) score += round <= 6 ? 8 : 14;
    else if (count < 3) score += round >= 7 ? 9 : 3;
    else if (count >= 4) score -= 14;
  }
  if (player.position === "WR") {
    if (count === 0 && round >= 3) score += 7;
    if (count < 3 && round >= 5) score += 8;
    if (count < 5 && round >= 9) score += 10;
  }
  if (player.position === "RB" && count < 2 && round >= 6) score += 6;
  if (player.position === "TE" && count === 0 && round >= 8) score += 5;
  if (["K", "DST"].includes(player.position)) score += round < 15 ? -28 : (count ? -20 : 5);
  return score;
}

function scorePlayer(player, targetPick, nextPick) {
  const goneChance = availability(player, nextPick);
  const rankValue = 101 - Math.min(100, player.base_composite_rank * .55);
  const marketValue = player.adp ? clamp((targetPick - player.adp) * .35, -8, 9) : -2;
  const need = positionNeed(player, targetPick);
  const bye = byeConflict(player);
  const context = contextAdjustment(player);
  const history = historicalPressure(player, targetPick, nextPick);
  const tiers = tierCliff(player);
  return {
    optimized: player.base_quality_score * .72 + rankValue * .18 + goneChance * 8 * state.weights.availability + marketValue + need * state.weights.roster + context * state.weights.context - bye * state.weights.bye + history * state.weights.history + tiers * state.weights.tiers,
    consensus: player.base_quality_score * .78 + rankValue * .17 + marketValue * .5,
    wildcard: player.base_quality_score * .55 + goneChance * 12 * state.weights.availability + Math.max(0, (player.adp || 240) - player.base_composite_rank) * .24 + Math.max(0, need) * .5 * state.weights.roster + context * state.weights.context - bye * state.weights.bye + tiers * state.weights.tiers,
    goneChance, need, bye, context, history, tiers
  };
}

function recommendations() {
  const target = nextUserOverall();
  const next = followingUserOverall(target);
  if (!target) return { target, next, optimized: [], consensus: [], wildcard: [] };
  const scored = availablePlayers().map((player) => ({ player, ...scorePlayer(player, target, next) }));
  const optimized = [...scored].sort((a, b) => b.optimized - a.optimized).slice(0, 3);
  const consensus = [...scored].sort((a, b) => b.consensus - a.consensus).slice(0, 3);
  const defaultNames = new Set([...optimized, ...consensus].map((x) => x.player.player));
  let wildcard = [...scored]
    .filter((x) => !defaultNames.has(x.player.player))
    .filter((x) => x.player.base_composite_rank <= target + 45 || (x.player.adp && x.player.adp <= (next || target + 20)))
    .filter((x) => !["K", "DST"].includes(x.player.position) || roundAt(target) >= 15)
    .sort((a, b) => b.wildcard - a.wildcard).slice(0, 3);
  if (wildcard.length < 3) wildcard = [...scored].filter((x) => !defaultNames.has(x.player.player)).sort((a, b) => b.wildcard - a.wildcard).slice(0, 3);
  return { target, next, optimized, consensus, wildcard };
}

function describe(entry, kind, target, next) {
  const { player } = entry;
  const targetRound = roundAt(target);
  const pct = Math.round(entry.goneChance * 100);
  const market = player.adp ? `Market ADP ${player.adp.toFixed(1)}` : "No matched public ADP";
  const source = `${player.source_count} ranking source${player.source_count === 1 ? "" : "s"}`;
  const cases = {
    optimized: `${player.position} value adjusted for your current roster, bye coverage, and the ${next ? next - target : 0}-pick wait after this selection.`,
    consensus: `Composite rank No. ${player.base_composite_rank}, using the current expert inputs as the neutral baseline.`,
    wildcard: `A defensible departure from the top of the board: the quality-versus-market gap creates upside without reaching blindly.`
  };
  const pros = [market, source];
  if (entry.need >= 6) pros.unshift(`Addresses a roster need by Round ${targetRound}`);
  if (player.adp && player.base_composite_rank + 8 < player.adp) pros.unshift("Experts rate him materially above his market cost");
  if (entry.context > 0) pros.unshift("Supported by verified positive context");
  const cons = [];
  if (entry.bye >= 7) cons.push("Creates a positional bye-coverage problem");
  else if (entry.bye > 0) cons.push("Adds another same-position player on this bye");
  if (!player.adp) cons.push("Public 2QB availability data is missing");
  if (!player.context.length) cons.push("No verified contextual adjustment is loaded yet");
  if (player.source_count < 2) cons.push("Thin expert-source coverage");
  if (!cons.length) cons.push(`About ${pct}% likely to be drafted before pick ${next || "—"}`);
  return { caseText: cases[kind], pros: pros.slice(0, 2).join(" · "), cons: cons.slice(0, 2).join(" · ") };
}

function renderCandidate(entry, kind, target, next) {
  const node = $("#candidate-template").content.firstElementChild.cloneNode(true);
  const player = entry.player;
  const copy = describe(entry, kind, target, next);
  node.querySelector("h3").textContent = player.player;
  node.querySelector(".player-meta").textContent = `${player.position} · ${player.team || "FA"} · Bye ${player.bye || "—"} · Composite ${player.base_composite_rank}`;
  node.querySelector(".availability").textContent = next ? `${Math.round(entry.goneChance * 100)}% gone by ${next}` : "Last pick";
  node.querySelector(".case").textContent = copy.caseText;
  node.querySelector(".pros").textContent = copy.pros;
  node.querySelector(".cons").textContent = copy.cons;
  const draftButton = node.querySelector(".draft-button");
  draftButton.textContent = currentOverall() === target ? "Draft this player" : "Record as next pick";
  draftButton.addEventListener("click", () => recordPlayer(player.player));
  node.querySelector(".research-button").addEventListener("click", () => openPlayer(player));
  node.querySelector(".team-button").addEventListener("click", () => openTeam(player.team));
  return node;
}

function renderList(selector, entries, kind, target, next) {
  const host = $(selector);
  host.replaceChildren();
  if (!entries.length) { host.innerHTML = '<p class="empty-state">No recommendation is available.</p>'; return; }
  entries.forEach((entry) => host.append(renderCandidate(entry, kind, target, next)));
}

function recordPlayer(playerName) {
  const overall = currentOverall();
  if (overall > 170) return;
  state.history.push(JSON.stringify(state.picks));
  state.picks.push({ overall, round: roundAt(overall), manager: ownerAt(overall), player: playerName, type: "live" });
  autoApplyKeepers();
  persist();
  $("#board-dialog").close();
  render();
}

function autoApplyKeepers() {
  state.data.draft.keepers.forEach((keeper) => {
    if (!state.picks.some((pick) => pick.overall === keeper.overall_pick)) {
      state.picks.push({ overall: keeper.overall_pick, round: keeper.round, manager: keeper.manager, player: keeper.player, type: "keeper", status: keeper.status });
    }
  });
  state.picks.sort((a, b) => a.overall - b.overall);
}

function persist() { localStorage.setItem(STORAGE_KEY, JSON.stringify({ picks: state.picks, history: state.history, weights: state.weights })); }
function restore() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  if (saved) { state.picks = saved.picks || []; state.history = saved.history || []; state.weights = { ...DEFAULT_WEIGHTS, ...(saved.weights || {}) }; }
  autoApplyKeepers();
}

function openPlayer(player) {
  const adps = Object.values(player.adp_sources || {});
  const notes = player.context.length ? player.context.map((item) => `<li>${item.summary} (${item.source}, ${item.date})</li>`).join("") : "<li>No verified contextual notes are loaded.  The model applies no narrative adjustment.</li>";
  $("#dialog-content").innerHTML = `
    <p class="eyebrow">Player research card</p><h2>${player.player}</h2><p>${player.position} · ${player.team || "FA"} · Bye ${player.bye || "—"}</p>
    <div class="detail-grid">
      <div class="detail-stat"><span>Composite</span><strong>No. ${player.base_composite_rank}</strong></div>
      <div class="detail-stat"><span>Quality score</span><strong>${player.base_quality_score.toFixed(1)}</strong></div>
      <div class="detail-stat"><span>Market ADP</span><strong>${player.adp ? player.adp.toFixed(1) : "Missing"}</strong></div>
      <div class="detail-stat"><span>Expert confidence</span><strong>${player.source_quality.expert}</strong></div>
      <div class="detail-stat"><span>Market confidence</span><strong>${player.source_quality.market}</strong></div>
      <div class="detail-stat"><span>ADP disagreement</span><strong>${player.source_quality.market_disagreement ?? "—"}</strong></div>
      <div class="detail-stat"><span>DraftSheets</span><strong>${player.draftsheets_overall_value_rank ? `No. ${player.draftsheets_overall_value_rank}` : "—"}</strong></div>
      <div class="detail-stat"><span>Mans rank</span><strong>${player.jeff_mans_rank ? `No. ${player.jeff_mans_rank}` : "—"}</strong></div>
      <div class="detail-stat"><span>QB tier</span><strong>${player.qb_chart_tier || "—"}</strong></div>
    </div>
    <h3>Verified context</h3><ul class="source-list">${notes}</ul>
    <h3>Market sources</h3><ul class="source-list">${adps.length ? adps.map((row) => `<li>${row.player_url ? `<a href="${row.player_url}" target="_blank" rel="noreferrer">${row.provider}</a>` : row.provider}: ADP ${Number(row.adp).toFixed(1)}${row.stdev ? `, spread ${row.stdev}` : ""}</li>`).join("") : "<li>No matched 2QB market record.</li>"}</ul>
    <h3>Further research</h3><ul class="source-list"><li><a href="${player.research_links.fantasyguru_projections}" target="_blank" rel="noreferrer">FantasyGuru projections</a></li></ul>`;
  $("#detail-dialog").showModal();
}

function openTeam(abbreviation) {
  const team = state.data.teams.find((item) => item.abbreviation === abbreviation);
  if (!team) return;
  const notes = team.verified_notes.length ? team.verified_notes.map((note) => `<li>${note.summary}</li>`).join("") : "<li>No verified coaching, personnel, line, or injury note has been loaded into this snapshot.</li>";
  $("#dialog-content").innerHTML = `
    <p class="eyebrow">Fantasy team one-sheet</p><h2>${team.name}</h2><p>Bye ${team.bye || "—"}</p>
    <h3>Draftable player map</h3><ul class="team-player-list">${team.players.slice(0, 12).map((p) => `<li><strong>${p.player}</strong> · ${p.position} · composite ${p.rank}</li>`).join("")}</ul>
    <h3>Verified decision context</h3><ul class="source-list">${notes}</ul>
    <h3>Research paths</h3><ul class="source-list">${Object.entries(team.source_links).map(([name, url]) => `<li><a href="${url}" target="_blank" rel="noreferrer">${name.replaceAll("_", " ")}</a></li>`).join("")}</ul>`;
  $("#detail-dialog").showModal();
}

function openSearch() {
  $("#player-search").value = "";
  renderSearch("");
  $("#board-dialog").showModal();
  $("#player-search").focus();
}

function openTuning() {
  const labels = { availability: "Availability risk", roster: "Roster need", bye: "Bye protection", history: "League history", tiers: "Tier cliffs", context: "Verified context" };
  $("#tuning-controls").replaceChildren(...Object.entries(labels).map(([key, label]) => {
    const wrapper = document.createElement("label");
    wrapper.className = "tuning-control";
    wrapper.innerHTML = `<span>${label}</span><input type="range" min="0" max="1.5" step="0.1" value="${state.weights[key]}" data-weight="${key}"><output>${Number(state.weights[key]).toFixed(1)}×</output>`;
    wrapper.querySelector("input").addEventListener("input", (event) => { wrapper.querySelector("output").textContent = `${Number(event.target.value).toFixed(1)}×`; });
    return wrapper;
  }));
  $("#tuning-dialog").showModal();
}

function saveTuning() {
  document.querySelectorAll("[data-weight]").forEach((input) => { state.weights[input.dataset.weight] = Number(input.value); });
  persist();
  $("#tuning-dialog").close();
  render();
}
function renderSearch(query) {
  const words = query.trim().toLowerCase();
  const players = availablePlayers().filter((p) => !words || p.player.toLowerCase().includes(words)).slice(0, 20);
  $("#search-results").replaceChildren(...players.map((player) => {
    const button = document.createElement("button");
    button.className = "search-result";
    button.innerHTML = `<strong>${player.player}</strong><span>${player.position} · ${player.team} · rank ${player.base_composite_rank}</span>`;
    button.addEventListener("click", () => recordPlayer(player.player));
    return button;
  }));
}

function renderRoster() {
  const roster = userPicks().sort((a, b) => a.overall - b.overall);
  $("#roster").replaceChildren(...roster.map((pick) => {
    const player = state.data.players.find((p) => p.player === pick.player);
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `<strong>${player?.position || "?"}</strong> ${pick.player}${pick.type === "keeper" ? " · K7" : ""}`;
    return chip;
  }));
}

function render() {
  const current = currentOverall();
  const recs = recommendations();
  $("#on-clock").textContent = current <= 170 ? `${ownerAt(current)} · Pick ${current}` : "Draft complete";
  $("#next-pick").textContent = recs.target ? `No. ${recs.target} · Round ${roundAt(recs.target)}` : "Complete";
  renderRoster();
  renderList("#optimized-list", recs.optimized, "optimized", recs.target, recs.next);
  renderList("#consensus-list", recs.consensus, "consensus", recs.target, recs.next);
  renderList("#wildcard-list", recs.wildcard, "wildcard", recs.target, recs.next);
  const unknown = state.data.draft.unknown_inputs;
  $("#data-alert").classList.toggle("visible", unknown.length > 0);
  $("#data-alert").textContent = `Working assumptions: Stafford is reserved at pick 64.  Still needed before draft day: ${unknown.slice(0, 2).join("; ").toLowerCase()}.`;
  $("#undo").disabled = !state.history.length;
}

async function init() {
  state.data = await fetch("data/draft-board.json").then((response) => response.json());
  restore();
  $("#undo").addEventListener("click", () => {
    if (!state.history.length) return;
    state.picks = JSON.parse(state.history.pop());
    autoApplyKeepers(); persist(); render();
  });
  $("#open-board").addEventListener("click", openSearch);
  $("#open-tuning").addEventListener("click", openTuning);
  $("#save-tuning").addEventListener("click", saveTuning);
  $("#reset-tuning").addEventListener("click", () => {
    document.querySelectorAll("[data-weight]").forEach((input) => {
      input.value = DEFAULT_WEIGHTS[input.dataset.weight];
      input.closest(".tuning-control").querySelector("output").textContent = `${Number(input.value).toFixed(1)}×`;
    });
  });
  $("#player-search").addEventListener("input", (event) => renderSearch(event.target.value));
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  render();
}

init().catch((error) => {
  $("#data-alert").classList.add("visible");
  $("#data-alert").textContent = `The draft data did not load.  Start this folder through the local preview command.  ${error.message}`;
});
