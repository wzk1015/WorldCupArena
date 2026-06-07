// WorldCupArena site — fetches language-specific data JSON written by src.leaderboard.build_site
// and renders everything client-side.

const fmtPct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const fmt2   = (x) => (x == null ? "—" : (+x).toFixed(2));
const esc    = (s) => String(s ?? "").replace(/[<>&"']/g, c =>
  ({ "<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;" }[c]));

const MATCHMATE_BRAND = "MatchMate AI比分预测";
const WORLDCUPARENA_BRAND = "WorldCupArena";

const I18N = {
  zh: {
    html_lang: "zh-CN",
    page_title: "WorldCupArena — AI 足球预测排行榜",
    meta_description: "用真实足球比赛评测大模型和 Deep Research Agent 的预测能力，包含实时排行榜和即将进行比赛的模型预测。",
    lang_button: "English",
    lang_button_title: "切换到英文",
    theme_dark: "深色",
    theme_light: "浅色",
    theme_select_label: "主题",
    theme_select_title: "切换网页主题",
    nav_incoming: "即将进行",
    nav_leaderboard: "排行榜",
    nav_history: "历史比赛",
    hero_tagline: "AI<span class=\"gradient-text\">预测足球比分</span>",
    author_html: "作者 <a class=\"underline hover:text-white\" href=\"https://www.wzk.plus\" target=\"_blank\">Zhaokai Wang</a> · <a class=\"underline hover:text-white\" href=\"mailto:zhaokaiwang99@gmail.com\">zhaokaiwang99@gmail.com</a>",
    section_incoming: "🔮 即将进行的比赛",
    section_leaderboard: "🏆 排行榜",
    section_history: "📋 历史比赛",
    tab_composite: "总榜",
    tab_layers: "分层分数",
    loading_predictions: "正在加载预测…",
    loading: "正在加载…",
    footer_html: "开源 · MIT · 研究项目 · <a class=\"underline\" href=\"https://github.com/wzk1015/WorldCupArena/\" target=\"_blank\">source</a>",
    setting_s1_tip: "S1 · 注入完整上下文包的大模型（官方阵容、近期状态、约 20 条新闻标题、统计数据）。不使用工具。",
    setting_s2_tip: "S2 · 可调用工具的 Agent，自主联网搜索。不预先注入上下文，由模型自己检索信息。",
    model_search_suffix: "（联网）",
    reasoning: "推理",
    full_reasoning_suffix: "完整推理",
    no_reasoning: "暂无推理内容。",
    reasoning_overall: "整体分析",
    reasoning_t1: "T1 · 赛果与比分",
    reasoning_t2: "T2 · 球员与阵容",
    reasoning_t3: "T3 · 事件与时间线",
    reasoning_t4: "T4 · 比赛数据",
    draw: "平局",
    home: "主队",
    away: "客队",
    substitute: "替补",
    actual: "实际",
    lineups: "⬡ 阵容",
    scorers: "⚽ 进球者",
    assisters: "🎯 助攻者",
    substitutions: "🔄 换人",
    cards: "🟨 红黄牌",
    penalties: "🥅 点球",
    own_goals: "⚽ 乌龙球",
    stats: "📊 数据统计",
    player: "球员",
    team: "球队",
    prob: "概率",
    minutes: "时间",
    min: "分钟",
    off_on: "下场 → 上场",
    card: "牌",
    taker: "主罚",
    outcome: "结果",
    stat: "数据",
    h: "主",
    a: "客",
    possession: "控球率 %",
    shots: "射门",
    shots_on_target: "射正",
    corners: "角球",
    pass_accuracy: "传球成功率 %",
    fouls: "犯规",
    saves: "扑救",
    no_goals: "无进球",
    no_assists: "无助攻记录",
    no_cards: "无红黄牌",
    no_penalties: "无点球",
    no_own_goals: "无乌龙球",
    no_details: "暂无详细预测数据。",
    search_sources: "🔗 联网来源",
    win_probabilities: "📊 胜率预测",
    score_distribution: "🎯 比分分布",
    full_reasoning: "📖 完整推理",
    hide_detail: "🔼 收起详情",
    show_details: "👇 展开完整分析",
    hide_details: "👇 收起分析",
    sources: "🔗 来源（{count}）",
    hide_sources: "🔗 收起来源",
    sources_omitted: "其余 {count} 个参考链接已省略。",
    show_all_models: "显示全部模型（+{count}）",
    show_all_models_mobile: "展开其余 {count} 个模型",
    show_fewer_models: "收起模型",
    show_predictions: "展开模型预测",
    no_predictions: "这场比赛还没有模型预测。",
    cost: "成本",
    unavailable: "暂不可用",
    not_run: "尚未运行",
    unavailable_detail: "预测暂不可用；之后会自动重试。",
    not_run_detail: "尚未运行；调度器会在合适时间执行。",
    pred_winner: "预测胜者",
    pred_score: "预测比分",
    live_predictions: "赛中实时预测",
    live_prediction_note: "赛中预测不计入排行榜",
    live_current_snapshot: "基于 {score} · {minute}",
    live_updated_at: "更新于 {time}",
    live_final_score: "最可能最终比分",
    future_scorers: "后续进球球员",
    no_future_scorers: "暂无后续进球预测",
    vs: "VS",
    win: "胜 {pct}",
    draw_prob: "平局 {pct}",
    no_model_predictions: "暂无模型预测（通常开赛前 24 小时运行）。",
    no_fixtures: "未来 7 天暂无赛程。",
    live: "🟢 进行中",
    live_red: "🔴 进行中",
    kickoff_in: "开赛倒计时 {h}小时 {m}分 {s}秒",
    no_graded: "暂无已评分比赛。",
    model: "模型",
    composite_score: "综合分",
    result_accuracy: "赛果准确率",
    leaderboard_sort_result: "排序：赛果准确率",
    leaderboard_sort_composite: "排序：综合分",
    leaderboard_sort_to_result: "切换为赛果准确率排序",
    leaderboard_sort_to_composite: "切换为综合分排序",
    games: "场次",
    layer_t1: "T1 赛果",
    layer_t2: "T2 球员",
    layer_t3: "T3 事件",
    layer_t4: "T4 数据",
    layer_t5: "T5 大赛背景",
    load_error: "无法加载 data.json，自动化 workflow 可能还在运行。"
  },
  en: {
    html_lang: "en",
    page_title: "WorldCupArena — LLM Football Prediction Leaderboard",
    meta_description: "Benchmarking LLMs and deep-research agents on real-world football prediction. Live leaderboard + next-match model predictions.",
    lang_button: "中文",
    lang_button_title: "Switch to Chinese",
    theme_dark: "Dark",
    theme_light: "Light",
    theme_select_label: "Theme",
    theme_select_title: "Change site theme",
    nav_incoming: "Incoming Matches",
    nav_leaderboard: "Leaderboard",
    nav_history: "Past Matches",
    hero_tagline: "AI <span class=\"gradient-text\">Football Score Prediction</span>",
    author_html: "by <a class=\"underline hover:text-white\" href=\"https://www.wzk.plus\" target=\"_blank\">Zhaokai Wang</a> · <a class=\"underline hover:text-white\" href=\"mailto:zhaokaiwang99@gmail.com\">zhaokaiwang99@gmail.com</a>",
    section_incoming: "🔮 Incoming Matches",
    section_leaderboard: "🏆 Leaderboard",
    section_history: "📋 Past Matches",
    tab_composite: "Ranking",
    tab_layers: "Per-layer Score",
    loading_predictions: "Loading predictions…",
    loading: "Loading…",
    footer_html: "Open-source · MIT · built for research · <a class=\"underline\" href=\"https://github.com/wzk1015/WorldCupArena/\" target=\"_blank\">source</a>",
    setting_s1_tip: "S1 · LLM with full injected context pack (official squads, recent form, ~20 news headlines, stats). No tools.",
    setting_s2_tip: "S2 · Tool-using agent, self-directed search. No context pre-injected — the model searches for everything itself.",
    model_search_suffix: " (Search)",
    reasoning: "Reasoning",
    full_reasoning_suffix: "Full Reasoning",
    no_reasoning: "No reasoning available.",
    reasoning_overall: "Overall Analysis",
    reasoning_t1: "T1 · Result & Score",
    reasoning_t2: "T2 · Players & Lineups",
    reasoning_t3: "T3 · Events & Timeline",
    reasoning_t4: "T4 · Match Statistics",
    draw: "Draw",
    home: "Home",
    away: "Away",
    substitute: "Sub",
    actual: "Actual",
    lineups: "⬡ Lineups",
    scorers: "⚽ Scorers",
    assisters: "🎯 Assisters",
    substitutions: "🔄 Substitutions",
    cards: "🟨 Cards",
    penalties: "🥅 Penalties",
    own_goals: "⚽ Own Goals",
    stats: "📊 Stats",
    player: "Player",
    team: "Team",
    prob: "Prob",
    minutes: "Minutes",
    min: "Min",
    off_on: "Off → On",
    card: "Card",
    taker: "Taker",
    outcome: "Outcome",
    stat: "Stat",
    h: "H",
    a: "A",
    possession: "Possession %",
    shots: "Shots",
    shots_on_target: "Shots on Target",
    corners: "Corners",
    pass_accuracy: "Pass Accuracy %",
    fouls: "Fouls",
    saves: "Saves",
    no_goals: "No goals",
    no_assists: "No assists recorded",
    no_cards: "No cards",
    no_penalties: "No penalties",
    no_own_goals: "No own goals",
    no_details: "No detailed prediction data available.",
    search_sources: "🔗 Search Sources",
    win_probabilities: "📊 Win Probabilities",
    score_distribution: "🎯 Score Distribution",
    full_reasoning: "📖 Full Reasoning",
    hide_detail: "🔼 Hide Detail",
    show_details: "👇 Show Full AI Analysis",
    hide_details: "👇 Hide Details",
    sources: "🔗 Sources ({count})",
    hide_sources: "🔗 Hide sources",
    sources_omitted: "{count} more links omitted.",
    show_all_models: "Show all models (+{count})",
    show_all_models_mobile: "Show {count} more models",
    show_fewer_models: "Show fewer models",
    show_predictions: "Show predictions",
    no_predictions: "No predictions for this fixture.",
    cost: "Cost",
    unavailable: "Unavailable",
    not_run: "Not Run",
    unavailable_detail: "Prediction unavailable; this model will retry later.",
    not_run_detail: "Not run yet; the scheduler will run this model when due.",
    pred_winner: "Pred Winner",
    pred_score: "Pred Score",
    live_predictions: "In-Play Predictions",
    live_prediction_note: "In-play predictions are not counted in the leaderboard",
    live_current_snapshot: "Based on {score} · {minute}",
    live_updated_at: "Updated {time}",
    live_final_score: "Most Likely Final Score",
    future_scorers: "Future Scorers",
    no_future_scorers: "No future scorers predicted",
    vs: "VS",
    win: "win {pct}",
    draw_prob: "draw {pct}",
    no_model_predictions: "No model predictions yet (runs 24 h before kickoff).",
    no_fixtures: "No fixtures scheduled in the next 7 days.",
    live: "🟢 Live",
    live_red: "🔴 LIVE",
    kickoff_in: "kickoff in {h}h {m}m {s}s",
    no_graded: "No graded fixtures yet.",
    model: "Model",
    composite_score: "Composite Score",
    result_accuracy: "Result Accuracy",
    leaderboard_sort_result: "Sort: Result Accuracy",
    leaderboard_sort_composite: "Sort: Composite Score",
    leaderboard_sort_to_result: "Switch to result accuracy sorting",
    leaderboard_sort_to_composite: "Switch to composite score sorting",
    games: "#Games",
    layer_t1: "T1 Result",
    layer_t2: "T2 Players",
    layer_t3: "T3 Events",
    layer_t4: "T4 Stats",
    layer_t5: "T5 Tournament",
    load_error: "Couldn't load data.json — is the automation workflow running?"
  }
};

const MATCHMATE_I18N = {
  zh: {
    page_title: "MatchMate AI比分预测",
    meta_description: "MatchMate AI比分预测：聚合多模型足球比分预测、赛果准确率和参考链接。",
    footer_html: "作者 <a class=\"underline hover:text-white\" href=\"https://www.wzk.plus\" target=\"_blank\">Zhaokai Wang</a> · <a class=\"underline hover:text-white\" href=\"mailto:zhaokaiwang99@gmail.com\">zhaokaiwang99@gmail.com</a> · <a class=\"chip hover:bg-white/15 transition text-[11px]\" href=\"https://github.com/wzk1015/WorldCupArena/\" target=\"_blank\">GitHub ↗</a>",
    search_sources: "🔗 参考链接",
    sources: "🔗 参考链接（{count}）",
    hide_sources: "🔗 收起参考链接",
  }
};

function normalizeTheme(theme) {
  return theme === "light" ? "light" : "dark";
}

function initialTheme() {
  const params = new URLSearchParams(window.location.search);
  return normalizeTheme(params.get("theme"));
}

function initialMatchMateMode() {
  const params = new URLSearchParams(window.location.search);
  const matchmateParam = params.get("matchmate");
  const matchmatePath = window.location.pathname.replace(/\/+$/, "") === "/predict";
  return matchmateParam === "1" || (matchmateParam !== "0" && matchmatePath);
}

const _matchmateMode = initialMatchMateMode();
let _lang = _matchmateMode ? "zh" : (localStorage.getItem("wca_lang") === "en" ? "en" : "zh");
let _theme = initialTheme();
let _siteData = null;
let _activeLeaderboardView = "main";
let _leaderboardSort = "result";
let _countdownIntervals = [];
let _mobilePredView = null;

function t(key, vars = {}) {
  const matchmateText = _matchmateMode ? (MATCHMATE_I18N[_lang] && MATCHMATE_I18N[_lang][key]) : undefined;
  let text = matchmateText
    ?? (I18N[_lang] && I18N[_lang][key])
    ?? I18N.en[key]
    ?? key;
  for (const [name, value] of Object.entries(vars)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

function settingTip(setting) {
  if (setting === "S1") return t("setting_s1_tip");
  if (setting === "S2") return t("setting_s2_tip");
  return setting || "";
}

function isMobilePredLayout() {
  return window.matchMedia("(max-width: 767px)").matches;
}

function showAllModelsText(count) {
  return t(isMobilePredLayout() ? "show_all_models_mobile" : "show_all_models", { count });
}

function applyStaticI18n() {
  document.documentElement.lang = t("html_lang");
  document.title = t("page_title");
  document.documentElement.dataset.mode = _matchmateMode ? "matchmate" : "worldcuparena";
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute("content", t("meta_description"));
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-html]").forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    el.setAttribute("title", t(el.dataset.i18nTitle));
  });
  applyBranding();
  applyModeControls();
  updateThemeControls();
  updateLeaderboardSortButton();
}

