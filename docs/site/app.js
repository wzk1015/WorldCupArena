// WorldCupArena site — fetches language-specific data JSON written by src.leaderboard.build_site
// and renders everything client-side.

const fmtPct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const fmt2   = (x) => (x == null ? "—" : (+x).toFixed(2));
const esc    = (s) => String(s ?? "").replace(/[<>&"']/g, c =>
  ({ "<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;" }[c]));

function renderMarkdownInline(s) {
  const codeBlocks = [];
  const protectedText = esc(s).replace(/`([^`]+)`/g, (_, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<code class="px-1 py-0.5 rounded bg-black/30 text-gray-100">${code}</code>`);
    return `\uE000${idx}\uE000`;
  });
  return protectedText
    .replace(/\*\*([^*]+)\*\*/g, "<strong class=\"font-bold text-gray-100\">$1</strong>")
    .replace(/__([^_]+)__/g, "<strong class=\"font-bold text-gray-100\">$1</strong>")
    .replace(/(^|[^\*])\*([^\*]+)\*/g, '$1<em class="italic text-gray-100">$2</em>')
    .replace(/\uE000(\d+)\uE000/g, (_, idx) => codeBlocks[Number(idx)] || "");
}

function renderMarkdownText(text) {
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let paragraph = [];
  let listType = "";

  const flushParagraph = () => {
    if (!paragraph.length) return;
    out.push(`<p class="my-2">${paragraph.map(renderMarkdownInline).join("<br>")}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!listType) return;
    out.push(`</${listType}>`);
    listType = "";
  };
  const openList = (type) => {
    flushParagraph();
    if (listType && listType !== type) flushList();
    if (!listType) {
      const cls = type === "ol"
        ? "list-decimal pl-5 my-2 space-y-1"
        : "list-disc pl-5 my-2 space-y-1";
      out.push(`<${type} class="${cls}">`);
      listType = type;
    }
  };

  for (const line of lines) {
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = line.match(/^\s{0,3}(#{1,4})\s+(.+?)\s*$/);
    if (heading) {
      flushParagraph();
      flushList();
      const levelClass = heading[1].length <= 2
        ? "text-sm font-black text-white mt-3 mb-1"
        : "text-xs font-bold text-gray-100 mt-3 mb-1";
      out.push(`<div class="${levelClass}">${renderMarkdownInline(heading[2])}</div>`);
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      openList("ol");
      out.push(`<li>${renderMarkdownInline(ordered[1])}</li>`);
      continue;
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    if (unordered) {
      openList("ul");
      out.push(`<li>${renderMarkdownInline(unordered[1])}</li>`);
      continue;
    }

    const quote = line.match(/^\s*>\s+(.+)$/);
    if (quote) {
      flushParagraph();
      flushList();
      out.push(`<blockquote class="my-2 pl-3 border-l border-white/20 text-gray-300">${renderMarkdownInline(quote[1])}</blockquote>`);
      continue;
    }

    flushList();
    paragraph.push(line.trimEnd());
  }

  flushParagraph();
  flushList();
  return out.join("");
}

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
    mobile_toc: "目录",
    hero_tagline: "AI<span class=\"gradient-text\">预测足球比分</span>",
    author_html: "作者 <a class=\"underline hover:text-white\" href=\"https://www.wzk.plus\" target=\"_blank\">Zhaokai Wang</a> · <a class=\"underline hover:text-white\" href=\"mailto:zhaokaiwang99@gmail.com\">zhaokaiwang99@gmail.com</a>",
    section_incoming: "🔮 即将进行的比赛",
    section_tournament: "🏟️ 完整赛事预测",
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
    reasoning_expand: "展开",
    reasoning_collapse: "收起",
    full_reasoning_suffix: "完整推理",
    no_reasoning: "暂无推理内容。",
    reasoning_overall: "整体分析",
    reasoning_market_odds: "赔率与市场先验",
    reasoning_lineup_analysis: "阵容分析",
    reasoning_tactical_analysis: "战术分析",
    reasoning_h2h_recent_form: "历史交手与近期战绩",
    reasoning_player_matchups: "球员对位",
    reasoning_injuries_availability: "伤停与可用性",
    reasoning_upset_draw_blowout_cases: "爆冷/平局/大胜路径",
    reasoning_score_result_rationale: "比分与结果逻辑",
    reasoning_t1: "T1 · 赛果与比分",
    reasoning_t2: "T2 · 球员与阵容",
    reasoning_t3: "T3 · 事件与时间线",
    reasoning_t4: "T4 · 比赛数据",
    draw: "平局",
    draw_winner_label: "🤝 平局",
    home: "主队",
    away: "客队",
    substitute: "替补",
    actual: "实际",
    event_timeline: "事件时间轴",
    predicted_timeline: "预测事件时间轴",
    actual_timeline: "实际比赛进程",
    no_timeline_events: "暂无事件时间轴",
    unspecified_goal: "未指定进球",
    assist_prefix: "助攻",
    penalty_goal: "点球",
    penalty_saved: "点球被扑",
    penalty_missed: "点球射失",
    own_goal_label: "乌龙球",
    yellow_card: "黄牌",
    red_card: "红牌",
    second_yellow_card: "两黄变红",
    substitution_event: "换人",
    key_event: "关键事件",
    key_event_big_chance: "绝佳机会",
    key_event_chance: "机会",
    key_event_injury: "伤病",
    key_event_missed_chance: "错失机会",
    key_event_momentum: "走势变化",
    key_event_save: "扑救",
    key_event_set_piece: "定位球",
    key_event_shot: "射门",
    key_event_territory: "场面压制",
    key_event_transition: "转换进攻",
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
    full_reasoning: "📖 完整推理",
    hide_detail: "🔼 收起详情",
    show_details: "👇 展开完整分析",
    show_prematch_prediction: "展开赛前预测",
    hide_prematch_prediction: "收起赛前预测",
    show_live_prediction: "展开实时预测",
    hide_live_prediction: "收起实时预测",
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
    prematch_prediction: "赛前预测",
    latest_live_prediction: "最新实时预测",
    latest_live_prediction_minute: "最新实时预测（第{minute}分钟）",
    live_prediction_history: "实时预测历史",
    live_history_minute_prefix: "第{minute}分钟：",
    live_history_prematch_prefix: "赛前：",
    live_history_item: "{time} · {basis} · 预测 {score}（{winner}）",
    live_predictions: "赛中实时预测",
    live_prediction_note: "赛中预测不计入排行榜",
    live_current_snapshot: "基于 {score} · {minute}",
    live_current_state: "基于{state}",
    live_current_score_state: "基于当前比分{score}",
    live_updated_at: "更新于 {time}",
    live_match_minute: "比赛第 {minute} 分钟",
    live_pre_match: "赛前",
    live_unknown_state: "状态未知",
    live_final_score: "最可能最终比分",
    future_scorers: "后续进球球员",
    no_future_scorers: "暂无后续进球预测",
    vs: "VS",
    win: "胜 {pct}",
    draw_prob: "平局 {pct}",
    no_model_predictions: "暂无模型预测（通常开赛前 24 小时运行）。",
    no_fixtures: "未来 3 天暂无赛程。",
    no_tournament_predictions: "暂无完整赛事预测；运行 tournament_predict 后会显示在这里。",
    tournament_champion: "预测冠军",
    tournament_runner_up: "亚军",
    tournament_third_place: "季军",
    tournament_show_path: "展开完整预测",
    tournament_hide_path: "收起完整预测",
    tournament_group_stage: "小组赛比分与进球者",
    tournament_standings: "小组积分榜",
    tournament_knockout: "淘汰赛路径",
    tournament_top_scorers: "射手榜",
    tournament_group: "小组 {group}",
    tournament_pts: "积分",
    tournament_gd: "净胜球",
    tournament_gf: "进球",
    tournament_ga: "失球",
    tournament_rank: "排名",
    tournament_goals: "进球",
    tournament_no_scorers: "无进球者",
    tournament_scorers_label: "进球者",
    tournament_penalty_shootout: "点球大战",
    tournament_reasoning: "预测说明",
    tournament_stage_R32: "1/16决赛",
    tournament_stage_R16: "1/8决赛",
    tournament_stage_QF: "1/4决赛",
    tournament_stage_SF: "半决赛",
    tournament_stage_THIRD_PLACE: "季军赛",
    tournament_stage_FINAL: "决赛",
    tournament_bracket_champion: "冠军",
    live: "🟢 进行中",
    live_red: "🔴 进行中",
    awaiting_result: "赛果同步中",
    kickoff_in: "开赛倒计时 {h}小时 {m}分 {s}秒",
    no_graded: "暂无已评分比赛。",
    model: "模型",
    composite_score: "综合分",
    result_accuracy: "赛果准确率",
    leaderboard_sort_result: "排序：赛果准确率",
    leaderboard_sort_composite: "排序：综合分",
    leaderboard_sort_to_result: "切换为赛果准确率排序",
    leaderboard_sort_to_composite: "切换为综合分排序",
    leaderboard_scope_all: "全程",
    leaderboard_scope_knockout: "淘汰赛",
    login_with_logto: "登录",
    logged_in_as: "已登录：{name}",
    user_prediction_title: "我的预测",
    user_prediction_guest: "登录后保存到账号；当前预览会暂存在本机。",
    user_prediction_result: "赛果",
    user_prediction_score: "比分",
    user_prediction_optional_score: "预测比分",
    user_prediction_hide_score: "不预测比分",
    user_prediction_invalid_result: "请选择胜平负",
    user_prediction_home_win: "{team}胜",
    user_prediction_draw: "平局",
    user_prediction_away_win: "{team}胜",
    user_prediction_save: "保存预测",
    user_prediction_update: "修改预测",
    user_prediction_saved: "已保存",
    user_prediction_saving: "保存中…",
    user_prediction_local_saved: "后端未连接，已暂存在本机",
    user_prediction_invalid_score: "请填写有效比分",
    user_prediction_locked: "已开赛，预测已锁定",
    user_prediction_history_title: "我的预测",
    user_prediction_no_history: "这场没有你的预测",
    user_prediction_correct_result: "赛果正确",
    user_prediction_wrong_result: "赛果未中",
    user_prediction_exact_score: "比分命中",
    user_prediction_wrong_score: "比分未中",
    user_leaderboard_name: "我的预测",
    user_leaderboard_exact: "比分 {correct}/{total}",
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
    mobile_toc: "Menu",
    hero_tagline: "AI <span class=\"gradient-text\">Football Score Prediction</span>",
    author_html: "by <a class=\"underline hover:text-white\" href=\"https://www.wzk.plus\" target=\"_blank\">Zhaokai Wang</a> · <a class=\"underline hover:text-white\" href=\"mailto:zhaokaiwang99@gmail.com\">zhaokaiwang99@gmail.com</a>",
    section_incoming: "🔮 Incoming Matches",
    section_tournament: "🏟️ Full Tournament Predictions",
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
    reasoning_expand: "Expand",
    reasoning_collapse: "Collapse",
    full_reasoning_suffix: "Full Reasoning",
    no_reasoning: "No reasoning available.",
    reasoning_overall: "Overall Analysis",
    reasoning_market_odds: "Odds & Market Prior",
    reasoning_lineup_analysis: "Lineup Analysis",
    reasoning_tactical_analysis: "Tactical Analysis",
    reasoning_h2h_recent_form: "H2H & Recent Form",
    reasoning_player_matchups: "Player Matchups",
    reasoning_injuries_availability: "Injuries & Availability",
    reasoning_upset_draw_blowout_cases: "Upset / Draw / Blowout Paths",
    reasoning_score_result_rationale: "Score & Result Logic",
    reasoning_t1: "T1 · Result & Score",
    reasoning_t2: "T2 · Players & Lineups",
    reasoning_t3: "T3 · Events & Timeline",
    reasoning_t4: "T4 · Match Statistics",
    draw: "Draw",
    draw_winner_label: "🤝 Draw",
    home: "Home",
    away: "Away",
    substitute: "Sub",
    actual: "Actual",
    event_timeline: "Event Timeline",
    predicted_timeline: "Predicted Event Timeline",
    actual_timeline: "Actual Match Timeline",
    no_timeline_events: "No timeline events available.",
    unspecified_goal: "Unspecified goal",
    assist_prefix: "Assist",
    penalty_goal: "Penalty",
    penalty_saved: "Penalty saved",
    penalty_missed: "Penalty missed",
    own_goal_label: "Own goal",
    yellow_card: "Yellow card",
    red_card: "Red card",
    second_yellow_card: "Second yellow",
    substitution_event: "Substitution",
    key_event: "Key event",
    key_event_big_chance: "Big chance",
    key_event_chance: "Chance",
    key_event_injury: "Injury",
    key_event_missed_chance: "Missed chance",
    key_event_momentum: "Momentum shift",
    key_event_save: "Save",
    key_event_set_piece: "Set piece",
    key_event_shot: "Shot",
    key_event_territory: "Territory",
    key_event_transition: "Transition attack",
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
    full_reasoning: "📖 Full Reasoning",
    hide_detail: "🔼 Hide Detail",
    show_details: "👇 Show Full AI Analysis",
    show_prematch_prediction: "Show pre-match prediction",
    hide_prematch_prediction: "Hide pre-match prediction",
    show_live_prediction: "Show live prediction",
    hide_live_prediction: "Hide live prediction",
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
    prematch_prediction: "Pre-Match Prediction",
    latest_live_prediction: "Latest In-Play Prediction",
    latest_live_prediction_minute: "Latest In-Play Prediction ({minute}′)",
    live_prediction_history: "In-Play Prediction History",
    live_history_minute_prefix: "{minute}′: ",
    live_history_prematch_prefix: "Pre-match: ",
    live_history_item: "{time} · {basis} · predicts {score} ({winner})",
    live_predictions: "In-Play Predictions",
    live_prediction_note: "In-play predictions are not counted in the leaderboard",
    live_current_snapshot: "Based on {score} · {minute}",
    live_current_state: "Based on {state}",
    live_current_score_state: "Based on current score {score}",
    live_updated_at: "Updated {time}",
    live_match_minute: "Match minute {minute}",
    live_pre_match: "Pre-match",
    live_unknown_state: "State unknown",
    live_final_score: "Most Likely Final Score",
    future_scorers: "Future Scorers",
    no_future_scorers: "No future scorers predicted",
    vs: "VS",
    win: "win {pct}",
    draw_prob: "draw {pct}",
    no_model_predictions: "No model predictions yet (runs 24 h before kickoff).",
    no_fixtures: "No fixtures scheduled in the next 3 days.",
    no_tournament_predictions: "No full-tournament predictions yet; run tournament_predict to populate this section.",
    tournament_champion: "Predicted Champion",
    tournament_runner_up: "Runner-up",
    tournament_third_place: "Third place",
    tournament_show_path: "Show full prediction",
    tournament_hide_path: "Hide full prediction",
    tournament_group_stage: "Group Match Scores & Scorers",
    tournament_standings: "Group Standings",
    tournament_knockout: "Knockout Path",
    tournament_top_scorers: "Top Scorers",
    tournament_group: "Group {group}",
    tournament_pts: "Pts",
    tournament_gd: "GD",
    tournament_gf: "GF",
    tournament_ga: "GA",
    tournament_rank: "Rank",
    tournament_goals: "Goals",
    tournament_no_scorers: "No scorers",
    tournament_scorers_label: "Scorers",
    tournament_penalty_shootout: "Penalties",
    tournament_reasoning: "Prediction Notes",
    tournament_stage_R32: "Round of 32",
    tournament_stage_R16: "Round of 16",
    tournament_stage_QF: "Quarterfinals",
    tournament_stage_SF: "Semifinals",
    tournament_stage_THIRD_PLACE: "Third-place Match",
    tournament_stage_FINAL: "Final",
    tournament_bracket_champion: "Champion",
    live: "🟢 Live",
    live_red: "🔴 LIVE",
    awaiting_result: "Awaiting result sync",
    kickoff_in: "kickoff in {h}h {m}m {s}s",
    no_graded: "No graded fixtures yet.",
    model: "Model",
    composite_score: "Composite Score",
    result_accuracy: "Result Accuracy",
    leaderboard_sort_result: "Sort: Result Accuracy",
    leaderboard_sort_composite: "Sort: Composite Score",
    leaderboard_sort_to_result: "Switch to result accuracy sorting",
    leaderboard_sort_to_composite: "Switch to composite score sorting",
    leaderboard_scope_all: "Overall",
    leaderboard_scope_knockout: "Knockout",
    login_with_logto: "Log in",
    logged_in_as: "Signed in: {name}",
    user_prediction_title: "My Prediction",
    user_prediction_guest: "Sign in to save to your account; local preview is stored on this device.",
    user_prediction_result: "Result",
    user_prediction_score: "Score",
    user_prediction_optional_score: "Predict score",
    user_prediction_hide_score: "Skip score",
    user_prediction_invalid_result: "Choose a result",
    user_prediction_home_win: "{team} win",
    user_prediction_draw: "Draw",
    user_prediction_away_win: "{team} win",
    user_prediction_save: "Save prediction",
    user_prediction_update: "Update prediction",
    user_prediction_saved: "Saved",
    user_prediction_saving: "Saving…",
    user_prediction_local_saved: "Backend not connected; saved locally",
    user_prediction_invalid_score: "Enter a valid score",
    user_prediction_locked: "Kickoff passed; prediction locked",
    user_prediction_history_title: "My Prediction",
    user_prediction_no_history: "No prediction for this match",
    user_prediction_correct_result: "Correct result",
    user_prediction_wrong_result: "Wrong result",
    user_prediction_exact_score: "Exact score",
    user_prediction_wrong_score: "Score missed",
    user_leaderboard_name: "My Prediction",
    user_leaderboard_exact: "Score {correct}/{total}",
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

function initialPredictionCardsPerRow() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("cards_per_row") || params.get("prediction_cards_per_row");
  const value = Number.parseInt(raw || "", 10);
  if (!Number.isFinite(value)) return 2;
  return Math.max(1, Math.min(4, value));
}

const _matchmateMode = initialMatchMateMode();
let _lang = _matchmateMode ? "zh" : (localStorage.getItem("wca_lang") === "en" ? "en" : "zh");
let _theme = initialTheme();
let _siteData = null;
let _activeLeaderboardView = "main";
let _leaderboardSort = "result";
let _leaderboardScope = "all";   // "all" | "knockout" — sample-set slice, defaults to overall
let _countdownIntervals = [];
let _mobilePredView = null;

const PREDICTION_CARDS_PER_ROW = initialPredictionCardsPerRow();

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

function mobileTocMatchLabel(match) {
  const home = match?.home || "?";
  const away = match?.away || "?";
  const date = match?.kickoff_utc ? `${new Date(match.kickoff_utc).toISOString().slice(5, 10)} · ` : "";
  return `${date}${home} ${t("vs")} ${away}`;
}

function closeMobileToc() {
  const panel = document.getElementById("mobile-toc-panel");
  const toggle = document.getElementById("mobile-toc-toggle");
  if (panel) {
    panel.hidden = true;
    panel.classList.add("hidden");
  }
  if (toggle) toggle.setAttribute("aria-expanded", "false");
}

function toggleMobileToc(event) {
  if (event) event.stopPropagation();
  const panel = document.getElementById("mobile-toc-panel");
  const toggle = document.getElementById("mobile-toc-toggle");
  if (!panel) return;
  const nextOpen = panel.hidden || panel.classList.contains("hidden");
  panel.hidden = !nextOpen;
  panel.classList.toggle("hidden", !nextOpen);
  if (toggle) toggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
}

function jumpToMobileTocTarget(id) {
  const target = document.getElementById(id);
  if (target && target.tagName === "DETAILS") target.open = true;
  if (target) {
    requestAnimationFrame(() => target.scrollIntoView({ behavior: "smooth", block: "start" }));
  }
  closeMobileToc();
}

function renderMobileToc() {
  const panel = document.getElementById("mobile-toc-panel");
  if (!panel) return;
  const incoming = (_siteData?.incoming_matches || [])
    .map((item, idx) => ({ id: `incoming-match-${idx}`, label: mobileTocMatchLabel(item.fixture || {}) }));
  const history = (_siteData?.history || [])
    .map((item, idx) => {
      const lv = item.live;
      const isLive = !item.result && lv && lv.status && lv.status !== "Match Finished" && lv.status !== "Not Started";
      return isLive ? null : { id: `history-match-${idx}`, label: mobileTocMatchLabel(item) };
    })
    .filter(Boolean);
  const link = (href, label) => `<a href="${href}" class="mobile-toc-link" onclick="closeMobileToc()">${esc(label)}</a>`;
  const sub = (id, label) => `<a href="#${id}" class="mobile-toc-sub" onclick="jumpToMobileTocTarget(${jsArg(id)})">${esc(label)}</a>`;
  panel.innerHTML = `
    ${link("#next", t("section_incoming"))}
    ${incoming.map(item => sub(item.id, item.label)).join("")}
    ${link("#tournament", t("section_tournament"))}
    ${link("#leaderboard", t("section_leaderboard"))}
    ${link("#history", t("section_history"))}
    ${history.map(item => sub(item.id, item.label)).join("")}
  `;
  closeMobileToc();
}

function setupMobileToc() {
  const toc = document.getElementById("mobile-toc");
  if (!toc) return;
  toc.addEventListener("click", event => event.stopPropagation());
  document.addEventListener("click", closeMobileToc);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeMobileToc();
  });
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
  updateUserAuthButton();
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
    renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
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

const VENUE_ZH = {
  "Estadio Azteca": "阿兹特克体育场",
  "Estadio Akron": "阿克伦体育场",
  "BMO Field": "BMO球场",
  "SoFi Stadium": "SoFi体育场",
  "Gillette Stadium": "吉列体育场",
  "BC Place": "BC体育馆",
  "MetLife Stadium": "大都会人寿体育场",
  "Levi's Stadium": "李维斯体育场",
  "NRG Stadium": "NRG体育场",
  "Mercedes-Benz Stadium": "梅赛德斯-奔驰体育场",
  "AT&T Stadium": "AT&T体育场",
  "Estadio BBVA": "BBVA体育场",
  "Arrowhead Stadium": "箭头体育场",
  "Hard Rock Stadium": "硬石体育场",
  "Lincoln Financial Field": "林肯金融球场",
  "Lumen Field": "流明球场",
};
const CITY_ZH = {
  "Mexico City": "墨西哥城",
  "Zapopan": "萨波潘",
  "Toronto": "多伦多",
  "Inglewood": "英格尔伍德",
  "Foxborough": "福克斯伯勒",
  "Vancouver": "温哥华",
  "East Rutherford": "东卢瑟福",
  "Santa Clara": "圣克拉拉",
  "Houston": "休斯敦",
  "Atlanta": "亚特兰大",
  "Arlington": "阿灵顿",
  "Monterrey": "蒙特雷",
  "Kansas City": "堪萨斯城",
  "Miami Gardens": "迈阿密花园",
  "Philadelphia": "费城",
  "Seattle": "西雅图",
};
const COUNTRY_ZH = {
  "United States": "美国",
  "USA": "美国",
  "Mexico": "墨西哥",
  "Canada": "加拿大",
};

function localizedVenueText(value, map) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return _lang === "zh" ? (map[raw] || raw) : raw;
}

function renderVenueLocation(match) {
  if (!match?.venue) return "";
  const country = String(match.venue_country ?? "").trim();
  const visibleCountry = country.toLowerCase() === "world" ? "" : localizedVenueText(country, COUNTRY_ZH);
  const venue = localizedVenueText(match.venue, VENUE_ZH);
  const city = localizedVenueText(match.venue_city, CITY_ZH);
  return `<div class="text-[10px] text-gray-500 mt-1">${esc(venue)}</div>${
    city
      ? `<div class="text-[10px] text-gray-500">${esc(city)}${visibleCountry ? `, ${esc(visibleCountry)}` : ""}</div>`
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
  if (id === USER_PREDICTION_MODEL_ID) return t("user_leaderboard_name");
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
  if (name === USER_PREDICTION_MODEL_ID) return t("user_leaderboard_name");
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
  if (key === USER_PREDICTION_MODEL_ID) return { emoji: "我" };
  // icon: brand SVG under docs/site/icons/ (vendored from lobehub/lobe-icons, MIT).
  // mono: black/currentColor glyph — CSS inverts it to white on the dark theme.
  // emoji stays as the fallback for models without a brand icon.
  if (key.includes("gpt") || key.includes("o1") || key.includes("o3") || key.includes("o4"))
                               return { emoji: "🟢", icon: "openai", mono: true };
  if (key.includes("claude"))  return { emoji: "🟠", icon: "claude-color" };
  if (key.includes("gemini"))  return { emoji: "🔵", icon: "gemini-color" };
  if (key.includes("grok"))    return { emoji: "⬛", icon: "grok", mono: true };
  if (key.includes("deepseek"))return { emoji: "🟣", icon: "deepseek-color" };
  if (key.includes("qwen"))    return { emoji: "🔴", icon: "qwen-color" };
  if (key.includes("kimi") || key.includes("moonshot")) return { emoji: "🌙", icon: "kimi", mono: true };
  if (key.includes("glm") || key.includes("zhipu"))     return { emoji: "💠", icon: "zhipu-color" };
  if (key.includes("doubao"))  return { emoji: "🫘", icon: "doubao-color" };
  if (key.includes("minimax")) return { emoji: "〽️", icon: "minimax-color" };
  if (key.includes("gemma"))   return { emoji: "💎", icon: "gemma-color" };
  if (key.includes("llama"))   return { emoji: "🦙", icon: "meta-color" };
  if (key.includes("perplexity")) return { emoji: "🔷", icon: "perplexity-color" };
  if (key.includes("mirothinker")) return { emoji: "✨" };
  return { emoji: "🤖" };
}

function badgeHtml(b, extraClass = "") {
  if (b.icon) {
    const cls = `model-logo${b.mono ? " model-logo-mono" : ""}${extraClass ? " " + extraClass : ""}`;
    return `<img class="${cls}" src="icons/${b.icon}.svg" alt="" aria-hidden="true" loading="lazy"/>`;
  }
  return `<span${extraClass ? ` class="${extraClass}"` : ""}>${b.emoji}</span>`;
}


// ---------- Current-user predictions -----------------------------------------

const USER_PREDICTION_MODEL_ID = "__current_user__";
const USER_PREDICTION_STORAGE_PREFIX = "matchmate:user_predictions:v1";

function userPredictionEnabled() {
  return new URLSearchParams(window.location.search).get("user_predict") === "1";
}

let _currentUser = null;
let _currentUserAccessToken = "";
let _userPredictions = {};
let _userPredictionSaveStatus = {};
let _authMessageListenerReady = false;

function userPredictionConfig() {
  return window.MATCHMATE_USER_PREDICTION_CONFIG || window.WCA_USER_PREDICTION_CONFIG || {};
}

function userPredictionApiBase() {
  const cfg = userPredictionConfig();
  return String(cfg.apiBase || cfg.userPredictionApiBase || "").replace(/\/+$/, "");
}

function safeJsonParse(value) {
  try { return JSON.parse(value); } catch { return null; }
}

function normalizeUserIdentity(raw) {
  if (!raw || typeof raw !== "object") return null;
  const user = raw.user && typeof raw.user === "object" ? raw.user : raw;
  const id = user.id || user.sub || user.userId || user.user_id || user.email;
  if (!id) return null;
  return {
    id: String(id),
    name: String(user.name || user.displayName || user.username || user.email || id),
    email: user.email || "",
  };
}

function readLocalAuthValue(keys) {
  for (const key of keys) {
    try {
      const value = localStorage.getItem(key) || sessionStorage.getItem(key);
      if (value) return value;
    } catch {}
  }
  return "";
}

function readCurrentUserFromHost() {
  const globals = [
    window.__MATCHMATE_AUTH__,
    window.__MATCHMATE_LOGTO__,
    window.__LOGTO_USER__,
    window.MatchMateAuth && (typeof window.MatchMateAuth.getState === "function" ? window.MatchMateAuth.getState() : window.MatchMateAuth),
  ];
  for (const value of globals) {
    const user = normalizeUserIdentity(value);
    if (user) return user;
  }
  const local = readLocalAuthValue([
    "matchmate:logto:user",
    "matchmate:user",
    "logto:user",
    "logto_user",
    "matchmate.auth.user",
  ]);
  return normalizeUserIdentity(safeJsonParse(local));
}

function readCurrentAccessToken() {
  const cfg = userPredictionConfig();
  if (cfg.accessToken) return String(cfg.accessToken);
  const globals = [window.__MATCHMATE_AUTH__, window.__MATCHMATE_LOGTO__];
  for (const value of globals) {
    if (value && typeof value === "object") {
      const token = value.accessToken || value.access_token || value.token;
      if (token) return String(token);
    }
  }
  return readLocalAuthValue([
    "matchmate:logto:access_token",
    "matchmate:access_token",
    "logto:access_token",
    "logto_access_token",
  ]);
}

function setupAuthMessageBridge() {
  if (!userPredictionEnabled()) return;
  if (_authMessageListenerReady) return;
  _authMessageListenerReady = true;
  window.addEventListener("message", event => {
    const data = event && event.data;
    if (!data || typeof data !== "object") return;
    if (!["matchmate:auth:state", "matchmate:logto:state", "logto:user"].includes(data.type)) return;
    const user = normalizeUserIdentity(data.user || data.auth || data);
    if (!user) return;
    _currentUser = user;
    _currentUserAccessToken = data.accessToken || data.access_token || _currentUserAccessToken;
    updateUserAuthButton();
    loadUserPredictions().then(renderSiteData).catch(console.error);
  });
}

function requestHostAuthState() {
  if (!userPredictionEnabled()) return;
  setupAuthMessageBridge();
  try {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: "matchmate:auth:request", source: "worldcuparena-predict" }, "*");
    }
  } catch {}
}

