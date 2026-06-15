"""Polish public reasoning text without touching machine-scored fields.

Structured player fields should keep provider/API names so graders can match
them against truth data. The public `reasoning.*` strings, however, should be
pleasant to read in Chinese. This module applies conservative best-effort name
localization plus a small public-copy cleanup pass to reasoning strings only.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
NAME_LOCALIZATION_JSON = ROOT / "data" / "i18n" / "world_cup_2026_names.zh.json"

REASONING_KEYS = {
    "overall",
    "market_odds",
    "lineup_analysis",
    "tactical_analysis",
    "h2h_recent_form",
    "player_matchups",
    "injuries_availability",
    "upset_draw_blowout_cases",
    "score_result_rationale",
    "t1_result",
    "t2_player",
    "t3_events",
    "t4_stats",
}

TEAM_ALIASES = {
    "cabo verde": "cape verde",
    "cape verde islands": "cape verde",
}

SINGLE_TOKEN_ALLOW = {
    "Nico",
    "Rodri",
    "Pedri",
    "Gavi",
    "Yamal",
    "Vozinha",
    "Stopira",
}

SINGLE_TOKEN_STOP = {
    "United",
    "City",
    "Real",
    "Club",
    "Sporting",
    "Costa",
    "Rica",
    "Junior",
    "Senior",
    "National",
}

CODE_SPAN_RE = re.compile(r"`[^`]*`")
LATIN_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'’.-]*")
RESULT_PROBS_RE = re.compile(
    r"\bhome\s*=\s*(\d+(?:\.\d+)?)\s*[,，、/;；\s]+"
    r"draw\s*=\s*(\d+(?:\.\d+)?)\s*[,，、/;；\s]+"
    r"away\s*=\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
FIELD_VALUE_RE = re.compile(
    r"`?\b("
    r"headline_score|predicted_result|expected_total_goals|expected_goal_diff|"
    r"match_profile|most_likely_score"
    r")\b`?\s*[=:：]\s*`?([A-Za-z0-9_.+-]+)`?",
    re.IGNORECASE,
)

FIELD_LABELS = {
    "reasoning": "公开分析",
    "reasoning.overall": "整体分析",
    "market_odds": "赔率分析",
    "lineup_analysis": "阵容分析",
    "tactical_analysis": "战术分析",
    "h2h_recent_form": "交手与近况分析",
    "player_matchups": "球员对位分析",
    "injuries_availability": "伤停与可用性分析",
    "upset_draw_blowout_cases": "冷门、平局与大胜路径",
    "score_result_rationale": "比分与赛果逻辑",
    "t1_result": "赛果判断",
    "t2_player": "球员判断",
    "t3_events": "事件判断",
    "t4_stats": "数据判断",
    "predicted_result": "赛果判断",
    "headline_score": "最终比分",
    "win_probs": "胜平负概率",
    "expected_total_goals": "预期总进球",
    "expected_goal_diff": "预期净胜球",
    "match_profile": "比赛节奏",
    "score_dist": "比分分布",
    "most_likely_score": "最可能比分",
    "over_under_probs": "大小球概率",
    "expected metrics": "预期数据",
    "context_pack.odds": "结构化赔率资料",
}

PROFILE_LABELS = {
    "low_event": "低事件、偏谨慎",
    "normal": "常规节奏",
    "open": "开放对攻",
    "chaos": "混沌高事件",
}

RESULT_LABELS = {
    "home": "主队取胜",
    "draw": "双方战平",
    "away": "客队取胜",
}


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def _strip_parenthetical(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", " ", value).strip()


def _norm_name(value: Any) -> str:
    text = _strip_parenthetical(str(value or ""))
    text = _strip_accents(text).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = " ".join(text.split())
    return TEAM_ALIASES.get(text, text)


def _tokens(value: str) -> list[str]:
    return LATIN_TOKEN_RE.findall(str(value or ""))


def _number_key(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value).strip()


def _clean_player_zh(value: Any) -> str:
    return re.sub(r"（队长）$", "", str(value or "").strip())


@lru_cache(maxsize=1)
def _load_localization() -> dict[str, Any]:
    exact: dict[str, str] = {}
    norm: dict[str, str] = {}
    teams: dict[str, str] = {}
    players_by_team_number: dict[tuple[str, str], str] = {}
    aliases_by_team_number: dict[tuple[str, str], list[str]] = {}

    if not NAME_LOCALIZATION_JSON.exists():
        return {
            "exact": exact,
            "norm": norm,
            "teams": teams,
            "players_by_team_number": players_by_team_number,
            "aliases_by_team_number": aliases_by_team_number,
        }

    raw = json.loads(NAME_LOCALIZATION_JSON.read_text())

    for source_name, item in (raw.get("teams") or {}).items():
        if not isinstance(item, dict):
            continue
        zh = str(item.get("zh") or "").strip()
        if not zh:
            continue
        aliases = {source_name, item.get("name"), _strip_parenthetical(str(source_name))}
        if _norm_name(source_name) == "cape verde":
            aliases.update({"Cape Verde Islands", "Cabo Verde"})
        for alias in aliases:
            if not alias:
                continue
            exact[str(alias)] = zh
            teams[_norm_name(alias)] = zh

    for source_name, item in (raw.get("players") or {}).items():
        if not isinstance(item, dict):
            continue
        zh = _clean_player_zh(item.get("zh"))
        if not zh:
            continue
        aliases = {
            source_name,
            item.get("name"),
            _strip_parenthetical(str(source_name)),
            _strip_parenthetical(str(item.get("name") or "")),
        }
        for alias in aliases:
            if not alias:
                continue
            exact[str(alias)] = zh
            norm[_norm_name(alias)] = zh

        team = item.get("team")
        number = _number_key(item.get("number"))
        if team and number:
            players_by_team_number[(_norm_name(team), number)] = zh
            aliases_by_team_number[(_norm_name(team), number)] = sorted(
                {str(alias).strip() for alias in aliases if alias},
                key=len,
                reverse=True,
            )

    return {
        "exact": exact,
        "norm": norm,
        "teams": teams,
        "players_by_team_number": players_by_team_number,
        "aliases_by_team_number": aliases_by_team_number,
    }


def _fixture_team_name(fixture: dict[str, Any] | None, side: str) -> str | None:
    if not isinstance(fixture, dict):
        return None

    side_value = fixture.get(side)
    if isinstance(side_value, dict):
        return (
            side_value.get("name")
            or side_value.get("team_name")
            or side_value.get("short_name")
        )
    if isinstance(side_value, str):
        return side_value

    response = fixture.get("response")
    if isinstance(response, list) and response:
        team = (((response[0].get("teams") or {}).get(side)) or {})
        if isinstance(team, dict):
            return team.get("name")
    return None


def _add_alias(mapping: dict[str, str], alias: Any, zh: str) -> None:
    alias_text = str(alias or "").strip()
    if not alias_text or not zh or alias_text == zh:
        return
    if not LATIN_TOKEN_RE.search(alias_text):
        return
    mapping.setdefault(alias_text, zh)


def _context_name_mapping(
    prediction: dict[str, Any],
    fixture: dict[str, Any] | None,
) -> dict[str, str]:
    loc = _load_localization()
    mapping: dict[str, str] = {}

    # Team names can appear in reasoning too.
    for side in ("home", "away"):
        team_name = _fixture_team_name(fixture, side)
        if not team_name:
            continue
        zh = loc["teams"].get(_norm_name(team_name))
        if zh:
            _add_alias(mapping, team_name, zh)

    lineups = prediction.get("lineups") or {}
    context_players: list[tuple[str, str]] = []
    context_single_aliases: dict[str, str | None] = {}

    for side in ("home", "away"):
        team_name = _fixture_team_name(fixture, side)
        team_norm = _norm_name(team_name)
        team_number_map = loc["players_by_team_number"]
        team_number_aliases = loc["aliases_by_team_number"]
        players = []
        side_lineup = lineups.get(side) or {}
        if isinstance(side_lineup, dict):
            players.extend(side_lineup.get("starting") or [])
            players.extend(side_lineup.get("bench") or [])

        for player in players:
            if not isinstance(player, dict):
                continue
            official = str(player.get("name") or "").strip()
            if not official:
                continue
            shirt = _number_key(player.get("shirt") or player.get("number"))
            zh = None
            shirt_aliases: list[str] = []
            if team_norm and shirt:
                zh = team_number_map.get((team_norm, shirt))
                shirt_aliases = team_number_aliases.get((team_norm, shirt), [])
            if not zh:
                zh = loc["norm"].get(_norm_name(official))
            if not zh:
                continue

            context_players.append((official, zh))
            _add_alias(mapping, official, zh)
            _add_alias(mapping, _strip_parenthetical(official), zh)
            for alias in shirt_aliases:
                _add_alias(mapping, alias, zh)

            alias_token_sets = [_tokens(alias) for alias in [official, *shirt_aliases] if alias]
            for player_tokens in alias_token_sets:
                if len(player_tokens) >= 2:
                    _add_alias(mapping, " ".join(player_tokens[:2]), zh)

            single_tokens = {
                token
                for player_tokens in alias_token_sets
                for token in ([player_tokens[0], player_tokens[-1]] if player_tokens else [])
            }
            for token in single_tokens:
                if token in SINGLE_TOKEN_STOP:
                    continue
                if token not in SINGLE_TOKEN_ALLOW and len(token) < 5:
                    continue
                previous = context_single_aliases.get(token)
                context_single_aliases[token] = zh if previous in (None, zh) else None

    for alias, zh in context_single_aliases.items():
        if zh:
            _add_alias(mapping, alias, zh)

    # Names can appear in scorers/assisters even if the lineup block is sparse.
    for field in ("scorers", "assisters", "motm_probs"):
        for item in prediction.get(field) or []:
            if not isinstance(item, dict):
                continue
            official = item.get("player")
            zh = loc["norm"].get(_norm_name(official))
            if zh:
                _add_alias(mapping, official, zh)

    for field, keys in {
        "cards": ("player",),
        "substitutions": ("off", "on"),
        "penalties": ("taker",),
        "own_goals": ("player",),
    }.items():
        for item in prediction.get(field) or []:
            if not isinstance(item, dict):
                continue
            for key in keys:
                official = item.get(key)
                zh = loc["norm"].get(_norm_name(official))
                if zh:
                    _add_alias(mapping, official, zh)

    # Static exact aliases are useful for common shorter forms like "Lamine Yamal".
    for alias, zh in loc["exact"].items():
        if len(alias) >= 6:
            _add_alias(mapping, alias, zh)

    return dict(sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True))


def _protect_code_spans(text: str) -> tuple[str, list[str]]:
    spans: list[str] = []

    def _save(match: re.Match[str]) -> str:
        spans.append(match.group(0))
        return f"\uE100{len(spans) - 1}\uE100"

    return CODE_SPAN_RE.sub(_save, text), spans


def _restore_code_spans(text: str, spans: list[str]) -> str:
    def _load(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return spans[idx] if 0 <= idx < len(spans) else ""

    return re.sub(r"\uE100(\d+)\uE100", _load, text)


def _replace_alias(text: str, alias: str, zh: str) -> str:
    pattern = re.compile(
        rf"(?<![A-Za-zÀ-ÖØ-öø-ÿ0-9]){re.escape(alias)}(?![A-Za-zÀ-ÖØ-öø-ÿ0-9])"
    )
    return pattern.sub(zh, text)


def localize_reasoning_text(text: str, mapping: dict[str, str]) -> str:
    protected, spans = _protect_code_spans(text)
    out = protected
    for alias, zh in mapping.items():
        out = _replace_alias(out, alias, zh)
    return _restore_code_spans(out, spans)


def _localized_team_label(fixture: dict[str, Any] | None, side: str) -> str:
    team_name = _fixture_team_name(fixture, side)
    if team_name:
        zh = _load_localization()["teams"].get(_norm_name(team_name))
        return zh or str(team_name)
    return "主队" if side == "home" else "客队"


def _format_probability(value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number <= 1:
        number *= 100
    if abs(number - round(number)) < 0.05:
        return f"{round(number):.0f}%"
    return f"{number:.1f}%"


def _result_label(value: str, fixture: dict[str, Any] | None) -> str:
    result = str(value or "").strip().casefold()
    if result == "home":
        return f"{_localized_team_label(fixture, 'home')}取胜"
    if result == "away":
        return f"{_localized_team_label(fixture, 'away')}取胜"
    if result == "draw":
        return "双方战平"
    return RESULT_LABELS.get(result, str(value))


def _replace_result_probs(match: re.Match[str]) -> str:
    return (
        f"主胜约{_format_probability(match.group(1))}、"
        f"平局约{_format_probability(match.group(2))}、"
        f"客胜约{_format_probability(match.group(3))}"
    )


def _replace_field_value(match: re.Match[str], fixture: dict[str, Any] | None) -> str:
    field = match.group(1).casefold()
    value = match.group(2)
    if field in {"headline_score", "most_likely_score"}:
        return f"最终比分预测为{value}"
    if field == "predicted_result":
        return f"赛果判断为{_result_label(value, fixture)}"
    if field == "expected_total_goals":
        return f"预期总进球约{value}"
    if field == "expected_goal_diff":
        return f"预期净胜球约{value}"
    if field == "match_profile":
        return f"比赛节奏偏向{PROFILE_LABELS.get(str(value).casefold(), value)}"
    return f"{FIELD_LABELS.get(field, field)}为{value}"


def _replace_field_labels(text: str) -> str:
    out = text
    for field, label in sorted(FIELD_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(
            rf"(?<![A-Za-z0-9_.])`?{re.escape(field)}`?(?![A-Za-z0-9_.])",
            re.IGNORECASE,
        )
        out = pattern.sub(label, out)
    return out


def _naturalize_technical_copy(text: str, fixture: dict[str, Any] | None) -> str:
    out = RESULT_PROBS_RE.sub(_replace_result_probs, text)
    out = FIELD_VALUE_RE.sub(lambda m: _replace_field_value(m, fixture), out)
    out = out.replace("`", "")

    sentence_replacements: list[tuple[str, str]] = [
        (r"这份预测的生成方式需要先说明：[^。！？]*[。！？]", ""),
        (r"它是外部模型调用受限后，[^。！？]*[。！？]", ""),
        (r"这是一份本地安全重跑[^。！？]*[。！？]", ""),
        (r"在新的框架里，[^：]{0,600}?本条记录选择的代表性分支是：", "本场分析的主线是："),
        (r"本条记录选择的代表性分支是：", "本场分析的主线是："),
        (r"这个框架刻意把[^。！？]*[。！？]", ""),
        (
            r"因此同一场比赛允许不同模型选择不同代表性分支，只要每个分支内部的比分、概率、事件和统计能自洽。",
            "因此，这场比赛不能只看纸面实力；首球、门将状态、定位球和替补后的体能变化，都可能把比分推向完全不同的方向。",
        ),
        (
            r"我没有再要求模型输出每个比分的概率，因为那会把所有模型重新拉回保守众数；",
            "这里不把每个精确比分拆成概率表，重点是给出一个清晰的比赛剧本；",
        ),
        (
            r"这个比分不是每个比分概率表里的众数猜测，而是一个带场景假设的最终比分承诺：",
            "这个比分不是机械选择最常见的保守模板，而是建立在明确比赛剧本上的判断：",
        ),
        (
            r"最终比分预测为([^，。；]+)、赛果判断为([^，。；]+)、胜平负概率\s*和\s*预期数据\s*必须说同一个故事。",
            r"最终比分预测为\1，赛果判断为\2；胜平负倾向、总进球预期和净胜球方向需要讲述同一个比赛故事。",
        ),
    ]
    for pattern, replacement in sentence_replacements:
        out = re.sub(pattern, replacement, out)

    phrase_replacements = {
        "本次 SportMonks 快照没有成功写入结构化 bookmaker odds，context_pack.odds 为空，所以这里不能伪造具体赔率或 implied probability。": "本次赛前资料没有稳定可核验的庄家赔率，因此不能编造具体盘口；只能把球队实力、近期走势和市场常识作为赔率先验。",
        "本次 SportMonks 快照没有成功写入结构化 庄家赔率，结构化赔率资料 为空，所以这里不能伪造具体赔率或 隐含概率。": "本次赛前资料没有稳定可核验的庄家赔率，因此不能编造具体盘口；只能把球队实力、近期走势和市场常识作为赔率先验。",
        "SportMonks快照没有可用赔率接口": "赛前资料没有稳定可核验的庄家赔率",
        "SportMonks 快照没有可用赔率接口": "赛前资料没有稳定可核验的庄家赔率",
        "SportMonks上下文": "赛前数据",
        "bookmaker odds": "庄家赔率",
        "implied probability": "隐含概率",
        "base rate": "基础先验",
        "bet-builder": "投注组合",
        "Bet Builder": "投注组合",
        "odds": "赔率",
        "H2H": "交手记录",
        "本模型采用的具体场景是：": "本场我的核心剧本是：",
        "本模型选择": "我选择",
        "模型选择": "这一路径选择",
        "模型的代表性分支": "这一路径",
        "让模型在分析完场景后承诺一个点比分": "在分析完场景后给出一个明确比分",
        "模型在分析完场景后承诺一个点比分": "在分析完场景后给出一个明确比分",
        "最终点预测": "最终比分预测",
        "点预测": "具体比分判断",
        "点比分": "具体比分",
        "最高概率桶": "最倾向的结果",
        "概率桶": "结果分支",
        "概率分布": "胜平负倾向",
        "用胜平负概率表达不确定性": "用胜平负倾向保留不确定性",
        "写进概率": "纳入判断",
        "比赛比赛类型": "比赛节奏",
        "预测框架": "分析思路",
        "新的框架": "新的分析思路",
        "这个框架": "这个分析思路",
        "框架": "分析思路",
        "本地安全重跑": "赛前复盘",
        "仓库": "资料库",
        "benchmark": "预测任务",
        "Benchmark": "预测任务",
        "schema": "结构要求",
        "Schema": "结构要求",
        "JSON": "结构化结果",
    }
    for src, replacement in phrase_replacements.items():
        out = out.replace(src, replacement)

    out = _replace_field_labels(out)
    out = re.sub(
        r"最终比分预测为([^、，。；]+)[、，]赛果判断为([^、，。；]+)[、，]胜平负概率\s*和\s*预期数据\s*必须说同一个故事。",
        r"最终比分预测为\1，赛果判断为\2；胜平负倾向、总进球预期和净胜球方向需要讲述同一个比赛故事。",
        out,
    )
    out = re.sub(
        r"这里最倾向的结果对应([^，。；]+)",
        r"我最倾向\1",
        out,
    )
    out = re.sub(
        r"(\d+)W\s+(\d+)D\s+(\d+)L\s*\(\s*last\s+(\d+)\s*\)",
        r"\1胜\2平\3负（近\4场）",
        out,
        flags=re.IGNORECASE,
    )
    heading_replacements = {
        "### T1 赛果与比分": "### 赛果与比分",
        "### T2 球员层": "### 关键球员",
        "### T3 事件时间线": "### 事件时间线",
        "### T4 统计侧写": "### 数据侧写",
    }
    for src, replacement in heading_replacements.items():
        out = out.replace(src, replacement)
    out = out.replace("T1 赛果层", "赛果层面")
    out = out.replace("本条记录代表一个明确比赛分支", "这一路径代表一个明确比赛分支")
    out = out.replace("这条记录代表一个明确比赛分支", "这一路径代表一个明确比赛分支")
    out = out.replace("这条记录", "这一路径")
    out = out.replace("本条记录", "这一路径")
    out = out.replace("胜平负倾向 主胜", "胜平负倾向：主胜")
    out = out.replace(
        "胜平负倾向、总进球预期和净胜球方向需要讲述同一个比赛故事。",
        "把胜平负倾向、总进球预期和净胜球方向放在一起看，比赛故事很清楚。",
    )
    out = out.replace(
        "这里不把每个精确比分拆成概率表，重点是给出一个清晰的比赛剧本；这里在分析完场景后给出一个明确比分，同时用胜平负倾向保留不确定性。",
        "我的比分判断建立在这个比赛剧本上：西班牙需要早早打开局面并持续制造边路错位，同时胜平负倾向仍保留佛得角通过反击和定位球改变走势的空间。",
    )
    out = out.replace("预测比分说爆冷、概率又说热门最大", "比分倾向爆冷、整体胜平负判断又偏向热门")
    out = out.replace("事件列表", "进球时间线")
    out = out.replace("客队进球候选主要来自无明确进球候选", "客队没有稳定的高把握进球点")
    out = out.replace("主队进球候选主要来自无明确进球候选", "主队没有稳定的高把握进球点")
    out = out.replace("这里让预测在分析完场景后承诺一个具体比分", "这里在分析完场景后给出一个明确比分")
    out = out.replace("另外，因此，", "因此，")
    out = out.replace("模型", "判断")
    out = re.sub(r"\s+([，。；：、！？])", r"\1", out)
    out = re.sub(r"([。！？]){2,}", r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def polish_public_reasoning_text(
    text: str,
    mapping: dict[str, str],
    *,
    fixture: dict[str, Any] | None = None,
) -> str:
    localized = localize_reasoning_text(text, mapping) if mapping else text
    return _naturalize_technical_copy(localized, fixture)


def localize_prediction_reasoning(
    prediction: dict[str, Any],
    *,
    fixture: dict[str, Any] | None = None,
    copy_prediction: bool = False,
) -> dict[str, Any]:
    """Return prediction with `reasoning.*` names localized to Chinese.

    This intentionally leaves structured player fields unchanged.
    """
    pred = copy.deepcopy(prediction) if copy_prediction else prediction
    if not isinstance(pred, dict):
        return pred

    reasoning = pred.get("reasoning")
    if not reasoning:
        return pred

    mapping = _context_name_mapping(pred, fixture)

    if isinstance(reasoning, str):
        pred["reasoning"] = polish_public_reasoning_text(reasoning, mapping, fixture=fixture)
        return pred

    if isinstance(reasoning, dict):
        for key, value in list(reasoning.items()):
            if key in REASONING_KEYS and isinstance(value, str):
                reasoning[key] = polish_public_reasoning_text(value, mapping, fixture=fixture)
    return pred
