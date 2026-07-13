"""Build the data payload consumed by the project website.

Emits language-specific JSON files for the static site:

    docs/site/data.en.json   original English payload
    docs/site/data.zh.json   Simplified Chinese payload
    docs/site/data.json      default Chinese payload

Each payload has three sections:

    {
      "generated_at": ISO-8601 UTC,
      "leaderboard": {
          "main":              [{model_id, mean, n, layers_mean}, ...],
          "by_model_setting":  {model_id: {S1, S2}, ...}
      },
      "next_match": {
          "fixture": {wca_id, home, away, kickoff_utc, lock_at_utc, venue, stage},
          "predictions": [{model_id, setting, win_probs, most_likely_score,
                            expected_goal_diff, reasoning_overall, scorers,
                            cost_usd}, ...]
      },
      "history": [{wca_id, home, away, kickoff_utc, result, models:
                    [{model_id, setting, composite}, ...]}, ...]
    }

The site reads a language-specific data file and renders everything
client-side — no server, no build step. New predictions store model-owned
`win_probs` plus system-generated `score_dist`/`most_likely_score`; older
artifacts fall back to score_dist-derived win probabilities.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import yaml
from dotenv import dotenv_values

from ..pipeline.prediction_derivatives import derive_most_likely_score, derive_win_probs_from_score_dist
from ..pipeline.reasoning_localization import localize_prediction_reasoning

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data" / "results"
PREDICTIONS = ROOT / "data" / "predictions"
SNAPSHOTS = ROOT / "data" / "snapshots"
LIVE_DIR = ROOT / "data" / "live"
LIVE_PREDICTIONS = ROOT / "data" / "live_predictions"
TOURNAMENT_SPEC = ROOT / "configs" / "world_cup_2026_tournament.json"
TOURNAMENT_PREDICTIONS = ROOT / "data" / "tournament_predictions" / "world_cup_2026"
SEARCH_LOGS = ROOT / "data" / "search_logs"
FIXTURES_YAML = ROOT / "configs" / "fixtures.yaml"
MODELS_YAML = ROOT / "configs" / "models.yaml"
COMMENTS_JSON = ROOT / "data" / "comments.json"
NAME_LOCALIZATION_JSON = ROOT / "data" / "i18n" / "world_cup_2026_names.zh.json"
OUT = ROOT / "docs" / "site" / "data.json"
OUT_EN = ROOT / "docs" / "site" / "data.en.json"
OUT_ZH = ROOT / "docs" / "site" / "data.zh.json"
API_FOOTBALL_LOGO_CACHE = ROOT / "data" / "api_football_team_logos.json"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_FOOTBALL_LOGO_PREFIX = "https://media.api-sports.io/football/teams/"
API_FOOTBALL_FLAG_PREFIX = "https://media.api-sports.io/flags/"
API_FOOTBALL_FLAG_CODES = {
    "Botswana": "bw",
    "Cabo Verde": "cv",
    "Cape Verde": "cv",
    "Cape Verde Islands": "cv",
    "Niger": "ne",
    "Peru": "pe",
    "Spain": "es",
    "China PR": "cn",
    "China": "cn",
    "Thailand": "th",
}
HIDDEN_SITE_MODELS = {"yunwu-o4-mini-deep-research"}

_API_FOOTBALL_LOGO_CACHE: dict | None = None
_API_FOOTBALL_LOGO_CACHE_DIRTY = False
_DOTENV_VALUES: dict | None = None


def _load_comments() -> dict[str, str]:
    if not COMMENTS_JSON.exists():
        return {}
    data = json.loads(COMMENTS_JSON.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_") and v}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load_fixtures() -> list[dict]:
    if not FIXTURES_YAML.exists():
        return []
    cfg = yaml.safe_load(FIXTURES_YAML.read_text()) or {}
    return [f for f in (cfg.get("fixtures") or []) if f.get("enabled", True)]


def _norm_team_name(name: str | None) -> str:
    return " ".join(str(name or "").casefold().replace(".", " " ).split())


TEAM_FLAG_ALIASES = {
    "cabo verde": ("Cape Verde", "Cape Verde Islands"),
    "cape verde": ("Cabo Verde", "Cape Verde Islands"),
    "cape verde islands": ("Cape Verde", "Cabo Verde"),
}


def _team_flag_name_candidates(team_name: str | None) -> list[str]:
    raw = str(team_name or "").strip()
    names = [raw] if raw else []
    names.extend(TEAM_FLAG_ALIASES.get(_norm_team_name(raw), ()))

    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
    return out


def _team_flag_lookup_keys(team_name: str | None) -> list[str]:
    keys: list[str] = []
    for name in _team_flag_name_candidates(team_name):
        key = _norm_team_name(name)
        if key and key not in keys:
            keys.append(key)
    return keys


def _is_api_football_logo(url: str | None) -> bool:
    value = str(url or "")
    return value.startswith(API_FOOTBALL_LOGO_PREFIX) or value.startswith(API_FOOTBALL_FLAG_PREFIX)


def _api_football_flag_for_team(team_name: str | None) -> str | None:
    code = None
    for name in _team_flag_name_candidates(team_name):
        code = API_FOOTBALL_FLAG_CODES.get(name)
        if code:
            break
    if not code:
        return None
    return f"{API_FOOTBALL_FLAG_PREFIX}{code}.svg"


def _dotenv_value(key: str) -> str | None:
    global _DOTENV_VALUES
    if _DOTENV_VALUES is None:
        env_path = ROOT / ".env"
        _DOTENV_VALUES = dict(dotenv_values(env_path)) if env_path.exists() else {}
    value = _DOTENV_VALUES.get(key)
    return str(value) if value else None


def _api_football_key() -> str | None:
    return (
        os.environ.get("API_FOOTBALL_KEY")
        or os.environ.get("APIFOOTBALL_API_KEY")
        or _dotenv_value("API_FOOTBALL_KEY")
        or _dotenv_value("APIFOOTBALL_API_KEY")
    )


def _team_search_variants(name: str | None) -> list[str]:
    raw = str(name or "").strip()
    variants = [raw]
    aliases = {
        "China PR": ["China", "China PR", "China PR National"],
        "Curaçao": ["Curaçao", "Curacao"],
        "Bayern München": ["Bayern Munich", "Bayern München"],
    }
    variants.extend(aliases.get(raw, []))
    out = []
    for item in variants:
        if item and item not in out:
            out.append(item)
    return out


def _cache_api_football_logo(team_name: str | None, logo: str | None, team_id: int | None = None) -> None:
    global _API_FOOTBALL_LOGO_CACHE_DIRTY
    if not team_name or not _is_api_football_logo(logo):
        return
    cache = _load_api_football_logo_cache()
    key = _norm_team_name(team_name)
    old = cache.setdefault("teams", {}).get(key)
    item = {"name": team_name, "logo": logo}
    if team_id is not None:
        item["team_id"] = team_id
    if old != item:
        cache["teams"][key] = item
        _API_FOOTBALL_LOGO_CACHE_DIRTY = True


def _seed_api_football_logo_cache_from_snapshots(cache: dict) -> None:
    if not SNAPSHOTS.exists():
        return
    teams = cache.setdefault("teams", {})
    for path in SNAPSHOTS.glob("*/**/*.json"):
        try:
            raw = json.loads(path.read_text())
            rows = raw.get("response") or []
        except Exception:
            continue
        for row in rows[:1]:
            for side in ("home", "away"):
                team = ((row.get("teams") or {}).get(side) or {})
                name = team.get("name")
                logo = team.get("logo")
                if name and _is_api_football_logo(logo):
                    teams.setdefault(
                        _norm_team_name(name),
                        {"name": name, "logo": logo, "team_id": team.get("id")},
                    )


def _load_api_football_logo_cache() -> dict:
    global _API_FOOTBALL_LOGO_CACHE, _API_FOOTBALL_LOGO_CACHE_DIRTY
    if _API_FOOTBALL_LOGO_CACHE is not None:
        return _API_FOOTBALL_LOGO_CACHE
    if API_FOOTBALL_LOGO_CACHE.exists():
        try:
            cache = json.loads(API_FOOTBALL_LOGO_CACHE.read_text())
        except Exception:
            cache = {}
    else:
        cache = {}
    cache.setdefault("teams", {})
    before = len(cache["teams"])
    _seed_api_football_logo_cache_from_snapshots(cache)
    if len(cache["teams"]) != before:
        _API_FOOTBALL_LOGO_CACHE_DIRTY = True
    _API_FOOTBALL_LOGO_CACHE = cache
    return cache


def _save_api_football_logo_cache() -> None:
    if not _API_FOOTBALL_LOGO_CACHE_DIRTY or _API_FOOTBALL_LOGO_CACHE is None:
        return
    API_FOOTBALL_LOGO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    API_FOOTBALL_LOGO_CACHE.write_text(json.dumps(_API_FOOTBALL_LOGO_CACHE, ensure_ascii=False, indent=2))


def _search_api_football_logo(team_name: str | None) -> str | None:
    api_key = _api_football_key()
    if not api_key or not team_name:
        return None
    headers = {"x-apisports-key": api_key}
    target_norm = _norm_team_name(team_name)
    try:
        with httpx.Client(base_url=API_FOOTBALL_BASE, headers=headers, timeout=20.0) as client:
            for query in _team_search_variants(team_name):
                response = client.get("/teams", params={"search": query})
                response.raise_for_status()
                rows = response.json().get("response") or []
                if not rows:
                    continue

                def _score(row: dict) -> tuple[int, int]:
                    team = row.get("team") or {}
                    name_norm = _norm_team_name(team.get("name"))
                    exact = 0 if name_norm == target_norm else 1
                    national = 0 if team.get("national") else 1
                    return exact, national

                for row in sorted(rows, key=_score):
                    team = row.get("team") or {}
                    logo = team.get("logo")
                    if _is_api_football_logo(logo):
                        _cache_api_football_logo(team_name, logo, team.get("id"))
                        return logo
    except Exception as exc:
        print(f"[site] API-Football logo lookup failed for {team_name!r}: {exc}")
    return None


def _api_football_logo_for_team(team_name: str | None, fallback: str | None = None) -> str | None:
    fallback_text = str(fallback or "")
    if fallback_text.startswith(API_FOOTBALL_LOGO_PREFIX):
        _cache_api_football_logo(team_name, fallback)
        return fallback
    if not team_name:
        return None

    cache = _load_api_football_logo_cache()
    cached = cache.get("teams", {}).get(_norm_team_name(team_name))
    cached_logo = str((cached or {}).get("logo") or "")
    if cached_logo.startswith(API_FOOTBALL_LOGO_PREFIX):
        return cached_logo

    # If an API-Football key is available, prefer the real team logo endpoint
    # over any cached country-flag fallback. Without a key, flags keep national
    # teams presentable while still coming from API-Sports media.
    logo = _search_api_football_logo(team_name)
    if logo:
        return logo

    # SportMonks fixtures include team image_path URLs. Use them as a provider
    # fallback when API-Football lookup is unavailable or rate-limited.
    if fallback_text.startswith(("https://", "http://")):
        if fallback_text.startswith(API_FOOTBALL_FLAG_PREFIX):
            _cache_api_football_logo(team_name, fallback)
        return fallback_text

    if cached_logo.startswith(API_FOOTBALL_FLAG_PREFIX):
        return cached_logo

    flag = _api_football_flag_for_team(team_name)
    if flag:
        _cache_api_football_logo(team_name, flag)
    return flag


def _apply_api_football_logos(hdr: dict) -> dict:
    hdr["home_logo"] = _api_football_logo_for_team(hdr.get("home"), hdr.get("home_logo"))
    hdr["away_logo"] = _api_football_logo_for_team(hdr.get("away"), hdr.get("away_logo"))
    return hdr


def _model_family(model_id: str, provider: str | None = None) -> str:
    key = str(model_id or "").lower()
    provider = str(provider or "").lower()
    if "claude" in key or provider == "anthropic":
        return "claude"
    if key.startswith(("gpt", "o1", "o3", "o4")) or "openai" in key or provider == "openai":
        return "openai"
    if "gemini" in key or provider == "google":
        return "gemini"
    if "deepseek" in key:
        return "deepseek"
    if "qwen" in key:
        return "qwen"
    if "kimi" in key or "moonshot" in key:
        return "kimi"
    if "glm" in key or "zhipu" in key:
        return "glm"
    if "doubao" in key:
        return "doubao"
    if "minimax" in key:
        return "minimax"
    if "llama" in key:
        return "llama"
    if "gemma" in key:
        return "gemma"
    return provider or "other"


def _display_model_name(model_id: str) -> str:
    explicit = {
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
    }
    if model_id in explicit:
        return explicit[model_id]
    words = str(model_id or "").replace("_", "-").split("-")
    acronyms = {"gpt", "glm", "qwen", "kimi", "llama", "gemma"}
    return " ".join(word.upper() if word.lower() in acronyms else word.capitalize() for word in words if word)


def _infer_model_metadata(model_id: str) -> dict:
    family = _model_family(model_id)
    return {
        "display_name": _display_model_name(model_id),
        "model_category": None,
        "provider": None,
        "model_family": family,
        "open_weight": family in {"deepseek", "qwen", "kimi", "glm", "minimax", "llama", "gemma"},
        "config_order": 9999,
    }


def _load_model_metadata() -> dict[str, dict]:
    if not MODELS_YAML.exists():
        return {}
    cfg = yaml.safe_load(MODELS_YAML.read_text()) or {}
    meta: dict[str, dict] = {}
    order = 0
    for category, entries in cfg.items():
        if category == "baselines":
            continue
        for m in entries or []:
            model_id = m.get("id")
            if not model_id or model_id in HIDDEN_SITE_MODELS:
                continue
            provider = m.get("provider")
            meta[model_id] = {
                "display_name": m.get("display_name") or _display_model_name(model_id),
                "model_category": category,
                "provider": provider,
                "model_family": _model_family(model_id, provider),
                "open_weight": bool(m.get("open_weight", category == "open_llm")),
                "config_order": order,
            }
            order += 1
    return meta


MODEL_META = _load_model_metadata()


def _load_model_roster() -> list[dict]:
    if not MODELS_YAML.exists():
        return []
    cfg = yaml.safe_load(MODELS_YAML.read_text()) or {}
    roster: list[dict] = []
    for category, entries in cfg.items():
        if category == "baselines":
            continue
        for m in entries or []:
            model_id = m.get("id")
            if not model_id:
                continue
            meta = MODEL_META.get(model_id) or _infer_model_metadata(model_id)
            for setting in m.get("settings_supported") or []:
                roster.append({
                    "model_id": model_id,
                    "setting": setting,
                    **meta,
                })
    return roster


MODEL_ROSTER = _load_model_roster()
ACTIVE_MODEL_SETTINGS = {(row["model_id"], row.get("setting")) for row in MODEL_ROSTER}


def _prediction_key_from_path(path: Path) -> tuple[str, str | None]:
    stem = path.stem
    if "__" not in stem:
        return stem, None
    model_id, setting = stem.rsplit("__", 1)
    return model_id, setting


def _public_error_summary(err: object) -> str:
    """Return a site-safe status message without provider internals."""
    text = str(err or "").lower()
    if "env var" in text or "api_key" in text or "api key" in text:
        return "Configuration missing; this model will retry after secrets are available."
    if "quota" in text or "ratelimit" in text or "rate limit" in text or "429" in text:
        return "Provider quota or rate limit; this model will retry later."
    if "timeout" in text or "timed out" in text:
        return "Provider timeout; this model will retry later."
    if "jsondecodeerror" in text or "no valid" in text:
        return "Provider returned no final prediction; this model will retry later."
    return "Prediction unavailable; this model will retry later."


def _clean_venue_country(country: str | None) -> str | None:
    country = (country or "").strip()
    if not country or country.lower() == "world":
        return None
    return country


def _display_name_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    return str(slug).replace("-", " ")


def _infer_fixture_names_from_wca_id(wca_id: str) -> dict:
    """Best-effort fallback for fixtures that are registered but not ingested yet."""
    parts = str(wca_id or "").split("_")
    if len(parts) < 4:
        return {}
    date = parts[-1]
    home = _display_name_from_slug(parts[-3])
    away = _display_name_from_slug(parts[-2])
    competition = _display_name_from_slug("_".join(parts[:-3]).replace("_", "-"))
    return {
        "home": home,
        "away": away,
        "competition": competition,
        "date": date,
    }


def _has_prediction_files(wca_id: str) -> bool:
    pred_dir = PREDICTIONS / wca_id
    return pred_dir.exists() and any(pred_dir.glob("*.json"))


def _fixture_header_from_registry(wca_id: str, fx: dict, existing: dict | None = None) -> dict:
    inferred = _infer_fixture_names_from_wca_id(wca_id)
    kick = _parse_iso(fx["kickoff_utc"]).isoformat()
    base = dict(existing or {})
    base.update({
        "wca_id":      wca_id,
        "home":        fx.get("home") or inferred.get("home"),
        "home_logo":   fx.get("home_logo") or fx.get("home_team_logo"),
        "away":        fx.get("away") or inferred.get("away"),
        "away_logo":   fx.get("away_logo") or fx.get("away_team_logo"),
        "kickoff_utc": kick,
        "lock_at_utc": base.get("lock_at_utc"),
        "venue":       fx.get("venue") or base.get("venue"),
        "venue_city":    fx.get("venue_city") or base.get("venue_city"),
        "venue_country": _clean_venue_country(fx.get("venue_country") or base.get("venue_country")),
        "stage":         fx.get("stage") or base.get("stage"),
        "competition": fx.get("competition") or inferred.get("competition") or base.get("competition"),
    })
    return _apply_api_football_logos(base)


def _enrich_history_header(hdr: dict, wca_id: str, truth: dict | None) -> dict:
    """Recover display fields for history rows whose pre-match snapshot was
    captured during a provider outage (null team names -> "? vs ?" + no flag).
    The wca_id and graded truth still carry the real teams, so fill the blanks
    and re-derive flags from the recovered names. Only touches blank fields, so
    healthy rows are left exactly as-is."""
    if hdr.get("home") and hdr.get("away") and hdr.get("kickoff_utc"):
        return hdr
    inferred = _infer_fixture_names_from_wca_id(wca_id)
    t = truth or {}
    if not hdr.get("home"):
        hdr["home"] = t.get("home_name") or inferred.get("home")
    if not hdr.get("away"):
        hdr["away"] = t.get("away_name") or inferred.get("away")
    if not hdr.get("kickoff_utc") and inferred.get("date"):
        hdr["kickoff_utc"] = inferred["date"] + "T00:00:00+00:00"
    return _apply_api_football_logos(hdr)


def _header_mismatches_registry(hdr: dict | None, fx: dict) -> bool:
    if not hdr or not hdr.get("kickoff_utc"):
        return True
    try:
        return abs(_parse_iso(hdr["kickoff_utc"]) - _parse_iso(fx["kickoff_utc"])) > timedelta(minutes=1)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Leaderboard (all graded fixtures, aggregated by model)
# ---------------------------------------------------------------------------

# Leaderboard reset: pre-tournament matches (UCL/EPL/etc. used to shake the
# pipeline down before the World Cup kicked off) shouldn't dilute the World Cup
# leaderboard. Ignore any fixture before LEADERBOARD_MIN_DATE in the leaderboard;
# a few marquee pre-cup matches are still kept in `history` as worked examples.
LEADERBOARD_MIN_DATE = "2026-06-10"
HISTORY_EXAMPLE_WHITELIST = {
    "UEFA-Champions-League_Paris-Saint-Germain_Arsenal_2026-05-30",
    "UEFA-Champions-League_Bayern-München_Paris-Saint-Germain_2026-05-06",
    "Premier-League_Chelsea_Tottenham_2026-05-19",
    "Premier-League_Manchester-City_Aston-Villa_2026-05-24",
}


def _is_pre_cutoff(wca_id: str) -> bool:
    """True if the fixture kicked off before LEADERBOARD_MIN_DATE (pre-World-Cup)."""
    kick = (_load_fixture_header(wca_id) or {}).get("kickoff_utc")
    day = str(kick)[:10] if kick else None
    if not day:  # fall back to the trailing _YYYY-MM-DD in the wca_id
        tail = wca_id[-10:]
        day = tail if len(tail) == 10 and tail[4] == "-" and tail[7] == "-" else None
    return bool(day and day < LEADERBOARD_MIN_DATE)


def _is_knockout_wca_id(wca_id: str) -> bool:
    """World-Cup knockout fixture (R32 onwards). Keyed on the immutable wca_id slug
    rather than snapshot stage text, which is localized and can be null when the
    provider was down at snapshot time. Any World-Cup slug that isn't a group-stage
    matchday is knockout, so future rounds (semis/final/third place) match without
    enumeration."""
    return wca_id.startswith("World-Cup_") and "_Group-Stage" not in wca_id


def build_leaderboard(fixture_filter=None) -> dict:
    by_model_composites: dict[str, list[float]] = defaultdict(list)
    by_model_layers: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_model_setting: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_model_winner_correct: dict[str, int] = defaultdict(int)
    by_model_winner_total: dict[str, int] = defaultdict(int)

    _truth_cache: dict[str, dict | None] = {}

    for fid_dir in sorted(RESULTS.glob("*")):
        wca_id = fid_dir.name
        if "_test" in wca_id.lower() or wca_id.lower().startswith("test_"):
            continue
        if _is_pre_cutoff(wca_id):   # leaderboard reset — World-Cup matches only
            continue
        if fixture_filter is not None and not fixture_filter(wca_id):
            continue
        if wca_id not in _truth_cache:
            _truth_cache[wca_id] = _load_truth_data(wca_id)
        truth_result = (_truth_cache[wca_id] or {}).get("result")

        for f in fid_dir.glob("*.json"):
            r = json.loads(f.read_text())
            if (r.get("leakage_audit") or {}).get("leaked"):
                continue
            model = r["model_id"]
            setting = r["setting"]
            comp = float(r.get("composite", 0.0))
            by_model_composites[model].append(comp)
            by_model_setting[(model, setting)].append(comp)
            for k, v in (r.get("layers") or {}).items():
                by_model_layers[model][k].append(float(v))

            # Win prediction accuracy
            if truth_result:
                pred_file = PREDICTIONS / wca_id / f.name
                if pred_file.exists():
                    pred_rec = json.loads(pred_file.read_text())
                    pred_obj = pred_rec.get("prediction") or {}
                    wp = pred_obj.get("win_probs") or derive_win_probs_from_score_dist(pred_obj.get("score_dist") or [])
                    if wp:
                        predicted = max(wp, key=lambda k: wp[k])
                        by_model_winner_correct[model] += int(predicted == truth_result)
                        by_model_winner_total[model] += 1

    main = []
    for m, v in by_model_composites.items():
        layers_mean = {k: sum(xs) / len(xs) for k, xs in by_model_layers[m].items() if xs}
        total = by_model_winner_total[m]
        meta = MODEL_META.get(m) or _infer_model_metadata(m)
        if m in HIDDEN_SITE_MODELS:
            continue
        main.append({
            "model_id":      m,
            "mean":          sum(v) / len(v),
            "n":             len(v),
            "layers_mean":   layers_mean,
            "winner_correct": by_model_winner_correct[m],
            "winner_total":   total,
            "winner_acc":    by_model_winner_correct[m] / total if total else None,
            **meta,
        })
    main.sort(key=lambda x: -x["mean"])

    by_setting = {}
    for (m, s), xs in by_model_setting.items():
        by_setting.setdefault(m, {})[s] = sum(xs) / len(xs)
    by_setting = {m: dict(sorted(v.items())) for m, v in sorted(by_setting.items())}

    return {"main": main, "by_model_setting": by_setting}


# ---------------------------------------------------------------------------
# Next match (soonest upcoming enabled fixture with predictions on disk)
# ---------------------------------------------------------------------------

def _load_fixture_header(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "fixture.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    if "response" in raw:
        r0 = raw["response"][0]
        return _apply_api_football_logos({
            "wca_id":      wca_id,
            "home":        r0["teams"]["home"]["name"],
            "home_logo":   r0["teams"]["home"].get("logo"),
            "away":        r0["teams"]["away"]["name"],
            "away_logo":   r0["teams"]["away"].get("logo"),
            "kickoff_utc": r0["fixture"]["date"],
            "lock_at_utc": raw.get("lock_at_utc"),
            "venue":       (r0["fixture"].get("venue") or {}).get("name"),
            "venue_city":    (r0["fixture"].get("venue") or {}).get("city"),
            "venue_country": _clean_venue_country((r0.get("league") or {}).get("country")),
            "stage":         (r0.get("league") or {}).get("round"),
            "competition":   (r0.get("league") or {}).get("name"),
        })
    return _apply_api_football_logos({
        "wca_id":      wca_id,
        "home":        raw.get("home", {}).get("name"),
        "away":        raw.get("away", {}).get("name"),
        "kickoff_utc": raw.get("kickoff_utc"),
        "lock_at_utc": raw.get("lock_at_utc"),
        "venue":       raw.get("venue"),
        "venue_city":    raw.get("venue_city"),
        "venue_country": _clean_venue_country(raw.get("venue_country")),
        "stage":         raw.get("stage"),
        "competition": raw.get("competition"),
    })


def _empty_prediction_payload(
    *,
    model_id: str,
    setting: str | None,
    status: str,
    error_summary: str | None = None,
    cost_usd: float | None = None,
    tokens: dict | None = None,
    sources: list[dict] | None = None,
) -> dict:
    meta = MODEL_META.get(model_id) or _infer_model_metadata(model_id)
    return {
        "model_id":           model_id,
        "setting":            setting,
        "status":             status,
        "error_summary":      error_summary,
        "win_probs":          {},
        "score_dist":         [],
        "most_likely_score":  None,
        "headline_score":     None,
        "predicted_result":   None,
        "expected_goal_diff": None,
        "advance_prob":       None,
        "reasoning":          {},
        "scorers":            [],
        "assisters":          [],
        "motm_probs":         [],
        "lineups":            {},
        "formations":         {},
        "substitutions":      [],
        "cards":              [],
        "penalties":          [],
        "own_goals":          [],
        "key_events":         [],
        "stats":              {},
        "cost_usd":           cost_usd,
        "tokens":             tokens or {},
        "sources":            sources or [],
        **meta,
    }


def _prediction_display_sort_key(pred: dict) -> tuple:
    return (
        int(pred.get("config_order", 9999)),
        str(pred.get("setting") or ""),
        pred.get("model_id", ""),
    )


def _is_deep_research_model(model_id: str) -> bool:
    meta = MODEL_META.get(model_id) or _infer_model_metadata(model_id)
    return meta.get("model_category") == "deep_research_agent"


def _collect_predictions(
    wca_id: str,
    *,
    fixture: dict | None = None,
    include_errors: bool = False,
    include_missing: bool = False,
) -> list[dict]:
    pred_dir = PREDICTIONS / wca_id
    out = []
    seen: set[tuple[str, str | None]] = set()
    for f in sorted(pred_dir.glob("*.json")):
        fallback_model_id, fallback_setting = _prediction_key_from_path(f)
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            print(f"  [warn] skipping malformed JSON: {f}")
            continue
        model_id = rec.get("model_id") or fallback_model_id
        setting = rec.get("setting") or fallback_setting
        if model_id in HIDDEN_SITE_MODELS:
            continue
        if ACTIVE_MODEL_SETTINGS and (model_id, setting) not in ACTIVE_MODEL_SETTINGS:
            continue
        seen.add((model_id, setting))
        if rec.get("error"):
            if include_errors and not _is_deep_research_model(model_id):
                out.append(_empty_prediction_payload(
                    model_id=model_id,
                    setting=setting,
                    status="failed",
                    error_summary=_public_error_summary(rec.get("error")),
                    cost_usd=rec.get("cost_usd"),
                    tokens=rec.get("tokens") or {},
                    sources=rec.get("sources") or [],
                ))
            continue
        p = localize_prediction_reasoning(rec.get("prediction") or {}, fixture=fixture, copy_prediction=True)

        # Load search sources from search_logs if available
        sources: list[dict] = []
        log_path = SEARCH_LOGS / wca_id / f.name
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text())
                sources = log.get("sources") or []
            except Exception:
                pass
        if not sources:
            sources = rec.get("sources") or []
        win_probs = p.get("win_probs") or derive_win_probs_from_score_dist(p.get("score_dist") or [])
        headline_score = p.get("headline_score")
        most_likely_score = headline_score or p.get("most_likely_score") or derive_most_likely_score(p.get("score_dist") or [])
        meta = MODEL_META.get(rec["model_id"]) or _infer_model_metadata(rec["model_id"])

        out.append({
            "model_id":           rec["model_id"],
            "setting":            rec["setting"],
            "win_probs":          win_probs,
            "score_dist":         p.get("score_dist") or [],
            "most_likely_score":  most_likely_score,
            "headline_score":     headline_score,
            "predicted_result":   p.get("predicted_result"),
            "expected_goal_diff": p.get("expected_goal_diff"),
            "advance_prob":       p.get("advance_prob"),
            "reasoning":          p.get("reasoning") or {},
            "scorers":            p.get("scorers") or [],
            "assisters":          p.get("assisters") or [],
            "motm_probs":         p.get("motm_probs") or [],
            "lineups":            p.get("lineups") or {},
            "formations":         p.get("formations") or {},
            "substitutions":      p.get("substitutions") or [],
            "cards":              p.get("cards") or [],
            "penalties":          p.get("penalties") or [],
            "own_goals":          p.get("own_goals") or [],
            "key_events":         p.get("key_events") or [],
            "stats":              p.get("stats") or {},
            "status":             "ok",
            "cost_usd":           rec.get("cost_usd"),
            "sources":            sources,
            **meta,
        })
    if include_missing:
        for expected in MODEL_ROSTER:
            key = (expected["model_id"], expected.get("setting"))
            if key in seen or _is_deep_research_model(expected["model_id"]):
                continue
            out.append(_empty_prediction_payload(
                model_id=expected["model_id"],
                setting=expected.get("setting"),
                status="not_run",
                error_summary="Not run yet; the scheduler will run this model when due.",
            ))
    if include_errors or include_missing:
        out.sort(key=_prediction_display_sort_key)
    return out


def _score_outcome(score: str | None) -> str | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        h_goals, a_goals = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return "home" if h_goals > a_goals else "away" if a_goals > h_goals else "draw"


def _score_total(score: str | None) -> int | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) + int(parts[1])
    except ValueError:
        return None


def _sorted_scores(pred: dict) -> list[dict]:
    return sorted(pred.get("score_dist") or [], key=lambda item: float(item.get("p", 0)), reverse=True)


def _best_score(
    pred: dict,
    predicate,
    *,
    min_ratio: float = 0.68,
    max_rank: int = 10,
) -> dict | None:
    scores = _sorted_scores(pred)
    if not scores:
        return None
    top_p = float(scores[0].get("p", 0))
    for rank, item in enumerate(scores[:max_rank], 1):
        p = float(item.get("p", 0))
        if top_p > 0 and p < top_p * min_ratio:
            continue
        score = str(item.get("score", ""))
        if predicate(score):
            return {"score": score, "p": p, "rank": rank}
    return None


def _display_candidates(pred: dict) -> list[dict]:
    scores = _sorted_scores(pred)
    if not scores:
        return []
    top_p = float(scores[0].get("p", 0))
    candidates = []
    for rank, item in enumerate(scores[:10], 1):
        p = float(item.get("p", 0))
        score = str(item.get("score", ""))
        if top_p > 0 and p < top_p * 0.68:
            continue
        total = _score_total(score) or 0
        candidates.append({
            "score": score,
            "p": p,
            "rank": rank,
            "outcome": _score_outcome(score),
            "total": total,
        })
    return candidates


def _attach_display_picks(preds: list[dict]) -> None:
    """Attach derived site metrics without changing prediction semantics."""
    if not preds:
        return

    for pred in preds:
        over_3_5 = 0.0
        for item in pred.get("score_dist") or []:
            total = _score_total(item.get("score"))
            if total is not None and total >= 4:
                over_3_5 += float(item.get("p", 0))
        pred["over_3_5_prob"] = round(over_3_5, 3)


def _leaderboard_rank_map(leaderboard: dict) -> dict[str, int]:
    return {row["model_id"]: idx for idx, row in enumerate(leaderboard.get("main") or [])}


def _prediction_sort_key(pred: dict, rank_map: dict[str, int]) -> tuple:
    rank = rank_map.get(pred.get("model_id"), 10000 + int(pred.get("config_order", 9999)))
    composite = pred.get("composite")
    composite_key = -(float(composite) if composite is not None else -1.0)
    return (rank, composite_key, int(pred.get("config_order", 9999)), pred.get("model_id", ""))


def _select_default_prediction_indexes(preds: list[dict], rank_map: dict[str, int]) -> set[int]:
    selected: set[int] = set()

    def add_best(predicate) -> None:
        candidates = [(idx, pred) for idx, pred in enumerate(preds) if predicate(pred)]
        if not candidates:
            return
        idx, _ = min(candidates, key=lambda item: _prediction_sort_key(item[1], rank_map))
        selected.add(idx)

    # One representative each for the main closed-model families.
    for family in ("claude", "openai", "gemini"):
        add_best(
            lambda pred, family=family: pred.get("model_family") == family
            and pred.get("model_category") != "deep_research_agent"
        )

    # Always surface all configured Deep Research agents.
    for idx, pred in enumerate(preds):
        if pred.get("model_category") == "deep_research_agent":
            selected.add(idx)

    # Then the strongest open-weight models according to the leaderboard.
    open_candidates = [
        (idx, pred)
        for idx, pred in enumerate(preds)
        if pred.get("model_category") == "open_llm" and pred.get("open_weight")
    ]
    open_candidates.sort(key=lambda item: _prediction_sort_key(item[1], rank_map))
    for idx, _ in open_candidates[:3]:
        selected.add(idx)

    if not selected and preds:
        selected.update(range(min(6, len(preds))))
    return selected


def _attach_default_visibility_to_preds(preds: list[dict], rank_map: dict[str, int]) -> None:
    selected = _select_default_prediction_indexes(preds, rank_map)
    for idx, pred in enumerate(preds):
        pred["default_visible"] = idx in selected
        pred["display_order"] = idx


def _attach_default_visibility(payload: dict, leaderboard: dict) -> None:
    rank_map = _leaderboard_rank_map(leaderboard)
    for item in payload.get("incoming_matches") or []:
        _attach_default_visibility_to_preds(item.get("predictions") or [], rank_map)
    for item in payload.get("history") or []:
        _attach_default_visibility_to_preds(item.get("predictions") or [], rank_map)
    if payload.get("featured_match"):
        _attach_default_visibility_to_preds(payload["featured_match"].get("predictions") or [], rank_map)


def _select_featured_match(history: list[dict]) -> dict | None:
    """Pick the most recent completed match that includes a Deep Research prediction."""
    for item in history:
        if any((p.get("model_category") == "deep_research_agent") for p in item.get("predictions") or []):
            return item
    return None


def build_incoming_matches() -> list[dict]:
    """Return fixtures to display in the Incoming Matches section.

    Includes:
    - Future fixtures within the next 3 days (not yet kicked off)
    - Fixtures that have kicked off but are STILL LIVE according to data/live/
      (status != "Match Finished")

    Fixtures whose live status is "Match Finished" are excluded here and handled
    by build_history() instead.
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)
    registry = _load_fixtures()
    results = []
    for fx in sorted(registry, key=lambda f: _parse_iso(f["kickoff_utc"])):
        kick = _parse_iso(fx["kickoff_utc"])
        if "_test" in fx["wca_id"].lower():
            continue
        wca_id = fx["wca_id"]

        has_predictions = _has_prediction_files(wca_id)
        is_future = kick > now and kick <= cutoff
        live = _load_live_state(wca_id)
        truth = _load_truth_data(wca_id)
        # truth.json is authoritative — if it exists the match is done
        is_finished = (truth is not None) or (live is not None and live.get("status") == "Match Finished")
        is_live = (not is_finished) and live is not None and live.get("status") not in (None, "Not Started", "Match Finished")
        # Match kicked off recently but has no live file and no result yet — treat as live.
        # After a normal match window, stop surfacing it as "live" on the site;
        # it will move to history once truth/live data arrives.
        is_in_progress = (not is_future and not is_finished and live is None
                          and kick <= now and now - kick < timedelta(minutes=135))

        # Skip far-future matches even when predictions already exist; the page
        # should only surface the next 3 days plus live/in-progress fixtures.
        if not is_future and not is_live and not is_in_progress:
            continue
        # If the match is finished, skip here (history picks it up)
        if is_finished:
            continue

        hdr = _load_fixture_header(wca_id)
        snapshot_mismatch = bool(hdr and _header_mismatches_registry(hdr, fx))
        if not hdr or snapshot_mismatch:
            hdr = _fixture_header_from_registry(wca_id, fx, hdr)
        if snapshot_mismatch:
            hdr["snapshot_mismatch"] = True
            hdr["data_warning"] = "Fixture snapshot does not match registry metadata; predictions are hidden until re-ingested."
        preds = [] if snapshot_mismatch else _collect_predictions(
            wca_id,
            fixture=hdr,
            include_errors=has_predictions,
            include_missing=has_predictions,
        )
        _attach_display_picks(preds)
        results.append({
            "fixture": hdr,
            "predictions": preds,
            "live": live,
            "live_predictions": _load_live_predictions(wca_id, fixture=hdr),
        })
    return results