function initUserSession() {
  if (!userPredictionEnabled()) {
    _currentUser = null;
    _currentUserAccessToken = "";
    _userPredictions = {};
    updateUserAuthButton();
    return;
  }
  _currentUser = readCurrentUserFromHost();
  _currentUserAccessToken = readCurrentAccessToken();
  setupAuthMessageBridge();
  requestHostAuthState();
  updateUserAuthButton();
}

function userDisplayName() {
  return _currentUser ? (_currentUser.name || _currentUser.email || _currentUser.id) : "";
}

function buildLoginUrl() {
  const cfg = userPredictionConfig();
  const raw = cfg.loginUrl || cfg.logtoLoginUrl || (_matchmateMode ? "/login" : "https://logto.io/");
  let url;
  try { url = new URL(raw, window.location.origin); }
  catch { return raw; }
  if (!url.searchParams.has("redirect_uri") && !url.searchParams.has("returnTo")) {
    url.searchParams.set("redirect_uri", window.location.href);
  }
  return url.toString();
}

function handleUserAuthButton() {
  if (!userPredictionEnabled()) return;
  if (_currentUser) return;
  window.location.href = buildLoginUrl();
}

function updateUserAuthButton() {
  const btn = document.getElementById("user-auth-button");
  if (!btn) return;
  const enabled = userPredictionEnabled();
  btn.classList.toggle("hidden", !enabled);
  btn.style.display = enabled ? "" : "none";
  if (!enabled) return;
  btn.textContent = _currentUser ? t("logged_in_as", { name: userDisplayName() }) : t("login_with_logto");
  btn.setAttribute("title", _currentUser ? t("logged_in_as", { name: userDisplayName() }) : t("login_with_logto"));
}

function userPredictionStorageKey() {
  const userId = _currentUser ? _currentUser.id : "local-preview";
  return `${USER_PREDICTION_STORAGE_PREFIX}:${userId}`;
}

function normalizePredictionRecord(raw) {
  if (!raw || typeof raw !== "object") return null;
  const fixtureId = raw.fixture_id || raw.wca_id;
  const score = normalizeScoreString(raw.score || raw.predicted_score || raw.prediction?.score);
  const winner = normalizeWinnerSide(raw.winner || raw.predicted_winner || raw.prediction?.winner || outcomeSideFromScoreString(score));
  if (!fixtureId || !winner) return null;
  return {
    fixture_id: String(fixtureId),
    wca_id: String(fixtureId),
    score,
    winner,
    home: raw.home || raw.fixture?.home || "",
    away: raw.away || raw.fixture?.away || "",
    kickoff_utc: raw.kickoff_utc || raw.fixture?.kickoff_utc || "",
    updated_at: raw.updated_at || raw.client_updated_at || new Date().toISOString(),
  };
}

function loadLocalUserPredictions() {
  const raw = readLocalAuthValue([userPredictionStorageKey()]);
  const parsed = safeJsonParse(raw);
  const rows = Array.isArray(parsed) ? parsed : Object.values(parsed || {});
  const out = {};
  for (const item of rows) {
    const record = normalizePredictionRecord(item);
    if (record) out[record.fixture_id] = record;
  }
  return out;
}

function writeLocalUserPredictions() {
  try {
    localStorage.setItem(userPredictionStorageKey(), JSON.stringify(_userPredictions));
  } catch (err) {
    console.warn("failed to store user predictions locally", err);
  }
}

function authHeaders() {
  return _currentUserAccessToken ? { Authorization: `Bearer ${_currentUserAccessToken}` } : {};
}

async function fetchRemoteUserPredictions() {
  const apiBase = userPredictionApiBase();
  if (!apiBase) return null;
  const resp = await fetch(`${apiBase}/predictions/me`, {
    headers: { Accept: "application/json", ...authHeaders() },
    credentials: "include",
  });
  if (!resp.ok) throw new Error(`user predictions fetch failed: ${resp.status}`);
  const payload = await resp.json();
  const rows = Array.isArray(payload) ? payload : (payload.predictions || []);
  const out = {};
  for (const item of rows) {
    const record = normalizePredictionRecord(item);
    if (record) out[record.fixture_id] = record;
  }
  return out;
}

