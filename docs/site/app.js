// WorldCupArena site — fetches data.json written by src.leaderboard.build_site
// and renders everything client-side.

const fmtPct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const fmt2   = (x) => (x == null ? "—" : (+x).toFixed(2));
const esc    = (s) => String(s ?? "").replace(/[<>&"']/g, c =>
  ({"<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;"}[c]));

function modelBadge(id) {
  const key = (id || "").toLowerCase();
  if (key.includes("gpt"))        return { emoji: "🟢", tint: "from-emerald-500/20 to-emerald-500/5" };
  if (key.includes("claude"))     return { emoji: "🟠", tint: "from-orange-500/20 to-orange-500/5"  };
  if (key.includes("gemini"))     return { emoji: "🔵", tint: "from-sky-500/20 to-sky-500/5"        };
  if (key.includes("grok"))       return { emoji: "⚫", tint: "from-gray-500/20 to-gray-500/5"      };
  if (key.includes("deepseek"))   return { emoji: "🟣", tint: "from-violet-500/20 to-violet-500/5"  };
  if (key.includes("qwen"))       return { emoji: "🔴", tint: "from-red-500/20 to-red-500/5"        };
  if (key.includes("llama"))      return { emoji: "🟤", tint: "from-amber-700/20 to-amber-700/5"    };
  if (key.includes("perplexity")) return { emoji: "🔷", tint: "from-blue-500/20 to-blue-500/5"      };
  if (key.includes("mirothinker"))return { emoji: "✨", tint: "from-fuchsia-500/20 to-fuchsia-500/5"};
  return { emoji: "🤖", tint: "from-gray-500/20 to-gray-500/5" };
}

// ---------- Next match ---------------------------------------------------

function renderNextMatch(nm) {
  const el = document.getElementById("next-container");
  if (!nm || !nm.fixture) { el.innerHTML = `<div class="text-gray-400">No upcoming fixture in the registry yet.</div>`; return; }
  const f = nm.fixture;
  const kick = f.kickoff_utc ? new Date(f.kickoff_utc) : null;
  const countdownId = "nm-countdown";
  const preds = nm.predictions || [];

  // Consensus: average win_probs across models
  const agg = { home: 0, draw: 0, away: 0 };
  let nProbs = 0;
  for (const p of preds) {
    if (p.win_probs && typeof p.win_probs.home === "number") {
      agg.home += p.win_probs.home;
      agg.draw += p.win_probs.draw;
      agg.away += p.win_probs.away;
      nProbs++;
    }
  }
  if (nProbs > 0) { agg.home/=nProbs; agg.draw/=nProbs; agg.away/=nProbs; }

  el.innerHTML = `
    <div class="pitch rounded-xl p-5 mb-6">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div class="flex-1 text-center">
          ${f.home_logo ? `<img src="${esc(f.home_logo)}" alt="${esc(f.home)}" class="h-14 mx-auto mb-2"/>` : `<div class="text-4xl">🏠</div>`}
          <div class="font-bold text-lg">${esc(f.home)}</div>
          <div class="text-xs text-gray-400">consensus ${fmtPct(agg.home)}</div>
        </div>
        <div class="text-center px-4">
          <div class="text-gray-300 text-sm">${esc(f.competition || "")} · ${esc(f.stage || "")}</div>
          <div class="mt-1 text-2xl font-black">VS</div>
          <div class="text-xs text-gray-400 mt-1">draw ${fmtPct(agg.draw)}</div>
          <div class="text-xs text-gray-400 mt-3" id="${countdownId}">${kick ? kick.toUTCString() : "—"}</div>
          <div class="text-[10px] text-gray-500">${esc(f.venue || "")}</div>
        </div>
        <div class="flex-1 text-center">
          ${f.away_logo ? `<img src="${esc(f.away_logo)}" alt="${esc(f.away)}" class="h-14 mx-auto mb-2"/>` : `<div class="text-4xl">🛫</div>`}
          <div class="font-bold text-lg">${esc(f.away)}</div>
          <div class="text-xs text-gray-400">consensus ${fmtPct(agg.away)}</div>
        </div>
      </div>
    </div>

    ${ preds.length === 0
        ? `<div class="text-gray-400 text-sm">No model predictions locked for this fixture yet (runs at T-1h).</div>`
        : `<div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-gray-400 text-xs uppercase tracking-wider">
                <tr>
                  <th class="text-left py-2 px-3">Model</th>
                  <th class="text-center py-2 px-3">Setting</th>
                  <th class="text-center py-2 px-3">Win / Draw / Loss</th>
                  <th class="text-center py-2 px-3">Most likely</th>
                  <th class="text-center py-2 px-3">xGD</th>
                  <th class="text-left py-2 px-3">Reasoning (hover)</th>
                </tr>
              </thead>
              <tbody>
                ${preds.map(p => {
                  const b = modelBadge(p.model_id);
                  const wp = p.win_probs || {};
                  const reason = (p.reasoning_overall || "").slice(0, 400);
                  return `
                    <tr class="border-t border-white/5 hover:bg-white/5 transition">
                      <td class="py-2 px-3"><span class="mr-1">${b.emoji}</span>${esc(p.model_id)}</td>
                      <td class="text-center"><span class="chip chip-${p.setting.toLowerCase()}">${esc(p.setting)}</span></td>
                      <td class="py-2 px-3">
                        <div class="flex gap-1 items-center justify-center">
                          <div class="bar w-12"><div class="bar-fill" style="width:${(wp.home||0)*100}%"></div></div>
                          <span class="text-xs opacity-70 w-10 text-right">${fmtPct(wp.home)}</span>
                          <span class="mx-1 opacity-50">/</span>
                          <span class="text-xs opacity-70 w-10">${fmtPct(wp.draw)}</span>
                          <span class="mx-1 opacity-50">/</span>
                          <div class="bar w-12"><div class="bar-fill" style="width:${(wp.away||0)*100}%"></div></div>
                          <span class="text-xs opacity-70 w-10 text-right">${fmtPct(wp.away)}</span>
                        </div>
                      </td>
                      <td class="text-center font-bold">${esc(p.most_likely_score || "—")}</td>
                      <td class="text-center">${fmt2(p.expected_goal_diff)}</td>
                      <td class="py-2 px-3 text-xs text-gray-400 max-w-[22rem] truncate" title="${esc(reason)}">${esc(reason)}</td>
                    </tr>`;
                }).join("")}
              </tbody>
            </table>
          </div>`
    }`;

  // Countdown
  if (kick) {
    const tick = () => {
      const diff = kick - new Date();
      if (diff <= 0) { document.getElementById(countdownId).textContent = "🔴 kicked off"; return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      document.getElementById(countdownId).textContent = `kickoff in ${h}h ${m}m ${s}s`;
    };
    tick(); setInterval(tick, 1000);
  }
}

// ---------- Leaderboard --------------------------------------------------

let chartInstance = null;

function renderLeaderboard(lb, view) {
  const el = document.getElementById("leaderboard-container");
  const rows = lb.main || [];
  if (rows.length === 0) { el.innerHTML = `<div class="text-gray-400 text-sm">No graded fixtures yet.</div>`; return; }

  if (view === "main") {
    el.innerHTML = `
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-gray-400 text-xs uppercase tracking-wider">
            <tr>
              <th class="text-left py-2 px-3 w-12">#</th>
              <th class="text-left py-2 px-3">Model</th>
              <th class="text-right py-2 px-3">Composite</th>
              <th class="text-right py-2 px-3">N fixtures</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r, i) => {
              const b = modelBadge(r.model_id);
              const medal = i === 0 ? "rank-1" : i === 1 ? "rank-2" : i === 2 ? "rank-3" : "";
              return `
                <tr class="border-t border-white/5 hover:bg-white/5 transition">
                  <td class="py-2 px-3"><span class="rank-medal ${medal}">${i+1}</span></td>
                  <td class="py-2 px-3"><span class="mr-2">${b.emoji}</span><span class="font-semibold">${esc(r.model_id)}</span></td>
                  <td class="py-2 px-3 text-right font-mono">
                    <div class="inline-flex items-center gap-2">
                      <div class="bar w-28"><div class="bar-fill" style="width:${Math.min(100, r.mean)}%"></div></div>
                      <span>${fmt2(r.mean)}</span>
                    </div>
                  </td>
                  <td class="py-2 px-3 text-right text-gray-400">${r.n}</td>
                </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
  } else if (view === "layers") {
    el.innerHTML = `<canvas id="layersChart" height="220"></canvas>`;
    const layers = ["T1_core_result","T2_player_level","T3_event_level","T4_tactics_stats","T5_tournament_macro"];
    const labels = ["T1 Result","T2 Players","T3 Events","T4 Stats","T5 Tournament"];
    const palette = ["#22c55e","#3b82f6","#a855f7","#ec4899","#f59e0b","#14b8a6","#ef4444","#eab308","#64748b"];
    const datasets = rows.slice(0, 9).map((r, i) => ({
      label: r.model_id,
      data: layers.map(l => (r.layers_mean||{})[l] || 0),
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
          grid: { color: "rgba(255,255,255,.08)" },
          pointLabels: { color: "#cbd5e1", font: { size: 11 } },
          ticks: { backdropColor: "transparent", color: "#64748b" }
        }},
        plugins: { legend: { labels: { color: "#cbd5e1", boxWidth: 12 } } },
      },
    });
  } else if (view === "uplift") {
    const by = lb.by_model_setting || {};
    const pairs = Object.entries(by)
      .map(([m, s]) => ({ model: m, s1: s.S1, s2: s.S2, uplift: (s.S2 != null && s.S1 != null) ? s.S2 - s.S1 : null }))
      .filter(p => p.uplift != null)
      .sort((a, b) => b.uplift - a.uplift);
    if (pairs.length === 0) {
      el.innerHTML = `<div class="text-gray-400 text-sm">Need both an S1 and an S2 entry for the same model to show uplift.</div>`;
      return;
    }
    el.innerHTML = `
      <div class="space-y-2">
        ${pairs.map(p => `
          <div class="flex items-center gap-3">
            <div class="w-48 truncate">${esc(p.model)}</div>
            <div class="flex-1 bar"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, p.uplift*2 + 50))}%"></div></div>
            <div class="w-32 text-right text-sm font-mono">
              S1 ${fmt2(p.s1)} → S2 ${fmt2(p.s2)}
              <span class="${p.uplift >= 0 ? 'text-emerald-400' : 'text-rose-400'} ml-2">
                (${p.uplift >= 0 ? "+" : ""}${fmt2(p.uplift)})
              </span>
            </div>
          </div>`).join("")}
      </div>`;
  }
}

