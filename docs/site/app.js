// WorldCupArena site — fetches data.json written by src.leaderboard.build_site
// and renders everything client-side.

const fmtPct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const fmt2   = (x) => (x == null ? "—" : (+x).toFixed(2));
const esc    = (s) => String(s ?? "").replace(/[<>&"']/g, c =>
  ({ "<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;" }[c]));

let _allPreds = [];  // flat registry of all rendered pred cards (for modal)

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
    `${p.model_id} (${p.setting}) — Full Reasoning`;
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
  if (btn) btn.textContent = showing ? "📊 More details" : "📊 Hide details";
}

function _lineupSide(lineup, formation, teamName, colorCls) {
  const POS = ["GK", "DF", "MF", "FW"];
  const starting = (lineup || {}).starting || [];
  const bench    = (lineup || {}).bench    || [];
  const byPos = {};
  for (const pl of starting) (byPos[pl.position] = byPos[pl.position] || []).push(pl.name);
  return `
    <div>
      <div class="text-xs font-semibold mb-2 ${colorCls}">
        ${esc(teamName)}${formation ? ` <span class="text-gray-400 font-normal">(${esc(formation)})</span>` : ""}
      </div>
      ${POS.filter(pos => byPos[pos]).map(pos => `
        <div class="text-xs mb-1 leading-snug">
          <span class="text-gray-500 inline-block w-7">${pos}</span>
          <span class="text-gray-200">${byPos[pos].map(esc).join(", ")}</span>
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
  const tName  = (t) => t === "home" ? hName : aName;
  const tColor = (t) => t === "home" ? "text-emerald-400" : "text-blue-400";
  let html = "";

  // Lineups
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
          ${_lineupSide(lin.home, (p.formations || {}).home, hName, "text-emerald-400")}
          ${_lineupSide(lin.away, (p.formations || {}).away, aName, "text-blue-400")}
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
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">⚽ Scorers</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1">Team</th>
            <th class="font-normal pb-1 text-center">Prob</th>
            <th class="font-normal pb-1 text-center">Minutes</th>
          </tr></thead>
          <tbody>
            ${p.scorers.map(s => `
              <tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 ${tColor(s.team)}">${esc(s.player)}</td>
                <td class="py-1 text-gray-400">${esc(tName(s.team))}</td>
                <td class="py-1 text-center font-mono">${fmtPct(s.p)}</td>
                <td class="py-1 text-center text-gray-400">
                  ${s.minute_range ? `${s.minute_range[0]}′–${s.minute_range[1]}′` : "—"}
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
        ${trScorers && trScorers.length ? _truthBlock(
          trScorers.map(s => `<span class="${tColor(s.team)} font-semibold">${esc(s.player)}</span> <span class="text-gray-400">(${esc(tName(s.team))} ${s.minute}′)</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No goals</span>`) : ""}
      </div>`;
  }

  // Assisters
  if ((p.assisters || []).length) {
    const trAssisters = tr && tr.assisters ? tr.assisters : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🎯 Assisters</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1">Team</th>
            <th class="font-normal pb-1 text-center">Prob</th>
          </tr></thead>
          <tbody>
            ${p.assisters.map(a => `
              <tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 ${tColor(a.team)}">${esc(a.player)}</td>
                <td class="py-1 text-gray-400">${esc(tName(a.team))}</td>
                <td class="py-1 text-center font-mono">${fmtPct(a.p)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
        ${trAssisters && trAssisters.length ? _truthBlock(
          trAssisters.map(a => `<span class="${tColor(a.team)} font-semibold">${esc(a.player)}</span> <span class="text-gray-400">(${esc(tName(a.team))})</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No assists recorded</span>`) : ""}
      </div>`;
  }

  // Substitutions
  if ((p.substitutions || []).length) {
    const trSubs = tr && tr.substitutions ? tr.substitutions : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🔄 Substitutions</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1">Team</th>
            <th class="font-normal pb-1">Off → On</th>
          </tr></thead>
          <tbody>
            ${p.substitutions.map(s => `
              <tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${s.minute}′</td>
                <td class="py-1 ${tColor(s.team)}">${esc(tName(s.team))}</td>
                <td class="py-1">${esc(s.off)} → <span class="text-emerald-400">${esc(s.on)}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
        ${trSubs && trSubs.length ? _truthBlock(`
          <table class="w-full mt-1" style="border-collapse:collapse;">
            ${trSubs.map(s => `
              <tr>
                <td class="pr-3 text-gray-400 font-mono">${s.minute}′</td>
                <td class="pr-3 ${tColor(s.team)}">${esc(s.team_name || tName(s.team))}</td>
                <td>${esc(s.off)} → <span class="text-amber-300">${esc(s.on)}</span></td>
              </tr>`).join("")}
          </table>`) : ""}
      </div>`;
  }

  // Cards
  if ((p.cards || []).length) {
    const trCards = tr && tr.cards ? tr.cards : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🟨 Cards</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1">Player</th>
            <th class="font-normal pb-1">Team</th>
            <th class="font-normal pb-1 text-center">Card</th>
          </tr></thead>
          <tbody>
            ${p.cards.map(c => `
              <tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${c.minute}′</td>
                <td class="py-1">${esc(c.player)}</td>
                <td class="py-1 ${tColor(c.team)}">${esc(tName(c.team))}</td>
                <td class="py-1 text-center">
                  ${c.color === "red" ? "🟥" : c.color === "second_yellow" ? "🟨🟥" : "🟨"}
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
        ${trCards && trCards.length ? _truthBlock(`
          <table class="w-full mt-1" style="border-collapse:collapse;">
            ${trCards.map(c => `
              <tr>
                <td class="pr-3 text-gray-400 font-mono">${c.minute}′</td>
                <td class="pr-3 ${tColor(c.team)} font-semibold">${esc(c.player)}</td>
                <td class="pr-3 text-gray-400">${esc(tName(c.team))}</td>
                <td>${c.color === "red" ? "🟥" : c.color === "second_yellow" ? "🟨🟥" : "🟨"}</td>
              </tr>`).join("")}
          </table>`) : tr ? _truthBlock(`<span class="text-gray-400">No cards</span>`) : ""}
      </div>`;
  }

  // Penalties
  if ((p.penalties || []).length) {
    const trPens = tr && tr.penalties ? tr.penalties : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">🥅 Penalties</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">Min</th>
            <th class="font-normal pb-1">Taker</th>
            <th class="font-normal pb-1">Team</th>
            <th class="font-normal pb-1">Outcome</th>
          </tr></thead>
          <tbody>
            ${p.penalties.map(pen => `
              <tr style="border-top:1px solid rgba(255,255,255,.06)">
                <td class="py-1 text-center text-gray-400">${pen.minute}′</td>
                <td class="py-1">${esc(pen.taker)}</td>
                <td class="py-1 ${tColor(pen.team)}">${esc(tName(pen.team))}</td>
                <td class="py-1">
                  ${pen.outcome === "scored" ? "✅" : pen.outcome === "saved" ? "🧤" : "❌"}
                  ${esc(pen.outcome)}
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
        ${trPens && trPens.length ? _truthBlock(
          trPens.map(pen => `<span class="${tColor(pen.team)} font-semibold">${esc(pen.taker)}</span> <span class="text-gray-400">${pen.minute}′ · ✅ scored</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">No penalties</span>`) : ""}
      </div>`;
  }

  // Own goals
  if ((p.own_goals || []).length) {
    const trOg = tr && tr.own_goals ? tr.own_goals : null;
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">⚽ Own Goals</div>
        <div class="space-y-1 text-xs">
          ${p.own_goals.map(og => `
            <div>${og.minute}′ —
              <span class="${tColor(og.team)}">${esc(og.player)}</span>
              <span class="text-gray-400">(${esc(tName(og.team))})</span>
            </div>`).join("")}
        </div>
        ${trOg && trOg.length ? _truthBlock(
          trOg.map(og => `<span class="${tColor(og.team)} font-semibold">${esc(og.player)}</span> <span class="text-gray-400">${og.minute}′</span>`).join(" &nbsp;·&nbsp; ")
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
    defensive_actions: "Defensive Actions",
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
          <td class="py-1.5 text-xs font-mono text-center w-10 ${hWin ? "text-emerald-400 font-bold" : ""}">${h}</td>
          <td class="py-1.5 px-2" style="width:6rem;">
            ${total !== null ? `
              <div style="display:flex;height:.375rem;border-radius:9999px;overflow:hidden;">
                <div style="width:${hPct}%;background:#22c55e70;"></div>
                <div style="width:${100 - hPct}%;background:#3b82f670;"></div>
              </div>` : ""}
          </td>
          <td class="py-1.5 text-xs font-mono text-center w-10 ${aWin ? "text-blue-400 font-bold" : ""}">${a}</td>
          ${trH != null || trA != null ? `
          <td class="py-1.5 pl-4 text-[10px] text-amber-400/80 font-mono text-center w-10 ${trHWin ? "text-amber-400 font-bold" : ""}">${trH ?? "—"}</td>
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
            <th class="font-normal text-emerald-400/70 text-center pb-1 w-10">${esc(hName)}</th>
            <th style="width:6rem;"></th>
            <th class="font-normal text-blue-400/70 text-center pb-1 w-10">${esc(aName)}</th>
            ${trStats ? `<th class="font-normal text-amber-400/70 text-center pb-1 pl-4 w-10">Act·H</th><th style="width:4rem;"></th><th class="font-normal text-amber-400/70 text-center pb-1 w-10">Act·A</th>` : ""}
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
  const topMotm    = (p.motm_probs || [])[0];
  const hScorers   = (p.scorers || []).filter(s => s.team === "home").slice(0, 3);
  const aScorers   = (p.scorers || []).filter(s => s.team === "away").slice(0, 3);
  const hasReason  = Object.keys(reasoning).length > 0;

  // Compute predicted winner (argmax of win_probs)
  const predWinner = (wp.home != null && wp.draw != null && wp.away != null)
    ? (wp.home >= wp.draw && wp.home >= wp.away ? hName
       : wp.away >= wp.home && wp.away >= wp.draw ? aName : "Draw")
    : null;
  const predWinnerProb = predWinner === hName ? wp.home : predWinner === aName ? wp.away : wp.draw;

  return `
    <div class="card rounded-xl p-4">

      <!-- Header -->
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-lg">${b.emoji}</span>
          <span class="font-bold text-sm text-white">${esc(p.model_id)}</span>
          <span class="chip chip-${(p.setting || "").toLowerCase()}">${esc(p.setting)}</span>
        </div>
        ${p.cost_usd != null ? `<span class="text-xs text-gray-600">$${(+p.cost_usd).toFixed(3)}</span>` : ""}
      </div>

      <!-- Prediction headline: winner + score -->
      ${predWinner || top3.length ? `
      <div class="flex items-center gap-4 mb-4 px-1">
        ${predWinner ? `
        <div>
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Predicted winner</div>
          <div class="text-lg font-black text-white leading-tight">${esc(predWinner)}</div>
          <div class="text-xs font-mono text-gray-400">${fmtPct(predWinnerProb)}</div>
        </div>` : ""}
        ${predWinner && top3.length ? `<div style="width:1px;height:2.5rem;background:rgba(255,255,255,.1);"></div>` : ""}
        ${top3[0] ? `
        <div>
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Top score</div>
          <div class="text-2xl font-black text-white leading-tight font-mono">${esc(top3[0].score)}</div>
          <div class="text-xs font-mono text-gray-400">${fmtPct(top3[0].p)}</div>
        </div>` : ""}
        ${f.truth ? `<div class="ml-auto">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Actual</div>
          <div class="text-2xl font-black font-mono leading-tight" style="color:#fbbf24;">${esc(f.truth.score || "—")}</div>
          <div class="text-xs font-mono" style="color:#fbbf2480;">${esc(
            f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : f.truth.result || "—"
          )}</div>
        </div>` : ""}
      </div>` : ""}

      <!-- 4-column detail grid -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">

        <!-- Win probs -->
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Win probs</div>
          ${[
            [hName, wp.home, "#e5e7eb", "#6b7280"],
            ["Draw", wp.draw, "#9ca3af", "#4b5563"],
            [aName,  wp.away, "#e5e7eb", "#6b7280"],
          ].map(([label, prob, textcol, barcol]) => `
            <div class="flex items-center gap-1.5 mb-1">
              <div class="w-14 flex-shrink-0 truncate text-[10px]" style="color:${textcol};">${esc(label)}</div>
              <div class="flex-1 bar h-1.5">
                <div class="h-full rounded-full" style="width:${(prob || 0) * 100}%;background:${barcol};"></div>
              </div>
              <div class="text-[10px] font-mono w-8 text-right font-bold" style="color:${textcol};">${fmtPct(prob)}</div>
            </div>`).join("")}
          <div class="text-[10px] text-gray-600 mt-1.5">
            xGD <span class="font-mono text-gray-300 font-bold">${fmt2(p.expected_goal_diff)}</span>
          </div>
        </div>

        <!-- Top 3 scores -->
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Score dist.</div>
          ${top3.length ? top3.map((s, i) => `
            <div class="flex items-center justify-between mb-1 ${i > 0 ? "opacity-50" : ""}">
              <span class="font-mono font-bold ${i === 0 ? "text-white text-sm" : "text-gray-300 text-xs"}">${esc(s.score)}</span>
              <span class="text-[10px] font-mono text-gray-500">${fmtPct(s.p)}</span>
            </div>`).join("")
            : `<div class="text-gray-600 text-xs">—</div>`}
        </div>

        <!-- Scorers -->
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Scorers</div>
          ${hScorers.length ? `
            <div class="text-[10px] text-gray-600 mb-1">${esc(hName)}</div>
            ${hScorers.map(s => `
              <div class="flex items-center justify-between mb-0.5">
                <span class="text-xs text-gray-200 font-semibold truncate" style="max-width:7rem;">${esc(s.player)}</span>
                <span class="text-[10px] font-mono text-gray-500 ml-1">${fmtPct(s.p)}</span>
              </div>`).join("")}` : ""}
          ${aScorers.length ? `
            <div class="text-[10px] text-gray-600 mt-2 mb-1">${esc(aName)}</div>
            ${aScorers.map(s => `
              <div class="flex items-center justify-between mb-0.5">
                <span class="text-xs text-gray-200 font-semibold truncate" style="max-width:7rem;">${esc(s.player)}</span>
                <span class="text-[10px] font-mono text-gray-500 ml-1">${fmtPct(s.p)}</span>
              </div>`).join("")}` : ""}
          ${!hScorers.length && !aScorers.length ? `<div class="text-gray-600 text-xs">—</div>` : ""}
          ${f.truth && f.truth.scorer_names && f.truth.scorer_names.length ? `
            <div class="text-[10px] text-gray-600 mt-2 pt-1.5 mb-0.5" style="border-top:1px solid rgba(255,255,255,.06);">Actual</div>
            ${f.truth.scorer_names.map(n => `<div class="text-xs font-bold truncate" style="color:#fbbf24;">${esc(n)}</div>`).join("")}` : ""}
        </div>

        <!-- MOTM -->
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-2">MOTM</div>
          ${topMotm ? `
            <div class="text-sm font-bold text-white leading-tight">${esc(topMotm.player)}</div>
            <div class="text-[10px] font-mono text-gray-500 mt-0.5">${fmtPct(topMotm.p)}</div>
            <div class="text-[10px] text-gray-600 mt-0.5">
              ${topMotm.team === "home" ? esc(hName) : esc(aName)}
            </div>` : `<div class="text-gray-600 text-xs">—</div>`}
          ${f.truth && f.truth.motm ? `
            <div class="text-[10px] text-gray-600 mt-2 pt-1.5 mb-0.5" style="border-top:1px solid rgba(255,255,255,.06);">Actual</div>
            <div class="text-xs font-bold" style="color:#fbbf24;">${esc(f.truth.motm)}</div>` : ""}
        </div>
      </div>

      <!-- Reasoning preview (4 lines) -->
      ${reasoning.overall ? `
        <div class="text-xs text-gray-300 leading-relaxed mb-2"
             style="display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;">
          ${esc(reasoning.overall)}
        </div>` : ""}

      <!-- Buttons -->
      <div class="flex flex-wrap gap-2 mt-1">
        ${hasReason ? `
          <button onclick="openReasoningModal(${idx})"
                  class="chip hover:bg-white/15 transition text-xs">📖 Full reasoning</button>` : ""}
        <button id="pred-details-btn-${idx}" onclick="toggleDetails(${idx})"
                class="chip hover:bg-white/15 transition text-xs">📊 More details</button>
      </div>

      <!-- Expandable details -->
      <div id="pred-details-${idx}" style="display:none;"
           class="mt-4 pt-4 space-y-5" style="border-top:1px solid rgba(255,255,255,.06);">
        ${_renderDetails(p, f)}
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
  const liveHtml = (lv && lv.status !== "Match Finished") ? `
    <div class="flex items-center justify-center gap-2 mb-4">
      <span class="chip" style="background:rgba(239,68,68,.2);border-color:rgba(239,68,68,.5);color:#fca5a5;">
        🔴 LIVE ${lv.elapsed != null ? `· ${lv.elapsed}′` : ""}
      </span>
      <span class="font-mono font-bold text-lg">
        ${lv.score ? `${lv.score.home ?? "?"}–${lv.score.away ?? "?"}` : ""}
      </span>
    </div>` : "";

  const agg = { home: 0, draw: 0, away: 0 };
  let nP = 0;
  for (const p of preds) {
    if (p.win_probs && typeof p.win_probs.home === "number") {
      agg.home += p.win_probs.home; agg.draw += p.win_probs.draw; agg.away += p.win_probs.away;
      nP++;
    }
  }
  if (nP > 0) { agg.home /= nP; agg.draw /= nP; agg.away /= nP; }

  const html = `
    <div class="card rounded-2xl p-6">
      <div class="pitch rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between flex-wrap gap-4">
          <div class="flex-1 text-center">
            ${f.home_logo ? `<img src="${esc(f.home_logo)}" alt="${esc(f.home)}" class="h-14 mx-auto mb-2"/>` : `<div class="text-4xl">🏠</div>`}
            <div class="font-bold text-lg">${esc(f.home || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">consensus ${fmtPct(agg.home)}</div>` : ""}
          </div>
          <div class="text-center px-4">
            <div class="text-gray-300 text-sm">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
            <div class="mt-1 text-2xl font-black">VS</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400 mt-1">draw ${fmtPct(agg.draw)}</div>` : ""}
            <div class="text-xs text-gray-400 mt-3" id="${cid}">${kick ? kick.toUTCString() : "—"}</div>
            ${f.venue ? `<div class="text-[10px] text-gray-500">${esc(f.venue)}</div>` : ""}
          </div>
          <div class="flex-1 text-center">
            ${f.away_logo ? `<img src="${esc(f.away_logo)}" alt="${esc(f.away)}" class="h-14 mx-auto mb-2"/>` : `<div class="text-4xl">🛫</div>`}
            <div class="font-bold text-lg">${esc(f.away || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">consensus ${fmtPct(agg.away)}</div>` : ""}
          </div>
        </div>
      </div>
      ${liveHtml}
      ${preds.length === 0
        ? `<div class="text-gray-400 text-sm">No model predictions locked yet (runs 24 h before kickoff).</div>`
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
      if (diff <= 0) { el2.textContent = "🔴 kicked off"; return; }
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
              <th class="text-right py-2 px-3">Composite</th>
              <th class="text-right py-2 px-3">Win %</th>
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
              return `
                <tr class="border-t border-white/5 hover:bg-white/5 transition">
                  <td class="py-2 px-3"><span class="rank-medal ${medal}">${i + 1}</span></td>
                  <td class="py-2 px-3"><span class="mr-2">${b.emoji}</span><span class="font-bold text-white">${esc(r.model_id)}</span></td>
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

    // Result badge: prefer live score during match, then truth, then "—"
    let resultBadge;
    if (isLive) {
      resultBadge = `
        <div class="flex items-center gap-2 justify-end">
          <span class="chip text-[10px]" style="background:rgba(239,68,68,.2);border-color:rgba(239,68,68,.5);color:#fca5a5;">
            🔴 LIVE${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}
          </span>
          <span class="font-mono font-bold text-xl">
            ${lv.score ? `${lv.score.home ?? "?"}–${lv.score.away ?? "?"}` : ""}
          </span>
        </div>`;
    } else {
      resultBadge = r.result
        ? `<div class="text-2xl font-black font-mono" style="color:#fbbf24;letter-spacing:-.02em;">${esc(r.result)}</div>`
        : `<div class="text-xl font-black text-gray-600">—</div>`;
    }

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
          <div class="text-right">
            ${resultBadge}
            ${r.models && r.models[0] ? `<div class="text-xs text-gray-400 mt-1">best composite: ${fmt2(r.models[0].composite)}</div>` : ""}
          </div>
        </summary>
        <div class="mt-4 space-y-3">
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
  document.getElementById("generated-at").textContent = "Last updated " + fmtTimestamp(data.generated_at);
  _allPreds = [];
  renderIncomingMatches(data.incoming_matches || []);
  renderLeaderboard(data.leaderboard || { main: [] }, "main");
  wireTabs(data.leaderboard || { main: [] });
  renderHistory(data.history || []);
}

main();