async function persistRemoteUserPrediction(record) {
  const apiBase = userPredictionApiBase();
  if (!apiBase) return false;
  const resp = await fetch(`${apiBase}/predictions/me/${encodeURIComponent(record.fixture_id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(record),
  });
  if (!resp.ok) throw new Error(`user prediction save failed: ${resp.status}`);
  return true;
}

async function loadUserPredictions() {
  if (!userPredictionEnabled()) {
    _userPredictions = {};
    _userPredictionSaveStatus = {};
    return;
  }
  _userPredictions = loadLocalUserPredictions();
  try {
    const remote = await fetchRemoteUserPredictions();
    if (remote) {
      _userPredictions = remote;
      writeLocalUserPredictions();
    }
  } catch (err) {
    console.warn("using local user predictions", err);
  }
}

function getUserPrediction(wcaId) {
  if (!userPredictionEnabled()) return null;
  return _userPredictions[String(wcaId || "")] || null;
}

function safeDomId(value) {
  return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "_");
}

function userPredictionFormId(wcaId) {
  return `user-pred-form-${safeDomId(wcaId)}`;
}

function jsArg(value) {
  return JSON.stringify(String(value ?? ""));
}

function parseUserScoreString(score) {
  const match = String(score || "").trim().match(/^(\d{1,2})\s*[-:]\s*(\d{1,2})$/);
  if (!match) return null;
  const home = Number(match[1]);
  const away = Number(match[2]);
  if (!Number.isInteger(home) || !Number.isInteger(away) || home < 0 || away < 0 || home > 30 || away > 30) return null;
  return { home, away };
}

function normalizeScoreString(score) {
  const parsed = parseUserScoreString(score);
  return parsed ? `${parsed.home}-${parsed.away}` : "";
}

function normalizeWinnerSide(side) {
  const value = String(side || "").toLowerCase();
  if (["home", "draw", "away"].includes(value)) return value;
  return "";
}

function outcomeSideFromScoreString(score) {
  const parsed = parseUserScoreString(score);
  if (!parsed) return "";
  if (parsed.home > parsed.away) return "home";
  if (parsed.away > parsed.home) return "away";
  return "draw";
}

function userOutcomeLabel(side, match) {
  if (side === "home") return t("user_prediction_home_win", { team: match.home || t("home") });
  if (side === "away") return t("user_prediction_away_win", { team: match.away || t("away") });
  if (side === "draw") return t("user_prediction_draw");
  return "—";
}

function isFixtureOpenForUserPrediction(match, live) {
  if (!match || !match.wca_id) return false;
  if (live && live.status && live.status !== "Not Started") return false;
  if (!match.kickoff_utc) return true;
  const kickoff = new Date(match.kickoff_utc);
  return Number.isNaN(kickoff.getTime()) || kickoff > new Date();
}

function findFixtureByWcaId(wcaId) {
  const id = String(wcaId || "");
  for (const item of (_siteData?.incoming_matches || [])) {
    const fixture = item.fixture || {};
    if (fixture.wca_id === id) return { ...fixture, live: item.live || null };
  }
  for (const item of (_siteData?.history || [])) {
    if (item.wca_id === id) return item;
  }
  return null;
}

function selectUserPredictionOutcome(wcaId, outcome) {
  const form = document.getElementById(userPredictionFormId(wcaId));
  if (!form) return;
  form.dataset.outcome = normalizeWinnerSide(outcome);
  form.querySelectorAll("[data-user-outcome]").forEach(btn => {
    const active = btn.dataset.userOutcome === form.dataset.outcome;
    btn.dataset.selected = active ? "1" : "0";
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function syncUserPredictionOutcomeFromScore(wcaId) {
  const form = document.getElementById(userPredictionFormId(wcaId));
  if (!form) return;
  const home = form.querySelector("[data-user-score='home']")?.value;
  const away = form.querySelector("[data-user-score='away']")?.value;
  const score = normalizeScoreString(`${home}-${away}`);
  const outcome = outcomeSideFromScoreString(score);
  if (outcome) selectUserPredictionOutcome(wcaId, outcome);
}

function toggleUserPredictionScore(wcaId, checked = null) {
  const form = document.getElementById(userPredictionFormId(wcaId));
  if (!form) return;
  const next = checked == null ? form.dataset.scoreVisible !== "1" : Boolean(checked);
  form.dataset.scoreVisible = next ? "1" : "0";
  const scoreWrap = form.querySelector("[data-user-score-wrap]");
  const checkbox = form.querySelector("[data-user-score-toggle]");
  if (scoreWrap) scoreWrap.classList.toggle("hidden", !next);
  if (checkbox) checkbox.checked = next;
  if (!next) {
    form.querySelectorAll("[data-user-score]").forEach(input => { input.value = ""; });
  }
}

function showUserPredictionMessage(wcaId, message, tone = "error") {
  const form = document.getElementById(userPredictionFormId(wcaId));
  const msg = form?.querySelector("[data-user-pred-message]");
  if (!msg) return;
  msg.textContent = message;
  msg.style.color = tone === "ok" ? "#86efac" : "#fca5a5";
}

function readUserPredictionForm(wcaId) {
  const form = document.getElementById(userPredictionFormId(wcaId));
  const fixture = findFixtureByWcaId(wcaId);
  if (!form || !fixture) return null;
  const winner = normalizeWinnerSide(form.dataset.outcome);
  if (!winner) return { error: t("user_prediction_invalid_result") };
  const scoreVisible = form.dataset.scoreVisible === "1";
  const home = form.querySelector("[data-user-score='home']")?.value;
  const away = form.querySelector("[data-user-score='away']")?.value;
  const score = scoreVisible ? normalizeScoreString(`${home}-${away}`) : "";
  if (scoreVisible && !score) return { error: t("user_prediction_invalid_score") };
  return {
    fixture_id: String(wcaId),
    wca_id: String(wcaId),
    home: fixture.home || "",
    away: fixture.away || "",
    kickoff_utc: fixture.kickoff_utc || "",
    score,
    winner,
    updated_at: new Date().toISOString(),
  };
}

async function saveUserPredictionForFixture(wcaId) {
  if (!userPredictionEnabled()) return;
  const fixture = findFixtureByWcaId(wcaId);
  if (!fixture || !isFixtureOpenForUserPrediction(fixture, fixture.live)) {
    showUserPredictionMessage(wcaId, t("user_prediction_locked"));
    return;
  }
  const record = readUserPredictionForm(wcaId);
  if (!record || record.error) {
    showUserPredictionMessage(wcaId, record?.error || t("user_prediction_invalid_score"));
    return;
  }
  _userPredictions[record.fixture_id] = record;
  _userPredictionSaveStatus[record.fixture_id] = "saving";
  writeLocalUserPredictions();
  renderSiteData();
  try {
    const remote = await persistRemoteUserPrediction(record);
    _userPredictionSaveStatus[record.fixture_id] = remote ? "saved" : "local";
  } catch (err) {
    console.warn("user prediction saved locally only", err);
    _userPredictionSaveStatus[record.fixture_id] = "local";
  }
  writeLocalUserPredictions();
  renderSiteData();
}

function renderOutcomeButton(wcaId, outcome, label, selected, logoUrl = "") {
  const active = selected === outcome;
  const logo = logoUrl ? `<img src="${esc(logoUrl)}" alt="" class="mx-auto mb-1" style="width:2rem;height:2rem;object-fit:contain;" />` : "";
  return `<button type="button" data-user-outcome="${esc(outcome)}" data-selected="${active ? "1" : "0"}" aria-pressed="${active ? "true" : "false"}" onclick='selectUserPredictionOutcome(${jsArg(wcaId)}, ${jsArg(outcome)})'
          class="user-outcome-btn rounded-lg px-2 sm:px-3 py-2 text-center transition hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-green-400/40 flex flex-col items-center justify-center">
            ${logo}
            <div class="text-sm sm:text-base font-black leading-tight">${esc(label)}</div>
          </button>`;
}

function renderUserPredictionEditor(nm) {
  if (!userPredictionEnabled()) return "";
  const f = nm?.fixture || {};
  if (!isFixtureOpenForUserPrediction(f, nm?.live)) return "";
  const existing = getUserPrediction(f.wca_id);
  const parsed = existing ? parseUserScoreString(existing.score) : null;
  const selected = normalizeWinnerSide(existing?.winner || outcomeSideFromScoreString(existing?.score));
  const scoreVisible = Boolean(parsed);
  const status = _userPredictionSaveStatus[f.wca_id] || (existing ? "saved" : "");
  const statusText = status === "saving" ? t("user_prediction_saving")
    : status === "local" ? t("user_prediction_local_saved")
      : status === "saved" ? t("user_prediction_saved") : (_currentUser ? t("logged_in_as", { name: userDisplayName() }) : t("user_prediction_guest"));
  return `
    <div class="rounded-xl p-3 sm:p-4 mb-4" style="background:rgba(34,197,94,.07);border:1px solid rgba(34,197,94,.18);">
      <div class="text-xs font-bold text-gray-200 uppercase tracking-wider text-center mb-3">${t("user_prediction_title")}</div>
      <div id="${userPredictionFormId(f.wca_id)}" data-outcome="${esc(selected)}" data-score-visible="${scoreVisible ? "1" : "0"}" class="flex flex-col gap-3">
        <div>
          <div class="text-[10px] text-gray-500 uppercase tracking-wider text-center mb-2">${t("user_prediction_result")}</div>
          <div class="grid grid-cols-3 gap-2 sm:gap-3">
            ${renderOutcomeButton(f.wca_id, "home", t("user_prediction_home_win", { team: f.home || t("home") }), selected, f.home_logo || "")}
            ${renderOutcomeButton(f.wca_id, "draw", t("user_prediction_draw"), selected)}
            ${renderOutcomeButton(f.wca_id, "away", t("user_prediction_away_win", { team: f.away || t("away") }), selected, f.away_logo || "")}
          </div>
        </div>
        <label class="inline-flex self-center items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-bold cursor-pointer" style="background:var(--soft-surface-bg);border:1px solid var(--soft-surface-border);color:var(--prediction-primary);">
          <input data-user-score-toggle class="user-score-checkbox" type="checkbox" ${scoreVisible ? "checked" : ""} onchange='toggleUserPredictionScore(${jsArg(f.wca_id)}, this.checked)' style="width:1.05rem;height:1.05rem;" />
          <span>${t("user_prediction_optional_score")}</span>
        </label>
        <div data-user-score-wrap class="${scoreVisible ? "self-center" : "hidden self-center"}">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1 text-center">${t("user_prediction_score")}</div>
          <div class="flex items-center justify-center gap-1.5">
            <input data-user-score="home" oninput='syncUserPredictionOutcomeFromScore(${jsArg(f.wca_id)})' inputmode="numeric" type="number" min="0" max="30" value="${esc(parsed ? parsed.home : "")}" class="w-14 rounded-lg px-2 py-1.5 text-center font-mono text-sm bg-white/10 border border-white/10 text-white outline-none" />
            <span class="text-gray-500 font-bold">-</span>
            <input data-user-score="away" oninput='syncUserPredictionOutcomeFromScore(${jsArg(f.wca_id)})' inputmode="numeric" type="number" min="0" max="30" value="${esc(parsed ? parsed.away : "")}" class="w-14 rounded-lg px-2 py-1.5 text-center font-mono text-sm bg-white/10 border border-white/10 text-white outline-none" />
          </div>
        </div>
        <button type="button" onclick='saveUserPredictionForFixture(${jsArg(f.wca_id)})' class="chip chip-live self-center hover:bg-white/15 transition justify-center py-2 px-5 text-sm font-black">${existing ? t("user_prediction_update") : t("user_prediction_save")}</button>
        <div data-user-pred-message class="text-[11px] text-gray-500 text-center">${esc(statusText)}</div>
      </div>
    </div>`;
}

function userPredictionEvaluation(match) {
  const pred = getUserPrediction(match?.wca_id);
  if (!pred || !match?.result) return { pred, actualWinner: "", winnerCorrect: false, scoreCorrect: false, hasScore: false };
  const actualScore = normalizeScoreString(match.result);
  const actualWinner = outcomeSideFromScoreString(actualScore);
  const winner = pred.winner || outcomeSideFromScoreString(pred.score);
  return {
    pred,
    actualWinner,
    winnerCorrect: Boolean(winner && actualWinner && winner === actualWinner),
    scoreCorrect: Boolean(pred.score && actualScore && normalizeScoreString(pred.score) === actualScore),
    hasScore: Boolean(pred.score),
  };
}

function renderUserPredictionHistoryCard(match) {
  if (!userPredictionEnabled()) return "";
  const { pred, winnerCorrect, scoreCorrect, hasScore } = userPredictionEvaluation(match);
  if (!pred) return "";
  return `
    <div class="rounded-xl p-3" style="background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.16);">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">${t("user_prediction_history_title")}</div>
          ${pred ? `<div class="text-sm text-gray-200">${pred.score ? `<span class="font-mono font-black">${esc(pred.score.replace("-", " - "))}</span><span class="mx-2 text-gray-500">·</span>` : ""}${esc(userOutcomeLabel(pred.winner, match))}</div>` : `<div class="text-sm text-gray-500">${t("user_prediction_no_history")}</div>`}
        </div>
        ${pred ? `<div class="flex flex-wrap gap-1.5 text-[10px]">
          <span class="chip ${winnerCorrect ? "chip-live" : ""}">${winnerCorrect ? t("user_prediction_correct_result") : t("user_prediction_wrong_result")}</span>
          ${hasScore ? `<span class="chip ${scoreCorrect ? "chip-live" : ""}">${scoreCorrect ? t("user_prediction_exact_score") : t("user_prediction_wrong_score")}</span>` : ""}
        </div>` : ""}
      </div>
    </div>`;
}

function currentUserLeaderboardRow() {
  if (!userPredictionEnabled()) return null;
  const history = (_siteData && _siteData.history) || [];
  let winnerTotal = 0;
  let winnerCorrect = 0;
  let scoreTotal = 0;
  let scoreCorrect = 0;
  for (const match of history) {
    if (!match.result) continue;
    // Mirror the model boards' sample-set slice so 我的预测 stays comparable.
    if (_leaderboardScope === "knockout" && !isKnockoutWcaId(match.wca_id)) continue;
    const { pred, winnerCorrect: wc, scoreCorrect: sc, hasScore } = userPredictionEvaluation(match);
    if (!pred) continue;
    winnerTotal += 1;
    if (hasScore) scoreTotal += 1;
    if (wc) winnerCorrect += 1;
    if (hasScore && sc) scoreCorrect += 1;
  }
  if (!_currentUser && Object.keys(_userPredictions).length === 0) return null;
  const winnerAcc = winnerTotal ? winnerCorrect / winnerTotal : null;
  return {
    model_id: USER_PREDICTION_MODEL_ID,
    is_user: true,
    n: winnerTotal,
    winner_total: winnerTotal,
    winner_correct: winnerCorrect,
    winner_acc: winnerAcc,
    score_total: scoreTotal,
    score_correct: scoreCorrect,
    mean: winnerAcc == null ? 0 : winnerAcc * 100,
  };
}

function withCurrentUserLeaderboardRow(rows) {
  const mine = currentUserLeaderboardRow();
  return mine ? [...(rows || []), mine] : (rows || []);
}

// ---------- Reasoning modal --------------------------------------------------

function reasoningLabels() {
  return {
    overall:   t("reasoning_overall"),
    market_odds: t("reasoning_market_odds"),
    lineup_analysis: t("reasoning_lineup_analysis"),
    tactical_analysis: t("reasoning_tactical_analysis"),
    h2h_recent_form: t("reasoning_h2h_recent_form"),
    player_matchups: t("reasoning_player_matchups"),
    injuries_availability: t("reasoning_injuries_availability"),
    upset_draw_blowout_cases: t("reasoning_upset_draw_blowout_cases"),
    score_result_rationale: t("reasoning_score_result_rationale"),
    t1_result: t("reasoning_t1"),
    t2_player: t("reasoning_t2"),
    t3_events: t("reasoning_t3"),
    t4_stats:  t("reasoning_t4"),
  };
}

function reasoningEntries(r) {
  const src = r || {};
  return Object.entries(reasoningLabels())
    .map(([k, label]) => [k, label, String(src[k] || "").trim()])
    .filter(([, , text]) => text);
}

function renderReasoningSections(r) {
  const rows = reasoningEntries(r);
  if (!rows.length) return `<div class="text-gray-400 text-sm py-2">${t("no_reasoning")}</div>`;
  return rows.map(([key, label, text], index) => {
    const open = key === "overall" || (index === 0 && !rows.some(([k]) => k === "overall"));
    return `
    <details${open ? " open" : ""} class="reasoning-section rounded-lg px-3 py-3" style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);">
      <summary class="reasoning-summary flex items-center justify-between gap-3">
        <span class="text-[10px] text-gray-400 uppercase tracking-wider">${esc(label)}</span>
        <span class="reasoning-toggle-chip">
          <span class="reasoning-toggle-expand">${t("reasoning_expand")}</span>
          <span class="reasoning-toggle-collapse">${t("reasoning_collapse")}</span>
          <span class="reasoning-summary-icon" aria-hidden="true"></span>
        </span>
      </summary>
      <div class="reasoning-body text-sm text-gray-200 leading-relaxed mt-2">${renderMarkdownText(text)}</div>
    </details>`;
  }).join("");
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
  const titleSetting = (!_matchmateMode && p.setting) ? ` (${p.setting})` : "";
  document.getElementById("reasoning-modal-title").textContent =
    `${fmtModelId(p)}${titleSetting} — ${t("full_reasoning_suffix")}`;
  const entries = reasoningEntries(r);
  const hasOverall = entries.some(([k]) => k === "overall");
  const rows = entries
    .map(([key, label, text], index) => {
      const open = key === "overall" || (index === 0 && !hasOverall);
      return `
        <details${open ? " open" : ""} class="reasoning-section rounded-lg px-3 py-3 mb-3" style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);">
          <summary class="reasoning-summary flex items-center justify-between gap-3">
            <span class="text-[10px] text-gray-400 uppercase tracking-wider">${esc(label)}</span>
            <span class="reasoning-toggle-chip">
              <span class="reasoning-toggle-expand">${t("reasoning_expand")}</span>
              <span class="reasoning-toggle-collapse">${t("reasoning_collapse")}</span>
              <span class="reasoning-summary-icon" aria-hidden="true"></span>
            </span>
          </summary>
          <div class="reasoning-body text-sm text-gray-200 leading-relaxed mt-2">${renderMarkdownText(text)}</div>
        </details>`;
    }).join("");
  document.getElementById("reasoning-modal-body").innerHTML =
    rows || `<div class="text-gray-400 text-sm py-2">${t("no_reasoning")}</div>`;
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

const WIN_PROB_KEYS = ["home", "draw", "away"];

function winProbPctLabels(wp) {
  const values = WIN_PROB_KEYS.map(key => Math.max(0, Number(wp && wp[key])));
  if (values.some(value => !Number.isFinite(value))) return {};
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return {};
  const exact = values.map(value => value / total * 100);
  const ints = exact.map(value => Math.floor(value));
  let remainder = 100 - ints.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((value, idx) => ({ idx, frac: value - Math.floor(value) }))
    .sort((a, b) => b.frac - a.frac || a.idx - b.idx);
  for (let i = 0; i < remainder; i++) ints[order[i % order.length].idx] += 1;
  return Object.fromEntries(WIN_PROB_KEYS.map((key, idx) => [key, `${ints[idx]}%`]));
}

function winnerFromWinProbs(wp, homeName, awayName) {
  if (!wp || wp.home == null || wp.draw == null || wp.away == null) return null;
  if (wp.home >= wp.draw && wp.home >= wp.away) return homeName;
  if (wp.away >= wp.home && wp.away >= wp.draw) return awayName;
  return t("draw");
}

function predictionWinnerDisplay(winner, f) {
  const value = String(winner || "").trim();
  if (!value) return { label: "—", flag: "" };
  const home = String(f?.home || "").trim();
  const away = String(f?.away || "").trim();
  if (value === home) return { label: value, flag: f?.home_flag_img || "" };
  if (value === away) return { label: value, flag: f?.away_flag_img || "" };
  if (value === t("draw") || value.toLowerCase() === "draw" || value === "平局") return { label: t("draw_winner_label"), flag: "" };
  return { label: value, flag: "" };
}

function renderPredictionWinnerLabel(winner, f, opts = {}) {
  const display = predictionWinnerDisplay(winner, f);
  const color = opts.color || "var(--prediction-primary)";
  const sizeClass = opts.sizeClass || "text-2xl";
  return `<div class="inline-flex items-center gap-1.5 whitespace-nowrap ${sizeClass} font-black leading-none max-w-full" style="color:${color};">${display.flag ? `<img src="${esc(display.flag)}" alt="" loading="lazy" style="height:1.05em;width:auto;flex:0 0 auto;border-radius:3px;box-shadow:0 0 0 1px rgba(0,0,0,.18);">` : ""}<span class="truncate" style="font-size:.72em;font-weight:800;opacity:.9;vertical-align:middle">${esc(display.label)}</span></div>`;
}

function togglePredPanel(idx, type) {
  const btnId = type === "live" ? `pred-live-btn-${idx}` : `pred-prematch-btn-${idx}`;
  const btn = document.getElementById(btnId);
  const group = btn?.closest("[data-pred-grid]");
  const row = btn?.closest("[data-pred-row]");
  const panel = row?.querySelector("[data-pred-panel='1']");
  if (!group || !row || !panel) return;

  const panelType = type === "live" ? "live" : "prematch";
  const showingSame = !panel.classList.contains("hidden")
    && panel.dataset.panelType === panelType
    && panel.dataset.predIdx === String(idx);

  resetPredGridButtons(group);
  if (showingSame) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    panel.dataset.panelType = "";
    panel.dataset.predIdx = "";
    return;
  }

  panel.innerHTML = type === "live" ? renderLiveDetailsPanel(idx) : renderPrematchDetailsPanel(idx);
  panel.dataset.panelType = panelType;
  panel.dataset.predIdx = String(idx);
  panel.classList.remove("hidden");
  if (btn) btn.textContent = type === "live" ? t("hide_live_prediction") : t("hide_prematch_prediction");
}

function toggleDetails(idx) {
  togglePredPanel(idx, "prematch");
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
  group.querySelectorAll("[id^='pred-prematch-btn-']").forEach(button => {
    button.textContent = t("show_prematch_prediction");
  });
  group.querySelectorAll("[id^='pred-live-btn-']").forEach(button => {
    button.textContent = t("show_live_prediction");
  });
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

// Normalize player name: strip accents/role notes, reduce to "firstInitial.lastName".
// "Kylian Mbappé (captain)" == "Kylian Mbappe" == "K. Mbappe".
const _plainNameCache = new Map();
function _plainNameForMatch(s) {
  const ck = String(s || "");
  const hit = _plainNameCache.get(ck);
  if (hit !== undefined) return hit;
  const out = ck
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[([{].*?[)\]}]/g, " ")
    .replace(/[’\x27]/g, "")
    .replace(/[^\p{Letter}\p{Number}\s.-]/gu, " ")
    .replace(/[.-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  _plainNameCache.set(ck, out);
  return out;
}

const _normNameCache = new Map();
function _normName(s) {
  const ck = String(s || "");
  const hit = _normNameCache.get(ck);
  if (hit !== undefined) return hit;
  const stripped = _plainNameForMatch(ck);
  const parts = stripped.split(/\s+/).filter(Boolean);
  let out;
  if (!parts.length) out = stripped.toLowerCase();
  else {
    const last = parts[parts.length - 1].toLowerCase();
    const init = parts[0][0]?.toLowerCase() || "";
    out = `${init}.${last}`;
  }
  _normNameCache.set(ck, out);
  return out;
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

function parseScore(score) {
  const match = String(score || "").trim().match(/^(\d+)\s*[-:]\s*(\d+)$/);
  if (!match) return { home: 0, away: 0 };
  return { home: Number(match[1]) || 0, away: Number(match[2]) || 0 };
}

function oppositeSide(side) {
  return side === "home" ? "away" : side === "away" ? "home" : side;
}

function eventMinute(item) {
  if (item && item.minute != null && Number.isFinite(Number(item.minute))) return Number(item.minute);
  const range = item && item.minute_range;
  if (Array.isArray(range) && range.length >= 2) {
    const a = Number(range[0]);
    const b = Number(range[1]);
    if (Number.isFinite(a) && Number.isFinite(b)) return Math.round((a + b) / 2);
  }
  return null;
}

function defaultGoalMinute(index, total) {
  const templates = {
    1: [58],
    2: [34, 72],
    3: [24, 55, 78],
    4: [18, 42, 66, 84],
    5: [12, 31, 52, 71, 86],
  };
  const arr = templates[Math.min(total, 5)] || [];
  return arr[index] || Math.min(90, Math.max(8, Math.round(((index + 1) * 90) / (total + 1))));
}

function normalizeMinute(minute) {
  const m = Number(minute);
  if (!Number.isFinite(m)) return 0;
  return Math.max(0, Math.min(130, Math.round(m)));
}

function sameEventMinute(a, b) {
  const ma = eventMinute(a);
  const mb = eventMinute(b);
  return ma != null && mb != null && Math.abs(ma - mb) <= 1;
}

function goalSignature(team, player, minute) {
  return `${team || ""}|${_normName(player || "")}|${minute == null ? "" : normalizeMinute(minute)}`;
}

function assignAssistsToGoals(goals, assisters) {
  const used = new Set();
  const byTeam = { home: [], away: [] };
  for (const a of assisters || []) {
    if (a && (a.player || a.name)) byTeam[a.team === "away" ? "away" : "home"].push(a);
  }
  for (const side of ["home", "away"]) {
    byTeam[side].sort((a, b) => (b.p || 0) - (a.p || 0));
  }
  for (const g of goals) {
    if (g.type !== "goal") continue;
    const list = byTeam[g.side] || [];
    let found = null;
    for (const a of list) {
      const name = a.player || a.name;
      const key = `${g.side}|${_normName(name)}`;
      if (used.has(key)) continue;
      if (_normName(name) && _normName(name) === _normName(g.player)) continue;
      if (a.minute != null && g.minute != null && Math.abs(Number(a.minute) - Number(g.minute)) > 2) continue;
      found = { key, name };
      break;
    }
    if (found) {
      used.add(found.key);
      g.assist = found.name;
    }
  }
}

function buildGoalEventsForScore(score, scorers = [], assisters = [], penalties = [], ownGoals = []) {
  const target = parseScore(score);
  const all = [];
  const penaltyGoalSigs = new Set();
  const penaltyGoalRefs = { home: [], away: [] };

  for (const pen of penalties || []) {
    if (!pen || pen.outcome !== "scored") continue;
    const side = pen.team === "away" ? "away" : "home";
    const minute = eventMinute(pen);
    const taker = pen.taker || pen.player;
    penaltyGoalSigs.add(goalSignature(side, taker, minute));
    penaltyGoalRefs[side].push({ player: _normName(taker || ""), minute });
    all.push({
      type: "penalty_goal",
      side,
      minute,
      extra: pen.extra,
      player: taker || t("unspecified_goal"),
      priority: 0,
      p: pen.p || 1,
    });
  }

  for (const og of ownGoals || []) {
    if (!og) continue;
    const ownTeam = og.team === "away" ? "away" : "home";
    const creditedSide = og.for_team === "away" || og.scoring_team === "away"
      ? "away"
      : og.for_team === "home" || og.scoring_team === "home"
        ? "home"
        : oppositeSide(ownTeam);
    all.push({
      type: "own_goal",
      side: creditedSide,
      team: ownTeam,
      minute: eventMinute(og),
      extra: og.extra,
      player: og.player || t("unspecified_goal"),
      priority: 1,
      p: og.p || 1,
    });
  }

  for (const s of scorers || []) {
    if (!s) continue;
    const side = s.team === "away" ? "away" : "home";
    const minute = eventMinute(s);
    const sig = goalSignature(side, s.player, minute);
    const scorerName = _normName(s.player || s.name || "");
    const duplicatesPenalty = (penaltyGoalRefs[side] || []).some(ref => {
      if (!ref.player || ref.player !== scorerName) return false;
      if (ref.minute == null || minute == null) return true;
      return Math.abs(Number(ref.minute) - Number(minute)) <= 2;
    });
    if (penaltyGoalSigs.has(sig) || duplicatesPenalty) continue;
    all.push({
      type: "goal",
      side,
      minute,
      extra: s.extra,
      player: s.player || s.name || t("unspecified_goal"),
      priority: 2,
      p: s.p || 0,
      minute_range: s.minute_range,
    });
  }

  const selected = [];
  for (const side of ["home", "away"]) {
    const needed = Math.max(0, target[side] || 0);
    const candidates = all
      .filter(e => e.side === side)
      .sort((a, b) => (a.priority - b.priority) || ((b.p || 0) - (a.p || 0)) || ((a.minute ?? 999) - (b.minute ?? 999)));
    const sideGoals = candidates.slice(0, needed).map(e => ({ ...e }));
    while (sideGoals.length < needed) {
      sideGoals.push({
        type: "goal",
        side,
        minute: null,
        player: t("unspecified_goal"),
        priority: 9,
        p: null,
      });
    }
    sideGoals.forEach((g, i) => {
      if (g.minute == null) g.minute = defaultGoalMinute(i, needed);
      g.minute = normalizeMinute(g.minute);
    });
    assignAssistsToGoals(sideGoals, assisters || []);
    selected.push(...sideGoals);
  }
  return selected;
}

function buildPredictedTimelineEvents(p) {
  const events = buildGoalEventsForScore(
    p.headline_score || p.most_likely_score,
    p.scorers || [],
    p.assisters || [],
    p.penalties || [],
    p.own_goals || [],
  );

  for (const pen of p.penalties || []) {
    if (!pen || pen.outcome === "scored") continue;
    events.push({
      type: pen.outcome === "saved" ? "penalty_saved" : "penalty_missed",
      side: pen.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(pen) ?? 70),
      extra: pen.extra,
      player: pen.taker || pen.player || "",
    });
  }
  for (const c of p.cards || []) {
    events.push({
      type: c.color === "red" ? "red_card" : c.color === "second_yellow" ? "second_yellow" : "yellow_card",
      side: c.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(c) ?? 60),
      extra: c.extra,
      player: c.player || "",
    });
  }
  for (const sub of p.substitutions || []) {
    events.push({
      type: "substitution",
      side: sub.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(sub) ?? 65),
      extra: sub.extra,
      off: sub.off || "",
      on: sub.on || "",
    });
  }
  for (const ev of p.key_events || []) {
    events.push({
      type: "key_event",
      side: ev.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(ev) ?? 60),
      extra: ev.extra,
      player: ev.player || "",
      label: timelineKeyEventLabel(ev),
    });
  }
  return events.sort(timelineSort);
}

function buildActualTimelineEvents(tr) {
  if (!tr) return [];
  const events = buildGoalEventsForScore(
    tr.score,
    tr.scorers || [],
    tr.assisters || [],
    tr.penalties || [],
    tr.own_goals || [],
  );
  for (const pen of tr.penalties || []) {
    if (!pen || pen.outcome === "scored") continue;
    events.push({
      type: pen.outcome === "saved" ? "penalty_saved" : "penalty_missed",
      side: pen.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(pen) ?? 70),
      extra: pen.extra,
      player: pen.taker || pen.player || "",
    });
  }
  for (const c of tr.cards || []) {
    events.push({
      type: c.color === "red" ? "red_card" : c.color === "second_yellow" ? "second_yellow" : "yellow_card",
      side: c.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(c) ?? 60),
      extra: c.extra,
      player: c.player || "",
    });
  }
  for (const sub of tr.substitutions || []) {
    events.push({
      type: "substitution",
      side: sub.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(sub) ?? 65),
      extra: sub.extra,
      off: sub.off || "",
      on: sub.on || "",
    });
  }
  for (const ev of tr.key_events || []) {
    events.push({
      type: "key_event",
      side: ev.team === "away" ? "away" : "home",
      minute: normalizeMinute(eventMinute(ev) ?? 60),
      extra: ev.extra,
      player: ev.player || "",
      label: timelineKeyEventLabel(ev),
    });
  }
  return events.sort(timelineSort);
}

function timelineSort(a, b) {
  const sideRank = side => side === "home" ? 0 : 1;
  return (a.minute - b.minute) || (sideRank(a.side) - sideRank(b.side)) || String(a.type).localeCompare(String(b.type));
}

function timelineIcon(ev) {
  if (ev.type === "goal" || ev.type === "penalty_goal" || ev.type === "own_goal") return "⚽";
  if (ev.type === "yellow_card") return "🟨";
  if (ev.type === "red_card") return "🟥";
  if (ev.type === "second_yellow") return "🟨🟥";
  if (ev.type === "substitution") return "↔";
  if (ev.type === "penalty_saved") return "🧤";
  if (ev.type === "penalty_missed") return "✕";
  return "•";
}

function timelineKeyEventLabel(ev) {
  const raw = ev?.label || ev?.detail || ev?.type || "";
  const normalized = String(raw).trim().toLowerCase().replace(/[\s-]+/g, "_");
  const key = `key_event_${normalized}`;
  const mapped = I18N[_lang]?.[key];
  if (mapped) return mapped;
  return raw || t("key_event");
}

function timelineEventLabel(ev, f) {
  const teamName = ev.side === "home" ? (f.home || t("home")) : (f.away || t("away"));
  if (ev.type === "goal") {
    return `${teamName} · ${ev.player || t("unspecified_goal")}${ev.assist ? ` · ${t("assist_prefix")}：${ev.assist}` : ""}`;
  }
  if (ev.type === "penalty_goal") return `${teamName} · ${t("penalty_goal")} · ${ev.player || t("unspecified_goal")}`;
  if (ev.type === "own_goal") return `${teamName} · ${t("own_goal_label")} · ${ev.player || t("unspecified_goal")}`;
  if (ev.type === "penalty_saved") return `${teamName} · ${t("penalty_saved")} · ${ev.player || ""}`;
  if (ev.type === "penalty_missed") return `${teamName} · ${t("penalty_missed")} · ${ev.player || ""}`;
  if (ev.type === "yellow_card") return `${teamName} · ${t("yellow_card")} · ${ev.player || ""}`;
  if (ev.type === "red_card") return `${teamName} · ${t("red_card")} · ${ev.player || ""}`;
  if (ev.type === "second_yellow") return `${teamName} · ${t("second_yellow_card")} · ${ev.player || ""}`;
  if (ev.type === "substitution") return `${teamName} · ${t("substitution_event")} · ${ev.off || "?"} → ${ev.on || "?"}`;
  return `${teamName} · ${ev.label || t("key_event")}${ev.player ? ` · ${ev.player}` : ""}`;
}

function eventExtraMinute(ev) {
  const raw = ev && (ev.extra ?? ev.minute_extra ?? ev.stoppage_extra ?? ev.added_time);
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? Math.round(n) : 0;
}

function isShootoutEvent(ev) {
  const text = `${ev?.type || ""} ${ev?.label || ""} ${ev?.detail || ""} ${ev?.period || ""}`.toLowerCase();
  return Boolean(ev?.shootout || ev?.penalty_shootout)
    || text.includes("shootout")
    || text.includes("penalty shoot")
    || text.includes("点球大战")
    || Number(ev?.minute) > 120;
}

function timelineHasExtraTime(rows, hasShootout) {
  return hasShootout || rows.some(ev => ev.extra_time || ev.period === "extra_time" || Number(ev.minute) > 105);
}

function timelinePlotMinute(ev, maxMinute, hasExtraTime, hasShootout) {
  if (hasShootout && isShootoutEvent(ev)) return Math.min(maxMinute, 126);
  const minute = normalizeMinute(eventMinute(ev));
  const extra = eventExtraMinute(ev);
  if (extra && [45, 90, 105, 120].includes(minute)) return Math.min(minute, maxMinute);
  if (!hasExtraTime && minute > 90 && minute < 120) return 90;
  if (ev?.period === "first_half_stoppage" && minute > 45 && minute < 60) return 45;
  return Math.min(minute, maxMinute);
}

function timelineMinuteLabel(ev, hasExtraTime, hasShootout) {
  if (hasShootout && isShootoutEvent(ev)) return _lang === "zh" ? "点球" : "PEN";
  const minute = normalizeMinute(eventMinute(ev));
  const extra = eventExtraMinute(ev);
  if (extra && [45, 90, 105, 120].includes(minute)) return `${minute}+${extra}`;
  if (!hasExtraTime && minute > 90 && minute < 120) return `90+${minute - 90}`;
  if (ev?.period === "first_half_stoppage" && minute > 45 && minute < 60) return `45+${minute - 45}`;
  return `${minute}`;
}

function timelineMarkerLabel(minute) {
  if (minute === 130) return _lang === "zh" ? "点球" : "PEN";
  return `${minute}′`;
}

function timelineMinuteText(label) {
  return label === "点球" || label === "PEN" ? label : `${label}′`;
}

function assignTimelineLayout(rows, maxMinute, hasExtraTime, hasShootout) {
  const lanesBySide = { home: [], away: [] };
  const minGapMinutes = maxMinute > 95 ? 5 : 6;
  return rows.map((ev, order) => {
    const side = ev.side === "away" ? "away" : "home";
    const plotMinute = timelinePlotMinute(ev, maxMinute, hasExtraTime, hasShootout);
    let lane = 0;
    while (
      lane < 4
      && lanesBySide[side].some(prev => prev.lane === lane && Math.abs(prev.plotMinute - plotMinute) <= minGapMinutes)
    ) {
      lane += 1;
    }
    lane = Math.min(lane, 3);
    lanesBySide[side].push({ lane, plotMinute });
    return { ...ev, _lane: lane, _plotMinute: plotMinute, _order: order };
  });
}

function renderEventTimeline(title, events, f, opts = {}) {
  const rows = (events || []).filter(ev => ev && ev.side && Number.isFinite(Number(eventMinute(ev)))).sort(timelineSort);
  if (!rows.length) return "";
  const hasShootout = rows.some(isShootoutEvent);
  const hasExtraTime = timelineHasExtraTime(rows, hasShootout);
  const maxMinute = hasShootout ? 130 : hasExtraTime ? 120 : 90;
  const markers = hasShootout
    ? [0, 15, 30, 45, 60, 75, 90, 105, 120, 130]
    : hasExtraTime
      ? [0, 15, 30, 45, 60, 75, 90, 105, 120]
      : [0, 15, 30, 45, 60, 75, 90];
  const layoutRows = assignTimelineLayout(rows, maxMinute, hasExtraTime, hasShootout);
  const maxLane = Math.max(0, ...layoutRows.map(ev => ev._lane || 0));
  const timelineHeight = Math.max(9.5, 8 + maxLane * 4.6);
  const teamLogo = side => side === "home" ? f.home_logo : f.away_logo;
  const teamName = side => side === "home" ? (f.home || t("home")) : (f.away || t("away"));
  const eventNodes = layoutRows.map((ev, i) => {
    const pct = Math.max(0, Math.min(100, (Number(ev._plotMinute) / maxMinute) * 100));
    const isHome = ev.side === "home";
    const lane = ev._lane || 0;
    const vertical = isHome
      ? `top:calc(50% - ${3.55 + lane * 2.25}rem);`
      : `top:calc(50% + ${0.85 + lane * 2.25}rem);`;
    const label = timelineEventLabel(ev, f);
    const minuteLabel = timelineMinuteLabel(ev, hasExtraTime, hasShootout);
    const minuteText = timelineMinuteText(minuteLabel);
    const bg = opts.actual ? "var(--timeline-actual-node-bg)" : "var(--timeline-node-bg)";
    const border = opts.actual ? "var(--timeline-actual-node-border)" : "var(--timeline-node-border)";
    return `<div title="${esc(`${minuteText} · ${label}`)}" style="position:absolute;left:${pct}%;${vertical}transform:translateX(-50%);z-index:${20 + i};text-align:center;min-width:2.5rem;">
      <div style="width:2rem;height:2rem;border-radius:9999px;display:inline-flex;align-items:center;justify-content:center;background:${bg};border:1px solid ${border};box-shadow:0 8px 20px rgba(0,0,0,.25);font-size:.95rem;">${timelineIcon(ev)}</div>
      <div class="font-mono text-[10px] text-gray-400 mt-0.5 whitespace-nowrap">${esc(minuteText)}</div>
    </div>`;
  }).join("");
  const detailRows = rows.map(ev => {
    const minuteLabel = timelineMinuteLabel(ev, hasExtraTime, hasShootout);
    const minuteText = timelineMinuteText(minuteLabel);
    return `
    <div class="rounded-lg px-2.5 py-1.5 text-xs" style="background:var(--timeline-detail-bg);border:1px solid var(--timeline-detail-border);">
      <span class="font-mono text-gray-400 mr-1.5">${esc(minuteText)}</span>
      <span class="mr-1.5">${timelineIcon(ev)}</span>
      <span style="color:var(--prediction-primary);">${esc(timelineEventLabel(ev, f))}</span>
    </div>`;
  }).join("");
  return `
    <div class="rounded-xl p-3 sm:p-4" style="background:var(--timeline-surface-bg);border:1px solid var(--timeline-surface-border);">
      <div class="text-xs text-gray-400 uppercase tracking-wider mb-3">${esc(title)}</div>
      <div class="grid gap-3" style="grid-template-columns:minmax(4rem,5.5rem) minmax(0,1fr);">
        <div class="flex flex-col justify-between py-2 text-xs text-gray-300">
          ${["home", "away"].map(side => `
            <div class="flex items-center gap-2 min-w-0">
              ${teamLogo(side) ? `<img src="${esc(teamLogo(side))}" alt="${esc(teamName(side))}" class="fixture-logo fixture-logo-sm"/>` : `<span>${side === "home" ? "🏠" : "🛫"}</span>`}
              <span class="truncate">${esc(teamName(side))}</span>
            </div>`).join("")}
        </div>
        <div style="position:relative;height:${timelineHeight}rem;padding:1rem .5rem;overflow:visible;">
          <div style="position:absolute;left:.5rem;right:.5rem;top:50%;height:2px;background:var(--timeline-line);"></div>
          ${markers.map(m => {
            const pct = Math.max(0, Math.min(100, (m / maxMinute) * 100));
            const isBoundary = m === 45 || m === 90 || m === 105 || m === 120;
            return `<div style="position:absolute;left:${pct}%;top:${isBoundary ? ".25rem" : "50%"};bottom:${isBoundary ? ".25rem" : "auto"};height:${isBoundary ? "auto" : ".75rem"};border-left:1px ${isBoundary ? "dashed" : "solid"} var(--timeline-tick);transform:translateX(-50%);"></div>
              <div class="font-mono text-[10px] text-gray-500 whitespace-nowrap" style="position:absolute;left:${pct}%;top:calc(50% + .65rem);transform:translateX(-50%);">${timelineMarkerLabel(m)}</div>`;
          }).join("")}
          ${eventNodes}
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">${detailRows}</div>
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

  const predictedTimeline = buildPredictedTimelineEvents(p);
  if (predictedTimeline.length) {
    html += renderEventTimeline(t("predicted_timeline"), predictedTimeline, f);
  }
  if (tr) {
    const actualTimeline = buildActualTimelineEvents(tr);
    html += actualTimeline.length
      ? renderEventTimeline(t("actual_timeline"), actualTimeline, f, { actual: true })
      : _truthBlock(`<span class="text-gray-400">${t("no_timeline_events")}</span>`);
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

function renderPrematchDetailsPanel(idx) {
  const p = _allPreds[idx] || {};
  const f = _predFixtures[idx] || {};
  const reasoning = p.reasoning || {};
  const scoreDist = (p.score_dist || []).slice().sort((a, b) => (b.p || 0) - (a.p || 0));
  const wp = p.win_probs || winProbsFromScoreDist(scoreDist) || {};
  const wpPct = winProbPctLabels(wp);
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
              <div class="win-prob-value text-base sm:text-lg font-black font-mono text-gray-100">${wpPct[k] || fmtPct(wp[k])}</div>
            </div>`).join("")}
        </div>
      </div>` : ""}

      ${hasReason ? `
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("full_reasoning")}</div>
          <div class="space-y-3">${renderReasoningSections(reasoning)}</div>
        </div>
      ` : ""}
      ${_renderDetails(p, f)}
      <div class="pt-2 border-t border-white/5">
        <button onclick="togglePredPanel(${idx}, 'prematch')" class="chip hover:bg-white/15 transition text-xs">${t("hide_prematch_prediction")}</button>
      </div>
    </div>`;
}

function renderLiveDetailsPanel(idx) {
  const p = _allPreds[idx] || {};
  const f = _predFixtures[idx] || {};
  const livePred = p._live_prediction || null;
  if (!livePred) {
    return `<div class="text-gray-500 text-sm">${t("unavailable_detail")}</div>`;
  }
  return `
    <div class="space-y-4">
      ${renderLivePredictionDetails(livePred, f, { showTimeline: true })}
      <div class="pt-2 border-t border-white/5">
        <button onclick="togglePredPanel(${idx}, 'live')" class="chip hover:bg-white/15 transition text-xs">${t("hide_live_prediction")}</button>
      </div>
    </div>`;
}

function renderPredCard(p, f, idx, opts = {}) {
  const b          = modelBadge(p.model_id);
  const scoreDist  = (p.score_dist || []).slice().sort((a, b) => (b.p || 0) - (a.p || 0));
  const wp         = p.win_probs || winProbsFromScoreDist(scoreDist) || {};
  const top3       = scoreDist.slice(0, 3);
  const predScore  = p.headline_score || p.most_likely_score || (top3[0] ? top3[0].score : null);
  const hName      = f.home || t("home");
  const aName      = f.away || t("away");
  const status     = p.status || "ok";
  const showActualSummary = opts.showActualSummary !== false;
  const extraPrematchButtonAttr = opts.isExtra ? ' data-extra-button="prematch"' : "";
  const extraLiveButtonAttr = opts.isExtra ? ' data-extra-button="live"' : "";
  const extraSourcesButtonAttr = opts.isExtra ? ' data-extra-button="sources"' : "";
  const sourceButtonHtml = p.sources && p.sources.length ? `<button id="pred-sources-btn-${idx}" onclick="toggleSources(${idx})"
                  class="chip pred-action hover:bg-white/15 transition text-[10px]"${extraSourcesButtonAttr} data-source-count="${p.sources.length}">${t("sources", { count: p.sources.length })}</button>` : "";
  const livePred = p._live_prediction || null;

  const scoreWinner = outcomeFromScore(predScore, hName, aName);
  const predWinner = winnerFromWinProbs(wp, hName, aName) || scoreWinner;
  const settingChip = (!_matchmateMode && p.setting)
    ? `<span class="chip chip-${(p.setting || "").toLowerCase()}" data-tip="${esc(settingTip(p.setting))}">${esc(p.setting || "")}</span>`
    : "";
  const headerHtml = `
      <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          ${badgeHtml(b, "text-base")}
          <span class="font-bold text-xs sm:text-sm text-white">${esc(fmtModelId(p))}</span>
          ${settingChip}
        </div>
        ${(!_matchmateMode && p.cost_usd != null) ? `<span class="text-xs text-gray-600">${t("cost")}: $${(+p.cost_usd).toFixed(3)}</span>` : ""}
      </div>`;

  if (status !== "ok") {
    const failed = status === "failed";
    const label = failed ? t("unavailable") : t("not_run");
    const tone = failed
      ? "color:#fca5a5;border-color:rgba(248,113,113,.28);background:rgba(248,113,113,.08);"
      : "color:#cbd5e1;border-color:rgba(148,163,184,.25);background:rgba(148,163,184,.08);";
    const detail = p.error_summary || (failed ? t("unavailable_detail") : t("not_run_detail"));
    return `
    <div class="card rounded-lg p-3 h-full flex flex-col">
      ${headerHtml}
      <div class="rounded-lg px-3 py-2" style="${tone}">
        <div class="text-[10px] uppercase tracking-wider mb-1">${label}</div>
        <div class="text-xs leading-snug">${esc(detail)}</div>
      </div>
    </div>`;
  }

  return `
    <div class="card rounded-lg p-3 h-full flex flex-col">

      <!-- Header -->
      ${headerHtml}

      <!-- Minimalist Prediction -->
      ${predWinner || top3.length || livePred ? `
      <div class="${livePred ? "grid grid-cols-1 sm:grid-cols-2 gap-3" : ""} mb-0 flex-1">
        ${predWinner || top3.length ? `
        <div class="rounded-lg px-3 py-2" style="min-height:6.75rem;display:flex;flex-direction:column;background:${livePred ? "rgba(255,255,255,.035)" : "transparent"};border:${livePred ? "1px solid rgba(255,255,255,.06)" : "0"};">
          <div style="flex:1 1 auto;display:flex;flex-direction:column;">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider">${t("prematch_prediction")}</div>
            <div class="flex items-start gap-3 sm:gap-4 flex-wrap" style="margin-top:auto;margin-bottom:auto;">
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
                  return renderPredictionWinnerLabel(predWinner, f, { color: winnerColor.replace(/^color:/, "").replace(/;$/, ""), sizeClass: "text-2xl" });
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
                <div class="text-xl font-black font-mono leading-tight whitespace-nowrap" style="color:var(--actual-score-color);">${esc(f.truth.score.replace("-", " - ") || "—")}</div>
                <div class="text-xs font-mono" style="color:#fbbf2480;">${esc(
                  f.truth.result === "home" ? hName : f.truth.result === "away" ? aName : f.truth.result === "draw" ? t("draw") : f.truth.result || "—"
                )}</div>
              </div>` : ""}
            </div>
          </div>
          <div class="pt-2 flex items-center gap-2" style="margin-top:auto;">
            <button id="pred-prematch-btn-${idx}" onclick="togglePredPanel(${idx}, 'prematch')"
                    class="chip pred-action hover:bg-white/15 transition text-[10px]"${extraPrematchButtonAttr}>${t("show_prematch_prediction")}</button>
            ${sourceButtonHtml ? `<div class="ml-auto">${sourceButtonHtml}</div>` : ""}
          </div>
        </div>` : ""}
        ${livePred ? renderInlineLivePrediction(livePred, f, { actionIdx: idx, extraButtonAttr: extraLiveButtonAttr }) : ""}
      </div>
      ` : ""}

    </div>`;
}

