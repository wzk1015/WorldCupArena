// WorldCupArena site — fetches data.json written by src.leaderboard.build_site
// and renders everything client-side.

const fmtPct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const fmt2   = (x) => (x == null ? "—" : (+x).toFixed(2));
const esc    = (s) => String(s ?? "").replace(/[<>&"']/g, c =>
  ({ "<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;" }[c]));

function fmtModelId(id) {
  if (!id) return id;
  if (id.endsWith("-search")) return id.slice(0, -7) + " (Search)";
  return id;
}

let _allPreds = [];  // flat registry of all rendered pred cards (for modal)

const SETTING_TIPS = {
  S1: "S1 · LLM with full injected context pack (official squads, recent form, ~20 news headlines, stats). No tools.",
  S2: "S2 · Tool-using agent, self-directed search. No context pre-injected — the model searches for everything itself.",
};

function modelBadge(id) {
  const key = (id || "").toLowerCase();
  if (key.includes("gpt") || key.includes("o1") || key.includes("o3") || key.includes("o4"))
                               return { emoji: "🟢" };
  if (key.includes("claude"))  return { emoji: "🟠" };
  if (key.includes("gemini"))  return { emoji: "🔵" };
  if (key.includes("grok"))    return { emoji: "⬛" };
  if (key.includes("deepseek"))return { emoji: "🟣" };
  if (key.includes("qwen"))    return { emoji: "🔴" };
  if (key.includes("kimi") || key.includes("moonshot")) return { emoji: "🌙" };
  if (key.includes("glm") || key.includes("zhipu"))     return { emoji: "💠" };
  if (key.includes("llama"))   return { emoji: "🦙" };
  if (key.includes("perplexity")) return { emoji: "🔷" };
  if (key.includes("mirothinker")) return { emoji: "✨" };
  return { emoji: "🤖" };
}

// ---------- Reasoning modal --------------------------------------------------

const REASONING_LABELS = {
  overall:   "Overall Analysis",
  t1_result: "T1 · Result & Score",
  t2_player: "T2 · Players & Lineups",
  t3_events: "T3 · Events & Timeline",
  t4_stats:  "T4 · Match Statistics",
};

function buildReasoningModal() {
  const div = document.createElement("div");
  div.id = "reasoning-modal";
  div.style.cssText = "display:none;position:fixed;inset:0;z-index:50;align-items:center;justify-content:center;padding:1rem;";
  div.innerHTML = `
    <div style="position:absolute;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);"
         onclick="closeReasoningModal()"></div>
    <div class="card rounded-2xl p-6 relative" style="max-width:42rem;width:100%;max-height:80vh;overflow-y:auto;background:rgba(10,15,28,.97);z-index:1;">
      <button onclick="closeReasoningModal()"
              class="absolute top-4 right-4 text-gray-400 hover:text-white text-xl leading-none">✕</button>
      <h3 class="font-bold text-base mb-4" id="reasoning-modal-title">Reasoning</h3>
      <div id="reasoning-modal-body"></div>
    </div>`;
  document.body.appendChild(div);
}

function openReasoningModal(idx) {
  const p = _allPreds[idx];
  if (!p) return;
  const r = p.reasoning || {};
  document.getElementById("reasoning-modal-title").textContent =
    `${fmtModelId(p.model_id)} (${p.setting}) — Full Reasoning`;
  const rows = Object.entries(REASONING_LABELS)
    .filter(([k]) => r[k])
    .map(([k, label]) => `
      <tr style="border-top:1px solid rgba(255,255,255,.08)">
        <td style="padding:.75rem .75rem .75rem 0;vertical-align:top;width:8rem;white-space:nowrap;"
            class="text-xs font-semibold text-gray-400">${esc(label)}</td>
        <td style="padding:.75rem 0;" class="text-sm text-gray-200 leading-relaxed">${esc(r[k])}</td>
      </tr>`).join("");
  document.getElementById("reasoning-modal-body").innerHTML =
    `<table style="width:100%;border-collapse:collapse;"><tbody>${rows ||
      '<tr><td class="text-gray-400 text-sm py-2">No reasoning available.</td></tr>'
    }</tbody></table>`;
  document.getElementById("reasoning-modal").style.display = "flex";
}

function closeReasoningModal() {
  document.getElementById("reasoning-modal").style.display = "none";
}

// ---------- Prediction card --------------------------------------------------

function toggleDetails(idx) {
  const el  = document.getElementById(`pred-details-${idx}`);
  const btn = document.getElementById(`pred-details-btn-${idx}`);
  if (!el) return;
  const showing = el.style.display !== "none";
  el.style.display = showing ? "none" : "block";
  if (btn) btn.textContent = showing ? "👇 Show Full AI Analysis" : "👇 Hide Details";
}

function toggleSources(idx) {
  const el  = document.getElementById(`pred-sources-${idx}`);
  const btn = document.getElementById(`pred-sources-btn-${idx}`);
  if (!el) return;
  const showing = el.style.display !== "none";
  el.style.display = showing ? "none" : "block";
  if (btn) {
    const count = el.querySelectorAll("a").length;
    btn.textContent = showing ? `🔗 Sources (${count})` : `🔗 Hide sources`;
  }
}

// Normalize player name: strip accents, reduce to "firstInitial.lastName"
// "Harry Kane" == "H. Kane", "L. Díaz" == "L. Diaz"
function _normName(s) {
  const stripped = (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
  const parts = stripped.trim().split(/\s+/);
  if (!parts.length) return stripped.toLowerCase();
  const last = parts[parts.length - 1].toLowerCase();
  const init = parts[0].replace(/\./g, "")[0]?.toLowerCase() || "";
  return `${init}.${last}`;
}

function _lineupSide(lineup, formation, teamName, trStarting, hasTruth) {
  const POS = ["GK", "DF", "MF", "FW"];
  const starting = (lineup || {}).starting || [];
  const bench    = (lineup || {}).bench    || [];
  const byPos = {};
  for (const pl of starting) (byPos[pl.position] = byPos[pl.position] || []).push(pl.name);
  const trNames = new Set((trStarting || []).map(p => _normName(p.player)));
  const plColor = (name) => !hasTruth ? "text-gray-200" : trNames.has(_normName(name)) ? "text-green-400" : "text-red-400";
  return `
    <div>
      <div class="text-xs font-semibold mb-2 text-gray-200">
        ${esc(teamName)}${formation ? ` <span class="text-gray-400 font-normal">(${esc(formation)})</span>` : ""}
      </div>
      ${POS.filter(pos => byPos[pos]).map(pos => `
        <div class="text-xs mb-1 leading-snug">
          <span class="text-gray-500 inline-block w-7">${pos}</span>
          ${byPos[pos].map(n => `<span class="${plColor(n)}">${esc(n)}</span>`).join(", ")}
        </div>`).join("")}
      ${bench.length ? `
        <div class="text-xs mt-2 leading-snug text-gray-500">
          <span class="inline-block w-7">Sub</span>${bench.map(pl => esc(pl.name)).join(", ")}
        </div>` : ""}
    </div>`;
}

// Renders a highlighted "Actual" truth block used in detail sections
function _truthBlock(content) {
  return `<div class="mt-2 rounded-lg px-3 py-2 text-xs" style="background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.25);">
    <span class="text-amber-400 font-semibold uppercase tracking-wider text-[10px] mr-2">Actual</span>${content}
  </div>`;
}

function _renderDetails(p, f) {
  const hName  = f.home || "Home";
  const aName  = f.away || "Away";
  const tr     = f.truth || null;
  let html = "";

  // Lineups
  const tTeam = (t) => esc(t === "home" ? hName : aName);
  // helper: correct/wrong color when truth available
  const hitColor = (hit) => hit ? "text-green-400" : "text-red-400";

  const lin = p.lineups || {};
  if (lin.home || lin.away) {
    const trLinHome = tr && tr.lineups && tr.lineups.home ? tr.lineups.home.starting || [] : null;
    const trLinAway = tr && tr.lineups && tr.lineups.away ? tr.lineups.away.starting || [] : null;
    const trFmHome  = tr && tr.formations ? tr.formations.home : null;
    const trFmAway  = tr && tr.formations ? tr.formations.away : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">⬡ Lineups</div>
        <div class="grid grid-cols-2 gap-4">
          ${_lineupSide(lin.home, (p.formations || {}).home, hName, trLinHome, !!tr)}
          ${_lineupSide(lin.away, (p.formations || {}).away, aName, trLinAway, !!tr)}
        </div>
        ${(trLinHome || trLinAway) ? _truthBlock(`
          <div class="grid grid-cols-2 gap-4 mt-1">
            <div>
              <div class="text-amber-300/70 text-[10px] mb-1">${esc(hName)}${trFmHome ? ` · ${esc(trFmHome)}` : ""}</div>
              ${(trLinHome || []).map(pl => `<div class="text-gray-200 leading-tight">${esc(pl.player)}${pl.pos ? ` <span class="text-gray-500">(${esc(pl.pos)})</span>` : ""}</div>`).join("")}
            </div>
            <div>
              <div class="text-amber-300/70 text-[10px] mb-1">${esc(aName)}${trFmAway ? ` · ${esc(trFmAway)}` : ""}</div>
              ${(trLinAway || []).map(pl => `<div class="text-gray-200 leading-tight">${esc(pl.player)}${pl.pos ? ` <span class="text-gray-500">(${esc(pl.pos)})</span>` : ""}</div>`).join("")}
            </div>
          </div>`) : ""}
      </div>`;
  }

  // Scorers
  if ((p.scorers || []).length) {
    const trScorers = tr && tr.scorers ? tr.scorers : null;
    const trScorerNames = new Set((trScorers || []).map(s => _normName(s.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">⚽ Scorers</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1 text-center">Team</th>
            <th class="font-normal pb-1 text-center">Prob</th>
            <th class="font-normal pb-1 text-center">Minutes</th>
          </tr></thead>
          <tbody>
            ${p.scorers.map(s => {
              const cls = tr ? hitColor(trScorerNames.has(_normName(s.player))) : "text-gray-200";
              return `<tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 ${cls}">${esc(s.player)}</td>
                <td class="py-1 text-center">${tTeam(s.team)}</td>
                <td class="py-1 text-center font-mono text-gray-300">${fmtPct(s.p)}</td>
                <td class="py-1 text-center text-gray-400">
                  ${s.minute_range ? `${s.minute_range[0]}′–${s.minute_range[1]}′` : "—"}
                </td>
              </tr>`;}).join("")}
          </tbody>
        </table>
        ${trScorers && trScorers.length ? _truthBlock(
          trScorers.map(s => `<span class="text-gray-200 font-semibold">${esc(s.player)}</span> <span class="text-gray-400">(${tTeam(s.team)} ${s.minute}′)</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No goals</span>`) : ""}
      </div>`;
  }

  // Assisters
  if ((p.assisters || []).length) {
    const trAssisters = tr && tr.assisters ? tr.assisters : null;
    const trAssisterNames = new Set((trAssisters || []).map(a => _normName(a.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🎯 Assisters</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1 text-center">Team</th>
            <th class="font-normal pb-1 text-center">Prob</th>
          </tr></thead>
          <tbody>
            ${p.assisters.map(a => {
              const cls = tr ? hitColor(trAssisterNames.has(_normName(a.player))) : "text-gray-200";
              return `<tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 ${cls}">${esc(a.player)}</td>
                <td class="py-1 text-center">${tTeam(a.team)}</td>
                <td class="py-1 text-center font-mono text-gray-300">${fmtPct(a.p)}</td>
              </tr>`;}).join("")}
          </tbody>
        </table>
        ${trAssisters && trAssisters.length ? _truthBlock(
          trAssisters.map(a => `<span class="text-gray-200 font-semibold">${esc(a.player)}</span> <span class="text-gray-400">(${tTeam(a.team)})</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No assists recorded</span>`) : ""}
      </div>`;
  }

  // Substitutions
  if ((p.substitutions || []).length) {
    const trSubs = tr && tr.substitutions ? tr.substitutions : null;
    const trSubOff = new Set((trSubs || []).map(s => _normName(s.off)));
    const trSubOn  = new Set((trSubs || []).map(s => _normName(s.on)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🔄 Substitutions</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1 text-center">Team</th>
            <th class="font-normal pb-1">Off → On</th>
          </tr></thead>
          <tbody>
            ${p.substitutions.map(s => {
              const offCls = tr ? hitColor(trSubOff.has(_normName(s.off))) : "text-gray-300";
              const onCls  = tr ? hitColor(trSubOn.has(_normName(s.on)))  : "text-gray-300";
              return `<tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${s.minute}′</td>
                <td class="py-1 text-center">${tTeam(s.team)}</td>
                <td class="py-1"><span class="${offCls}">${esc(s.off)}</span> → <span class="${onCls}">${esc(s.on)}</span></td>
              </tr>`;}).join("")}
          </tbody>
        </table>
        ${trSubs && trSubs.length ? _truthBlock(`
          <table class="w-full mt-1" style="border-collapse:collapse;">
            ${trSubs.map(s => `
              <tr>
                <td class="pr-3 text-gray-400 font-mono">${s.minute}′</td>
                <td class="pr-2">${tTeam(s.team)}</td>
                <td>${esc(s.off)} → <span class="text-amber-300">${esc(s.on)}</span></td>
              </tr>`).join("")}
          </table>`) : ""}
      </div>`;
  }

  // Cards
  if ((p.cards || []).length) {
    const trCards = tr && tr.cards ? tr.cards : null;
    const trCardPlayers = new Set((trCards || []).map(c => _normName(c.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🟨 Cards</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1 text-center">Team</th>
            <th class="font-normal pb-1 text-center">Card</th>
          </tr></thead>
          <tbody>
            ${p.cards.map(c => {
              const cls = tr ? hitColor(trCardPlayers.has(_normName(c.player))) : "text-gray-200";
              return `<tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${c.minute}′</td>
                <td class="py-1 ${cls}">${esc(c.player)}</td>
                <td class="py-1 text-center">${tTeam(c.team)}</td>
                <td class="py-1 text-center">
                  ${c.color === "red" ? "🟥" : c.color === "second_yellow" ? "🟨🟥" : "🟨"}
                </td>
              </tr>`;}).join("")}
          </tbody>
        </table>
        ${trCards && trCards.length ? _truthBlock(`
          <table class="w-full mt-1" style="border-collapse:collapse;">
            ${trCards.map(c => `
              <tr>
                <td class="pr-3 text-gray-400 font-mono">${c.minute}′</td>
                <td class="pr-2">${tTeam(c.team)}</td>
                <td class="pr-3 text-gray-200 font-semibold">${esc(c.player)}</td>
                <td>${c.color === "red" ? "🟥" : c.color === "second_yellow" ? "🟨🟥" : "🟨"}</td>
              </tr>`).join("")}
          </table>`) : tr ? _truthBlock(`<span class="text-gray-400">No cards</span>`) : ""}
      </div>`;
  }

  // Penalties
  if ((p.penalties || []).length) {
    const trPens = tr && tr.penalties ? tr.penalties : null;
    const trPenTakers = new Set((trPens || []).map(p => _normName(p.taker)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🥅 Penalties</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1">Taker</th>
            <th class="font-normal pb-1 text-center">Team</th>
            <th class="font-normal pb-1">Outcome</th>
          </tr></thead>
          <tbody>
            ${p.penalties.map(pen => {
              const cls = tr ? hitColor(trPenTakers.has(_normName(pen.taker))) : "text-gray-200";
              return `<tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${pen.minute}′</td>
                <td class="py-1 ${cls}">${esc(pen.taker)}</td>
                <td class="py-1 text-center">${tTeam(pen.team)}</td>
                <td class="py-1 text-gray-300">
                  ${pen.outcome === "scored" ? "✅" : pen.outcome === "saved" ? "🧤" : "❌"}
                  ${esc(pen.outcome)}
                </td>
              </tr>`;}).join("")}
          </tbody>
        </table>
        ${trPens && trPens.length ? _truthBlock(
          trPens.map(pen => `<span class="text-gray-200 font-semibold">${esc(pen.taker)}</span> <span class="text-gray-400">${pen.minute}′ · ✅ scored</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No penalties</span>`) : ""}
      </div>`;
  }

  // Own goals
  if ((p.own_goals || []).length) {
    const trOg = tr && tr.own_goals ? tr.own_goals : null;
    const trOgPlayers = new Set((trOg || []).map(o => _normName(o.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">⚽ Own Goals</div>
        <div class="space-y-1 text-xs">
          ${p.own_goals.map(og => {
            const cls = tr ? hitColor(trOgPlayers.has(_normName(og.player))) : "text-gray-200";
            return `<div>${og.minute}′ — <span class="${cls}">${esc(og.player)}</span> ${tTeam(og.team)}</div>`;
          }).join("")}
        </div>
        ${trOg && trOg.length ? _truthBlock(
          trOg.map(og => `<span class="text-gray-200 font-semibold">${esc(og.player)}</span> <span class="text-gray-400">${og.minute}′</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No own goals</span>`) : ""}
      </div>`;
  }

  // Stats
  const STAT_LABELS = {
    possession:        "Possession %",
    shots:             "Shots",
    shots_on_target:   "Shots on Target",
    corners:           "Corners",
    pass_accuracy:     "Pass Accuracy %",
    fouls:             "Fouls",
    saves:             "Saves",
  };
  const LOWER_BETTER = new Set(["fouls"]);
  const stats = p.stats || {};
  const trStats = tr && tr.stats ? tr.stats : null;
  const statRows = Object.entries(STAT_LABELS)
    .filter(([k]) => stats[k] && (stats[k].home != null || stats[k].away != null))
    .map(([k, label]) => {
      const h = stats[k].home ?? "—";
      const a = stats[k].away ?? "—";
      const total = (typeof h === "number" && typeof a === "number") ? h + a : null;
      const hPct  = total ? (h / total * 100) : 50;
      const lower = LOWER_BETTER.has(k);
      const hWin  = typeof h === "number" && typeof a === "number" && (lower ? h < a : h > a);
      const aWin  = typeof h === "number" && typeof a === "number" && (lower ? a < h : a > h);
      const trH   = trStats && trStats[k] ? trStats[k].home : null;
      const trA   = trStats && trStats[k] ? trStats[k].away : null;
      const trTotal = (typeof trH === "number" && typeof trA === "number") ? trH + trA : null;
      const trHPct  = trTotal ? (trH / trTotal * 100) : 50;
      const trHWin  = typeof trH === "number" && typeof trA === "number" && (lower ? trH < trA : trH > trA);
      const trAWin  = typeof trH === "number" && typeof trA === "number" && (lower ? trA < trH : trA > trH);
      return `
        <tr style="border-top:1px solid rgba(255,255,255,.06)">
          <td class="py-1.5 text-xs text-gray-400 pr-2">${esc(label)}</td>
          <td class="py-1.5 text-xs font-mono text-center w-10 ${hWin ? "text-gray-100 font-bold" : "text-gray-300"}">${h}</td>
          <td class="py-1.5 px-2" style="width:6rem;">
            ${total !== null ? `
              <div style="display:flex;height:.375rem;border-radius:9999px;overflow:hidden;">
                <div style="width:${hPct}%;background:rgba(255,255,255,.3);"></div>
                <div style="width:${100 - hPct}%;background:rgba(255,255,255,.1);"></div>
              </div>` : ""}
          </td>
          <td class="py-1.5 text-xs font-mono text-center w-10 ${aWin ? "text-gray-100 font-bold" : "text-gray-300"}">${a}</td>
          ${trH != null || trA != null ? `
          <td class="py-1.5 text-[10px] text-amber-400/80 font-mono text-center w-10 ${trHWin ? "text-amber-400 font-bold" : ""}">${trH ?? "—"}</td>
          <td class="py-1.5 px-1" style="width:4rem;">
            ${trTotal !== null ? `
              <div style="display:flex;height:.375rem;border-radius:9999px;overflow:hidden;">
                <div style="width:${trHPct}%;background:#fbbf2470;"></div>
                <div style="width:${100 - trHPct}%;background:#fbbf2430;"></div>
              </div>` : ""}
          </td>
          <td class="py-1.5 text-[10px] text-amber-400/80 font-mono text-center w-10 ${trAWin ? "text-amber-400 font-bold" : ""}">${trA ?? "—"}</td>` : ""}
        </tr>`;
    }).join("");

  if (statRows) {
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">📊 Stats</div>
        <table class="w-full" style="border-collapse:collapse;">
          <thead><tr class="text-xs">
            <th class="font-normal text-gray-500 text-left pb-1">Stat</th>
            <th class="font-normal text-gray-400 text-center pb-1 w-10">H</th>
            <th style="width:6rem;"></th>
            <th class="font-normal text-gray-400 text-center pb-1 w-10">A</th>
            ${trStats ? `<th colspan="3" class="font-normal text-amber-400/70 text-center pb-1">Actual</th>` : ""}
          </tr></thead>
          <tbody>${statRows}</tbody>
        </table>
      </div>`;
  }

  return html || `<div class="text-gray-500 text-xs">No detailed prediction data available.</div>`;
}

function renderPredCard(p, f, idx) {
  const b          = modelBadge(p.model_id);
  const wp         = p.win_probs || {};
  const reasoning  = p.reasoning || {};
  const top3       = (p.score_dist || []).slice(0, 3);
  const hName      = f.home || "Home";
  const aName      = f.away || "Away";
  const hasReason  = Object.keys(reasoning).length > 0;

  // Compute predicted winner (argmax of win_probs)
  const predWinner = (wp.home != null && wp.draw != null && wp.away != null)
    ? (wp.home >= wp.draw && wp.home >= wp.away ? hName
       : wp.away >= wp.home && wp.away >= wp.draw ? aName : "Draw")
    : null;


  return `
    <div class="card rounded-xl p-4">

      <!-- Header -->
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-lg">${b.emoji}</span>
          <span class="font-bold text-sm text-white">${esc(fmtModelId(p.model_id))}</span>
          <span class="chip chip-${(p.setting || "").toLowerCase()}"
                data-tip="${esc(SETTING_TIPS[p.setting] || p.setting)}">${esc(p.setting)}</span>
        </div>
        ${p.cost_usd != null ? `<span class="text-xs text-gray-600">Cost: $${(+p.cost_usd).toFixed(3)}</span>` : ""}
      </div>

      <!-- Minimalist Prediction -->
      ${predWinner || top3.length ? `
      <div class="mb-4">
        <div class="flex items-start gap-6">
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Pred Winner</div>
            ${(() => {
              const truthOutcome = f.truth
                ? (f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : "Draw")
                : null;
              const winnerCorrect = truthOutcome && predWinner && truthOutcome === predWinner;
              const winnerColor = truthOutcome
                ? (winnerCorrect ? "color:#4ade80;" : "color:#f87171;")
                : "color:#fff;";
              return `<div class="text-2xl font-black leading-tight" style="${winnerColor}">${esc(predWinner)}</div>`;
            })()}
          </div>
          <div style="width:1px;height:2.5rem;background:rgba(255,255,255,.1);"></div>
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Pred Score</div>
            ${(() => {
              const topScore = top3[0] ? top3[0].score : null;
              const actualScore = f.truth ? f.truth.score : null;
              const scoreCorrect = topScore && actualScore && topScore === actualScore;
              const scoreColor = actualScore
                ? (scoreCorrect ? "color:#4ade80;" : "color:#f87171;")
                : "color:#fff;";
              return `<div class="text-2xl font-black leading-tight font-mono whitespace-nowrap" style="${scoreColor}">${esc(topScore.replace("-", " - ") || "—")}</div>`;
            })()}
          </div>
          ${f.truth ? `<div class="ml-auto">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Actual</div>
            <div class="text-2xl font-black font-mono leading-tight whitespace-nowrap" style="color:#fbbf24;">${esc(f.truth.score.replace("-", " - ") || "—")}</div>
            <div class="text-xs font-mono" style="color:#fbbf2480;">${esc(
              f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : f.truth.result || "—"
            )}</div>
          </div>` : ""}
        </div>
      </div>
      ` : ""}

      <!-- Buttons -->
      <div class="flex flex-wrap gap-2 mt-1">
        <button id="pred-details-btn-${idx}" onclick="toggleDetails(${idx})"
                class="chip hover:bg-white/15 transition text-xs">👇 Show Full AI Analysis</button>
        ${p.sources && p.sources.length ? `
        <button id="pred-sources-btn-${idx}" onclick="toggleSources(${idx})"
                class="chip hover:bg-white/15 transition text-xs">🔗 Sources (${p.sources.length})</button>` : ""}
      </div>

      <!-- Expandable sources -->
      ${p.sources && p.sources.length ? `
      <div id="pred-sources-${idx}"
           style="display:none;border-top:1px solid rgba(255,255,255,.06);"
           class="mt-3 pt-3 space-y-1">
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🔗 Search Sources</div>
        ${p.sources.map(s => {
          const title = esc(s.title || s.url || "");
          const url   = esc(s.url || "");
          const date  = s.accessed_at ? esc(s.accessed_at.slice(0, 10)) : "";
          return `<div class="text-xs leading-snug">
            <a href="${url}" target="_blank" rel="noopener"
               class="text-blue-400 hover:text-blue-300 underline break-all">${title}</a>
            ${date ? `<span class="text-gray-600 ml-1">${date}</span>` : ""}
          </div>`;
        }).join("")}
      </div>` : ""}

      <!-- Expandable details -->
      <div id="pred-details-${idx}"
           style="display:none;border-top:1px solid rgba(255,255,255,.06);"
           class="mt-4 pt-4 space-y-5">

        <!-- Win probabilities (full) -->
        ${wp.home != null ? `
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">📊 Win Probabilities</div>
          <div class="flex gap-3">
            ${[["home", hName], ["draw", "Draw"], ["away", aName]
              ].map(([k, label]) => `
              <div class="flex-1 rounded-lg px-3 py-2 text-center" style="background:rgba(255,255,255,.06);">
                <div class="text-[10px] text-gray-400 uppercase tracking-wider">${esc(label)}</div>
                <div class="text-lg font-black font-mono text-gray-100">${fmtPct(wp[k])}</div>
              </div>`).join("")}
          </div>
        </div>` : ""}

        <!-- Score distribution (full) -->
        ${top3.length ? (() => {
          const allScores = (p.score_dist || []).slice(0, 15);
          const maxP = Math.max(...allScores.map(s => s.p || 0));
          return `
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🎯 Score Distribution</div>
          <div class="space-y-1">
            ${allScores.map(s => {
              const barW = maxP > 0 ? Math.round((s.p / maxP) * 100) : 0;
              const sc   = (s.score || "").split("-");
              const hg   = parseInt(sc[0] ?? "-1");
              const ag   = parseInt(sc[1] ?? "-1");
              const outcomeCls = hg > ag || ag > hg ? "text-gray-100" : "text-gray-300";
              return `<div class="flex items-center gap-2">
                <span class="font-mono font-bold text-sm w-10 text-right ${outcomeCls}">${esc(s.score)}</span>
                <div class="flex-1 h-2 rounded-full overflow-hidden" style="background:rgba(255,255,255,.07);">
                  <div class="h-full rounded-full" style="width:${barW}%;background:rgba(255,255,255,.3);"></div>
                </div>
                <span class="font-mono text-xs text-gray-400 w-10">${fmtPct(s.p)}</span>
              </div>`;
            }).join("")}
          </div>
        </div>`;
        })() : ""}

        ${hasReason ? `
          <div>
            <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">📖 Full Reasoning</div>
            <div class="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">${esc(reasoning.overall)}</div>
          </div>
        ` : ""}
        ${_renderDetails(p, f)}
        <div class="pt-2 border-t border-white/5">
          <button onclick="toggleDetails(${idx})" class="chip hover:bg-white/15 transition text-xs">🔼 Hide Detail</button>
        </div>
      </div>
    </div>`;
}

// ---------- Incoming matches -------------------------------------------------

function _renderOneFixture(nm, cardIdx) {
  const f     = nm.fixture;
  const kick  = f.kickoff_utc ? new Date(f.kickoff_utc) : null;
  const cid   = `nm-countdown-${cardIdx}`;
  const preds = nm.predictions || [];
  const nmStart = _allPreds.length;
  _allPreds.push(...preds);

  const lv = nm.live;
  const isMatchLive = lv && lv.status && lv.status !== "Match Finished" && lv.status !== "Not Started";

  const agg = { home: 0, draw: 0, away: 0 };
  let nP = 0;
  for (const p of preds) {
    if (p.win_probs && typeof p.win_probs.home === "number") {
      agg.home += p.win_probs.home; agg.draw += p.win_probs.draw; agg.away += p.win_probs.away;
      nP++;
    }
  }
  if (nP > 0) { agg.home /= nP; agg.draw /= nP; agg.away /= nP; }

  const centerMiddle = isMatchLive
    ? `<div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-3xl font-black font-mono" style="color:#f87171;">${lv.score ? `${lv.score.home ?? "?"} – ${lv.score.away ?? "?"}` : "?–?"}</div>
       <div class="text-xs font-semibold" style="color:#fca5a5;">🔴 LIVE${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}</div>
       ${f.venue ? `<div class="text-[10px] text-gray-500 mt-1">${esc(f.venue)}</div>${f.venue_city ? `<div class="text-[10px] text-gray-500">${esc(f.venue_city)}${f.venue_country ? `, ${esc(f.venue_country)}` : ""}</div>` : ""}` : ""}`
    : `${kick ? `<div class="text-xs text-gray-300 font-medium mb-1">${fmtLocalKickoff(kick)}</div>` : ""}
       <div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-2xl font-black">VS</div>
       ${nP > 0 ? `<div class="text-xs text-gray-400">draw ${fmtPct(agg.draw)}</div>` : ""}
       <div class="text-xs text-gray-400 mt-1" id="${cid}">${kick ? "" : "—"}</div>
       ${f.venue ? `<div class="text-[10px] text-gray-500 mt-1">${esc(f.venue)}</div>${f.venue_city ? `<div class="text-[10px] text-gray-500">${esc(f.venue_city)}${f.venue_country ? `, ${esc(f.venue_country)}` : ""}</div>` : ""}` : ""}`;

  const html = `
    <div class="card rounded-2xl p-6">
      <div class="pitch rounded-xl p-5 mb-6">
        <div class="grid grid-cols-3 items-center gap-2">
          <div class="text-center">
            ${f.home_logo ? `<img src="${esc(f.home_logo)}" alt="${esc(f.home)}" class="h-16 sm:h-24 mx-auto mb-2"/>` : `<div class="text-4xl">🏠</div>`}
            <div class="font-bold text-sm sm:text-lg leading-tight">${esc(f.home || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">win ${fmtPct(agg.home)}</div>` : ""}
          </div>
          <div class="text-center">${centerMiddle}</div>
          <div class="text-center">
            ${f.away_logo ? `<img src="${esc(f.away_logo)}" alt="${esc(f.away)}" class="h-16 sm:h-24 mx-auto mb-2"/>` : `<div class="text-4xl">🛫</div>`}
            <div class="font-bold text-sm sm:text-lg leading-tight">${esc(f.away || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">win ${fmtPct(agg.away)}</div>` : ""}
          </div>
        </div>
      </div>
      ${preds.length === 0
        ? `<div class="text-gray-400 text-sm">No model predictions yet (runs 24 h before kickoff).</div>`
        : `<div class="space-y-3">${preds.map((p, i) => renderPredCard(p, f, nmStart + i)).join("")}</div>`}
    </div>`;

  // Start countdown timer after DOM insertion (called by caller)
  return { html, kick, cid };
}

function renderIncomingMatches(matches) {
  const el = document.getElementById("next-container");
  if (!matches || matches.length === 0) {
    el.innerHTML = `<div class="text-gray-400">No fixtures scheduled in the next 3 days.</div>`;
    return;
  }

  const timers = [];
  const parts  = matches.map((nm, i) => {
    const { html, kick, cid } = _renderOneFixture(nm, i);
    if (kick) timers.push({ kick, cid });
    return html;
  });
  el.innerHTML = parts.join("");

  for (const { kick, cid } of timers) {
    const tick = () => {
      const el2 = document.getElementById(cid);
      if (!el2) return;
      const diff = kick - new Date();
      if (diff <= 0) { el2.textContent = "🟢 Live"; return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el2.textContent = `kickoff in ${h}h ${m}m ${s}s`;
    };
    tick(); setInterval(tick, 1000);
  }
}

// ---------- Leaderboard ------------------------------------------------------

let chartInstance = null;

function renderLeaderboard(lb, view) {
  const el   = document.getElementById("leaderboard-container");
  const rows = lb.main || [];
  if (rows.length === 0) {
    el.innerHTML = `<div class="text-gray-400 text-sm">No graded fixtures yet.</div>`;
    return;
  }

  if (view === "main") {
    el.innerHTML = `
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-gray-400 text-xs uppercase tracking-wider">
            <tr>
              <th class="text-left py-2 px-3 w-12">#</th>
              <th class="text-left py-2 px-3">Model</th>
              <th class="text-right py-2 px-3">Composite Score</th>
              <th class="text-right py-2 px-3">Result Accuracy</th>
              <th class="text-right py-2 px-3">#Games</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r, i) => {
              const b = modelBadge(r.model_id);
              const medal = i === 0 ? "rank-1" : i === 1 ? "rank-2" : i === 2 ? "rank-3" : "";
              const winAcc = r.winner_acc != null
                ? `${(r.winner_acc * 100).toFixed(1)}% (${r.winner_correct}/${r.winner_total})`
                : "—";
              const settings = Object.keys((lb.by_model_setting || {})[r.model_id] || {}).sort();
              const settingBadges = settings.map(s =>
                `<span class="chip chip-${s.toLowerCase()}"
                       data-tip="${esc(SETTING_TIPS[s] || s)}">${esc(s)}</span>`
              ).join(" ");
              return `
                <tr class="border-t border-white/5 hover:bg-white/5 transition">
                  <td class="py-2 px-3"><span class="rank-medal ${medal}">${i + 1}</span></td>
                  <td class="py-2 px-3">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="mr-1">${b.emoji}</span>
                      <span class="font-bold text-white">${esc(fmtModelId(r.model_id))}</span>
                      ${settingBadges}
                    </div>
                  </td>
                  <td class="py-2 px-3 text-right font-mono">
                    <div class="inline-flex items-center gap-2">
                      <div class="bar w-28"><div class="bar-fill" style="width:${Math.min(100, r.mean)}%"></div></div>
                      <span class="font-bold text-white">${fmt2(r.mean)}</span>
                    </div>
                  </td>
                  <td class="py-2 px-3 text-right font-mono font-bold text-gray-300">${winAcc}</td>
                  <td class="py-2 px-3 text-right text-gray-500">${r.n}</td>
                </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
  } else if (view === "layers") {
    el.innerHTML = `<canvas id="layersChart" height="220"></canvas>`;
    const layers  = ["T1_core_result", "T2_player_level", "T3_event_level", "T4_tactics_stats", "T5_tournament_macro"];
    const labels  = ["T1 Result", "T2 Players", "T3 Events", "T4 Stats", "T5 Tournament"];
    const palette = ["#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#f59e0b", "#14b8a6", "#ef4444", "#eab308", "#64748b"];
    const datasets = rows.slice(0, 9).map((r, i) => ({
      label: r.model_id,
      data: layers.map(l => (r.layers_mean || {})[l] || 0),
      backgroundColor: palette[i] + "cc",
      borderColor: palette[i], borderWidth: 2,
      pointBackgroundColor: palette[i],
    }));
    if (chartInstance) chartInstance.destroy();
    chartInstance = new Chart(document.getElementById("layersChart"), {
      type: "radar",
      data: { labels, datasets },
      options: {
        responsive: true,
        scales: { r: {
          suggestedMin: 0, suggestedMax: 100,
          angleLines: { color: "rgba(255,255,255,.12)" },
          grid:        { color: "rgba(255,255,255,.08)" },
          pointLabels: { color: "#cbd5e1", font: { size: 11 } },
          ticks:       { backdropColor: "transparent", color: "#64748b" },
        }},
        plugins: { legend: { labels: { color: "#cbd5e1", boxWidth: 12 } } },
      },
    });
  }
}

function wireTabs(lb) {
  document.querySelectorAll(".tab-btn").forEach(btn =>
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderLeaderboard(lb, btn.dataset.view);
    })
  );
}

// ---------- History ----------------------------------------------------------

function renderHistory(rows) {
  const el = document.getElementById("history-container");
  if (!rows || rows.length === 0) {
    el.innerHTML = `<div class="text-gray-400 text-sm">No graded fixtures yet.</div>`;
    return;
  }
  el.innerHTML = rows.map(r => {
    const date  = r.kickoff_utc ? new Date(r.kickoff_utc).toISOString().slice(0, 10) : "";
    const preds = r.predictions || [];
    const lv    = r.live;
    const isLive = lv && lv.status && lv.status !== "Match Finished" && lv.status !== "Not Started";

    // Skip live matches — they belong in Incoming Matches
    if (isLive) return "";

    const liveScore = isLive && lv.score ? `${lv.score.home ?? "?"} – ${lv.score.away ?? "?"}` : null;
    const scoreHtml = isLive
      ? `<div class="text-3xl font-black font-mono" style="color:#f87171;">${esc(liveScore || "?–?")}</div>
         <div class="text-xs font-semibold mt-0.5" style="color:#fca5a5;">🔴 LIVE${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}</div>`
      : `<div class="text-3xl font-black font-mono" style="color:#fbbf24;">${esc((r.result || "—").replace("-", " – "))}</div>`;

    const hStart = _allPreds.length;
    _allPreds.push(...preds);

    const predCards = preds.length
      ? preds.map((p, i) => renderPredCard(p, r, hStart + i)).join("")
      : `<div class="text-gray-500 text-sm py-2">No predictions for this fixture.</div>`;

    return `
      <details open class="card rounded-xl p-4 col-span-2">
        <summary class="flex items-center justify-between cursor-pointer select-none">
          <div>
            <div class="text-xs text-gray-400">${esc(date)} · ${esc(r.competition || "")} ${esc(r.stage || "")}</div>
            <div class="font-semibold text-lg">${esc(r.home || "?")} <span class="text-gray-500 mx-2">vs</span> ${esc(r.away || "?")}</div>
          </div>
        </summary>
        <div class="mt-4 space-y-3">
          <div class="pitch rounded-xl p-4 mb-4">
            <div class="grid grid-cols-3 items-center gap-2">
              <div class="text-center">
                ${r.home_logo ? `<img src="${esc(r.home_logo)}" alt="${esc(r.home)}" class="h-16 sm:h-24 mx-auto mb-2"/>` : `<div class="text-3xl">🏠</div>`}
                <div class="font-bold text-sm sm:text-lg leading-tight">${esc(r.home || "?")}</div>
              </div>
              <div class="text-center">
                ${r.kickoff_utc ? `<div class="text-xs text-gray-300 font-medium mb-1">${fmtLocalKickoff(new Date(r.kickoff_utc))}</div>` : ""}
                ${r.competition ? `<div class="text-[10px] text-gray-400 mb-1">${esc(r.competition)}${r.stage ? ` · ${esc(r.stage)}` : ""}</div>` : ""}
                ${scoreHtml}
                ${r.venue ? `<div class="text-[10px] text-gray-500 mt-1">${esc(r.venue)}</div>${r.venue_city ? `<div class="text-[10px] text-gray-500">${esc(r.venue_city)}${r.venue_country ? `, ${esc(r.venue_country)}` : ""}</div>` : ""}` : ""}
              </div>
              <div class="text-center">
                ${r.away_logo ? `<img src="${esc(r.away_logo)}" alt="${esc(r.away)}" class="h-16 sm:h-24 mx-auto mb-2"/>` : `<div class="text-3xl">🛫</div>`}
                <div class="font-bold text-sm sm:text-lg leading-tight">${esc(r.away || "?")}</div>
              </div>
            </div>
          </div>
          ${predCards}
        </div>
      </details>`;
  }).join("");
}

// ---------- Boot -------------------------------------------------------------

function fmtTimestamp(iso) {
  if (!iso) return "—";
  const d   = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} `
       + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} (UTC+0)`;
}

function fmtLocalKickoff(date) {
  if (!date) return null;
  const pad = n => String(n).padStart(2, "0");
  const yr  = date.getFullYear();
  const mo  = pad(date.getMonth() + 1);
  const dy  = pad(date.getDate());
  const hr  = pad(date.getHours());
  const mn  = pad(date.getMinutes());
  const off = -date.getTimezoneOffset();
  const tz  = `UTC${off >= 0 ? "+" : ""}${Math.floor(off / 60)}${off % 60 ? `:${pad(Math.abs(off % 60))}` : ""}`;
  return `${yr}-${mo}-${dy} ${hr}:${mn} ${tz}`;
}

async function main() {
  buildReasoningModal();
  let data;
  try {
    const resp = await fetch("data.json?ts=" + Date.now());
    data = await resp.json();
  } catch (e) {
    document.getElementById("next-container").innerHTML =
      `<div class="text-rose-300 text-sm">Couldn't load data.json — is the automation workflow running?</div>`;
    console.error(e);
    return;
  }
  // document.getElementById("generated-at").textContent = "Last updated " + fmtTimestamp(data.generated_at);
  _allPreds = [];
  renderIncomingMatches(data.incoming_matches || []);
  renderLeaderboard(data.leaderboard || { main: [] }, "main");
  wireTabs(data.leaderboard || { main: [] });
  renderHistory(data.history || []);
}

main();