async function toggleLanguage() {
  if (_matchmateMode) return;
  _lang = _lang === "zh" ? "en" : "zh";
  localStorage.setItem("wca_lang", _lang);
  applyStaticI18n();
  await loadSiteData();
}

function brandHtml() {
  if (_matchmateMode) return esc(MATCHMATE_BRAND);
  return `${WORLDCUPARENA_BRAND.slice(0, 8)}<span class="gradient-text">${WORLDCUPARENA_BRAND.slice(8)}</span>`;
}

function applyBranding() {
  document.querySelectorAll("[data-brand]").forEach(el => {
    el.innerHTML = brandHtml();
  });
}

function applyModeControls() {
  const langToggle = document.getElementById("lang-toggle");
  const navGithub = document.getElementById("github-nav-link");
  const leaderboardControls = document.getElementById("leaderboard-controls");
  if (langToggle) langToggle.classList.toggle("hidden", _matchmateMode);
  if (navGithub) navGithub.classList.toggle("hidden", _matchmateMode);
  if (leaderboardControls) leaderboardControls.classList.toggle("hidden", _matchmateMode);
  if (_matchmateMode) {
    _lang = "zh";
    _activeLeaderboardView = "main";
    _leaderboardSort = "result";
  }
}

function setTheme(theme, options = {}) {
  _theme = normalizeTheme(theme);
  document.documentElement.dataset.theme = _theme;
  document.documentElement.style.colorScheme = _theme;
  updateThemeControls();
  if (options.updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("theme", _theme);
    window.history.replaceState(null, "", url);
  }
  if (_siteData && _activeLeaderboardView === "layers") {
    renderLeaderboard(_siteData.leaderboard || { main: [] }, _activeLeaderboardView);
  }
}

function updateThemeControls() {
  const select = document.getElementById("theme-select");
  if (!select) return;
  select.innerHTML = `
    <option value="dark">${esc(t("theme_dark"))}</option>
    <option value="light">${esc(t("theme_light"))}</option>
  `;
  select.value = _theme;
  select.setAttribute("aria-label", t("theme_select_label"));
  select.setAttribute("title", t("theme_select_title"));
}

function renderVenueLocation(match) {
  if (!match?.venue) return "";
  const country = String(match.venue_country ?? "").trim();
  const visibleCountry = country.toLowerCase() === "world" ? "" : country;
  return `<div class="text-[10px] text-gray-500 mt-1">${esc(match.venue)}</div>${
    match.venue_city
      ? `<div class="text-[10px] text-gray-500">${esc(match.venue_city)}${visibleCountry ? `, ${esc(visibleCountry)}` : ""}</div>`
      : ""
  }`;
}

