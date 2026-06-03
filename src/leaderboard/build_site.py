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
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from ..pipeline.prediction_derivatives import derive_most_likely_score, derive_win_probs_from_score_dist
from .translate_site_data import translate_payload_to_zh

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data" / "results"
PREDICTIONS = ROOT / "data" / "predictions"
SNAPSHOTS = ROOT / "data" / "snapshots"
LIVE_DIR = ROOT / "data" / "live"
SEARCH_LOGS = ROOT / "data" / "search_logs"
FIXTURES_YAML = ROOT / "configs" / "fixtures.yaml"
MODELS_YAML = ROOT / "configs" / "models.yaml"
COMMENTS_JSON = ROOT / "data" / "comments.json"
OUT = ROOT / "docs" / "site" / "data.json"
OUT_EN = ROOT / "docs" / "site" / "data.en.json"
OUT_ZH = ROOT / "docs" / "site" / "data.zh.json"
HIDDEN_SITE_MODELS = {"yunwu-o4-mini-deep-research"}


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
        "venue":       base.get("venue"),
        "venue_city":    base.get("venue_city"),
        "venue_country": base.get("venue_country"),
        "stage":         base.get("stage"),
        "competition": fx.get("competition") or inferred.get("competition") or base.get("competition"),
    })
    return base


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

def build_leaderboard() -> dict:
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
        return {
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
        }
    return {
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
    }


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


def _collect_predictions(
    wca_id: str,
    *,
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
        seen.add((model_id, setting))
        if rec.get("error"):
            if include_errors:
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
        p = rec.get("prediction") or {}

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
        most_likely_score = p.get("most_likely_score") or derive_most_likely_score(p.get("score_dist") or [])
        meta = MODEL_META.get(rec["model_id"]) or _infer_model_metadata(rec["model_id"])

        out.append({
            "model_id":           rec["model_id"],
            "setting":            rec["setting"],
            "win_probs":          win_probs,
            "score_dist":         p.get("score_dist") or [],
            "most_likely_score":  most_likely_score,
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
            "stats":              p.get("stats") or {},
            "status":             "ok",
            "cost_usd":           rec.get("cost_usd"),
            "sources":            sources,
            **meta,
        })
    if include_missing:
        for expected in MODEL_ROSTER:
            key = (expected["model_id"], expected.get("setting"))
            if key in seen:
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
    - Future fixtures within the next 7 days (not yet kicked off)
    - Fixtures that have kicked off but are STILL LIVE according to data/live/
      (status != "Match Finished")

    Fixtures whose live status is "Match Finished" are excluded here and handled
    by build_history() instead.
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=7)
    registry = _load_fixtures()
    results = []
    for fx in sorted(registry, key=lambda f: _parse_iso(f["kickoff_utc"])):
        kick = _parse_iso(fx["kickoff_utc"])
        if "_test" in fx["wca_id"].lower():
            continue
        wca_id = fx["wca_id"]

        has_predictions = _has_prediction_files(wca_id)
        is_future = kick > now and kick <= cutoff
        is_future_with_predictions = kick > now and has_predictions
        live = _load_live_state(wca_id)
        truth = _load_truth_data(wca_id)
        # truth.json is authoritative — if it exists the match is done
        is_finished = (truth is not None) or (live is not None and live.get("status") == "Match Finished")
        is_live = (not is_finished) and live is not None and live.get("status") not in (None, "Not Started", "Match Finished")
        # Match kicked off recently but has no live file and no result yet — treat as live
        is_in_progress = (not is_future and not is_finished and live is None
                          and kick <= now and now - kick < timedelta(hours=3))

        # Skip far-future unless predictions already exist, and anything done.
        if not is_future and not is_future_with_predictions and not is_live and not is_in_progress:
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
            include_errors=has_predictions,
            include_missing=has_predictions,
        )
        _attach_display_picks(preds)
        results.append({"fixture": hdr, "predictions": preds, "live": live})
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