function renderPredGrid(preds, f, startIdx, groupId, opts = {}) {
  if (!preds.length) return `<div class="text-gray-500 text-sm py-2">${t("no_predictions")}</div>`;
  const mobileFoldTopN = Number(opts.mobileFoldTopN || 0);
  const desktopFoldTopN = Number(opts.desktopFoldTopN || 0);
  const useMobileFold = mobileFoldTopN > 0 && isMobilePredLayout() && preds.length > mobileFoldTopN;
  const useDesktopFold = !isMobilePredLayout() && desktopFoldTopN > 0 && preds.length > desktopFoldTopN;
  const useTopNFold = useMobileFold || useDesktopFold;
  const allowFold = opts.allowFold !== false;
  const indexed = preds.map((p, i) => ({
    pred: p,
    idx: startIdx + i,
    hidden: useMobileFold
      ? i >= mobileFoldTopN
      : useDesktopFold
        ? i >= desktopFoldTopN
        : (allowFold && !useTopNFold && p.default_visible === false),
  }));
  const hiddenCount = allowFold ? indexed.filter(item => item.hidden).length : 0;
  const visibleItems = allowFold ? indexed.filter(item => !item.hidden) : indexed;
  const hiddenItems = allowFold ? indexed.filter(item => item.hidden) : [];

  const renderRows = (items, hiddenRows) => {
    const rows = [];
    const desktopCardsPerRow = Math.max(1, Math.min(4, Number(PREDICTION_CARDS_PER_ROW) || 2));
    const rowSize = isMobilePredLayout() ? 1 : desktopCardsPerRow;
    const gridStyle = isMobilePredLayout()
      ? ""
      : ` style="grid-template-columns:repeat(${rowSize},minmax(0,1fr));"`;
    for (let rowStart = 0; rowStart < items.length; rowStart += rowSize) {
      const cards = items.slice(rowStart, rowStart + rowSize).map(item => `
        <div class="h-full">${renderPredCard(item.pred, f, item.idx, {
          showActualSummary: opts.showActualSummary,
          isExtra: hiddenRows,
        })}</div>
      `).join("");
      rows.push(`
        <div class="${hiddenRows ? "hidden " : ""}space-y-2" data-pred-row="1"${hiddenRows ? ' data-pred-extra-row="1"' : ""}>
          <div class="grid grid-cols-1 gap-2"${gridStyle}>${cards}</div>
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
              class="pred-toggle prominent-toggle hover:bg-white/15 transition mt-3"
              data-hidden-count="${hiddenCount}">${showAllModelsText(hiddenCount)}</button>
    ` : ""}`;
}

function renderPredList(preds, f, startIdx, groupId) {
  return renderPredGrid(preds, f, startIdx, groupId, {
    allowFold: true,
    showActualSummary: false,
    desktopFoldTopN: 4,
    mobileFoldTopN: 4,
  });
}

function renderAllPredCards(preds, f, startIdx) {
  return renderPredGrid(preds, f, startIdx, `pred-grid-${startIdx}`, {
    allowFold: true,
    showActualSummary: true,
    desktopFoldTopN: 4,
    mobileFoldTopN: 4,
  });
}

function renderIncomingPredCards(preds, f, startIdx, groupId) {
  return renderPredGrid(preds, f, startIdx, groupId, {
    allowFold: true,
    showActualSummary: true,
    desktopFoldTopN: 4,
    mobileFoldTopN: 4,
  });
}

function inferredLiveElapsed(live, submittedAt) {
  if (live && live.elapsed != null) {
    const elapsed = Number(live.elapsed);
    return Number.isFinite(elapsed) ? Math.round(elapsed) : null;
  }
  if (!live || live.status === "Not Started" || !live.kickoff_utc || !submittedAt) return null;
  const kickoff = new Date(live.kickoff_utc);
  const submitted = new Date(submittedAt);
  if (Number.isNaN(kickoff.getTime()) || Number.isNaN(submitted.getTime())) return null;
  const delta = Math.floor((submitted.getTime() - kickoff.getTime()) / 60000);
  if (!Number.isFinite(delta) || delta < 0) return null;
  const status = String(live.status || "").toLowerCase();
  if (status.includes("half time") || status.includes("halftime") || status === "ht") return 45;
  if (status.includes("1st") || status.includes("first")) return Math.max(1, Math.min(45, delta));
  if (status.includes("2nd") || status.includes("second")) return Math.max(46, Math.min(90, delta >= 60 ? delta - 15 : delta));
  if (status.includes("extra")) return Math.max(91, Math.min(130, delta - 15));
  // Some providers only expose a generic "In Play" status. If natural elapsed
  // has passed the halftime break, subtract a standard 15 minute interval so
  // the display tracks match clock rather than wall-clock minutes.
  if (status.includes("play") || status.includes("live") || status.includes("progress")) {
    return Math.max(1, Math.min(90, delta > 60 ? delta - 15 : delta));
  }
  return Math.max(1, Math.min(130, delta));
}

function liveMinuteLabel(live, submittedAt) {
  const elapsed = inferredLiveElapsed(live, submittedAt);
  if (elapsed != null) return `${elapsed}′`;
  if (live && live.status === "Not Started") return t("live_pre_match");
  return (live && live.status) ? live.status : t("live");
}

function liveScoreLabel(live) {
  const sc = (live && live.score) || {};
  return `${sc.home ?? "?"}-${sc.away ?? "?"}`;
}

function liveHasKnownScore(live) {
  const sc = (live && live.score) || {};
  return sc.home != null && sc.away != null;
}

function liveSnapshotLabel(live, submittedAt) {
  if (!live) return t("live_unknown_state");
  if (liveHasKnownScore(live)) return liveScoreLabel(live);
  if (live.status === "Not Started") return t("live_pre_match");
  return liveMinuteLabel(live, submittedAt);
}

function liveBasisLabel(live, submittedAt) {
  const state = liveSnapshotLabel(live, submittedAt);
  if (liveHasKnownScore(live)) return t("live_current_score_state", { score: state });
  return t("live_current_state", { state });
}

function liveUpdatedStateLabel(live, submittedAt) {
  const elapsed = inferredLiveElapsed(live, submittedAt);
  if (elapsed != null) return t("live_match_minute", { minute: elapsed });
  return liveSnapshotLabel(live, submittedAt);
}

function livePredictionTitle(item) {
  const live = (item && item.live) || {};
  const elapsed = inferredLiveElapsed(live, item && item.submitted_at);
  if (elapsed != null) return t("latest_live_prediction_minute", { minute: elapsed });
  return t("latest_live_prediction");
}

function liveTeamName(side, f) {
  if (side === "home") return f.home || t("home");
  if (side === "away") return f.away || t("away");
  return side || "—";
}

function attachLivePredictions(preds, livePreds) {
  if (!livePreds || !livePreds.length) return preds || [];
  const byModel = new Map();
  for (const item of livePreds) {
    if (item && item.model_id) byModel.set(item.model_id, item);
  }
  return (preds || []).map(pred => ({
    ...pred,
    _live_prediction: byModel.get(pred.model_id) || null,
  }));
}

function unmatchedLivePredictions(preds, livePreds) {
  const seen = new Set((preds || []).map(p => p.model_id));
  return (livePreds || []).filter(item => item && !seen.has(item.model_id));
}

function livePredictionWinner(item, f) {
  const hName = f.home || t("home");
  const aName = f.away || t("away");
  return winnerFromWinProbs((item && item.win_probs) || {}, hName, aName) || "—";
}

function livePredictionScore(item) {
  const score = item && item.most_likely_score;
  return score ? String(score).replace("-", " - ") : "—";
}

function livePredictionTimestamp(item) {
  return item && item.submitted_at ? fmtLocalKickoff(new Date(item.submitted_at)) : "—";
}

function liveHistoryMinutePrefix(entry) {
  const live = (entry && entry.live) || {};
  const elapsed = inferredLiveElapsed(live, entry && entry.submitted_at);
  if (elapsed != null) return t("live_history_minute_prefix", { minute: elapsed });
  if (live.status === "Not Started") return t("live_history_prematch_prefix");
  return "";
}

function renderInlineLivePrediction(item, f, opts = {}) {
  if (!item) return "";
  if ((item.status || "ok") !== "ok") {
    return `
      <div class="rounded-lg px-3 py-2" style="color:#fca5a5;border:1px solid rgba(248,113,113,.28);background:rgba(248,113,113,.08);">
        <div class="text-[10px] uppercase tracking-wider mb-1">${esc(livePredictionTitle(item))}</div>
        <div class="text-xs leading-snug">${esc(item.error_summary || t("unavailable_detail"))}</div>
      </div>`;
  }
  const live = item.live || {};
  const wp = item.win_probs || {};
  const wpPct = winProbPctLabels(wp);
  const actionIdx = opts.actionIdx;
  const actionButton = actionIdx != null ? `
          <button id="pred-live-btn-${actionIdx}" onclick="togglePredPanel(${actionIdx}, 'live')"
                  class="chip pred-action hover:bg-white/15 transition text-[10px]"${opts.extraButtonAttr || ""}>${t("show_live_prediction")}</button>` : "";
  return `
    <div class="rounded-lg px-3 py-2" style="min-height:9rem;display:flex;flex-direction:column;border:1px solid rgba(248,113,113,.24);background:rgba(248,113,113,.075);">
      <div style="flex:1 1 auto;">
        <div class="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
          <div class="text-[10px] text-gray-400 uppercase tracking-wider">${esc(livePredictionTitle(item))}</div>
          <div class="flex items-center gap-1.5 flex-wrap justify-end">
            <span class="chip chip-live text-[10px]">LIVE</span>
          </div>
        </div>
        <div class="text-[11px] text-gray-500 mb-2">
          ${esc(liveBasisLabel(live, item.submitted_at))}
        </div>
        <div class="flex items-start gap-3 flex-wrap">
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("pred_winner")}</div>
            ${renderPredictionWinnerLabel(livePredictionWinner(item, f), f, { color: "#fca5a5", sizeClass: "text-xl" })}
          </div>
          <div style="width:1px;height:2rem;background:rgba(255,255,255,.14);"></div>
          <div>
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("live_final_score")}</div>
            <div class="text-lg font-black leading-tight font-mono whitespace-nowrap" style="color:#fca5a5;">${esc(livePredictionScore(item))}</div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-1.5 mt-2">
          ${[["home", f.home || t("home")], ["draw", t("draw")], ["away", f.away || t("away")]].map(([key, label]) => `
            <div class="text-center rounded-md px-1.5 py-1" style="background:rgba(255,255,255,.055);">
              <div class="text-[9px] text-gray-500 uppercase tracking-wider truncate">${esc(label)}</div>
              <div class="text-xs font-black font-mono text-gray-100">${wpPct[key] || fmtPct(wp[key])}</div>
            </div>`).join("")}
        </div>
        <div class="text-[10px] text-gray-500 mt-1.5">${esc(t("live_updated_at", { time: livePredictionTimestamp(item) }))}</div>
      </div>
      ${actionButton ? `<div class="pt-2 flex justify-start" style="margin-top:auto;">${actionButton}</div>` : ""}
    </div>`;
}

function livePredictionReasoningText(item) {
  const reasoning = item && item.reasoning;
  if (typeof reasoning === "string") return reasoning.trim();
  if (reasoning && typeof reasoning === "object") {
    return String(reasoning.overall || reasoning.summary || reasoning.analysis || "").trim();
  }
  return "";
}

function renderLivePredictionHistoryList(item, f) {
  if (!item) return "";
  const rawHistory = item.history && item.history.length ? item.history : [item];
  const history = rawHistory.filter(Boolean);
  if (!history.length) return "";
  return `
    <div>
      <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("live_prediction_history")}</div>
      <div class="space-y-1.5 pr-1" style="max-height:26rem;overflow-y:auto;">
        ${history.map(entry => {
          const status = entry.status || "ok";
          const basis = liveBasisLabel(entry.live || {}, entry.submitted_at);
          const minutePrefix = liveHistoryMinutePrefix(entry);
          const reasoning = livePredictionReasoningText(entry);
          if (status !== "ok") {
            return `
              <div class="rounded-lg px-3 py-2 text-xs" style="color:#fca5a5;background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.2);">
                ${minutePrefix ? `<span class="font-semibold text-gray-200">${esc(minutePrefix)}</span>` : ""}
                <span class="font-mono text-gray-400">${esc(livePredictionTimestamp(entry))}</span>
                <span class="mx-1">·</span>${esc(entry.error_summary || t("unavailable_detail"))}
              </div>`;
          }
          return `
            <div class="rounded-lg px-3 py-2 text-xs" style="background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.06);">
              <div>${minutePrefix ? `<span class="font-semibold text-gray-200">${esc(minutePrefix)}</span>` : ""}${esc(t("live_history_item", {
                time: livePredictionTimestamp(entry),
                basis,
                score: livePredictionScore(entry),
                winner: livePredictionWinner(entry, f),
              }))}</div>
              ${reasoning ? `<div class="mt-2 pt-2 border-t border-white/5"><div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">${t("full_reasoning")}</div><div class="text-xs leading-relaxed text-gray-300">${renderMarkdownText(reasoning)}</div></div>` : ""}
            </div>`;
        }).join("")}
      </div>
    </div>`;
}

function defaultLiveFutureGoalMinute(index, total, elapsed) {
  const start = Math.max(1, Number(elapsed) || 0);
  const spanStart = Math.min(84, start + 8);
  const spanEnd = start < 45 ? 88 : 118;
  const slots = Math.max(1, total + 1);
  return normalizeMinute(Math.min(spanEnd, Math.round(spanStart + ((index + 1) * (spanEnd - spanStart)) / slots)));
}

function livePredictionGoalMinute(item, scorer, index, total) {
  const elapsed = inferredLiveElapsed((item && item.live) || {}, item && item.submitted_at) || 0;
  let minute = eventMinute(scorer);
  if (minute == null) minute = defaultLiveFutureGoalMinute(index, total, elapsed);
  minute = normalizeMinute(minute);
  if (minute <= elapsed) minute = normalizeMinute(Math.min(130, elapsed + 5 + index * 7));
  return minute;
}

function buildLivePredictionTimelineEvents(item) {
  if (!item) return [];
  const live = item.live || {};
  const current = live.score || {};
  const final = parseScore(item.most_likely_score);
  const scorers = (item.scorers || []).filter(Boolean);
  const events = [];
  const used = new Set();

  for (const side of ["home", "away"]) {
    const finalGoals = final ? Math.max(0, Number(final[side]) || 0) : null;
    const currentGoals = Math.max(0, Number(current[side]) || 0);
    const needed = finalGoals == null
      ? scorers.filter(s => (s.team === side)).length
      : Math.max(0, finalGoals - currentGoals);
    if (!needed) continue;

    const sideScorers = scorers
      .map((s, originalIndex) => ({ ...s, originalIndex }))
      .filter(s => s.team === side)
      .sort((a, b) => (eventMinute(a) ?? 999) - (eventMinute(b) ?? 999) || ((b.p || 0) - (a.p || 0)));

    for (let i = 0; i < needed; i += 1) {
      const scorer = sideScorers[i] || {};
      if (scorer.originalIndex != null) used.add(scorer.originalIndex);
      events.push({
        type: "goal",
        side,
        minute: livePredictionGoalMinute(item, scorer, i, needed),
        player: scorer.player || scorer.name || t("unspecified_goal"),
        p: scorer.p ?? null,
      });
    }
  }

  if (!final) {
    scorers.forEach((s, i) => {
      if (used.has(i) || !s.team) return;
      events.push({
        type: "goal",
        side: s.team,
        minute: livePredictionGoalMinute(item, s, i, scorers.length),
        player: s.player || s.name || t("unspecified_goal"),
        p: s.p ?? null,
      });
    });
  }

  return events.sort(timelineSort);
}

function renderLivePredictionTimeline(item, f) {
  const events = buildLivePredictionTimelineEvents(item);
  return events.length
    ? renderEventTimeline(t("predicted_timeline"), events, f)
    : _truthBlock(`<span class="text-gray-400">${t("no_timeline_events")}</span>`);
}

function renderLivePredictionDetails(item, f, opts = {}) {
  if (!item) return "";
  const plainShell = opts.showTimeline;
  const shellClass = plainShell ? "space-y-3" : "rounded-xl p-3 sm:p-4";
  const shellStyle = plainShell ? "" : ' style="background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.18);"';
  return `
    <div class="${shellClass}"${shellStyle}>
      ${renderInlineLivePrediction(item, f)}
      <div>${renderLivePredictionHistoryList(item, f)}</div>
    </div>`;
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
          const wpPct = winProbPctLabels(wp);
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
                    ${badgeHtml(b)}
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
                  ${badgeHtml(b)}
                  <span class="font-bold text-xs sm:text-sm text-white truncate">${esc(fmtModelId(p))}</span>
                  <span class="chip chip-live">LIVE</span>
                </div>
                ${(!_matchmateMode && p.cost_usd != null) ? `<span class="text-xs text-gray-600 whitespace-nowrap">${t("cost")}: $${(+p.cost_usd).toFixed(3)}</span>` : ""}
              </div>
              <div class="text-[11px] text-gray-500 mb-2">
                ${esc(liveBasisLabel(live, p.submitted_at))}
                <span class="mx-1">·</span>${esc(t("live_updated_at", { time: updated }))}
              </div>
              <div class="grid grid-cols-3 gap-2 mb-3">
                ${[["home", hName], ["draw", t("draw")], ["away", aName]].map(([key, label]) => `
                  <div class="rounded-lg px-2 py-2 text-center" style="background:rgba(255,255,255,.055);">
                    <div class="text-[10px] text-gray-500 uppercase tracking-wider truncate">${esc(label)}</div>
                    <div class="text-lg font-black font-mono text-gray-100">${wpPct[key] || fmtPct(wp[key])}</div>
                  </div>
                `).join("")}
              </div>
              <div class="flex items-start gap-4 flex-wrap mb-3">
                <div>
                  <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">${t("pred_winner")}</div>
                  ${renderPredictionWinnerLabel(predWinner, f, { color: "var(--prediction-primary)", sizeClass: "text-xl" })}
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
              ${reasoning ? `<div class="text-sm text-gray-300 leading-relaxed mb-3">${renderMarkdownText(reasoning)}</div>` : ""}
              ${renderLivePredictionHistoryList(p, f)}
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

// ---------- Full tournament predictions --------------------------------------

const WORLD_CUP_2026_LOGO = "https://upload.wikimedia.org/wikipedia/en/thumb/1/17/2026_FIFA_World_Cup_emblem.svg/250px-2026_FIFA_World_Cup_emblem.svg.png";
const TOURNAMENT_TEAM_ALIASES = {
  england: { zh: "英格兰", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  eng: { zh: "英格兰", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  scotland: { zh: "苏格兰", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}" },
  sco: { zh: "苏格兰", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}" },
};

function tournamentLocalization() {
  return (_siteData?.tournament_predictions?.name_localization) || { teams: {}, players: {} };
}

function tournamentStageLabel(stage) {
  return t(`tournament_stage_${stage}`) || stage || "—";
}

function tournamentRawTeamName(team) {
  return typeof team === "string" ? team : (team && (team.name || team.team)) || "—";
}

function tournamentTeamAlias(team) {
  const raw = tournamentRawTeamName(team);
  const id = typeof team === "object" && team ? String(team.id || team.team_id || "") : "";
  const values = [raw, id].map(value => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]/g, "")
    .toLowerCase()
  ).filter(Boolean);
  if (values.some(value => value === "england" || value === "eng" || value.startsWith("england") || value.startsWith("eng"))) return TOURNAMENT_TEAM_ALIASES.england;
  if (values.some(value => value === "scotland" || value === "sco" || value.startsWith("scotland") || value.startsWith("sco"))) return TOURNAMENT_TEAM_ALIASES.scotland;
  return null;
}

function tournamentTeamName(team) {
  const raw = tournamentRawTeamName(team);
  const alias = tournamentTeamAlias(team);
  if (alias) return alias.zh;
  return tournamentLocalization().teams?.[raw] || raw;
}

let _tplIndexKey = null, _tplIndex = null;
function _tournamentPlayerIndex(players) {
  if (_tplIndexKey === players && _tplIndex) return _tplIndex;
  const byNorm = new Map(), byPlain = new Map();
  for (const [key, item] of Object.entries(players)) {
    const nk = _normName(key), pk = _plainNameForMatch(key).toLowerCase();
    if (!byNorm.has(nk)) byNorm.set(nk, { raw: key, item });
    if (!byPlain.has(pk)) byPlain.set(pk, { raw: key, item });
  }
  _tplIndexKey = players; _tplIndex = { byNorm, byPlain };
  return _tplIndex;
}
function tournamentPlayerInfo(name) {
  const raw = String(name || "").trim();
  const players = tournamentLocalization().players || {};
  if (players[raw]) return { raw, ...players[raw], zh: players[raw].zh || raw };
  const idx = _tournamentPlayerIndex(players);
  const hit = idx.byNorm.get(_normName(raw)) || idx.byPlain.get(_plainNameForMatch(raw).toLowerCase());
  if (hit) return { raw: hit.raw, ...hit.item, zh: hit.item.zh || raw };
  return { raw, zh: raw, photo: "" };
}

function tournamentCleanPlayerName(name) {
  return String(name || "—").replace(/[（(][^（）()]*[）)]/g, "").replace(/\s+/g, " ").trim() || "—";
}

function tournamentPlayerName(name) {
  return tournamentCleanPlayerName(tournamentPlayerInfo(name).zh || String(name || "—"));
}

function tournamentTeamFlag(team) {
  const alias = tournamentTeamAlias(team);
  if (alias) return alias.flag;
  return typeof team === "object" && team ? (team.flag || "") : "";
}

function tournamentTeamHtml(team, opts = {}) {
  const flag = tournamentTeamFlag(team);
  const name = tournamentTeamName(team);
  const raw = tournamentRawTeamName(team);
  const title = raw && raw !== name ? ` title="${esc(raw)}"` : "";
  const align = opts.align === "right" ? "justify-end text-right" : "";
  return `<span class="inline-flex items-center gap-1.5 min-w-0 ${align}"${title}>${(typeof team==="object"&&team&&team.flag_img)?`<img src="${esc(team.flag_img)}" alt="" loading="lazy" class="shrink-0" style="height:1em;width:auto;border-radius:2px;">`:(flag?`<span class="shrink-0">${esc(flag)}</span>`:"")}<span class="truncate">${esc(name)}</span></span>`;
}

function tournamentScoreText(score) {
  return String(score || "—").replace("-", " - ");
}

function tournamentDeciderText(decider) {
  return String(decider || "").toUpperCase() === "PEN" ? t("tournament_penalty_shootout") : "";
}

function tournamentMatchTeam(match, side) {
  if (side === "away") return tournamentTeamName(match.away);
  if (side === "home") return tournamentTeamName(match.home);
  return tournamentTeamName(side);
}

function tournamentScorerRows(match) {
  const scorers = match.scorers || [];
  return scorers.map(s => ({
    team: tournamentMatchTeam(match, s.team),
    player: tournamentPlayerName(s.player || t("unspecified_goal")),
    minute: s.minute != null ? `${s.minute}′` : "",
  }));
}

function tournamentScorersText(match) {
  const rows = tournamentScorerRows(match);
  if (!rows.length) return t("tournament_no_scorers");
  return rows.map(row => `${row.team}: ${row.player}${row.minute ? ` ${row.minute}` : ""}`).join("；");
}

function renderTournamentScorersTooltip(match, opts = {}) {
  const rows = tournamentScorerRows(match);
  const placement = opts.placement === "left" ? "right-0" : "left-0";
  const vertical = opts.vertical === "up" ? "bottom-5" : "top-5";
  return `<span class="relative inline-flex group shrink-0">
    <button type="button" class="inline-flex items-center justify-center rounded-full text-[9px] font-bold text-gray-400 transition hover:text-gray-200" style="width:.9rem;height:.9rem;border:1px solid rgba(148,163,184,.28);background:rgba(148,163,184,.09);" aria-label="${esc(t("tournament_scorers_label"))}">i</button>
    <span class="hidden group-hover:block group-focus-within:block absolute ${placement} ${vertical} z-50 w-56 rounded-lg p-2 text-left" style="background:var(--tooltip-bg);border:1px solid var(--tooltip-border);box-shadow:0 18px 48px rgba(0,0,0,.22);">
      <span class="block text-[10px] uppercase tracking-wider mb-1" style="color:var(--tooltip-title);">${t("tournament_scorers_label")}</span>
      ${rows.length ? rows.map(row => `<span class="block text-[11px] leading-snug" style="color:var(--tooltip-text);"><span style="color:var(--tooltip-text);">${esc(row.team)}</span>：${esc(row.player)}${row.minute ? ` <span style="color:var(--tooltip-muted);">${esc(row.minute)}</span>` : ""}</span>`).join("") : `<span class="block text-[11px]" style="color:var(--tooltip-muted);">${t("tournament_no_scorers")}</span>`}
    </span>
  </span>`;
}

function toggleTournamentPrediction(idx) {
  const panel = document.getElementById(`tournament-detail-${idx}`);
  const btn = document.getElementById(`tournament-toggle-${idx}`);
  if (!panel || !btn) return;
  const willShow = panel.classList.contains("hidden");
  if (willShow && !panel.dataset.rendered) {
    const p = ((_siteData && _siteData.tournament_predictions && _siteData.tournament_predictions.predictions) || [])[idx];
    if (p) { panel.innerHTML = renderTournamentDetails(p); panel.dataset.rendered = "1"; }
  }
  panel.classList.toggle("hidden", !willShow);
  btn.textContent = willShow ? t("tournament_hide_path") : t("tournament_show_path");
}

function renderTournamentSummaryBlock(p) {
  const champion = p.champion || null;
  const runnerUp = p.runner_up || null;
  const thirdPlace = p.third_place || null;
  return `
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
      ${[["tournament_champion", champion, "text-gray-100"], ["tournament_runner_up", runnerUp, "text-gray-100"], ["tournament_third_place", thirdPlace, "text-gray-100"]].map(([labelKey, team, color]) => `
        <div class="rounded-lg px-3 py-2" style="background:var(--soft-surface-bg-strong);border:1px solid var(--soft-surface-border);">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">${t(labelKey)}</div>
          <div class="font-black text-lg ${color} min-w-0">${team ? tournamentTeamHtml(team) : "—"}</div>
        </div>`).join("")}
    </div>`;
}

function tournamentMatchesByNumber(matches) {
  const out = {};
  for (const match of matches || []) out[Number(match.match_no)] = match;
  return out;
}

function tournamentBracketTeamLine(match, side) {
  const team = side === "away" ? match.away : match.home;
  const score = parseScore(match.score || "0-0");
  const goals = side === "away" ? score.away : score.home;
  const winnerSide = match.winner_side || (tournamentRawTeamName(match.winner) === tournamentRawTeamName(team) ? side : "");
  const active = winnerSide === side;
  return `<div class="flex items-center justify-between gap-2 ${active ? "text-white" : "text-gray-400"}">
    <span class="min-w-0 text-[11px] font-semibold ${active ? "font-black" : ""}">${tournamentTeamHtml(team)}</span>
    <span class="font-mono text-xs ${active ? "text-green-300" : "text-gray-500"}">${Number.isFinite(goals) ? goals : "—"}</span>
  </div>`;
}

function tournamentBracketCard(match, opts = {}) {
  if (!match) return `<div class="rounded-md border border-white/5 bg-white/[.025]" style="height:${opts.small ? "3rem" : "3.75rem"};"></div>`;
  const decider = tournamentDeciderText(match.decider);
  return `<div class="rounded-md px-2 py-1.5" style="background:var(--tournament-bracket-card-bg);border:1px solid var(--tournament-bracket-card-border);box-shadow:var(--tournament-bracket-card-shadow);min-height:${opts.small ? "3.15rem" : "3.75rem"};">
    <div class="flex items-center justify-between gap-1 mb-1">
      <span class="text-[9px] uppercase tracking-wider" style="color:var(--tournament-bracket-stage);">${esc(tournamentStageLabel(match.stage))}</span>
      ${renderTournamentScorersTooltip(match, { placement: opts.tooltipPlacement || "left", vertical: opts.tooltipVertical || "down" })}
    </div>
    <div class="space-y-0.5">
      ${tournamentBracketTeamLine(match, "home")}
      ${tournamentBracketTeamLine(match, "away")}
    </div>
    ${decider ? `<div class="text-[10px] mt-0.5" style="color:var(--tournament-bracket-decider);">${esc(decider)}</div>` : ""}
  </div>`;
}

function renderTournamentBracketColumn(label, matchNos, slots, byNo, opts = {}) {
  return `<div class="flex flex-col gap-1 min-w-0">
    <div class="text-center text-[10px] uppercase tracking-wider text-lime-200/70 h-4">${esc(label || "")}</div>
    <div class="grid gap-1" style="grid-template-rows:repeat(16,minmax(1.8rem,1fr));height:34rem;">
      ${matchNos.map((no, i) => `<div style="grid-row:${slots[i]} / span 2;align-self:center;">${tournamentBracketCard(byNo[no], { tooltipPlacement: opts.tooltipPlacement || "left", tooltipVertical: slots[i] >= 12 ? "up" : "down" })}</div>`).join("")}
    </div>
  </div>`;
}

function renderTournamentBracketCenter(final, third) {
  return `<div class="flex flex-col gap-1 min-w-0">
    <div class="h-4"></div>
    <div class="grid gap-1" style="grid-template-rows:repeat(16,minmax(1.8rem,1fr));height:34rem;">
      <div style="grid-row:7 / span 2;align-self:center;transform:translateY(-.75rem);">${tournamentBracketCard(final, { tooltipPlacement: "left" })}</div>
      ${third ? `<div style="grid-row:10 / span 2;align-self:center;transform:translateY(-.75rem);">${tournamentBracketCard(third, { small: true, tooltipPlacement: "left", tooltipVertical: "up" })}</div>` : ""}
    </div>
  </div>`;
}

function renderTournamentBracket(p) {
  const byNo = tournamentMatchesByNumber(p.knockout_matches || []);
  const r32Slots = [1,3,5,7,9,11,13,15];
  const r16Slots = [2,6,10,14];
  const qfSlots = [4,12];
  const sfSlots = [8];
  const columns = [
    { label: tournamentStageLabel("R32"), matches: [73,75,74,77,83,84,81,82], slots: r32Slots, tooltipPlacement: "right" },
    { label: tournamentStageLabel("R16"), matches: [89,90,93,94], slots: r16Slots, tooltipPlacement: "right" },
    { label: tournamentStageLabel("QF"), matches: [97,98], slots: qfSlots, tooltipPlacement: "right" },
    { label: tournamentStageLabel("SF"), matches: [101], slots: sfSlots, tooltipPlacement: "right" },
    { center: true },
    { label: tournamentStageLabel("SF"), matches: [102], slots: sfSlots, tooltipPlacement: "left" },
    { label: tournamentStageLabel("QF"), matches: [99,100], slots: qfSlots, tooltipPlacement: "left" },
    { label: tournamentStageLabel("R16"), matches: [91,92,95,96], slots: r16Slots, tooltipPlacement: "left" },
    { label: tournamentStageLabel("R32"), matches: [76,78,79,80,86,88,85,87], slots: r32Slots, tooltipPlacement: "left" },
  ];
  const final = byNo[104];
  const third = byNo[103];
  const champion = p.champion || final?.winner;
  return `
    <div>
      <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("tournament_knockout")}</div>
      <div class="overflow-x-auto rounded-xl" style="background:linear-gradient(180deg,#15203a 0%,#4b1168 58%,#742099 100%);border:1px solid rgba(255,255,255,.12);">
        <div class="p-4 sm:p-5 relative" style="min-width:960px;min-height:43rem;">
          <div class="absolute left-4 top-4 flex items-center gap-2">
            <img src="${WORLD_CUP_2026_LOGO}" alt="FIFA World Cup 2026" style="height:3.4rem;width:auto;object-fit:contain;" onerror="this.style.display='none'" />
            <div class="text-xs font-black leading-tight" style="color:#fff;">FIFA WORLD CUP<br><span style="color:#d9f99d;">2026</span></div>
          </div>
          <div class="absolute right-4 top-4 flex items-center gap-2 text-right">
            <div>
              <div class="text-xs font-black" style="color:#fff;">MatchMate AI 预测</div>
              <div class="text-[11px]" style="color:#ecfccb;">模型：${esc(fmtModelId(p))}</div>
              <div class="text-[10px]" style="color:#e5e7eb;">www.matchmate.tv/predict</div>
            </div>
            <img src="matchmate_logo_white.png" alt="MatchMate" style="height:4.4rem;width:4.4rem;object-fit:contain;border-radius:.8rem;background:#050816;padding:.28rem;" onerror="this.style.display='none'" />
          </div>
          <div class="absolute inset-x-0 top-16 text-center pointer-events-none">
            <div class="text-[11px] uppercase tracking-[.22em]" style="color:#d9f99d;">${t("tournament_bracket_champion")}</div>
            <div class="text-3xl font-black mt-1" style="color:#fff;">${champion ? tournamentTeamHtml(champion) : "—"}</div>
          </div>
          <div class="grid gap-2 pt-28" style="grid-template-columns:1fr .92fr .84fr .78fr .98fr .78fr .84fr .92fr 1fr;align-items:stretch;">
            ${columns.map(col => col.center
              ? renderTournamentBracketCenter(final, third)
              : renderTournamentBracketColumn(col.label, col.matches, col.slots, byNo, { tooltipPlacement: col.tooltipPlacement })
            ).join("")}
          </div>
        </div>
      </div>
    </div>`;
}

function renderTournamentGroupMatchList(matches) {
  if (!matches || !matches.length) return "";
  return `<div class="mt-3 pt-3 border-t border-white/5 space-y-2">
    ${[...matches].sort((a,b) => (a.match_no || 0) - (b.match_no || 0)).map(match => `
      <div class="text-xs leading-snug">
        <div class="flex items-center gap-2 min-w-0">
          <span class="truncate flex-1 text-right">${esc(tournamentTeamName(match.home))}</span>
          <span class="font-mono font-black text-gray-100 w-14 text-center">${esc(tournamentScoreText(match.score))}</span>
          <span class="truncate flex-1">${esc(tournamentTeamName(match.away))}</span>
          ${renderTournamentScorersTooltip(match, { placement: "left" })}
        </div>
      </div>`).join("")}
  </div>`;
}

function renderTournamentStandings(standings, matches) {
  const groups = Object.keys(standings || {}).sort();
  if (!groups.length) return "";
  const byGroup = {};
  for (const match of matches || []) (byGroup[match.group] = byGroup[match.group] || []).push(match);
  return `
    <div>
      <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("tournament_standings")}</div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
        ${groups.map(group => `
          <div class="rounded-lg p-3" style="background:var(--soft-surface-bg);border:1px solid var(--soft-surface-border);">
            <div class="font-bold text-sm text-white mb-2">${t("tournament_group", { group })}</div>
            <table class="w-full text-xs">
              <thead class="text-gray-500"><tr>
                <th class="text-left font-normal py-1">#</th>
                <th class="text-left font-normal py-1">${t("team")}</th>
                <th class="text-right font-normal py-1">${t("tournament_pts")}</th>
                <th class="text-right font-normal py-1">${t("tournament_gd")}</th>
                <th class="text-right font-normal py-1">${t("tournament_gf")}</th>
                <th class="text-right font-normal py-1">${t("tournament_ga")}</th>
              </tr></thead>
              <tbody>
                ${(standings[group] || []).map(row => `
                  <tr class="border-t border-white/5">
                    <td class="py-1 font-mono text-gray-500">${esc(row.rank)}</td>
                    <td class="py-1 font-semibold text-gray-200 min-w-0">${tournamentTeamHtml(row)}</td>
                    <td class="py-1 text-right font-mono text-white">${esc(row.points)}</td>
                    <td class="py-1 text-right font-mono">${esc(row.goal_difference)}</td>
                    <td class="py-1 text-right font-mono">${esc(row.goals_for)}</td>
                    <td class="py-1 text-right font-mono">${esc(row.goals_against)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
            ${renderTournamentGroupMatchList(byGroup[group] || [])}
          </div>`).join("")}
      </div>
    </div>`;
}

function renderTournamentTopScorers(rows) {
  if (!rows || !rows.length) return "";
  return `
    <div>
      <div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("tournament_top_scorers")}</div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        ${rows.slice(0, 5).map((row, i) => {
          const info = tournamentPlayerInfo(row.player);
          const photo = info.photo || "";
          const displayName = tournamentCleanPlayerName(info.zh || row.player);
          return `
          <div class="rounded-lg px-3 py-2 flex items-center justify-between gap-3" style="background:var(--soft-surface-bg);border:1px solid var(--soft-surface-border);">
            <div class="flex items-center gap-2 min-w-0">
              <div class="shrink-0 rounded-full overflow-hidden flex items-center justify-center font-black text-xs" style="width:2.35rem;height:2.35rem;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);">
                ${photo ? `<img src="${esc(photo)}" alt="${esc(displayName)}" style="width:100%;height:100%;object-fit:cover;"/>` : `<span>${i + 1}</span>`}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-bold text-gray-100 truncate">${esc(displayName)}</div>
                <div class="text-[11px] text-gray-500 truncate">${esc(tournamentTeamName(row.team || info.team || ""))}</div>
              </div>
            </div>
            <div class="font-mono font-black text-lg text-white whitespace-nowrap">${esc(row.goals)} <span class="text-xs text-gray-500">${t("tournament_goals")}</span></div>
          </div>`;
        }).join("")}
      </div>
    </div>`;
}

function renderTournamentDetails(p) {
  const summaries = p.summary || {};
  const notes = [summaries.group_stage, summaries.knockout].filter(Boolean).join("\n\n");
  return `
    <div class="mt-4 space-y-5">
      ${notes ? `<div><div class="text-xs text-gray-400 uppercase tracking-wider mb-2">${t("tournament_reasoning")}</div><div class="text-sm text-gray-300 leading-relaxed">${renderMarkdownText(notes)}</div></div>` : ""}
      ${renderTournamentBracket(p)}
      ${renderTournamentStandings(p.group_standings || {}, p.group_matches || [])}
      ${renderTournamentTopScorers(p.top_scorers || [])}
    </div>`;
}

function renderTournamentPredictions(data) {
  const el = document.getElementById("tournament-container");
  if (!el) return;
  const preds = (data && data.predictions) || [];
  if (!preds.length) {
    el.innerHTML = `<div class="text-gray-400 text-sm">${t("no_tournament_predictions")}</div>`;
    return;
  }
  el.innerHTML = `
    <div class="grid grid-cols-1 gap-3">
      ${preds.map((p, idx) => {
        const b = modelBadge(p.model_id);
        const status = p.status || "ok";
        if (status !== "ok") {
          return `<div class="card rounded-xl p-4">
            <div class="flex items-center gap-2 mb-2">${badgeHtml(b)}<span class="font-bold text-white">${esc(fmtModelId(p))}</span></div>
            <div class="rounded-lg px-3 py-2 text-sm" style="color:#fca5a5;border:1px solid rgba(248,113,113,.28);background:rgba(248,113,113,.08);">${esc(p.error_summary || t("unavailable_detail"))}</div>
          </div>`;
        }
        return `<div class="card rounded-xl p-4">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div class="flex items-center gap-2 min-w-0">
              ${badgeHtml(b)}
              <span class="font-bold text-white truncate">${esc(fmtModelId(p))}</span>
              ${(!_matchmateMode && p.setting) ? `<span class="chip chip-${String(p.setting).toLowerCase()}">${esc(p.setting)}</span>` : ""}
            </div>
            <button id="tournament-toggle-${idx}" onclick="toggleTournamentPrediction(${idx})" class="chip chip-live hover:bg-white/15 transition text-xs justify-center py-1.5 px-3">${t("tournament_show_path")}</button>
          </div>
          <div class="mt-3">${renderTournamentSummaryBlock(p)}</div>
          <div id="tournament-detail-${idx}" class="hidden"></div>
        </div>`;
      }).join("")}
    </div>`;
}

// ---------- Incoming matches -------------------------------------------------

function _renderOneFixture(nm, cardIdx) {
  const f     = nm.fixture;
  const kick  = f.kickoff_utc ? new Date(f.kickoff_utc) : null;
  const cid   = `nm-countdown-${cardIdx}`;
  const fixtureId = `incoming-match-${cardIdx}`;
  const basePreds = nm.predictions || [];
  const livePreds = nm.live_predictions || [];
  const preds = attachLivePredictions(basePreds, livePreds);
  const standaloneLivePreds = unmatchedLivePredictions(preds, livePreds);
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
  const aggPct = winProbPctLabels(agg);

  const centerMiddle = isMatchLive
    ? `<div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-3xl font-black font-mono" style="color:#f87171;">${lv.score ? `${lv.score.home ?? "?"} – ${lv.score.away ?? "?"}` : "?–?"}</div>
       <div class="text-xs font-semibold" style="color:#fca5a5;">${t("live_red")}${lv.elapsed != null ? ` · ${lv.elapsed}′` : ""}</div>
       ${renderVenueLocation(f)}`
    : `${kick ? `<div class="text-xs text-gray-300 font-medium mb-1">${fmtLocalKickoff(kick)}</div>` : ""}
       <div class="text-gray-400 text-xs">${esc(f.competition || "")}${f.stage ? ` · ${esc(f.stage)}` : ""}</div>
       <div class="mt-1 text-2xl font-black">${t("vs")}</div>
       ${nP > 0 ? `<div class="text-xs text-gray-400">${t("draw_prob", { pct: aggPct.draw || fmtPct(agg.draw) })}</div>` : ""}
       <div class="text-xs text-gray-400 mt-1" id="${cid}">${kick ? "" : "—"}</div>
       ${renderVenueLocation(f)}`;

  const html = `
    <div id="${fixtureId}" class="card rounded-2xl p-4 sm:p-6 mobile-anchor">
      <div class="pitch rounded-xl p-3 sm:p-5 mb-4 sm:mb-6">
        <div class="grid grid-cols-3 items-center gap-2">
          <div class="text-center">
            ${f.home_logo ? `<img src="${esc(f.home_logo)}" alt="${esc(f.home)}" class="fixture-logo"/>` : `<div class="text-4xl">🏠</div>`}
            <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(f.home || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">${t("win", { pct: aggPct.home || fmtPct(agg.home) })}</div>` : ""}
          </div>
          <div class="text-center">${centerMiddle}</div>
          <div class="text-center">
            ${f.away_logo ? `<img src="${esc(f.away_logo)}" alt="${esc(f.away)}" class="fixture-logo"/>` : `<div class="text-4xl">🛫</div>`}
            <div class="team-name font-bold text-sm sm:text-lg leading-tight">${esc(f.away || "?")}</div>
            ${nP > 0 ? `<div class="text-xs text-gray-400">${t("win", { pct: aggPct.away || fmtPct(agg.away) })}</div>` : ""}
          </div>
        </div>
      </div>
      ${renderUserPredictionEditor(nm)}
      ${renderLivePredictions(standaloneLivePreds, f)}
      ${preds.length === 0
        ? (livePreds.length ? "" : `<div class="text-gray-400 text-sm">${t("no_model_predictions")}</div>`)
        : renderIncomingPredCards(preds, f, nmStart, `pred-group-incoming-${nmStart}`)}
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
      if (diff <= 0) {
        el2.textContent = Math.abs(diff) > 135 * 60000 ? t("awaiting_result") : t("live");
        return;
      }
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

// Knockout membership is keyed on the immutable wca_id slug (same rule as
// build_site.py), not on the localized/nullable stage text.
function isKnockoutWcaId(wcaId) {
  const id = String(wcaId || "");
  return id.startsWith("World-Cup_") && !id.includes("_Group-Stage");
}

function activeLeaderboardData() {
  if (_leaderboardScope === "knockout" && _siteData && _siteData.leaderboard_knockout) {
    return _siteData.leaderboard_knockout;
  }
  return (_siteData && _siteData.leaderboard) || { main: [] };
}

function updateLeaderboardScopeControls() {
  const wrap = document.getElementById("leaderboard-scope");
  if (!wrap) return;
  // Old data JSON without the knockout slice ⇒ keep the toggle hidden, board as before.
  const hasKnockout = Boolean(_siteData && _siteData.leaderboard_knockout);
  if (!hasKnockout) _leaderboardScope = "all";
  wrap.classList.toggle("hidden", !hasKnockout);
  const allBtn = document.getElementById("leaderboard-scope-all");
  const koBtn = document.getElementById("leaderboard-scope-knockout");
  if (allBtn) allBtn.classList.toggle("active", _leaderboardScope === "all");
  if (koBtn) koBtn.classList.toggle("active", _leaderboardScope === "knockout");
}

function setLeaderboardScope(scope) {
  const next = scope === "knockout" ? "knockout" : "all";
  if (next === "knockout" && !(_siteData && _siteData.leaderboard_knockout)) return;
  if (next === _leaderboardScope) return;
  _leaderboardScope = next;
  updateLeaderboardScopeControls();
  renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
}

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
  renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
}

function renderLeaderboard(lb, view) {
  const el   = document.getElementById("leaderboard-container");
  const baseRows = lb.main || [];
  const rows = view === "main"
    ? sortLeaderboardRows(withCurrentUserLeaderboardRow(baseRows))
    : sortLeaderboardRows(baseRows);
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
              const settingBadges = r.is_user
                ? `<span class="chip">${esc(t("user_leaderboard_exact", { correct: r.score_correct || 0, total: r.score_total || 0 }))}</span>`
                : (_matchmateMode ? "" : settings.map(s =>
                  `<span class="chip chip-${s.toLowerCase()}"
                         data-tip="${esc(settingTip(s))}">${esc(s)}</span>`
                ).join(" "));
              return `
                <tr class="border-t border-white/5 hover:bg-white/5 transition"${r.is_user ? ' style="background:rgba(34,197,94,.055);"' : ""}>
                  <td class="leaderboard-rank-cell py-2 px-3"><span class="rank-medal ${medal}">${i + 1}</span></td>
                  <td class="py-2 px-3">
                    <div class="leaderboard-model-row flex items-center gap-2">
                      ${badgeHtml(b, "shrink-0")}
                      <span class="leaderboard-model-name font-bold text-white">${esc(fmtModelId(r))}</span>
                      ${settingBadges ? `<span class="leaderboard-setting-badges inline-flex items-center gap-1 flex-wrap">${settingBadges}</span>` : ""}
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
      renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
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
      : `<div class="text-3xl font-black font-mono" style="color:var(--actual-score-color);">${esc((r.result || "—").replace("-", " – "))}</div>`;

    const hStart = registerPreds(preds, r);

    const predCards = renderPredList(preds, r, hStart, `pred-group-history-${hStart}`);
    const collapsedByDefault = rowIdx >= 3;
    const compactMobileSummary = isMobilePredLayout() && collapsedByDefault;
    const mobileScoreboard = compactMobileSummary ? `
          <div class="mobile-history-scoreboard mt-3 md:hidden">
            <div class="grid grid-cols-3 items-center gap-2">
              <div class="text-center min-w-0">
                ${r.home_logo ? `<img src="${esc(r.home_logo)}" alt="${esc(r.home)}" class="fixture-logo fixture-logo-sm"/>` : `<div class="text-2xl">🏠</div>`}
                <div class="team-name text-xs font-bold leading-tight">${esc(r.home || "?")}</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-black font-mono" style="color:var(--actual-score-color);">${esc((r.result || "—").replace("-", " – "))}</div>
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
      <details id="history-match-${rowIdx}"${collapsedByDefault ? "" : " open"} class="card rounded-xl p-4 col-span-2 mobile-anchor">
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
          ${compactMobileSummary ? "" : fullPitch}
          ${renderUserPredictionHistoryCard(r)}
          ${predCards}
        </div>
      </details>`;
  }).join("");
}

// ---------- Boot -------------------------------------------------------------

function chineseNumber(n) {
  const nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四"];
  return nums[n] || String(n);
}

function fmtChineseTimeZone(offsetMinutes) {
  if (!offsetMinutes) return "零时区";
  const sign = offsetMinutes > 0 ? "东" : "西";
  const abs = Math.abs(offsetMinutes);
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  const base = `${sign}${chineseNumber(hours)}区`;
  return minutes ? `${base}${minutes}分` : base;
}

function fmtTimestamp(iso) {
  if (!iso) return "—";
  const d   = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} `
       + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} 零时区`;
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
  return `${yr}-${mo}-${dy} ${hr}:${mn} ${fmtChineseTimeZone(off)}`;
}

function renderSiteData() {
  if (!_siteData) return;
  _allPreds = [];
  _predFixtures = [];
  renderIncomingMatches(_siteData.incoming_matches || []);
  renderTournamentPredictions(_siteData.tournament_predictions || null);
  syncLeaderboardTabs();
  updateLeaderboardScopeControls();
  renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
  requestAnimationFrame(() => {
    const histPending = _siteData._history_url && !(_siteData.history && _siteData.history.length);
    if (histPending) {
      const el = document.getElementById("history-container");
      if (el) el.innerHTML = `<div class="text-gray-500 text-sm">${_lang === "en" ? "Loading history…" : "历史加载中…"}</div>`;
    } else {
      renderHistory(_siteData.history || []);
    }
    renderMobileToc();
  });
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
  const lang = _lang === "en" ? "en" : "zh";
  try {
    const resp = await fetch(`data.live.${lang}.json`, { cache: "no-cache" });
    if (resp.ok) return await resp.json();
  } catch (err) { /* fall through to full payload */ }
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
  if (_siteData._history_url && !(_siteData.history && _siteData.history.length)) {
    loadHistoryLazy(_siteData._history_url);
  }
}

async function loadHistoryLazy(url) {
  try {
    const resp = await fetch(url, { cache: "no-cache" });
    if (!resp.ok) throw new Error(`${url}: ${resp.status}`);
    const data = await resp.json();
    if (!_siteData) return;
    _siteData.history = data.history || [];
    renderHistory(_siteData.history);
    // 我的预测 row is evaluated against history — re-render the board now that it exists.
    renderLeaderboard(activeLeaderboardData(), _activeLeaderboardView);
    renderMobileToc();
  } catch (err) {
    console.warn("history lazy-load failed:", err);
    const el = document.getElementById("history-container");
    if (el) el.innerHTML = `<div class="text-gray-500 text-sm">${t("no_graded")}</div>`;
  }
}

async function main() {
  setTheme(_theme, { updateUrl: false });
  applyStaticI18n();
  buildReasoningModal();
  wireTabs();
  setupMobileToc();
  setupResponsivePredictions();
  initUserSession();
  await loadUserPredictions();
  await loadSiteData();
}

main();