const MODEL_DISPLAY_NAMES = {
  "gemini-3.1-pro-preview-thinking": "Gemini 3.1 Pro Preview (Thinking)",
  "gemini-3.1-pro-preview-thinking-search": "Gemini 3.1 Pro Preview (Thinking + Search)",
  "claude-opus-4-7-thinking": "Claude Opus 4.7 (Thinking)",
  "claude-opus-4-7-thinking-search": "Claude Opus 4.7 (Thinking + Search)",
  "gpt-5.4": "GPT-5.4",
  "gpt-5.4-search": "GPT-5.4 (Search)",
  "deepseek-r1": "DeepSeek V4 Pro",
  "qwen3-max": "Qwen3.7 Max",
  "kimi-k2": "Kimi K2.6",
  "glm-4.5": "GLM-5.1",
  "doubao-seed-1.6-thinking": "Doubao Seed 2.0 Lite",
  "minimax-m2.7": "MiniMax M2.7",
  "llama-4-maverick": "Llama 4 Maverick",
  "gemma-7b": "Gemma 4 31B IT",
  "gemini-deep-research": "Gemini Deep Research",
};

function fmtModelId(model) {
  const id = typeof model === "string" ? model : model?.model_id;
  const displayName = typeof model === "string" ? null : model?.display_name;
  if (displayName) return formatModelNameForMode(displayName);
  if (!id) return id;
  if (MODEL_DISPLAY_NAMES[id]) return formatModelNameForMode(MODEL_DISPLAY_NAMES[id]);
  const words = String(id).replaceAll("_", "-").split("-");
  const acronyms = new Set(["gpt", "glm", "qwen", "kimi", "llama", "gemma", "api"]);
  const generated = words.filter(Boolean).map(word => {
    const lower = word.toLowerCase();
    if (acronyms.has(lower)) return word.toUpperCase();
    if (/^\d+(\.\d+)?$/.test(word)) return word;
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(" ");
  return formatModelNameForMode(generated);
}

function formatModelNameForMode(name) {
  if (!_matchmateMode) return name;
  let out = String(name || "");
  out = out.replace(/\s*\(\s*(?:thinking\s*\+\s*search|thinking\+search|search)\s*\)\s*/ig, "（自主搜索）");
  out = out.replace(/\s*\(\s*thinking\s*\)\s*/ig, "");
  out = out.replace(/\s*（\s*自主搜索\s*）\s*/g, "（自主搜索）");
  out = out.replace(/\bDoubao\s+Seed\b/ig, "豆包 Seed");
  if (/^Qwen/i.test(out) && !/^千问\s/i.test(out)) {
    out = out.replace(/^Qwen/i, "千问 Qwen");
  }
  return out.trim();
}

let _allPreds = [];     // flat registry of all rendered pred cards
let _predFixtures = []; // fixture/history object per rendered pred

function registerPreds(preds, fixture) {
  const start = _allPreds.length;
  for (const pred of preds || []) {
    _allPreds.push(pred);
    _predFixtures.push(fixture);
  }
  return start;
}

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
  if (key.includes("doubao"))  return { emoji: "🫘" };
  if (key.includes("minimax")) return { emoji: "〽️" };
  if (key.includes("gemma"))   return { emoji: "💎" };
  if (key.includes("llama"))   return { emoji: "🦙" };
  if (key.includes("perplexity")) return { emoji: "🔷" };
  if (key.includes("mirothinker")) return { emoji: "✨" };
  return { emoji: "🤖" };
}

// ---------- Reasoning modal --------------------------------------------------

function reasoningLabels() {
  return {
    overall:   t("reasoning_overall"),
    t1_result: t("reasoning_t1"),
    t2_player: t("reasoning_t2"),
    t3_events: t("reasoning_t3"),
    t4_stats:  t("reasoning_t4"),
  };
}

function buildReasoningModal() {
  const div = document.createElement("div");
  div.id = "reasoning-modal";
  div.style.cssText = "display:none;position:fixed;inset:0;z-index:50;align-items:center;justify-content:center;padding:1rem;";
  div.innerHTML = `
    <div class="reasoning-modal-backdrop" style="position:absolute;inset:0;backdrop-filter:blur(4px);"
         onclick="closeReasoningModal()"></div>
    <div class="card reasoning-modal-card rounded-2xl p-6 relative" style="max-width:42rem;width:100%;max-height:80vh;overflow-y:auto;z-index:1;">
      <button onclick="closeReasoningModal()"
              class="absolute top-4 right-4 text-gray-400 hover:text-white text-xl leading-none">✕</button>
      <h3 class="font-bold text-base mb-4" id="reasoning-modal-title">${t("reasoning")}</h3>
      <div id="reasoning-modal-body"></div>
    </div>`;
  document.body.appendChild(div);
}

function openReasoningModal(idx) {
  const p = _allPreds[idx];
  if (!p) return;
  const r = p.reasoning || {};
  document.getElementById("reasoning-modal-title").textContent =
    `${fmtModelId(p)} (${p.setting}) — ${t("full_reasoning_suffix")}`;
  const rows = Object.entries(reasoningLabels())
    .filter(([k]) => r[k])
    .map(([k, label]) => `
      <tr style="border-top:1px solid rgba(255,255,255,.08)">
        <td style="padding:.75rem .75rem .75rem 0;vertical-align:top;width:8rem;white-space:nowrap;"
            class="text-xs font-semibold text-gray-400">${esc(label)}</td>
        <td style="padding:.75rem 0;" class="text-sm text-gray-200 leading-relaxed">${esc(r[k])}</td>
      </tr>`).join("");
  document.getElementById("reasoning-modal-body").innerHTML =
    `<table style="width:100%;border-collapse:collapse;"><tbody>${rows ||
      `<tr><td class="text-gray-400 text-sm py-2">${t("no_reasoning")}</td></tr>`
    }</tbody></table>`;
  document.getElementById("reasoning-modal").style.display = "flex";
}

function closeReasoningModal() {
  document.getElementById("reasoning-modal").style.display = "none";
}

// ---------- Prediction card --------------------------------------------------

function outcomeFromScore(score, homeName, awayName) {
  const match = String(score || "").trim().match(/^(\d+)\s*[-:]\s*(\d+)$/);
  if (!match) return null;
  const homeGoals = Number(match[1]);
  const awayGoals = Number(match[2]);
  if (homeGoals === awayGoals) return t("draw");
  return homeGoals > awayGoals ? homeName : awayName;
}

function winProbsFromScoreDist(scoreDist) {
  const totals = { home: 0, draw: 0, away: 0 };
  let total = 0;
  for (const item of scoreDist || []) {
    const match = String(item.score || "").trim().match(/^(\d+)\s*[-:]\s*(\d+)$/);
    if (!match) continue;
    const p = Math.max(0, Number(item.p) || 0);
    const homeGoals = Number(match[1]);
    const awayGoals = Number(match[2]);
    const outcome = homeGoals > awayGoals ? "home" : awayGoals > homeGoals ? "away" : "draw";
    totals[outcome] += p;
    total += p;
  }
  if (total <= 0) return null;
  return {
    home: totals.home / total,
    draw: totals.draw / total,
    away: totals.away / total,
  };
}

function winnerFromWinProbs(wp, homeName, awayName) {
  if (!wp || wp.home == null || wp.draw == null || wp.away == null) return null;
  if (wp.home >= wp.draw && wp.home >= wp.away) return homeName;
  if (wp.away >= wp.home && wp.away >= wp.draw) return awayName;
  return t("draw");
}

function toggleDetails(idx) {
  const btn = document.getElementById(`pred-details-btn-${idx}`);
  const group = btn?.closest("[data-pred-grid]");
  const row = btn?.closest("[data-pred-row]");
  const panel = row?.querySelector("[data-pred-panel='1']");
  if (!group || !row || !panel) return;

  const showingSame = !panel.classList.contains("hidden")
    && panel.dataset.panelType === "details"
    && panel.dataset.predIdx === String(idx);

  resetPredGridButtons(group);
  if (showingSame) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    panel.dataset.panelType = "";
    panel.dataset.predIdx = "";
    return;
  }

  panel.innerHTML = renderDetailsPanel(idx);
  panel.dataset.panelType = "details";
  panel.dataset.predIdx = String(idx);
  panel.classList.remove("hidden");
  if (btn) btn.textContent = t("hide_details");
}