# ---------------------------------------------------------------------------
# Live state (T+0h → T+3h window)
# ---------------------------------------------------------------------------

def _load_live_state(wca_id: str) -> dict | None:
    path = LIVE_DIR / f"{wca_id}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    if "response" not in raw:
        return None
    r0 = raw["response"][0]
    return {
        "status":  (r0["fixture"]["status"] or {}).get("long"),
        "elapsed": (r0["fixture"]["status"] or {}).get("elapsed"),
        "score":   r0.get("goals"),   # {"home": N, "away": N}
        "events":  r0.get("events") or [],
    }


def _public_live_prediction_entry(record: dict, fixture: dict | None = None) -> dict:
    pred = localize_prediction_reasoning(record.get("prediction") or {}, fixture=fixture, copy_prediction=True)
    err = record.get("error")
    status = record.get("status") or ("failed" if err else "ok")
    return {
        "status": status,
        "error_summary": _public_error_summary(err) if err else record.get("error_summary"),
        "submitted_at": record.get("submitted_at"),
        "live": record.get("live") or {},
        "win_probs": pred.get("win_probs") or record.get("win_probs") or {},
        "most_likely_score": pred.get("most_likely_score") or record.get("most_likely_score"),
        "scorers": pred.get("scorers") or record.get("scorers") or record.get("future_scorers") or [],
        "reasoning": pred.get("reasoning") or record.get("reasoning") or {},
        "sources": record.get("sources") or [],
        "cost_usd": record.get("cost_usd"),
        "tokens": record.get("tokens") or {},
        "tool_calls": record.get("tool_calls"),
    }