_STAT_TYPE_MAP = {
    "Ball Possession":    "possession",
    "Total Shots":        "shots",
    "Shots on Goal":      "shots_on_target",
    "Corner Kicks":       "corners",
    "Passes %":           "pass_accuracy",
    "Fouls":              "fouls",
    "Goalkeeper Saves":   "saves",
}


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
    result = "home" if (hg or 0) > (ag or 0) else "away" if (ag or 0) > (hg or 0) else "draw" if score else None

    teams_raw = r0.get("teams") or {}
    home_id   = (teams_raw.get("home") or {}).get("id")
    home_name = (teams_raw.get("home") or {}).get("name", "Home")
    away_name = (teams_raw.get("away") or {}).get("name", "Away")

    events = r0.get("events") or []
    scorers, assisters, cards, substitutions, own_goals, penalties = [], [], [], [], [], []
    scorer_names, assister_names = [], []
    for ev in events:
        team_id   = (ev.get("team") or {}).get("id")
        team_name = (ev.get("team") or {}).get("name", "")
        side      = "home" if team_id == home_id else "away"
        player    = (ev.get("player") or {}).get("name", "")
        assist    = (ev.get("assist") or {}).get("name")
        minute    = (ev.get("time") or {}).get("elapsed", 0)
        ev_type   = ev.get("type", "")
        detail    = ev.get("detail", "")
        if ev_type == "Goal":
            if detail == "Own Goal":
                own_goals.append({"minute": minute, "player": player, "team": side})
            elif detail == "Penalty":
                penalties.append({"minute": minute, "taker": player, "team": side, "outcome": "scored"})
                scorers.append({"minute": minute, "player": player, "team": side})
                scorer_names.append(player)
            else:
                scorers.append({"minute": minute, "player": player, "team": side})
                scorer_names.append(player)
            if assist:
                assisters.append({"player": assist, "team": side})
                assister_names.append(assist)
        elif ev_type == "Card":
            color = "yellow" if detail == "Yellow Card" else "red" if detail == "Red Card" else "second_yellow"
            cards.append({"minute": minute, "player": player, "team": side, "color": color})
        elif ev_type == "subst":
            off = player
            on  = (ev.get("assist") or {}).get("name", "")
            substitutions.append({"minute": minute, "team": side, "team_name": team_name, "off": off, "on": on})

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
        "formations":     formations,
        "lineups":        lineups,
        "stats":          stats,
        "events":         events,
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
            kick_dt = _parse_iso(hdr.get("kickoff_utc") or "")
            if (kick_dt and live is None
                    and kick_dt <= now and now - kick_dt < timedelta(hours=3)):
                continue

        # Only include past fixtures (or live-finished ones detected above)
        kick = hdr.get("kickoff_utc")
        if kick and _parse_iso(kick) > now:
            continue

        truth = _load_truth_data(wca_id)

        # If truth.json not yet available, try to build score from live.json
        result = None
        if truth:
            result = truth.get("score")
        elif live and live.get("score"):
            sc = live["score"]
            h, a = sc.get("home"), sc.get("away")
            if h is not None and a is not None:
                result = f"{h}-{a}"
        if not result:
            continue

        # Composite scores from results dir (for leaderboard ordering within card)
        composites: dict[str, float] = {}
        result_dir = RESULTS / wca_id
        if result_dir.exists():
            for f in result_dir.glob("*.json"):
                r = json.loads(f.read_text())
                key = f"{r['model_id']}_{r['setting']}"
                composites[key] = r.get("composite", 0.0)

        # Full predictions
        preds = _collect_predictions(wca_id)
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


def main() -> None:
    incoming = build_incoming_matches()
    _attach_comments(incoming, key="fixture")
    history = build_history()
    _attach_comments(history, key=None)
    leaderboard = build_leaderboard()
    payload = {
        # "generated_at":     _now_iso(),
        "leaderboard":      leaderboard,
        "incoming_matches": incoming,
        "featured_match":   _select_featured_match(history),
        "history":          history,
    }
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

    rounded_payload = _round3(payload)
    OUT_EN.write_text(json.dumps(rounded_payload, ensure_ascii=False, indent=2))
    print(f"wrote {OUT_EN}")

    try:
        print("[translate] building Simplified Chinese site payload", flush=True)
        zh_payload = translate_payload_to_zh(rounded_payload)
    except Exception as exc:
        print(f"[translate] failed to build Chinese payload; falling back to English data: {exc}")
        zh_payload = rounded_payload

    OUT_ZH.write_text(json.dumps(zh_payload, ensure_ascii=False, indent=2))
    OUT.write_text(json.dumps(zh_payload, ensure_ascii=False, indent=2))
    print(f"wrote {OUT}, {OUT_ZH}, {OUT_EN} "
          f"(leaderboard_models={len(payload['leaderboard']['main'])}, "
          f"incoming={len(incoming)}, "
          f"history={len(payload['history'])})")


if __name__ == "__main__":
    main()