function toggleSources(idx) {
  const btn = document.getElementById(`pred-sources-btn-${idx}`);
  const group = btn?.closest("[data-pred-grid]");
  const row = btn?.closest("[data-pred-row]");
  const panel = row?.querySelector("[data-pred-panel='1']");
  if (!group || !row || !panel) return;

  const showingSame = !panel.classList.contains("hidden")
    && panel.dataset.panelType === "sources"
    && panel.dataset.predIdx === String(idx);

  resetPredGridButtons(group);
  if (showingSame) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    panel.dataset.panelType = "";
    panel.dataset.predIdx = "";
    return;
  }

  panel.innerHTML = renderSourcesPanel(idx);
  panel.dataset.panelType = "sources";
  panel.dataset.predIdx = String(idx);
  panel.classList.remove("hidden");
  if (btn) btn.textContent = t("hide_sources");
}

function resetPredGridButtons(group) {
  group.querySelectorAll("[id^='pred-details-btn-']").forEach(button => {
    button.textContent = t("show_details");
  });
  group.querySelectorAll("[id^='pred-sources-btn-']").forEach(button => {
    const count = button.dataset.sourceCount || "0";
    button.textContent = t("sources", { count });
  });
}

function togglePredictionGroup(groupId, btn) {
  const group = document.getElementById(groupId);
  if (!group) return;
  const extras = group.querySelectorAll("[data-pred-extra-row='1']");
  const showingExtras = Array.from(extras).some(el => !el.classList.contains("hidden"));
  const hiddenCount = btn?.dataset.hiddenCount || extras.length;
  extras.forEach(el => el.classList.toggle("hidden", showingExtras));
  if (showingExtras) {
    resetPredGridButtons(group);
    group.querySelectorAll("[data-pred-panel='1']").forEach(panel => {
      panel.classList.add("hidden");
      panel.innerHTML = "";
      panel.dataset.panelType = "";
      panel.dataset.predIdx = "";
    });
  }
  if (btn) btn.textContent = showingExtras
    ? showAllModelsText(hiddenCount)
    : t("show_fewer_models");
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

const POSITION_ALIASES = {
  GK: "GK",
  G: "GK",
  "门将": "GK",
  DF: "DF",
  D: "DF",
  "后卫": "DF",
  MF: "MF",
  M: "MF",
  "中场": "MF",
  FW: "FW",
  F: "FW",
  "前锋": "FW",
};

function _positionCode(pos) {
  return POSITION_ALIASES[String(pos || "").trim()] || String(pos || "").trim();
}

function _positionLabel(pos) {
  const code = _positionCode(pos);
  const zh = { GK: "门将", DF: "后卫", MF: "中场", FW: "前锋" };
  return _lang === "zh" ? (zh[code] || pos || "") : code;
}

function _lineupSide(lineup, formation, teamName, trStarting, hasTruth) {
  const POS = ["GK", "DF", "MF", "FW"];
  const starting = (lineup || {}).starting || [];
  const bench    = (lineup || {}).bench    || [];
  const byPos = {};
  for (const pl of starting) {
    const pos = _positionCode(pl.position);
    (byPos[pos] = byPos[pos] || []).push(pl.name);
  }
  const trNames = new Set((trStarting || []).map(p => _normName(p.player)));
  const plColor = (name) => !hasTruth ? "text-gray-200" : trNames.has(_normName(name)) ? "text-green-400" : "text-red-400";
  return `
    <div>
      <div class="text-xs font-semibold mb-2 text-gray-200">
        ${esc(teamName)}${formation ? ` <span class="text-gray-400 font-normal">(${esc(formation)})</span>` : ""}
      </div>
      ${POS.filter(pos => byPos[pos]).map(pos => `
        <div class="text-xs mb-1 leading-snug">
          <span class="text-gray-500 inline-block w-9">${esc(_positionLabel(pos))}</span>
          ${byPos[pos].map(n => `<span class="${plColor(n)}">${esc(n)}</span>`).join(", ")}
        </div>`).join("")}
      ${bench.length ? `
        <div class="text-xs mt-2 leading-snug text-gray-500">
          <span class="inline-block w-7">${t("substitute")}</span>${bench.map(pl => esc(pl.name)).join(", ")}
        </div>` : ""}
    </div>`;
}

// Renders a highlighted "Actual" truth block used in detail sections
function _truthBlock(content) {
  return `<div class="mt-2 rounded-lg px-3 py-2 text-xs" style="background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.25);">
    <span class="text-amber-400 font-semibold uppercase tracking-wider text-[10px] mr-2">${t("actual")}</span>${content}
  </div>`;
}

function _renderDetails(p, f) {
  const hName  = f.home || t("home");
  const aName  = f.away || t("away");
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
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("lineups")}</div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          ${_lineupSide(lin.home, (p.formations || {}).home, hName, trLinHome, !!tr)}
          ${_lineupSide(lin.away, (p.formations || {}).away, aName, trLinAway, !!tr)}
        </div>
        ${(trLinHome || trLinAway) ? _truthBlock(`
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-1">
            <div>
              <div class="text-amber-300/70 text-[10px] mb-1">${esc(hName)}${trFmHome ? ` · ${esc(trFmHome)}` : ""}</div>
              ${(trLinHome || []).map(pl => `<div class="text-gray-200 leading-tight">${esc(pl.player)}${pl.pos ? ` <span class="text-gray-500">(${esc(_positionLabel(pl.pos))})</span>` : ""}</div>`).join("")}
            </div>
            <div>
              <div class="text-amber-300/70 text-[10px] mb-1">${esc(aName)}${trFmAway ? ` · ${esc(trFmAway)}` : ""}</div>
              ${(trLinAway || []).map(pl => `<div class="text-gray-200 leading-tight">${esc(pl.player)}${pl.pos ? ` <span class="text-gray-500">(${esc(_positionLabel(pl.pos))})</span>` : ""}</div>`).join("")}
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
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("scorers")}</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">${t("player")}</th>
            <th class="font-normal pb-1 text-center">${t("team")}</th>
            <th class="font-normal pb-1 text-center">${t("prob")}</th>
            <th class="font-normal pb-1 text-center">${t("minutes")}</th>
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
        ) : tr ? _truthBlock(`<span class="text-gray-400">${t("no_goals")}</span>`) : ""}
      </div>`;
  }

  // Assisters
  if ((p.assisters || []).length) {
    const trAssisters = tr && tr.assisters ? tr.assisters : null;
    const trAssisterNames = new Set((trAssisters || []).map(a => _normName(a.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("assisters")}</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1">${t("player")}</th>
            <th class="font-normal pb-1 text-center">${t("team")}</th>
            <th class="font-normal pb-1 text-center">${t("prob")}</th>
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
        ) : tr ? _truthBlock(`<span class="text-gray-400">${t("no_assists")}</span>`) : ""}
      </div>`;
  }

  // Substitutions
  if ((p.substitutions || []).length) {
    const trSubs = tr && tr.substitutions ? tr.substitutions : null;
    const trSubOff = new Set((trSubs || []).map(s => _normName(s.off)));
    const trSubOn  = new Set((trSubs || []).map(s => _normName(s.on)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("substitutions")}</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">${t("min")}</th>
            <th class="font-normal pb-1 text-center">${t("team")}</th>
            <th class="font-normal pb-1">${t("off_on")}</th>
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
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("cards")}</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">${t("min")}</th>
            <th class="font-normal pb-1">${t("player")}</th>
            <th class="font-normal pb-1 text-center">${t("team")}</th>
            <th class="font-normal pb-1 text-center">${t("card")}</th>
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
          </table>`) : tr ? _truthBlock(`<span class="text-gray-400">${t("no_cards")}</span>`) : ""}
      </div>`;
  }

  // Penalties
  if ((p.penalties || []).length) {
    const trPens = tr && tr.penalties ? tr.penalties : null;
    const trPenTakers = new Set((trPens || []).map(p => _normName(p.taker)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("penalties")}</div>
        <table class="w-full text-xs" style="border-collapse:collapse;">
          <thead><tr class="text-gray-500 text-left">
            <th class="font-normal pb-1 w-10 text-center">${t("min")}</th>
            <th class="font-normal pb-1">${t("taker")}</th>
            <th class="font-normal pb-1 text-center">${t("team")}</th>
            <th class="font-normal pb-1">${t("outcome")}</th>
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
        ) : tr ? _truthBlock(`<span class="text-gray-400">${t("no_penalties")}</span>`) : ""}
      </div>`;
  }

  // Own goals
  if ((p.own_goals || []).length) {
    const trOg = tr && tr.own_goals ? tr.own_goals : null;
    const trOgPlayers = new Set((trOg || []).map(o => _normName(o.player)));
    html += `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("own_goals")}</div>
        <div class="space-y-1 text-xs">
          ${p.own_goals.map(og => {
            const cls = tr ? hitColor(trOgPlayers.has(_normName(og.player))) : "text-gray-200";
            return `<div>${og.minute}′ — <span class="${cls}">${esc(og.player)}</span> ${tTeam(og.team)}</div>`;
          }).join("")}
        </div>
        ${trOg && trOg.length ? _truthBlock(
          trOg.map(og => `<span class="text-gray-200 font-semibold">${esc(og.player)}</span> <span class="text-gray-400">${og.minute}′</span>`).join(" &nbsp;·&nbsp; ")
        ) : tr ? _truthBlock(`<span class="text-gray-400">${t("no_own_goals")}</span>`) : ""}
      </div>`;
  }

  // Stats
  const STAT_LABELS = {
    possession:        t("possession"),
    shots:             t("shots"),
    shots_on_target:   t("shots_on_target"),
    corners:           t("corners"),
    pass_accuracy:     t("pass_accuracy"),
    fouls:             t("fouls"),
    saves:             t("saves"),
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
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("stats")}</div>
        <table class="w-full" style="border-collapse:collapse;">
          <thead><tr class="text-xs">
            <th class="font-normal text-gray-500 text-left pb-1">${t("stat")}</th>
            <th class="font-normal text-gray-400 text-center pb-1 w-10">${t("h")}</th>
            <th style="width:6rem;"></th>
            <th class="font-normal text-gray-400 text-center pb-1 w-10">${t("a")}</th>
            ${trStats ? `<th colspan="3" class="font-normal text-amber-400/70 text-center pb-1">${t("actual")}</th>` : ""}
          </tr></thead>
          <tbody>${statRows}</tbody>
        </table>
      </div>`;
  }

  return html || `<div class="text-gray-500 text-xs">${t("no_details")}</div>`;
}

function renderSourcesList(sources) {
  if (!sources.length) return "";
  const visibleSources = _matchmateMode ? sources.slice(0, 20) : sources;
  const omitted = Math.max(0, sources.length - visibleSources.length);
  return `
    <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("search_sources")}</div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
      ${visibleSources.map(s => {
        const title = esc(s.title || s.url || "");
        const url   = esc(s.url || "");
        const date  = s.accessed_at ? esc(s.accessed_at.slice(0, 10)) : "";
        return `<div class="text-xs leading-snug rounded-lg px-3 py-2" style="background:rgba(255,255,255,.045);">
          <a href="${url}" target="_blank" rel="noopener"
             class="text-blue-400 hover:text-blue-300 underline break-all">${title}</a>
          ${date ? `<span class="text-gray-600 ml-1">${date}</span>` : ""}
        </div>`;
      }).join("")}
    </div>
    ${omitted ? `<div class="mt-2 text-xs text-gray-500">${t("sources_omitted", { count: omitted })}</div>` : ""}
  `;
}

function renderSourcesPanel(idx) {
  const p = _allPreds[idx] || {};
  return renderSourcesList(p.sources || []);
}

function renderDetailsPanel(idx) {
  const p = _allPreds[idx] || {};
  const f = _predFixtures[idx] || {};
  const reasoning = p.reasoning || {};
  const scoreDist = (p.score_dist || []).slice().sort((a, b) => (b.p || 0) - (a.p || 0));
  const wp = p.win_probs || winProbsFromScoreDist(scoreDist) || {};
  const top3 = scoreDist.slice(0, 3);
  const hName = f.home || t("home");
  const aName = f.away || t("away");
  const winProbItems = isMobilePredLayout()
    ? [["home", t("h")], ["draw", t("draw")], ["away", t("a")]]
    : [["home", hName], ["draw", t("draw")], ["away", aName]];
  const hasReason = Object.keys(reasoning).length > 0;

  return `
    <div class="space-y-4">
      ${wp.home != null ? `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("win_probabilities")}</div>
        <div class="win-prob-grid grid grid-cols-3 gap-2 sm:gap-3">
          ${winProbItems.map(([k, label]) => `
            <div class="win-prob-card rounded-lg px-2 sm:px-3 py-2 text-center" style="background:rgba(255,255,255,.06);">
              <div class="win-prob-label text-[10px] text-gray-400 uppercase tracking-wider truncate">${esc(label)}</div>
              <div class="win-prob-value text-base sm:text-lg font-black font-mono text-gray-100">${fmtPct(wp[k])}</div>
            </div>`).join("")}
        </div>
      </div>` : ""}

      ${top3.length ? (() => {
        const allScores = scoreDist.slice(0, 15);
        const maxP = Math.max(...allScores.map(s => s.p || 0));
        return `
      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("score_distribution")}</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
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
          <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("full_reasoning")}</div>
          <div class="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">${esc(reasoning.overall)}</div>
        </div>
      ` : ""}
      ${_renderDetails(p, f)}
      <div class="pt-2 border-t border-white/5">
        <button onclick="toggleDetails(${idx})" class="chip hover:bg-white/15 transition text-xs">${t("hide_detail")}</button>
      </div>
    </div>`;
}

function renderPredCard(p, f, idx, opts = {}) {
  const b          = modelBadge(p.model_id);
  const scoreDist  = (p.score_dist || []).slice().sort((a, b) => (b.p || 0) - (a.p || 0));
  const wp         = p.win_probs || winProbsFromScoreDist(scoreDist) || {};
  const top3       = scoreDist.slice(0, 3);
  const predScore  = p.most_likely_score || (top3[0] ? top3[0].score : null);
  const hName      = f.home || t("home");
  const aName      = f.away || t("away");
  const status     = p.status || "ok";
  const showActualSummary = opts.showActualSummary !== false;
  const extraButtonAttr = opts.isExtra ? ' data-extra-button="details"' : "";
  const extraSourcesButtonAttr = opts.isExtra ? ' data-extra-button="sources"' : "";

  const scoreWinner = outcomeFromScore(predScore, hName, aName);
  const predWinner = winnerFromWinProbs(wp, hName, aName) || scoreWinner;
  const headerHtml = `
      <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-base">${b.emoji}</span>
          <span class="font-bold text-xs sm:text-sm text-white">${esc(fmtModelId(p))}</span>
          <span class="chip chip-${(p.setting || "").toLowerCase()}"
                data-tip="${esc(settingTip(p.setting))}">${esc(p.setting || "")}</span>
        </div>
        ${p.cost_usd != null ? `<span class="text-xs text-gray-600">${t("cost")}: $${(+p.cost_usd).toFixed(3)}</span>` : ""}
      </div>`;

  if (status !== "ok") {
    const failed = status === "failed";
    const label = failed ? t("unavailable") : t("not_run");
    const tone = failed
      ? "color:#fca5a5;border-color:rgba(248,113,113,.28);background:rgba(248,113,113,.08);"
      : "color:#cbd5e1;border-color:rgba(148,163,184,.25);background:rgba(148,163,184,.08);";
    const detail = p.error_summary || (failed ? t("unavailable_detail") : t("not_run_detail"));
    return `
    <div class="card rounded-lg p-3">
      ${headerHtml}
      <div class="rounded-lg px-3 py-2" style="${tone}">
        <div class="text-[10px] uppercase tracking-wider mb-1">${label}</div>
        <div class="text-xs leading-snug">${esc(detail)}</div>
      </div>
    </div>`;
  }

  return `
    <div class="card rounded-lg p-3">

      <!-- Header -->
      ${headerHtml}

      <!-- Minimalist Prediction -->
      ${predWinner || top3.length ? `
      <div class="mb-2">
        <div class="flex items-start gap-3 sm:gap-4 flex-wrap">
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("pred_winner")}</div>
            ${(() => {
              const truthOutcome = f.truth
                ? (f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : t("draw"))
                : null;
              const winnerCorrect = truthOutcome && predWinner && truthOutcome === predWinner;
              const winnerColor = truthOutcome
                ? (winnerCorrect ? "color:#4ade80;" : "color:#f87171;")
                : "color:var(--prediction-primary);";
              return `<div class="text-xl font-black leading-tight" style="${winnerColor}">${esc(predWinner || "—")}</div>`;
            })()}
          </div>
          <div style="width:1px;height:2.15rem;background:var(--prediction-divider);"></div>
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("pred_score")}</div>
            ${(() => {
              const actualScore = f.truth ? f.truth.score : null;
              const scoreCorrect = predScore && actualScore && predScore === actualScore;
              const scoreColor = actualScore
                ? (scoreCorrect ? "color:#4ade80;" : "color:#f87171;")
                : "color:var(--prediction-primary);";
              return `<div class="text-xl font-black leading-tight font-mono whitespace-nowrap" style="${scoreColor}">${esc(predScore ? predScore.replace("-", " - ") : "—")}</div>`;
            })()}
          </div>
          ${showActualSummary && f.truth ? `<div class="ml-auto">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("actual")}</div>
            <div class="text-xl font-black font-mono leading-tight whitespace-nowrap" style="color:#fbbf24;">${esc(f.truth.score.replace("-", " - ") || "—")}</div>
            <div class="text-xs font-mono" style="color:#fbbf2480;">${esc(
              f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : f.truth.result === "draw" ? t("draw") : f.truth.result || "—"
            )}</div>
          </div>` : ""}
        </div>
      </div>
      ` : ""}

      <!-- Buttons -->
      <div class="flex flex-wrap gap-2 mt-1">
        <button id="pred-details-btn-${idx}" onclick="toggleDetails(${idx})"
                class="chip pred-action hover:bg-white/15 transition text-[11px]"${extraButtonAttr}>${t("show_details")}</button>
        ${p.sources && p.sources.length ? `
        <button id="pred-sources-btn-${idx}" onclick="toggleSources(${idx})"
                class="chip pred-action hover:bg-white/15 transition text-[11px]"${extraSourcesButtonAttr} data-source-count="${p.sources.length}">${t("sources", { count: p.sources.length })}</button>` : ""}
      </div>
    </div>`;
}

function renderPredGrid(preds, f, startIdx, groupId, opts = {}) {
  if (!preds.length) return `<div class="text-gray-500 text-sm py-2">${t("no_predictions")}</div>`;
  const mobileFoldTopN = Number(opts.mobileFoldTopN || 0);
  const desktopFoldTopN = Number(opts.desktopFoldTopN || 0);
  const useMobileFold = mobileFoldTopN > 0 && isMobilePredLayout() && preds.length > mobileFoldTopN;
  const useDesktopFold = !isMobilePredLayout() && desktopFoldTopN > 0 && preds.length > desktopFoldTopN;
  const allowFold = opts.allowFold !== false || useMobileFold;
  const indexed = preds.map((p, i) => ({
    pred: p,
    idx: startIdx + i,
    hidden: useMobileFold
      ? i >= mobileFoldTopN
      : useDesktopFold
        ? i >= desktopFoldTopN
        : (allowFold && p.default_visible === false),
  }));
  const hiddenCount = allowFold ? indexed.filter(item => item.hidden).length : 0;
  const visibleItems = allowFold ? indexed.filter(item => !item.hidden) : indexed;
  const hiddenItems = allowFold ? indexed.filter(item => item.hidden) : [];

  const renderRows = (items, hiddenRows) => {
    const rows = [];
    const rowSize = isMobilePredLayout() ? 1 : 2;
    for (let rowStart = 0; rowStart < items.length; rowStart += rowSize) {
      const cards = items.slice(rowStart, rowStart + rowSize).map(item => `
        <div>${renderPredCard(item.pred, f, item.idx, {
          showActualSummary: opts.showActualSummary,
          isExtra: hiddenRows,
        })}</div>
      `).join("");
      rows.push(`
        <div class="${hiddenRows ? "hidden " : ""}space-y-2" data-pred-row="1"${hiddenRows ? ' data-pred-extra-row="1"' : ""}>
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-2">${cards}</div>
          <div class="pred-expanded card rounded-lg p-4 hidden" data-pred-panel="1"></div>
        </div>
      `);
    }
    return rows.join("");
  };

  return `
    <div id="${groupId}" class="pred-grid space-y-2" data-pred-grid="1">
      ${renderRows(visibleItems, false)}
      ${renderRows(hiddenItems, true)}
    </div>
    ${hiddenCount ? `
      <button onclick="togglePredictionGroup('${groupId}', this)"
              class="chip pred-toggle hover:bg-white/15 transition text-xs mt-2"
              data-hidden-count="${hiddenCount}">${showAllModelsText(hiddenCount)}</button>
    ` : ""}`;
}

function renderPredList(preds, f, startIdx, groupId) {
  return renderPredGrid(preds, f, startIdx, groupId, {
    allowFold: true,
    showActualSummary: false,
    desktopFoldTopN: 4,
    mobileFoldTopN: 3,
  });
}

function renderAllPredCards(preds, f, startIdx) {
  return renderPredGrid(preds, f, startIdx, `pred-grid-${startIdx}`, {
    allowFold: false,
    showActualSummary: true,
    mobileFoldTopN: 3,
  });
}

function liveMinuteLabel(live) {
  if (live && live.elapsed != null) return `${live.elapsed}′`;
  return (live && live.status) ? live.status : t("live");
}

function liveScoreLabel(live) {
  const sc = (live && live.score) || {};
  return `${sc.home ?? "?"}-${sc.away ?? "?"}`;
}

function liveTeamName(side, f) {
  if (side === "home") return f.home || t("home");
  if (side === "away") return f.away || t("away");
  return side || "—";
}

function renderLivePredictions(items, f) {
  if (!items || !items.length) return "";
  const hName = f.home || t("home");
  const aName = f.away || t("away");
  return `
    <div class="mb-4">
      <div class="flex items-end justify-between gap-3 mb-2">
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wider">${t("live_predictions")}</div>
          <div class="text-[11px] text-gray-500">${t("live_prediction_note")}</div>
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-2">
        ${items.map(p => {
          const b = modelBadge(p.model_id);
          const live = p.live || {};
          const wp = p.win_probs || {};
          const predWinner = winnerFromWinProbs(wp, hName, aName);
          const score = p.most_likely_score || "—";
          const updated = p.submitted_at ? fmtLocalKickoff(new Date(p.submitted_at)) : "—";
          const scorers = p.scorers || [];
          const sources = p.sources || [];
          const status = p.status || "ok";
          const reasoning = (p.reasoning && p.reasoning.overall) || "";
          if (status !== "ok") {
            return `
              <div class="card rounded-lg p-3">
                <div class="flex items-center justify-between gap-2 mb-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <span>${b.emoji}</span>
                    <span class="font-bold text-xs sm:text-sm text-white truncate">${esc(fmtModelId(p))}</span>
                    <span class="chip chip-live">LIVE</span>
                  </div>
                </div>
                <div class="rounded-lg px-3 py-2" style="color:#fca5a5;border:1px solid rgba(248,113,113,.28);background:rgba(248,113,113,.08);">
                  <div class="text-[10px] uppercase tracking-wider mb-1">${t("unavailable")}</div>
                  <div class="text-xs leading-snug">${esc(p.error_summary || t("unavailable_detail"))}</div>
                </div>
              </div>`;
          }
          return `
            <div class="card rounded-lg p-3">
              <div class="flex items-center justify-between gap-2 mb-2">
                <div class="flex items-center gap-2 min-w-0">
                  <span>${b.emoji}</span>
                  <span class="font-bold text-xs sm:text-sm text-white truncate">${esc(fmtModelId(p))}</span>
                  <span class="chip chip-live">LIVE</span>
                </div>
                ${p.cost_usd != null ? `<span class="text-xs text-gray-600 whitespace-nowrap">${t("cost")}: $${(+p.cost_usd).toFixed(3)}</span>` : ""}
              </div>
              <div class="text-[11px] text-gray-500 mb-2">
                ${esc(t("live_current_snapshot", { score: liveScoreLabel(live), minute: liveMinuteLabel(live) }))}
                <span class="mx-1">·</span>${esc(t("live_updated_at", { time: updated }))}
              </div>
              <div class="grid grid-cols-3 gap-2 mb-3">
                ${[["home", hName], ["draw", t("draw")], ["away", aName]].map(([key, label]) => `
                  <div class="rounded-lg px-2 py-2 text-center" style="background:rgba(255,255,255,.055);">
                    <div class="text-[10px] text-gray-500 uppercase tracking-wider truncate">${esc(label)}</div>
                    <div class="text-lg font-black font-mono text-gray-100">${fmtPct(wp[key])}</div>
                  </div>
                `).join("")}
              </div>
              <div class="flex items-start gap-4 flex-wrap mb-3">
                <div>
                  <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("pred_winner")}</div>
                  <div class="text-lg font-black leading-tight" style="color:var(--prediction-primary);">${esc(predWinner || "—")}</div>
                </div>
                <div style="width:1px;height:2rem;background:var(--prediction-divider);"></div>
                <div>
                  <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("live_final_score")}</div>
                  <div class="text-lg font-black leading-tight font-mono" style="color:var(--prediction-primary);">${esc(String(score).replace("-", " - "))}</div>
                </div>
              </div>
              <div class="mb-3">
                <div class="text-xs text-gray-400 uppercase tracking-wider mb-1">${t("future_scorers")}</div>
                ${scorers.length ? `
                  <div class="flex flex-wrap gap-1.5">
                    ${scorers.map(s => `
                      <span class="chip">
                        ${esc(s.player)}
                        ${s.team ? `<span class="text-gray-500">${esc(liveTeamName(s.team, f))}</span>` : ""}
                        ${s.minute != null ? `<span class="font-mono text-gray-400">${s.minute}′</span>` : ""}
                        ${s.p != null ? `<span class="font-mono text-gray-400">${fmtPct(s.p)}</span>` : ""}
                      </span>
                    `).join("")}
                  </div>` : `<div class="text-xs text-gray-500">${t("no_future_scorers")}</div>`}
              </div>
              ${reasoning ? `<div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">${esc(reasoning)}</div>` : ""}
              ${sources.length ? `
                <details class="mt-3">
                  <summary class="chip hover:bg-white/15 transition text-[11px]">${t("sources", { count: sources.length })}</summary>
                  <div class="mt-2">${renderSourcesList(sources)}</div>
                </details>` : ""}
            </div>`;
        }).join("")}
      </div>
    </div>`;
}

// ---------- Incoming matches -------------------------------------------------

function _renderOneFixture(nm, cardIdx) {
  const f     = nm.fixture;
  const kick  = f.kickoff_utc ? new Date(f.kickoff_utc) : null;
  const cid   = `nm-countdown-${cardIdx}`;
  const preds = nm.predictions || [];
  const livePreds = nm.live_predictions || [];
  const nmStart = registerPreds(preds, f);

  const lv = nm.live;
  const isMatchLive = lv && lv.status && lv.status !== "Match Finished" && lv.status !== "Not Started";

  const agg = { home: 0, draw: 0, away: 0 };
  let nP = 0;
  for (const p of preds) {
    const wp = p.win_probs || winProbsFromScoreDist(p.score_dist || []);
    if (wp && typeof wp.home === "number") {
      agg.home += wp.home; agg.draw += wp.draw; agg.away += wp.away;
      nP++;
    }
  }
  if (nP > 0) { agg.home /= nP; agg.draw /= nP; agg.away /= nP; }

  const centerMiddle = isMatchLive
    ? `<div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-3xl font-black font-mono" style="color:#f87171;">${lv.score ? `${lv.score.home ?? "?"} – ${lv.score.away ?? "?"}` : "?–?"}</div>
       <div class="text-xs font-semibold" style="color:#fca5a5;">${t("live_red")}${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}</div>
       ${renderVenueLocation(f)}`
    : `${kick ? `<div class="text-xs text-gray-300 font-medium mb-1">${fmtLocalKickoff(kick)}</div>` : ""}
       <div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-2xl font-black">${t("vs")}</div>
       ${nP > 0 ? `<div class="text-xs text-gray-400">${t("draw_prob", { pct: fmtPct(agg.draw) })}</div>` : ""}
       <div class="text-xs text-gray-400 mt-1" id="${cid}">${kick ? "" : "—"}</div>
       ${renderVenueLocation(f)}`;

  const html = `
    <div class="card rounded-2xl p-4 sm:p-6">
      <div class="pitch rounded-xl p-3 sm:p-5 mb-4 sm:mb-6">
        <div class="grid grid-cols-3 items-center gap-2">
          <div class="text-center">
            ${f.home_logo ? `<img src="${esc(f.home_logo)}" alt="${esc(f.home)}" class="fixture-logo"/>` : `<div class="text-4xl">🏠</div>`}
            <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(f.home || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">${t("win", { pct: fmtPct(agg.home) })}</div>` : ""}
          </div>
          <div class="text-center">${centerMiddle}</div>
          <div class="text-center">
            ${f.away_logo ? `<img src="${esc(f.away_logo)}" alt="${esc(f.away)}" class="fixture-logo"/>` : `<div class="text-4xl">🛫</div>`}
            <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(f.away || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">${t("win", { pct: fmtPct(agg.away) })}</div>` : ""}
          </div>
        </div>
      </div>
      ${renderLivePredictions(livePreds, f)}
      ${preds.length === 0
        ? (livePreds.length ? "" : `<div class="text-gray-400 text-sm">${t("no_model_predictions")}</div>`)
        : renderAllPredCards(preds, f, nmStart)}
      ${f.data_warning ? `<div class="mt-3 text-xs text-amber-300/80">${esc(f.data_warning)}</div>` : ""}
    </div>`;

  // Start countdown timer after DOM insertion (called by caller)
  return { html, kick, cid };
}

function renderIncomingMatches(matches) {
  const el = document.getElementById("next-container");
  _countdownIntervals.forEach(clearInterval);
  _countdownIntervals = [];
  if (!matches || matches.length === 0) {
    el.innerHTML = `<div class="text-gray-400">${t("no_fixtures")}</div>`;
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
      if (diff <= 0) { el2.textContent = t("live"); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el2.textContent = t("kickoff_in", { h, m, s });
    };
    tick();
    _countdownIntervals.push(setInterval(tick, 1000));
  }
}

// ---------- Leaderboard ------------------------------------------------------

let chartInstance = null;

function leaderboardResultAcc(row) {
  return row?.winner_acc == null ? null : Number(row.winner_acc);
}

function formatWinnerAcc(row) {
  const acc = leaderboardResultAcc(row);
  if (acc == null) return "—";
  const detail = row.winner_correct != null && row.winner_total != null
    ? ` (${row.winner_correct}/${row.winner_total})`
    : "";
  return `${(acc * 100).toFixed(1)}%${detail}`;
}

function sortLeaderboardRows(rows) {
  const sorted = (rows || []).slice();
  sorted.sort((a, b) => {
    if (_leaderboardSort === "result") {
      const accA = leaderboardResultAcc(a);
      const accB = leaderboardResultAcc(b);
      const primary = (accB ?? -1) - (accA ?? -1);
      if (primary) return primary;
      const total = (b.winner_total || 0) - (a.winner_total || 0);
      if (total) return total;
    }
    const composite = (b.mean || 0) - (a.mean || 0);
    if (composite) return composite;
    return String(fmtModelId(a)).localeCompare(String(fmtModelId(b)));
  });
  return sorted;
}

function leaderboardMetric(row, kind) {
  if (kind === "result") {
    const acc = leaderboardResultAcc(row);
    return {
      label: t("result_accuracy"),
      display: formatWinnerAcc(row),
      barWidth: acc == null ? 0 : Math.max(0, Math.min(100, acc * 100)),
    };
  }
  return {
    label: t("composite_score"),
    display: fmt2(row.mean),
    barWidth: Math.max(0, Math.min(100, Number(row.mean) || 0)),
  };
}

function updateLeaderboardSortButton() {
  const btn = document.getElementById("leaderboard-sort-toggle");
  if (!btn) return;
  btn.textContent = t(_leaderboardSort === "result" ? "leaderboard_sort_result" : "leaderboard_sort_composite");
  btn.setAttribute("title", t(_leaderboardSort === "result" ? "leaderboard_sort_to_composite" : "leaderboard_sort_to_result"));
  btn.setAttribute("aria-label", btn.getAttribute("title"));
}

function toggleLeaderboardSort() {
  _leaderboardSort = _leaderboardSort === "result" ? "composite" : "result";
  updateLeaderboardSortButton();
  renderLeaderboard((_siteData && _siteData.leaderboard) || { main: [] }, _activeLeaderboardView);
}

function renderLeaderboard(lb, view) {
  const el   = document.getElementById("leaderboard-container");
  const rows = sortLeaderboardRows(lb.main || []);
  if (rows.length === 0) {
    el.innerHTML = `<div class="text-gray-400 text-sm">${t("no_graded")}</div>`;
    return;
  }

  if (view === "main") {
    const primaryKind = _leaderboardSort;
    const primaryLabel = leaderboardMetric(rows[0], primaryKind).label;
    el.innerHTML = `
      <div class="overflow-x-auto">
        <table class="leaderboard-table w-full text-sm">
          <thead class="text-gray-400 text-xs uppercase tracking-wider">
            <tr>
              <th class="leaderboard-rank-cell text-left py-2 px-3 w-12">#</th>
              <th class="text-left py-2 px-3">${t("model")}</th>
              <th class="leaderboard-score-cell text-right py-2 px-3">${primaryLabel}</th>
              <th class="leaderboard-mobile-hide text-right py-2 px-3">${t("games")}</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r, i) => {
              const b = modelBadge(r.model_id);
              const medal = i === 0 ? "rank-1" : i === 1 ? "rank-2" : i === 2 ? "rank-3" : "";
              const primary = leaderboardMetric(r, primaryKind);
              const settings = Object.keys((lb.by_model_setting || {})[r.model_id] || {}).sort();
              const settingBadges = settings.map(s =>
                `<span class="chip chip-${s.toLowerCase()}"
                       data-tip="${esc(settingTip(s))}">${esc(s)}</span>`
              ).join(" ");
              return `
                <tr class="border-t border-white/5 hover:bg-white/5 transition">
                  <td class="leaderboard-rank-cell py-2 px-3"><span class="rank-medal ${medal}">${i + 1}</span></td>
                  <td class="py-2 px-3">
                    <div class="leaderboard-model-row flex items-center gap-2">
                      <span class="shrink-0">${b.emoji}</span>
                      <span class="leaderboard-model-name font-bold text-white">${esc(fmtModelId(r))}</span>
                      <span class="leaderboard-setting-badges inline-flex items-center gap-1 flex-wrap">${settingBadges}</span>
                    </div>
                  </td>
                  <td class="leaderboard-score-cell py-2 px-3 text-right font-mono">
                    <div class="leaderboard-metric">
                      <div class="leaderboard-score-bar bar w-28"><div class="bar-fill" style="width:${primary.barWidth}%"></div></div>
                      <span class="leaderboard-metric-value font-bold text-white">${primary.display}</span>
                    </div>
                  </td>
                  <td class="leaderboard-mobile-hide py-2 px-3 text-right text-gray-500">${r.n}</td>
                </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
  } else if (view === "layers") {
    el.innerHTML = `<canvas id="layersChart" height="220"></canvas>`;
    const layers  = ["T1_core_result", "T2_player_level", "T3_event_level", "T4_tactics_stats", "T5_tournament_macro"];
    const labels  = [t("layer_t1"), t("layer_t2"), t("layer_t3"), t("layer_t4"), t("layer_t5")];
    const palette = ["#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#f59e0b", "#14b8a6", "#ef4444", "#eab308", "#64748b"];
    const light = _theme === "light";
    const datasets = rows.slice(0, 9).map((r, i) => ({
      label: fmtModelId(r),
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
          angleLines: { color: light ? "rgba(15,23,42,.14)" : "rgba(255,255,255,.12)" },
          grid:        { color: light ? "rgba(15,23,42,.1)" : "rgba(255,255,255,.08)" },
          pointLabels: { color: light ? "#334155" : "#cbd5e1", font: { size: 11 } },
          ticks:       { backdropColor: "transparent", color: light ? "#64748b" : "#64748b" },
        }},
        plugins: { legend: { labels: { color: light ? "#334155" : "#cbd5e1", boxWidth: 12 } } },
      },
    });
  }
}

function syncLeaderboardTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === _activeLeaderboardView);
  });
}

function wireTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.onclick = () => {
      _activeLeaderboardView = btn.dataset.view || "main";
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderLeaderboard((_siteData && _siteData.leaderboard) || { main: [] }, _activeLeaderboardView);
    };
  });
  syncLeaderboardTabs();
}

// ---------- History ----------------------------------------------------------

function renderHistory(rows) {
  const el = document.getElementById("history-container");
  if (!rows || rows.length === 0) {
    el.innerHTML = `<div class="text-gray-400 text-sm">${t("no_graded")}</div>`;
    return;
  }
  el.innerHTML = rows.map((r, rowIdx) => {
    const date  = r.kickoff_utc ? new Date(r.kickoff_utc).toISOString().slice(0, 10) : "";
    const preds = r.predictions || [];
    const lv    = r.live;
    // truth data (r.result) is authoritative — if it exists the match is done
    const isLive = !r.result && lv && lv.status && lv.status !== "Match Finished" && lv.status !== "Not Started";

    // Skip live matches — they belong in Incoming Matches
    if (isLive) return "";

    const liveScore = isLive && lv.score ? `${lv.score.home ?? "?"} – ${lv.score.away ?? "?"}` : null;
    const scoreHtml = isLive
      ? `<div class="text-3xl font-black font-mono" style="color:#f87171;">${esc(liveScore || "?–?")}</div>
         <div class="text-xs font-semibold mt-0.5" style="color:#fca5a5;">${t("live_red")}${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}</div>`
      : `<div class="text-3xl font-black font-mono" style="color:#fbbf24;">${esc((r.result || "—").replace("-", " – "))}</div>`;

    const hStart = registerPreds(preds, r);

    const predCards = renderPredList(preds, r, hStart, `pred-group-history-${hStart}`);
    const collapseOnMobile = isMobilePredLayout() && rowIdx >= 3;
    const mobileScoreboard = collapseOnMobile ? `
          <div class="mobile-history-scoreboard mt-3 md:hidden">
            <div class="grid grid-cols-3 items-center gap-2">
              <div class="text-center min-w-0">
                ${r.home_logo ? `<img src="${esc(r.home_logo)}" alt="${esc(r.home)}" class="fixture-logo fixture-logo-sm"/>` : `<div class="text-2xl">🏠</div>`}
                <div class="team-name text-xs font-bold leading-tight">${esc(r.home || "?")}</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-black font-mono" style="color:#fbbf24;">${esc((r.result || "—").replace("-", " – "))}</div>
                <div class="mt-1 inline-flex chip text-[10px]">${t("show_predictions")}</div>
              </div>
              <div class="text-center min-w-0">
                ${r.away_logo ? `<img src="${esc(r.away_logo)}" alt="${esc(r.away)}" class="fixture-logo fixture-logo-sm"/>` : `<div class="text-2xl">🛫</div>`}
                <div class="team-name text-xs font-bold leading-tight">${esc(r.away || "?")}</div>
              </div>
            </div>
          </div>` : "";
    const fullPitch = `
          <div class="pitch rounded-xl p-3 sm:p-4 mb-4">
            <div class="grid grid-cols-3 items-center gap-2">
              <div class="text-center">
                ${r.home_logo ? `<img src="${esc(r.home_logo)}" alt="${esc(r.home)}" class="fixture-logo"/>` : `<div class="text-3xl">🏠</div>`}
                <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(r.home || "?")}</div>
              </div>
              <div class="text-center">
                ${r.kickoff_utc ? `<div class="text-xs text-gray-300 font-medium mb-1">${fmtLocalKickoff(new Date(r.kickoff_utc))}</div>` : ""}
                ${r.competition ? `<div class="text-[10px] text-gray-400 mb-1">${esc(r.competition)}${r.stage ? ` · ${esc(r.stage)}` : ""}</div>` : ""}
                ${scoreHtml}
                ${renderVenueLocation(r)}
              </div>
              <div class="text-center">
                ${r.away_logo ? `<img src="${esc(r.away_logo)}" alt="${esc(r.away)}" class="fixture-logo"/>` : `<div class="text-3xl">🛫</div>`}
                <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(r.away || "?")}</div>
              </div>
            </div>
          </div>`;

    return `
      <details${collapseOnMobile ? "" : " open"} class="card rounded-xl p-4 col-span-2">
        <summary class="cursor-pointer select-none">
          <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400">${esc(date)} · ${esc(r.competition || "")} ${esc(r.stage || "")}</div>
            <div class="font-semibold text-lg">${esc(r.home || "?")} <span class="text-gray-500 mx-2">${t("vs")}</span> ${esc(r.away || "?")}</div>
          </div>
          </div>
          ${mobileScoreboard}
        </summary>
        <div class="mt-4 space-y-3">
          ${collapseOnMobile ? "" : fullPitch}
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

function renderSiteData() {
  if (!_siteData) return;
  _allPreds = [];
  _predFixtures = [];
  renderIncomingMatches(_siteData.incoming_matches || []);
  syncLeaderboardTabs();
  renderLeaderboard(_siteData.leaderboard || { main: [] }, _activeLeaderboardView);
  requestAnimationFrame(() => renderHistory(_siteData.history || []));
}

function setupResponsivePredictions() {
  _mobilePredView = isMobilePredLayout();
  const media = window.matchMedia("(max-width: 767px)");
  const onChange = () => {
    const nextMobile = isMobilePredLayout();
    if (nextMobile === _mobilePredView) return;
    _mobilePredView = nextMobile;
    renderSiteData();
  };
  if (media.addEventListener) media.addEventListener("change", onChange);
  else media.addListener(onChange);
}

async function fetchDataForLanguage() {
  const preferred = _lang === "en" ? "data.en.json" : "data.zh.json";
  const fallbacks = _lang === "en" ? ["data.en.json", "data.json"] : ["data.zh.json", "data.json"];
  let lastError = null;
  for (const url of [...new Set(fallbacks)]) {
    try {
      const resp = await fetch(url, { cache: "no-cache" });
      if (!resp.ok) throw new Error(`${url}: ${resp.status}`);
      return await resp.json();
    } catch (err) {
      lastError = err;
      if (url === preferred) continue;
    }
  }
  throw lastError || new Error("data load failed");
}

async function loadSiteData() {
  try {
    _siteData = await fetchDataForLanguage();
  } catch (e) {
    document.getElementById("next-container").innerHTML =
      `<div class="text-rose-300 text-sm">${t("load_error")}</div>`;
    console.error(e);
    return;
  }
  // document.getElementById("generated-at").textContent = "Last updated " + fmtTimestamp(data.generated_at);
  renderSiteData();
}

async function main() {
  setTheme(_theme, { updateUrl: false });
  applyStaticI18n();
  buildReasoningModal();
  wireTabs();
  setupResponsivePredictions();
  await loadSiteData();
}

main();