function wireTabs(lb) {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach(btn => btn.addEventListener("click", () => {
    buttons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    renderLeaderboard(lb, btn.dataset.view);
  }));
}

// ---------- History ------------------------------------------------------

function renderHistory(rows) {
  const el = document.getElementById("history-container");
  if (!rows || rows.length === 0) { el.innerHTML = `<div class="text-gray-400 text-sm col-span-2">No graded fixtures yet.</div>`; return; }
  el.innerHTML = rows.map(r => {
    const best = r.models && r.models[0];
    const date = r.kickoff_utc ? new Date(r.kickoff_utc).toISOString().slice(0, 10) : "";
    return `
      <details class="card rounded-xl p-4">
        <summary class="flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400">${esc(date)} · ${esc(r.competition || "")} ${esc(r.stage || "")}</div>
            <div class="font-semibold">${esc(r.home || "?")} <span class="text-gray-500 mx-2">vs</span> ${esc(r.away || "?")}</div>
          </div>
          <div class="text-right">
            <div class="text-xl font-black">${esc(r.result || "—")}</div>
            ${best ? `<div class="text-xs text-gray-400">best: ${esc(best.model_id)} · ${fmt2(best.composite)}</div>` : ""}
          </div>
        </summary>
        <div class="mt-3 space-y-1 text-sm">
          ${(r.models || []).map(m => `
            <div class="flex items-center justify-between border-t border-white/5 pt-1">
              <span class="text-gray-300">${modelBadge(m.model_id).emoji} ${esc(m.model_id)}
                <span class="chip chip-${(m.setting || "").toLowerCase()} ml-1">${esc(m.setting)}</span></span>
              <span class="font-mono">${fmt2(m.composite)}</span>
            </div>`).join("")}
        </div>
      </details>`;
  }).join("");
}

// ---------- Boot ---------------------------------------------------------

async function main() {
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
  document.getElementById("generated-at").textContent =
    "Last updated " + (data.generated_at || "—");
  renderNextMatch(data.next_match);
  renderLeaderboard(data.leaderboard || { main: [] }, "main");
  wireTabs(data.leaderboard || { main: [] });
  renderHistory(data.history || []);
}

main();
