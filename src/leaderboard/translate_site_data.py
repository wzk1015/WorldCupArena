"""Translate the website data payload into Simplified Chinese.

The translator is intentionally cache-first. Entity names are translated once
and reused everywhere, so a team/player/venue keeps the same Chinese spelling
across fixtures, predictions, reasoning text, and future rebuilds.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "i18n" / "zh_translation_cache.json"

POSITION_ZH = {
    "GK": "门将",
    "G": "门将",
    "DF": "后卫",
    "D": "后卫",
    "MF": "中场",
    "M": "中场",
    "FW": "前锋",
    "F": "前锋",
}

DEFAULT_ENTITY_TRANSLATIONS = {
    "World": "世界",
    "England": "英格兰",
    "Germany": "德国",
    "France": "法国",
    "Spain": "西班牙",
    "Italy": "意大利",
    "Mexico": "墨西哥",
    "South Africa": "南非",
    "Curaçao": "库拉索",
    "Curacao": "库拉索",
    "UEFA Champions League": "欧冠",
    "Premier League": "英超",
    "Bundesliga": "德甲",
    "DFB Pokal": "德国杯",
    "DFB-Pokal": "德国杯",
    "FA Cup": "足总杯",
    "Group Stage": "小组赛",
    "Final": "决赛",
    "Semi-finals": "半决赛",
    "Quarter-finals": "四分之一决赛",
    "Round of 16": "十六强",
    "Regular Season": "常规赛",
    "Paris Saint Germain": "巴黎圣日耳曼",
    "Paris-Saint-Germain": "巴黎圣日耳曼",
    "PSG": "巴黎圣日耳曼",
    "Arsenal": "阿森纳",
    "Bayern München": "拜仁慕尼黑",
    "Bayern Munich": "拜仁慕尼黑",
    "Atletico Madrid": "马德里竞技",
    "Atlético Madrid": "马德里竞技",
    "Manchester City": "曼城",
    "Manchester-City": "曼城",
    "Tottenham": "热刺",
    "Chelsea": "切尔西",
    "Leeds": "利兹联",
    "Crystal Palace": "水晶宫",
    "Aston Villa": "阿斯顿维拉",
    "West Ham": "西汉姆联",
    "Wolves": "狼队",
    "Burnley": "伯恩利",
    "Everton": "埃弗顿",
    "VfB Stuttgart": "斯图加特",
    "SC Freiburg": "弗赖堡",
    "Bayer Leverkusen": "勒沃库森",
    "1. FC Köln": "科隆",
    "Germany": "德国",
    "Botswana": "博茨瓦纳",
    "Niger": "尼日尔",
    "Peru": "秘鲁",
    "China PR": "中国",
    "Thailand": "泰国",
    "Friendly International": "国际友谊赛",
    "Friendlies 1": "友谊赛第1组",
    "Friendlies 3": "友谊赛第3组",
}

BUILTIN_TEXT_TRANSLATIONS = {
    "Configuration missing; this model will retry after secrets are available.": "配置缺失；密钥可用后该模型会自动重试。",
    "Provider quota or rate limit; this model will retry later.": "供应商配额或限流；该模型稍后会自动重试。",
    "Provider timeout; this model will retry later.": "供应商超时；该模型稍后会自动重试。",
    "Provider returned no final prediction; this model will retry later.": "供应商未返回最终预测；该模型稍后会自动重试。",
    "Prediction unavailable; this model will retry later.": "预测暂不可用；该模型稍后会自动重试。",
    "Not run yet; the scheduler will run this model when due.": "尚未运行；调度器会在合适时间执行该模型。",
    "Fixture snapshot does not match registry metadata; predictions are hidden until re-ingested.": "赛程快照与登记元数据不一致；重新 ingest 前会隐藏预测。",
    "Var - Goal Disallowed - offside": "VAR - 进球因越位被取消",
    "Goal Disallowed - offside": "进球因越位被取消",
    "Var - Goal Disallowed": "VAR - 进球被取消",
    "Goal Disallowed": "进球被取消",
    "Var - Penalty confirmed": "VAR - 点球确认",
    "Penalty confirmed": "点球确认",
    "Var - Penalty cancelled": "VAR - 点球取消",
    "Penalty cancelled": "点球取消",
}

ENTITY_KEYS = {
    "home",
    "away",
    "home_name",
    "away_name",
    "venue",
    "venue_city",
    "venue_country",
    "stage",
    "competition",
    "player",
    "name",
    "taker",
    "off",
    "on",
    "team_name",
}

ENTITY_LIST_KEYS = {"scorer_names", "assister_names"}
TEXT_KEYS = {"comment", "data_warning", "error_summary", "title", "label", "detail"}

_ALLOWED_LATIN_TEXT_TOKENS = {
    "ESPN", "FIFA", "UEFA", "AFC", "CAF", "CONCACAF", "CONMEBOL",
    "VAR", "xG", "Elo", "Goal", "Goal.com", "Transfermarkt", "Flashscore",
    "FOX", "Sports", "WorldCupArena", "MatchMate",
}

COMMON_TEXT_REPLACEMENTS = {
    "FIFA": "国际足联",
    "UEFA": "欧足联",
    "AFC": "亚足联",
    "CAF": "非洲足联",
    "CONCACAF": "中北美及加勒比海足联",
    "CONMEBOL": "南美足联",
    "xG": "预期进球",
    "World Cup": "世界杯",
}
REASONING_KEYS = {"overall", "t1_result", "t2_player", "t3_events", "t4_stats"}
POSITION_KEYS = {"position", "pos"}
NEVER_TRANSLATE_KEYS = {
    "wca_id",
    "model_id",
    "display_name",
    "setting",
    "status",
    "provider",
    "model_family",
    "model_category",
    "url",
    "home_logo",
    "away_logo",
    "kickoff_utc",
    "lock_at_utc",
    "accessed_at",
    "score",
    "most_likely_score",
    "result",
    "team",
    "color",
    "outcome",
}

_SCORE_RE = re.compile(r"^\d+\s*[-:]\s*\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_URL_RE = re.compile(r"^https?://", re.I)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cache(path: Path = CACHE_PATH) -> dict[str, Any]:
    if path.exists():
        try:
            cache = json.loads(path.read_text())
        except json.JSONDecodeError:
            cache = {}
    else:
        cache = {}
    cache.setdefault("entities", {})
    cache.setdefault("texts", {})
    for src, zh in DEFAULT_ENTITY_TRANSLATIONS.items():
        cache["entities"].setdefault(src, zh)
    for src, zh in BUILTIN_TEXT_TRANSLATIONS.items():
        cache["texts"].setdefault(_sha(src), {"src": src, "zh": zh})
    return cache


def _save_cache(cache: dict[str, Any], path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_content = {k: v for k, v in cache.items() if k != "_meta"}
    new_meta = {
        "entity_count": len(cache.get("entities") or {}),
        "text_count": len(cache.get("texts") or {}),
    }
    old_meta = {}
    if path.exists():
        try:
            old_cache = json.loads(path.read_text())
            old_meta = old_cache.get("_meta") or {}
            old_content = {k: v for k, v in old_cache.items() if k != "_meta"}
            if old_content == new_content and old_meta == new_meta:
                cache["_meta"] = old_meta
                return
        except Exception:
            pass
    cache["_meta"] = new_meta
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True))


def _looks_nontranslatable(value: str) -> bool:
    s = str(value or "").strip()
    if not s:
        return True
    if _URL_RE.search(s) or _DATE_RE.search(s) or _SCORE_RE.match(s):
        return True
    if "@" in s and " " not in s:
        return True
    return False


def _looks_englishish(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]", str(value or "")))


def _cached_zh(cached: Any) -> str:
    if isinstance(cached, dict):
        return str(cached.get("zh") or "").strip()
    return str(cached or "").strip()


def _contains_unwanted_latin_text(value: str) -> bool:
    tokens = re.findall(r"[A-Za-z][A-Za-zÀ-ÖØ-öø-ÿ.\'-]*", str(value or ""))
    for token in tokens:
        stripped = token.strip(".")
        if len(stripped) <= 1:
            continue
        if stripped in _ALLOWED_LATIN_TEXT_TOKENS:
            continue
        if stripped.upper() in _ALLOWED_LATIN_TEXT_TOKENS:
            continue
        return True
    return False


_ENTITY_REPLACEMENT_PAIR_CACHE: dict[int, list[tuple[str, str]]] = {}


def _entity_replacement_pairs(cache: dict[str, Any]) -> list[tuple[str, str]]:
    cache_key = id(cache)
    cached = _ENTITY_REPLACEMENT_PAIR_CACHE.get(cache_key)
    if cached is not None:
        return cached
    entities = cache.get("entities", {}) or {}
    pairs = [
        (src, zh)
        for src, zh in entities.items()
        if src and zh and src != zh and not _looks_englishish(zh) and _looks_englishish(src) and len(src) >= 3
    ]
    pairs.sort(key=lambda item: -len(item[0]))
    _ENTITY_REPLACEMENT_PAIR_CACHE[cache_key] = pairs
    return pairs


def _normalize_translated_text(value: str, cache: dict[str, Any] | None = None) -> str:
    out = str(value or "")
    for src, zh in COMMON_TEXT_REPLACEMENTS.items():
        if src in out:
            out = re.sub(rf"(?<![A-Za-z]){re.escape(src)}(?![A-Za-z])", zh, out)
    if cache and _looks_englishish(out):
        for src, zh in _entity_replacement_pairs(cache):
            if src not in out:
                continue
            out = re.sub(rf"(?<![A-Za-zÀ-ÖØ-öø-ÿ]){re.escape(src)}(?![A-Za-zÀ-ÖØ-öø-ÿ])", zh, out)
    return out


def _needs_cached_translation(src: str, cached: Any) -> bool:
    zh = _cached_zh(cached)
    return (not zh) or (zh == src and _looks_englishish(src)) or _contains_unwanted_latin_text(zh)


def _needs_cached_entity_translation(src: str, cached: Any) -> bool:
    zh = _cached_zh(cached)
    return _needs_cached_translation(src, cached) or _looks_englishish(zh)


_ABBREV_ENTITY_RE = re.compile(r"^([A-Z])\.\s+(.+)$")


def _latin_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", asciiish.lower())


def _fill_abbreviated_entity_translations(entities: dict[str, str], active_strings: set[str]) -> None:
    full_by_key: dict[tuple[str, str], list[str]] = {}
    for src, zh in entities.items():
        if _ABBREV_ENTITY_RE.match(src):
            continue
        if not zh or zh == src or _looks_englishish(zh):
            continue
        parts = src.strip().split()
        if len(parts) < 2:
            continue
        initial = _latin_key(parts[0][:1])
        surname = _latin_key(parts[-1])
        if initial and surname:
            full_by_key.setdefault((initial, surname), []).append(src)

    for src in active_strings:
        m = _ABBREV_ENTITY_RE.match(src.strip())
        if not m:
            continue
        initial = _latin_key(m.group(1))
        surname = _latin_key(m.group(2).split()[-1])
        candidates = full_by_key.get((initial, surname), [])
        if len(candidates) == 1:
            zh = entities.get(candidates[0])
            if zh and not _looks_englishish(zh):
                entities[src] = zh


def _is_reasoning_path(path: tuple[str, ...]) -> bool:
    return "reasoning" in path and path[-1] in REASONING_KEYS


def _is_entity_path(path: tuple[str, ...]) -> bool:
    key = path[-1] if path else ""
    parent = path[-2] if len(path) >= 2 else ""
    if key in NEVER_TRANSLATE_KEYS:
        return False
    if key in POSITION_KEYS:
        return False
    if key in ENTITY_KEYS:
        return True
    if parent in ENTITY_LIST_KEYS:
        return True
    return False


def _is_text_path(path: tuple[str, ...]) -> bool:
    key = path[-1] if path else ""
    if key in NEVER_TRANSLATE_KEYS:
        return False
    return key in TEXT_KEYS or _is_reasoning_path(path)


def _collect_strings(obj: Any, path: tuple[str, ...], entities: set[str], texts: dict[str, str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            _collect_strings(value, path + (str(key),), entities, texts)
        return
    if isinstance(obj, list):
        for item in obj:
            _collect_strings(item, path, entities, texts)
        return
    if not isinstance(obj, str) or _looks_nontranslatable(obj):
        return
    if _is_entity_path(path):
        entities.add(obj.strip())
    elif _is_text_path(path):
        texts[_sha(obj)] = obj


class LLMTranslator:
    def __init__(self) -> None:
        if os.getenv("SITE_TRANSLATION_DISABLE_LLM"):
            self.enabled = False
            return

        if os.getenv("OPENROUTER_API_KEY"):
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            self.base_url = os.getenv("OPENROUTER_BASE_URL")
            default_model = "openai/gpt-4.1-mini"
        elif os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.base_url = os.getenv("OPENAI_BASE_URL")
            default_model = "gpt-4.1-mini"
        elif os.getenv("GPTPLUS5_API_KEY"):
            self.api_key = os.getenv("GPTPLUS5_API_KEY")
            self.base_url = os.getenv("GPTPLUS5_BASE_URL") or "https://az.gptplus5.com/v1"
            default_model = "gpt-5.4-mini"
        else:
            self.api_key = None
            self.base_url = None
            default_model = ""

        if not self.api_key:
            self.enabled = False
            return
        self.model = os.getenv("SITE_TRANSLATION_MODEL") or default_model
        self.enabled = True

    def _client(self):
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        kwargs["timeout"] = 90
        kwargs["max_retries"] = 0
        return OpenAI(**kwargs)

    def _chat_json(self, system: str, user: str) -> Any:
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if self.base_url and "openrouter" in self.base_url:
            kwargs["extra_headers"] = {
                "HTTP-Referer": "https://wzk1015.github.io/WorldCupArena/",
                "X-Title": "WorldCupArena site translation",
            }
        try:
            response = client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
        except Exception:
            response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                return json.loads(content[start:end + 1])
            raise

    def translate_entities(self, strings: list[str]) -> dict[str, str]:
        if not self.enabled or not strings:
            if not self.enabled:
                print("[translate] LLM disabled/unavailable; entity translation will use cache/fallbacks", flush=True)
            return {}
        out: dict[str, str] = {}
        system = (
            "You translate football website entity names into Simplified Chinese. "
            "Return ONLY JSON. Use the most common Chinese football-media names. "
            "For every football player/person name written with Latin letters, output a Chinese name: "
            "use the established Chinese football-media name when known, otherwise transliterate naturally. "
            "Do not return a Latin player/person name unchanged. "
            "Keep model IDs, URLs, dates, score strings, and already-Chinese strings unchanged if they appear."
        )
        total_batches = (len(strings) + 79) // 80
        for batch_no, start in enumerate(range(0, len(strings), 80), 1):
            batch = strings[start:start + 80]
            print(
                f"[translate] entities batch {batch_no}/{total_batches}: requesting {len(batch)} names",
                flush=True,
            )
            user = json.dumps({"strings": batch}, ensure_ascii=False)
            try:
                data = self._chat_json(system, user)
            except Exception as exc:
                print(f"[translate] entities batch {batch_no}/{total_batches} failed: {exc}", flush=True)
                continue
            mapping = data.get("translations") if isinstance(data, dict) else None
            if not isinstance(mapping, dict):
                mapping = data if isinstance(data, dict) else {}
            for src in batch:
                zh = str(mapping.get(src) or src).strip()
                out[src] = zh or src
            print(
                f"[translate] entities batch {batch_no}/{total_batches}: cached {len(out)}/{len(strings)}",
                flush=True,
            )
        return out

    def translate_texts(
        self,
        items: list[dict[str, Any]],
        *,
        on_batch: Any | None = None,
    ) -> dict[str, str]:
        if not self.enabled or not items:
            if not self.enabled:
                print("[translate] LLM disabled/unavailable; text translation will use cache/fallbacks", flush=True)
            return {}
        out: dict[str, str] = {}
        system = (
            "You translate football prediction website copy into Simplified Chinese. "
            "Return ONLY JSON as {\"items\":[{\"id\":\"...\",\"zh\":\"...\"}]}. "
            "Preserve JSON meaning, probabilities, scores, model names, and URLs. "
            "Use the supplied glossary exactly for entity names. "
            "Translate every Latin-script football player, coach, stadium, city, and team name into Chinese; "
            "if no official Chinese name is known, transliterate naturally. Do not leave names such as Gallese, "
            "Gimenez, Lozano, Cubarsi, Laporte, Orebonye, or Dangda in Latin letters. Translate common football "
            "organizations and metrics such as FIFA/UEFA/CAF/xG into common Chinese wording."
        )
        batch: list[dict[str, Any]] = []
        chars = 0
        total_items = len(items)
        done_items = 0
        batch_no = 0

        def flush() -> None:
            nonlocal batch, chars, done_items, batch_no
            if not batch:
                return
            batch_no += 1
            batch_size = len(batch)
            batch_chars = chars
            print(
                f"[translate] texts batch {batch_no}: requesting {batch_size} items "
                f"({done_items}/{total_items} done, ~{batch_chars} chars)",
                flush=True,
            )
            try:
                data = self._chat_json(system, json.dumps({"items": batch}, ensure_ascii=False))
            except Exception as exc:
                print(f"[translate] texts batch {batch_no} failed: {exc}", flush=True)
                done_items += batch_size
                batch = []
                chars = 0
                return
            rows = data.get("items") if isinstance(data, dict) else []
            if isinstance(rows, list):
                batch_out: dict[str, str] = {}
                for row in rows:
                    if isinstance(row, dict) and row.get("id") and row.get("zh"):
                        batch_out[str(row["id"])] = _normalize_translated_text(str(row["zh"]).strip())
                out.update(batch_out)
                if on_batch and batch_out:
                    on_batch(batch_out)
            done_items += batch_size
            print(
                f"[translate] texts batch {batch_no}: cached {len(out)} translated texts "
                f"({done_items}/{total_items} processed)",
                flush=True,
            )
            batch = []
            chars = 0

        for item in items:
            text = item.get("text") or ""
            size = len(text) + len(json.dumps(item.get("glossary") or {}, ensure_ascii=False))
            if batch and (len(batch) >= 32 or chars + size > 24000):
                flush()
            batch.append(item)
            chars += size
        flush()
        return out


def _glossary_for_text(text: str, entities: dict[str, str], *, limit: int = 80) -> dict[str, str]:
    pairs = [(src, zh) for src, zh in entities.items() if src and src in text and src != zh]
    pairs.sort(key=lambda item: -len(item[0]))
    return dict(pairs[:limit])


def _load_team_name_seed() -> dict:
    seed = ROOT / "data" / "i18n" / "team_name_zh.json"
    if not seed.exists():
        return {}
    try:
        return {str(k): str(v) for k, v in json.loads(seed.read_text()).items() if k and v}
    except Exception:
        return {}


DEFAULT_ENTITY_TRANSLATIONS = {**_load_team_name_seed(), **DEFAULT_ENTITY_TRANSLATIONS}


def _translate_entity_string(value: str, cache: dict[str, Any]) -> str:
    entities = cache.get("entities", {})
    exact = entities.get(value)
    if exact and exact != value:
        return exact
    # API-Football often returns stages like "Group Stage - 1" or
    # "Regular Season - 38". Translate the known phase prefix and preserve the
    # round suffix instead of leaving the whole combined string in English.
    for sep in (" - ", " – ", " — "):
        if sep not in value:
            continue
        prefix, suffix = value.split(sep, 1)
        translated_prefix = entities.get(prefix)
        if translated_prefix:
            return f"{translated_prefix}{sep}{suffix}"
    return value


def _translate_string(value: str, path: tuple[str, ...], cache: dict[str, Any]) -> str:
    if _looks_nontranslatable(value):
        return value
    key = path[-1] if path else ""
    if key in POSITION_KEYS:
        return POSITION_ZH.get(value, value)
    if _is_entity_path(path):
        return _translate_entity_string(value, cache)
    if _is_text_path(path):
        row = cache.get("texts", {}).get(_sha(value))
        return _normalize_translated_text((row or {}).get("zh", value), cache)
    return value


def _translate_obj(obj: Any, path: tuple[str, ...], cache: dict[str, Any]) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            out[key] = _translate_obj(value, path + (str(key),), cache)
        return out
    if isinstance(obj, list):
        return [_translate_obj(item, path, cache) for item in obj]
    if isinstance(obj, str):
        return _translate_string(obj, path, cache)
    return obj


def translate_payload_to_zh(payload: dict[str, Any], *, cache_path: Path = CACHE_PATH) -> dict[str, Any]:
    cache = _load_cache(cache_path)
    entities: set[str] = set()
    texts: dict[str, str] = {}
    _collect_strings(payload, (), entities, texts)

    missing_entities = sorted(
        s for s in entities
        if _needs_cached_entity_translation(s, cache["entities"].get(s))
    )
    print(
        f"[translate] collected entities={len(entities)} "
        f"(cached={len(entities) - len(missing_entities)}, missing={len(missing_entities)}), "
        f"texts={len(texts)}",
        flush=True,
    )
    entity_limit = int(os.getenv("SITE_TRANSLATION_ENTITY_LIMIT") or "0")
    if entity_limit > 0 and len(missing_entities) > entity_limit:
        print(f"[translate] limiting entity translation to {entity_limit}/{len(missing_entities)} cache misses", flush=True)
        missing_entities = missing_entities[:entity_limit]
    llm = LLMTranslator()
    print(
        f"[translate] llm={'enabled' if llm.enabled else 'disabled'}"
        f"{f' model={llm.model}' if llm.enabled else ''}",
        flush=True,
    )
    try:
        cache["entities"].update(llm.translate_entities(missing_entities))
        _fill_abbreviated_entity_translations(cache["entities"], entities)
        if missing_entities:
            _save_cache(cache, cache_path)
    except Exception as exc:
        print(f"[translate] entity LLM translation failed; using cache/fallbacks: {exc}")

    text_items = []
    for text_id, src in sorted(texts.items()):
        if not _needs_cached_translation(src, cache["texts"].get(text_id)):
            continue
        text_items.append({
            "id": text_id,
            "text": src,
            "glossary": _glossary_for_text(src, cache["entities"]),
        })
    limit = int(os.getenv("SITE_TRANSLATION_TEXT_LIMIT") or "0")
    if limit > 0 and len(text_items) > limit:
        print(f"[translate] limiting long-text translation to {limit}/{len(text_items)} cache misses", flush=True)
        text_items = text_items[:limit]
    print(
        f"[translate] text cache misses to translate now={len(text_items)} "
        f"(cached={len(texts) - len(text_items)})",
        flush=True,
    )

    def _store_text_batch(batch: dict[str, str]) -> None:
        for text_id, zh in batch.items():
            if text_id in texts and zh:
                cache["texts"][text_id] = {"src": texts[text_id], "zh": zh}
        _save_cache(cache, cache_path)

    try:
        translated = llm.translate_texts(text_items, on_batch=_store_text_batch)
        for text_id, zh in translated.items():
            if text_id in texts and zh:
                cache["texts"][text_id] = {"src": texts[text_id], "zh": zh}
    except Exception as exc:
        print(f"[translate] text LLM translation failed; using cache/fallbacks: {exc}")

    for text_id, src in texts.items():
        cache["texts"].setdefault(text_id, {"src": src, "zh": BUILTIN_TEXT_TRANSLATIONS.get(src, src)})

    _fill_abbreviated_entity_translations(cache["entities"], entities)
    _save_cache(cache, cache_path)
    print(
        f"[translate] cache saved: entities={len(cache.get('entities') or {})}, "
        f"texts={len(cache.get('texts') or {})}",
        flush=True,
    )
    translated_payload = _translate_obj(copy.deepcopy(payload), (), cache)
    return translated_payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Translate a WorldCupArena site data JSON file to Chinese.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", type=Path, default=CACHE_PATH)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    zh = translate_payload_to_zh(payload, cache_path=args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(zh, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