def _load_live_predictions(wca_id: str, fixture: dict | None = None) -> list[dict]:
    """Load local in-play model forecasts.

    These files are produced by src.pipeline.live_predict and are intentionally
    excluded from grading/leaderboard aggregation.
    """
    pred_dir = LIVE_PREDICTIONS / wca_id
    if not pred_dir.exists():
        return []

    rows: list[dict] = []
    for path in sorted(pred_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except Exception:
            continue
        model_id = record.get("model_id") or _prediction_key_from_path(path)[0]
        if model_id in HIDDEN_SITE_MODELS:
            continue
        meta = MODEL_META.get(model_id) or _infer_model_metadata(model_id)
        latest = _public_live_prediction_entry(record, fixture=fixture)
        history = [_public_live_prediction_entry(item, fixture=fixture) for item in (record.get("history") or [])]
        if not history and record.get("submitted_at"):
            history = [latest]
        rows.append({
            "model_id": model_id,
            "display_name": record.get("display_name") or meta.get("display_name") or _display_model_name(model_id),
            "setting": record.get("setting") or "LIVE",
            "model_category": meta.get("model_category"),
            "provider": meta.get("provider"),
            "model_family": meta.get("model_family"),
            **latest,
            "history": history,
        })

    rows.sort(key=lambda r: (
        MODEL_META.get(r["model_id"], {}).get("config_order", 9999),
        r.get("model_id") or "",
    ))
    return rows


_STAT_TYPE_MAP = {
    "Ball Possession":    "possession",
    "Total Shots":        "shots",
    "Shots on Goal":      "shots_on_target",
    "Corner Kicks":       "corners",
    "Passes %":           "pass_accuracy",
    "Fouls":              "fouls",
    "Goalkeeper Saves":   "saves",
}


def _penalty_shootout_score(truth: dict) -> dict | None:
    """Penalty-shootout tally {home, away} from a sportmonks-shaped truth file, or None.

    The api-football wrapper hardcodes score.penalty to {None, None}; the real shootout count
    lives in the raw sportmonks fixture `scores` under a penalty/shootout description. Returns the
    participant-keyed goals when present (knockout only), else None — the advancing side is still
    derived from teams.*.winner regardless, so this is display polish, not correctness-critical.
    """
    raw = truth.get("_sportmonks_raw") or {}
    pair = {"home": None, "away": None}
    for row in raw.get("scores") or []:
        desc = str(row.get("description") or "").upper()
        if "PENALT" not in desc and "SHOOTOUT" not in desc:
            continue
        sc = row.get("score") or {}
        side = sc.get("participant")
        if side in pair:
            pair[side] = sc.get("goals")
    return pair if (pair["home"] is not None or pair["away"] is not None) else None


def _load_truth_data(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "truth.json"
    if not path.exists():
        return None
    t = json.loads(path.read_text())
    if "response" not in t:
        return {"score": t.get("score"), "result": t.get("result"), "events": []}

    r0 = t["response"][0]
    g = r0.get("goals") or {}
    hg = g.get("home")
    ag = g.get("away")
    score = f"{hg}-{ag}" if hg is not None and ag is not None else None

    teams_raw = r0.get("teams") or {}
    home_id   = (teams_raw.get("home") or {}).get("id")
    home_name = (teams_raw.get("home") or {}).get("name", "Home")
    away_name = (teams_raw.get("away") or {}).get("name", "Away")

    # Knockout ties are level after 90/120 min but still produce a winner (extra time / penalty
    # shootout); derive result from teams.*.winner so it is never "draw" in a single-leg knockout
    # (mirrors ingest.api_football.normalize_to_truth used for grading — keeps display, winner_acc
    # and grading consistent). Only override a level scoreline when exactly one side is flagged
    # winner; a genuine group-stage draw has winner None/False on both sides and stays "draw".
    home_won = (teams_raw.get("home") or {}).get("winner")
    away_won = (teams_raw.get("away") or {}).get("winner")
    if (hg or 0) > (ag or 0):
        result = "home"
    elif (ag or 0) > (hg or 0):
        result = "away"
    elif not score:
        result = None
    elif home_won is True and away_won is not True:
        result = "home"
    elif away_won is True and home_won is not True:
        result = "away"
    else:
        result = "draw"

    # Penalty tally + decider (knockout) for display; advancing side comes from teams.*.winner.
    penalty = _penalty_shootout_score(t)
    status_short = str(((r0.get("fixture") or {}).get("status") or {}).get("short") or "").upper()
    decider = "PEN" if (penalty or "PEN" in status_short) else "AET" if status_short == "AET" else None
    advanced = home_won

    events = r0.get("events") or []
    scorers, assisters, cards, substitutions, own_goals, penalties, key_events = [], [], [], [], [], [], []
    scorer_names, assister_names = [], []
    for ev in events:
        team_id   = (ev.get("team") or {}).get("id")
        team_name = (ev.get("team") or {}).get("name", "")
        side      = "home" if team_id == home_id else "away"
        player    = (ev.get("player") or {}).get("name", "")
        assist    = (ev.get("assist") or {}).get("name")
        minute    = (ev.get("time") or {}).get("elapsed", 0)
        extra     = (ev.get("time") or {}).get("extra")
        ev_type   = ev.get("type", "")
        detail    = ev.get("detail", "")
        if ev_type == "Goal":
            if detail == "Own Goal":
                # API-Football reports the team credited with the goal for own-goal
                # events. Keep that as `for_team`; `team` is the player's own side
                # so the web timeline can use the same semantics as predictions.
                own_goals.append({
                    "minute": minute,
                    "extra": extra,
                    "player": player,
                    "team": "away" if side == "home" else "home",
                    "for_team": side,
                })
            elif detail == "Penalty":
                penalties.append({"minute": minute, "extra": extra, "taker": player, "team": side, "outcome": "scored"})
                scorers.append({"minute": minute, "extra": extra, "player": player, "team": side})
                scorer_names.append(player)
            else:
                scorers.append({"minute": minute, "extra": extra, "player": player, "team": side})
                scorer_names.append(player)
            if assist:
                assisters.append({"minute": minute, "extra": extra, "player": assist, "team": side})
                assister_names.append(assist)
        elif ev_type == "Card":
            color = "yellow" if detail == "Yellow Card" else "red" if detail == "Red Card" else "second_yellow"
            cards.append({"minute": minute, "extra": extra, "player": player, "team": side, "color": color})
        elif ev_type == "subst":
            off = player
            on  = (ev.get("assist") or {}).get("name", "")
            substitutions.append({"minute": minute, "extra": extra, "team": side, "team_name": team_name, "off": off, "on": on})
        elif ev_type or detail:
            label = " - ".join(part for part in [ev_type, detail] if part)
            key_events.append({
                "minute": minute,
                "extra": extra,
                "team": side,
                "player": player,
                "type": ev_type,
                "detail": detail,
                "label": label,
            })

    lineups_raw = r0.get("lineups") or []
    lineups: dict[str, dict] = {}
    formations: dict[str, str] = {}
    for side_data in lineups_raw:
        side_team_id = (side_data.get("team") or {}).get("id")
        side_key = "home" if side_team_id == home_id else "away"
        formations[side_key] = side_data.get("formation", "")
        starting = [
            {"player": (p.get("player") or {}).get("name", ""), "pos": (p.get("player") or {}).get("pos", "")}
            for p in (side_data.get("startXI") or [])
        ]
        lineups[side_key] = {"starting": starting}

    stats_raw = r0.get("statistics") or []
    stats: dict[str, dict] = {}
    for side_idx, side_key in enumerate(["home", "away"]):
        if side_idx >= len(stats_raw):
            break
        for entry in stats_raw[side_idx].get("statistics") or []:
            wca_key = _STAT_TYPE_MAP.get(entry.get("type", ""))
            if not wca_key:
                continue
            val = entry.get("value")
            if isinstance(val, str) and val.endswith("%"):
                val = float(val.rstrip("%"))
            if val is None:
                continue
            stats.setdefault(wca_key, {})[side_key] = val

    return {
        "score":          score,
        "result":         result,
        "advanced":       advanced,
        "penalty":        penalty,
        "decider":        decider,
        "home_name":      home_name,
        "away_name":      away_name,
        "scorer_names":   scorer_names,
        "assister_names": assister_names,
        "scorers":        scorers,
        "assisters":      assisters,
        "cards":          cards,
        "substitutions":  substitutions,
        "own_goals":      own_goals,
        "penalties":      penalties,
        "key_events":     key_events,
        "formations":     formations,
        "lineups":        lineups,
        "stats":          stats,
        "events":         events,
    }


def _side_from_event_team_name(team_name: str | None, hdr: dict) -> str:
    def compact(value: str | None) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    team_key = compact(team_name)
    home_key = compact(hdr.get("home"))
    away_key = compact(hdr.get("away"))
    if team_key and home_key and team_key == home_key:
        return "home"
    if team_key and away_key and team_key == away_key:
        return "away"
    return "home"


def _truth_from_live_state(live: dict | None, hdr: dict) -> dict | None:
    if not live or not live.get("score"):
        return None
    sc = live.get("score") or {}
    hg, ag = sc.get("home"), sc.get("away")
    score = f"{hg}-{ag}" if hg is not None and ag is not None else None
    if not score:
        return None
    result = "home" if (hg or 0) > (ag or 0) else "away" if (ag or 0) > (hg or 0) else "draw"

    scorers, assisters, cards, substitutions, own_goals, penalties, key_events = [], [], [], [], [], [], []
    scorer_names, assister_names = [], []
    events = live.get("events") or []
    for ev in events:
        team_name = (ev.get("team") or {}).get("name", "")
        side = _side_from_event_team_name(team_name, hdr)
        player = (ev.get("player") or {}).get("name", "")
        assist = (ev.get("assist") or {}).get("name")
        minute = (ev.get("time") or {}).get("elapsed", 0)
        extra = (ev.get("time") or {}).get("extra")
        ev_type = ev.get("type", "")
        detail = ev.get("detail", "")
        if ev_type == "Goal":
            if detail == "Own Goal":
                own_goals.append({
                    "minute": minute,
                    "extra": extra,
                    "player": player,
                    "team": "away" if side == "home" else "home",
                    "for_team": side,
                })
            elif detail == "Penalty":
                penalties.append({"minute": minute, "extra": extra, "taker": player, "team": side, "outcome": "scored"})
                scorers.append({"minute": minute, "extra": extra, "player": player, "team": side})
                scorer_names.append(player)
            else:
                scorers.append({"minute": minute, "extra": extra, "player": player, "team": side})
                scorer_names.append(player)
            if assist:
                assisters.append({"minute": minute, "extra": extra, "player": assist, "team": side})
                assister_names.append(assist)
        elif ev_type == "Card":
            color = "yellow" if detail == "Yellow Card" else "red" if detail == "Red Card" else "second_yellow"
            cards.append({"minute": minute, "extra": extra, "player": player, "team": side, "color": color})
        elif ev_type == "subst":
            substitutions.append({
                "minute": minute,
                "extra": extra,
                "team": side,
                "team_name": team_name,
                "off": player,
                "on": (ev.get("assist") or {}).get("name", ""),
            })
        elif ev_type or detail:
            label = " - ".join(part for part in [ev_type, detail] if part)
            key_events.append({
                "minute": minute,
                "extra": extra,
                "team": side,
                "player": player,
                "type": ev_type,
                "detail": detail,
                "label": label,
            })

    return {
        "score": score,
        "result": result,
        "home_name": hdr.get("home"),
        "away_name": hdr.get("away"),
        "scorer_names": scorer_names,
        "assister_names": assister_names,
        "scorers": scorers,
        "assisters": assisters,
        "cards": cards,
        "substitutions": substitutions,
        "own_goals": own_goals,
        "penalties": penalties,
        "key_events": key_events,
        "formations": {},
        "lineups": {},
        "stats": {},
        "events": events,
    }


# ---------------------------------------------------------------------------
# History (past fixtures — combines graded results with full predictions)
# ---------------------------------------------------------------------------

def build_history() -> list[dict]:
    now = datetime.now(timezone.utc)

    # Collect all known wca_ids from results + predictions dirs + yaml
    wca_ids: set[str] = set()
    if RESULTS.exists():
        wca_ids.update(d.name for d in RESULTS.glob("*") if d.is_dir())
    if PREDICTIONS.exists():
        wca_ids.update(d.name for d in PREDICTIONS.glob("*") if d.is_dir())
    for fx in _load_fixtures():
        if _parse_iso(fx["kickoff_utc"]) <= now:
            wca_ids.add(fx["wca_id"])
    # Also include fixtures whose live.json says "Match Finished" even if
    # truth.json hasn't arrived yet (grading will run on the next tick).
    if LIVE_DIR.exists():
        for lf in LIVE_DIR.glob("*.json"):
            try:
                raw = json.loads(lf.read_text())
                r0 = raw["response"][0]
                status = (r0["fixture"]["status"] or {}).get("long")
                if status == "Match Finished":
                    wca_ids.add(lf.stem)
            except Exception:
                pass

    rows = []
    for wca_id in wca_ids:
        if "_test" in wca_id.lower() or wca_id.lower().startswith("test_"):
            continue
        # Reset: drop pre-World-Cup matches from history except a few kept as examples.
        if _is_pre_cutoff(wca_id) and wca_id not in HISTORY_EXAMPLE_WHITELIST:
            continue
        hdr = _load_fixture_header(wca_id) or {"wca_id": wca_id}

        # Exclude fixtures still live (they show in incoming_matches instead)
        live = _load_live_state(wca_id)
        truth_check = _load_truth_data(wca_id)
        # truth.json is authoritative — if it exists the match is done (even if live file is stale)
        is_done = truth_check is not None or (live and live.get("status") == "Match Finished")
        if not is_done:
            if live and live.get("status") and live.get("status") != "Match Finished":
                continue  # still live, shows in incoming
            # Exclude matches that kicked off recently but have no result/live yet
            kick_for_recent_check = hdr.get("kickoff_utc")
            kick_dt = _parse_iso(kick_for_recent_check) if kick_for_recent_check else None
            if (kick_dt and live is None
                    and kick_dt <= now and now - kick_dt < timedelta(hours=3)):
                continue

        # Only include past fixtures (or live-finished ones detected above)
        kick = hdr.get("kickoff_utc")
        if kick and _parse_iso(kick) > now:
            continue

        truth = _load_truth_data(wca_id)

        # If truth.json not yet available, try to build score and event timeline from live.json.
        result = None
        if truth:
            result = truth.get("score")
        elif live and live.get("score"):
            sc = live["score"]
            h, a = sc.get("home"), sc.get("away")
            if h is not None and a is not None:
                result = f"{h}-{a}"
                truth = _truth_from_live_state(live, hdr)
        if not result:
            continue

        # Recover team names/flags/kickoff for fixtures whose pre-match snapshot
        # was captured during a provider outage (null teams -> "? vs ?").
        hdr = _enrich_history_header(hdr, wca_id, truth)

        # Composite scores from results dir (for leaderboard ordering within card)
        composites: dict[str, float] = {}
        result_dir = RESULTS / wca_id
        if result_dir.exists():
            for f in result_dir.glob("*.json"):
                r = json.loads(f.read_text())
                key = f"{r['model_id']}_{r['setting']}"
                composites[key] = r.get("composite", 0.0)

        # Full predictions
        preds = _collect_predictions(wca_id, fixture=hdr)
        _attach_display_picks(preds)
        for p in preds:
            key = f"{p['model_id']}_{p['setting']}"
            p["composite"] = composites.get(key)

        models = sorted(
            [{"model_id": p["model_id"], "setting": p["setting"],
              "composite": composites.get(f"{p['model_id']}_{p['setting']}", 0.0)}
             for p in preds],
            key=lambda m: -(m["composite"] or 0.0),
        )

        rows.append({**hdr, "result": result, "truth": truth, "live": live,
                     "models": models, "predictions": preds})

    # Sort by kickoff descending
    rows.sort(key=lambda r: _parse_iso(r["kickoff_utc"]) if r.get("kickoff_utc") else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


def _attach_comments(items: list[dict], key: str = "fixture") -> None:
    comments = _load_comments()
    for item in items:
        wca_id = (item.get(key) or item).get("wca_id") if key else item.get("wca_id")
        if wca_id and wca_id in comments:
            item["comment"] = comments[wca_id]


def _load_name_localization() -> dict:
    if not NAME_LOCALIZATION_JSON.exists():
        return {"teams": {}, "players": {}}
    try:
        raw = json.loads(NAME_LOCALIZATION_JSON.read_text())
    except Exception as exc:
        print(f"[site] skipping name localization: {exc}")
        return {"teams": {}, "players": {}}
    teams = {
        name: (item.get("zh") if isinstance(item, dict) else item)
        for name, item in (raw.get("teams") or {}).items()
        if name and item
    }
    players = {}
    for name, item in (raw.get("players") or {}).items():
        if not isinstance(item, dict):
            continue
        players[name] = {
            "zh": item.get("zh") or name,
            "team": item.get("team"),
            "team_zh": item.get("team_zh"),
            "number": item.get("number"),
            "position": item.get("position"),
            "photo": item.get("photo") or "",
        }
    return {
        "teams": teams,
        "players": players,
        "sources": raw.get("sources") or [],
    }


def _public_tournament_prediction(record: dict, path: Path) -> dict:
    fallback_model_id, fallback_setting = _prediction_key_from_path(path)
    model_id = record.get("model_id") or fallback_model_id
    meta = MODEL_META.get(model_id) or _infer_model_metadata(model_id)
    pred = record.get("prediction") or {}
    status = record.get("status") or ("failed" if record.get("error") else "ok")
    return {
        "model_id": model_id,
        "display_name": record.get("display_name") or meta.get("display_name") or _display_model_name(model_id),
        "setting": record.get("setting") or fallback_setting,
        "model_category": record.get("model_category") or meta.get("model_category"),
        "provider": meta.get("provider"),
        "model_family": meta.get("model_family"),
        "status": status,
        "error_summary": _public_error_summary(record.get("error")) if record.get("error") else record.get("error_summary"),
        "submitted_at": record.get("submitted_at"),
        "champion": pred.get("champion"),
        "runner_up": pred.get("runner_up"),
        "third_place": pred.get("third_place"),
        "summary": pred.get("summary") or {},
        "group_matches": pred.get("group_matches") or [],
        "group_standings": pred.get("group_standings") or {},
        "third_place_qualifiers": pred.get("third_place_qualifiers") or [],
        "third_place_slot_assignment": pred.get("third_place_slot_assignment") or {},
        "round_of_32": pred.get("round_of_32") or [],
        "knockout_matches": pred.get("knockout_matches") or [],
        "top_scorers": pred.get("top_scorers") or [],
        "sources": record.get("sources") or [],
        "tokens": record.get("tokens") or {},
        "tool_calls": record.get("tool_calls"),
        "cost_usd": record.get("cost_usd"),
        "wall_seconds": record.get("wall_seconds"),
        **meta,
    }


def build_tournament_predictions() -> dict | None:
    if not TOURNAMENT_SPEC.exists():
        return None
    try:
        spec = json.loads(TOURNAMENT_SPEC.read_text())
    except Exception as exc:
        print(f"[site] skipping tournament spec: {exc}")
        return None

    rows: list[dict] = []
    if TOURNAMENT_PREDICTIONS.exists():
        for path in sorted(TOURNAMENT_PREDICTIONS.glob("*.json")):
            try:
                record = json.loads(path.read_text())
            except Exception:
                continue
            model_id = record.get("model_id") or _prediction_key_from_path(path)[0]
            if model_id in HIDDEN_SITE_MODELS:
                continue
            rows.append(_public_tournament_prediction(record, path))

    rows.sort(key=lambda row: (
        int(row.get("config_order", 9999)),
        str(row.get("setting") or ""),
        row.get("model_id") or "",
    ))
    return {
        "tournament_id": spec.get("tournament_id"),
        "name": spec.get("name"),
        "format": spec.get("format") or {},
        "groups": spec.get("groups") or {},
        "group_stage_matches": spec.get("group_stage_matches") or [],
        "knockout_matches": spec.get("knockout_matches") or [],
        "sources": spec.get("sources") or [],
        "name_localization": _load_name_localization(),
        "predictions": rows,
    }


def main() -> None:
    incoming = build_incoming_matches()
    _attach_comments(incoming, key="fixture")
    history = build_history()
    _attach_comments(history, key=None)
    leaderboard = build_leaderboard()
    payload = {
        # "generated_at":     _now_iso(),
        "leaderboard":      leaderboard,
        # Knockout-only slice (R32 onwards), same shape/metrics as `leaderboard`.
        # Absent key ⇒ old data JSON; the site hides the scope toggle then.
        "leaderboard_knockout": build_leaderboard(fixture_filter=_is_knockout_wca_id),
        "incoming_matches": incoming,
        "featured_match":   _select_featured_match(history),
        "history":          history,
        "tournament_predictions": build_tournament_predictions(),
    }
    # Attach the country flag to each fixture so the prediction card can show it
    # prominently next to the predicted winner. We attach BOTH the emoji (home_flag)
    # and an image URL (home_flag_img) decoded from the emoji's country code — emoji
    # flags don't render on Windows (they degrade to letters, e.g. "MX"), so the card
    # uses the image; the emoji is kept as a lightweight fallback.
    def _flag_img_url(_emoji: str) -> str:
        _code = "".join(
            chr(ord(_c) - 0x1F1E6 + ord("a")) for _c in _emoji if 0x1F1E6 <= ord(_c) <= 0x1F1FF
        )
        return f"https://media.api-sports.io/flags/{_code}.svg" if len(_code) == 2 else ""

    _flag_by_team: dict[str, str] = {}
    _groups = (payload.get("tournament_predictions") or {}).get("groups") or {}
    for _grp in (_groups.values() if isinstance(_groups, dict) else _groups):
        for _tm in (_grp or []):
            if isinstance(_tm, dict) and _tm.get("name") and _tm.get("flag"):
                for _key in _team_flag_lookup_keys(_tm["name"]):
                    _flag_by_team[_key] = _tm["flag"]
    for _m in (payload.get("incoming_matches") or []) + (payload.get("history") or []):
        _fx = _m.get("fixture") or {}
        for _side in ("home", "away"):
            _emoji = next(
                (_flag_by_team[_key] for _key in _team_flag_lookup_keys(_fx.get(_side)) if _key in _flag_by_team),
                None,
            )
            if _emoji:
                _fx[f"{_side}_flag"] = _emoji
                _img = _flag_img_url(_emoji)
                if _img:
                    _fx[f"{_side}_flag_img"] = _img
    # Tournament team objects (groups[].teams[]) carry their own flag emoji — attach a
    # flag_img to each so 完整赛事预测 (tournamentTeamHtml) can render the flag image too.
    def _attach_team_flag_imgs(_o):
        if isinstance(_o, dict):
            _fl = _o.get("flag")
            if isinstance(_fl, str) and not _o.get("flag_img"):
                _img = _flag_img_url(_fl)
                if _img:
                    _o["flag_img"] = _img
            for _v in _o.values():
                _attach_team_flag_imgs(_v)
        elif isinstance(_o, list):
            for _v in _o:
                _attach_team_flag_imgs(_v)

    _attach_team_flag_imgs(payload.get("tournament_predictions"))
    _attach_default_visibility(payload, leaderboard)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # # Only write if content changed (ignoring generated_at), so the cron commit
    # # isn't triggered purely by a timestamp update.
    # def _content(p: dict) -> str:
    #     return json.dumps({k: v for k, v in p.items() if k != "generated_at"},
    #                       ensure_ascii=False, sort_keys=True)

    # if OUT.exists():
    #     try:
    #         old = json.loads(OUT.read_text())
    #         if _content(old) == _content(payload):
    #             print(f"skip write — content unchanged "
    #                   f"(leaderboard_models={len(payload['leaderboard']['main'])}, "
    #                   f"incoming={len(incoming)}, "
    #                   f"history={len(payload['history'])})")
    #             return
    #     except Exception:
    #         pass  # malformed existing file — overwrite

    def _round3(obj):
        if isinstance(obj, float):
            return round(obj, 3)
        if isinstance(obj, dict):
            return {k: _round3(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_round3(v) for v in obj]
        return obj

    _save_api_football_logo_cache()

    rounded_payload = _round3(payload)
    from .translate_site_data import translate_payload_to_zh
    zh_payload = translate_payload_to_zh(rounded_payload)
    def _dump(obj):
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    for out_path in (OUT_EN, OUT):
        out_path.write_text(_dump(rounded_payload))
    OUT_ZH.write_text(_dump(zh_payload))
    for full_path, full in ((OUT, rounded_payload), (OUT_EN, rounded_payload), (OUT_ZH, zh_payload)):
        hist_name = full_path.name.replace("data.", "data.history.", 1)
        live = {k: v for k, v in full.items() if k != "history"}
        live["_history_url"] = hist_name
        full_path.with_name(full_path.name.replace("data.", "data.live.", 1)).write_text(_dump(live))
        full_path.with_name(hist_name).write_text(_dump({"history": full.get("history") or []}))
    print(f"wrote {OUT}, {OUT_ZH}, {OUT_EN} "
          f"(model_native_payload=1, "
          f"leaderboard_models={len(payload['leaderboard']['main'])}, "
          f"knockout_models={len(payload['leaderboard_knockout']['main'])}, "
          f"incoming={len(incoming)}, "
          f"history={len(payload['history'])})")


if __name__ == "__main__":
    main()
