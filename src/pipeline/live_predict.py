"""In-play prediction runner for a single fixture.

This module is intentionally outside the GitHub automation scheduler. It is a
local operator tool for matchday: fetch the current API-Football live state,
ask one or more models for an updated final-result forecast, write
data/live_predictions/, and optionally rebuild the static site payload.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from ..ingest.api_football import football_api_provider, get_football_client
from ..runners import build_runner
from .prediction_derivatives import best_win_outcome, normalize_win_probs, score_outcome


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
LIVE_DIR = DATA / "live"
LIVE_PREDICTIONS_DIR = DATA / "live_predictions"
MODELS_YAML = CONFIGS / "models.yaml"
FIXTURES_YAML = CONFIGS / "fixtures.yaml"
DEFAULT_LIVE_MODELS = ["gpt-5.4"]
LIVE_HISTORY_LIMIT = 288
FINISHED_STATUSES = {"Match Finished"}
HALFTIME_STATUSES = {"ht", "half time", "halftime"}
NON_LIVE_STATUSES = {None, "Not Started", "Match Finished", "Match Postponed", "Match Cancelled"}

load_dotenv(ROOT / ".env")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_models() -> dict[str, dict[str, Any]]:
    cfg = yaml.safe_load(MODELS_YAML.read_text()) or {}
    models: dict[str, dict[str, Any]] = {}
    for category, entries in cfg.items():
        if category == "baselines":
            continue
        for model in entries or []:
            model_id = model.get("id")
            if not model_id:
                continue
            models[model_id] = {"model_category": category, **model}
    return models


def _fixture_registry() -> list[dict[str, Any]]:
    if not FIXTURES_YAML.exists():
        return []
    cfg = yaml.safe_load(FIXTURES_YAML.read_text()) or {}
    return [fx for fx in (cfg.get("fixtures") or []) if fx.get("enabled", True)]


def _provider_for_fixture(wca_id: str, explicit_provider: str | None = None) -> str:
    if explicit_provider:
        return football_api_provider(explicit_provider)
    for fx in _fixture_registry():
        if str(fx.get("wca_id")) == str(wca_id):
            return football_api_provider(fx.get("provider"))
    return football_api_provider(None)


def _fixture_response(raw: dict[str, Any]) -> dict[str, Any]:
    response = raw.get("response") or []
    if not response:
        raise RuntimeError("API-Football returned an empty fixture response")
    return response[0]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _event_minute(event: dict[str, Any]) -> int | None:
    time_obj = event.get("time") or {}
    elapsed = time_obj.get("elapsed")
    extra = time_obj.get("extra") or 0
    if elapsed is None:
        return None
    try:
        return int(elapsed) + int(extra)
    except (TypeError, ValueError):
        return None


def _team_side(team_id: Any, home_id: Any, away_id: Any) -> str | None:
    if team_id == home_id:
        return "home"
    if team_id == away_id:
        return "away"
    return None


def _current_score(raw: dict[str, Any]) -> tuple[int, int]:
    r0 = _fixture_response(raw)
    goals = r0.get("goals") or {}
    return _safe_int(goals.get("home")), _safe_int(goals.get("away"))


def _elapsed_from_kickoff(kickoff_utc: str | None, status_long: str | None) -> int | None:
    if not kickoff_utc or status_long in NON_LIVE_STATUSES:
        return None
    try:
        kickoff = datetime.fromisoformat(str(kickoff_utc).replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    delta = int((datetime.now(timezone.utc) - kickoff).total_seconds() // 60)
    if delta < 0:
        return None

    status = str(status_long or "").casefold()
    if "half time" in status or status in {"ht", "halftime"}:
        return 45
    if "1st" in status or "first" in status:
        return max(1, min(45, delta))
    if "2nd" in status or "second" in status:
        return max(46, min(90, delta - 15 if delta >= 60 else delta))
    if "extra" in status:
        return max(91, min(130, delta - 15))
    return max(1, min(130, delta))


def _live_summary(raw: dict[str, Any]) -> dict[str, Any]:
    r0 = _fixture_response(raw)
    fixture = r0.get("fixture") or {}
    status = fixture.get("status") or {}
    league = r0.get("league") or {}
    teams = r0.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    goals = r0.get("goals") or {}
    venue = fixture.get("venue") or {}

    status_long = status.get("long")
    elapsed = status.get("elapsed")
    if elapsed is not None:
        elapsed = _safe_int(elapsed, default=None)
    if elapsed is None:
        elapsed = _elapsed_from_kickoff(fixture.get("date"), status_long)

    return {
        "status": status_long,
        "elapsed": elapsed,
        "score": {"home": goals.get("home"), "away": goals.get("away")},
        "home": home.get("name"),
        "away": away.get("name"),
        "competition": league.get("name"),
        "stage": league.get("round"),
        "kickoff_utc": fixture.get("date"),
        "venue": venue.get("name"),
        "venue_city": venue.get("city"),
    }


def _compact_statistics(raw: dict[str, Any]) -> list[dict[str, Any]]:
    r0 = _fixture_response(raw)
    out: list[dict[str, Any]] = []
    for item in r0.get("statistics") or []:
        team = (item.get("team") or {}).get("name")
        stats = {}
        for stat in item.get("statistics") or []:
            key = stat.get("type")
            value = stat.get("value")
            if key and value is not None:
                stats[key] = value
        if team and stats:
            out.append({"team": team, "stats": stats})
    return out


def _compact_events(raw: dict[str, Any]) -> list[dict[str, Any]]:
    r0 = _fixture_response(raw)
    teams = r0.get("teams") or {}
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")
    events = []
    for event in r0.get("events") or []:
        team = event.get("team") or {}
        player = event.get("player") or {}
        assist = event.get("assist") or {}
        events.append({
            "minute": _event_minute(event),
            "team": team.get("name"),
            "side": _team_side(team.get("id"), home_id, away_id),
            "type": event.get("type"),
            "detail": event.get("detail"),
            "player": player.get("name"),
            "assist": assist.get("name"),
        })
    return events


def _build_live_prompt(raw: dict[str, Any], wca_id: str) -> tuple[str, str]:
    summary = _live_summary(raw)
    payload = {
        "fixture_id": wca_id,
        "live": summary,
        "events_so_far": _compact_events(raw),
        "statistics_so_far": _compact_statistics(raw),
    }
    elapsed = summary.get("elapsed")
    elapsed_text = f"{elapsed}'" if elapsed is not None else "the current live minute"
    current_score = summary.get("score") or {}

    system_prompt = (
        "You are WorldCupArena's in-play football prediction engine. "
        "Return only a single valid JSON object. Do not include markdown. "
        "Write narrative reasoning in Simplified Chinese, while keeping schema field names, "
        "enum values, score strings, probabilities, and structured player names machine-stable."
    )
    user_prompt = f"""
Update the live prediction for this match using only the current match state below.

Current score: {current_score.get("home")} - {current_score.get("away")}
Current time: {elapsed_text}

Language and scoring constraints:
- Write `reasoning.overall` in Simplified Chinese as a complete in-play rationale, covering current score/time, match flow from available events/statistics, probability changes, final-score logic, and future-goalscorer logic.
- Keep `team` values exactly `home` or `away`.
- Keep `most_likely_score` as an `H-A` score string and probabilities as numbers.
- For `scorers[].player`, use the official/API player name form from the live state when available. Do not translate structured player-name fields into Chinese-only names; bilingual names may appear in the Chinese reasoning text.

You must predict:
- final win/draw/loss probabilities as win_probs.home, win_probs.draw, win_probs.away;
- the single most likely FINAL score as most_likely_score;
- likely future goalscorers only after {elapsed_text}.

Do not predict starting lineups, match statistics, cards, substitutions, or key events.
The final score must be compatible with the highest win probability:
- if home is highest, most_likely_score must be a home win;
- if draw is highest, most_likely_score must be a draw;
- if away is highest, most_likely_score must be an away win.
The final score must not be lower than the current score for either team.
Every scorer minute must be strictly after the current elapsed minute.

JSON schema:
{{
  "win_probs": {{"home": 0.0, "draw": 0.0, "away": 0.0}},
  "most_likely_score": "0-0",
  "scorers": [
    {{"player": "Player Name", "team": "home", "minute": 72, "p": 0.32}}
  ],
  "reasoning": {{"overall": "用中文完整说明本次赛中预测更新，包括当前比分与时间、场面依据、概率判断、最可能最终比分和后续进球逻辑。"}},
  "sources": []
}}

Live match state:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
    return system_prompt, user_prompt


def _parse_score(value: Any) -> tuple[int, int] | None:
    parts = str(value or "").replace(":", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None


def _consistent_score(raw_score: Any, win_probs: dict[str, float], current: tuple[int, int]) -> str:
    h, a = _parse_score(raw_score) or current
    h = max(h, current[0])
    a = max(a, current[1])
    target = best_win_outcome(win_probs) or score_outcome(f"{h}-{a}") or "draw"

    if target == "home" and h <= a:
        h = max(current[0], a + 1)
    elif target == "away" and a <= h:
        a = max(current[1], h + 1)
    elif target == "draw" and h != a:
        tied = max(h, a, current[0], current[1])
        h = tied
        a = tied
    return f"{h}-{a}"


def _normalize_team(value: Any, raw: dict[str, Any]) -> str | None:
    team = str(value or "").strip().lower()
    if team in {"home", "h"}:
        return "home"
    if team in {"away", "a"}:
        return "away"
    r0 = _fixture_response(raw)
    teams = r0.get("teams") or {}
    home_name = str((teams.get("home") or {}).get("name") or "").strip().lower()
    away_name = str((teams.get("away") or {}).get("name") or "").strip().lower()
    if team and team == home_name:
        return "home"
    if team and team == away_name:
        return "away"
    return None


def _normalize_scorers(pred: dict[str, Any], raw: dict[str, Any], final_score: str) -> list[dict[str, Any]]:
    r0 = _fixture_response(raw)
    status = ((r0.get("fixture") or {}).get("status") or {})
    elapsed = _safe_int(status.get("elapsed"), default=-1)
    current_h, current_a = _current_score(raw)
    final_h, final_a = _parse_score(final_score) or (current_h, current_a)
    expected_future_goals = max(0, final_h - current_h) + max(0, final_a - current_a)
    if expected_future_goals <= 0:
        return []

    raw_items = (
        pred.get("scorers")
        or pred.get("future_scorers")
        or pred.get("goal_scorers")
        or []
    )
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, str):
            item = {"player": item}
        if not isinstance(item, dict):
            continue
        player = str(item.get("player") or item.get("name") or "").strip()
        if not player:
            continue
        minute = item.get("minute") or item.get("min")
        try:
            minute_int = int(minute)
        except (TypeError, ValueError):
            continue
        if minute_int <= elapsed:
            continue
        if minute_int > 130:
            continue
        team = _normalize_team(item.get("team") or item.get("side"), raw)
        try:
            p = float(item.get("p", item.get("probability", item.get("prob", 0.0))))
        except (TypeError, ValueError):
            p = 0.0
        entry: dict[str, Any] = {
            "player": player,
            "minute": minute_int,
            "p": round(max(0.0, min(1.0, p)), 3),
        }
        if team:
            entry["team"] = team
        normalized.append(entry)

    normalized.sort(key=lambda item: (-(item.get("p") or 0), item.get("minute") or 999))
    return normalized[:8]


def _normalize_reasoning(reasoning: Any) -> dict[str, str]:
    if isinstance(reasoning, str):
        return {"overall": reasoning.strip()}
    if isinstance(reasoning, dict):
        overall = reasoning.get("overall") or reasoning.get("summary") or reasoning.get("analysis") or ""
        return {"overall": str(overall).strip()}
    return {"overall": ""}


def _normalize_prediction(pred: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    win_probs = normalize_win_probs(pred.get("win_probs"))
    if not win_probs:
        raise ValueError("live prediction missing valid win_probs")
    score = _consistent_score(pred.get("most_likely_score") or pred.get("final_score"), win_probs, _current_score(raw))
    return {
        "win_probs": win_probs,
        "most_likely_score": score,
        "scorers": _normalize_scorers(pred, raw, score),
        "reasoning": _normalize_reasoning(pred.get("reasoning")),
    }


def fetch_live_fixture(fixture_id: str, wca_id: str, provider: str | None = None) -> dict[str, Any]:
    client = get_football_client(provider)
    raw = client.fixture(int(fixture_id))
    raw["fixture_id"] = wca_id
    raw["lock_at_utc"] = ""
    raw.setdefault("context_pack", {})
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / f"{wca_id}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    return raw


def run_live_prediction(
    *,
    raw: dict[str, Any],
    fixture_id: str,
    wca_id: str,
    model_cfg: dict[str, Any],
) -> dict[str, Any]:
    system_prompt, user_prompt = _build_live_prompt(raw, wca_id)
    model_id = model_cfg["id"]
    started = time.time()
    record: dict[str, Any] = {
        "fixture_id": wca_id,
        "provider_fixture_id": str(fixture_id),
        "model_id": model_id,
        "display_name": model_cfg.get("display_name"),
        "setting": "LIVE",
        "submitted_at": _now_iso(),
        "live": _live_summary(raw),
        "prediction": {},
        "sources": [],
        "tokens": {"input": 0, "output": 0},
        "tool_calls": 0,
        "cost_usd": 0.0,
        "wall_seconds": 0.0,
        "error": None,
        "raw_text": "",
        "thinking_text": None,
    }

    try:
        runner = build_runner(model_cfg)
        out = runner.generate(system_prompt, [{"role": "user", "content": user_prompt}])
        raw_text = out.get("text", "")
        parsed = runner.parse_json(raw_text)
        prediction = _normalize_prediction(parsed, raw)
        model_sources = parsed.get("sources") if isinstance(parsed, dict) else []
        sources = out.get("sources") or []
        if isinstance(model_sources, list):
            sources = sources + [s for s in model_sources if s not in sources]

        input_tokens = int(out.get("input_tokens") or 0)
        output_tokens = int(out.get("output_tokens") or 0)
        record.update({
            "prediction": prediction,
            "sources": sources,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "tool_calls": int(out.get("tool_calls") or 0),
            "cost_usd": float(out.get("cost_usd", runner.price_tokens(input_tokens, output_tokens)) or 0.0),
            "raw_text": raw_text,
            "thinking_text": out.get("thinking"),
        })
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["wall_seconds"] = round(time.time() - started, 3)

    return record


def _live_history_entry(record: dict[str, Any]) -> dict[str, Any]:
    pred = record.get("prediction") or {}
    return {
        "submitted_at": record.get("submitted_at"),
        "live": record.get("live") or {},
        "status": "failed" if record.get("error") else "ok",
        "error": record.get("error"),
        "win_probs": pred.get("win_probs") or {},
        "most_likely_score": pred.get("most_likely_score"),
        "scorers": pred.get("scorers") or [],
        "reasoning": pred.get("reasoning") or {},
        "sources": record.get("sources") or [],
        "cost_usd": record.get("cost_usd"),
        "tokens": record.get("tokens") or {},
        "tool_calls": record.get("tool_calls"),
        "wall_seconds": record.get("wall_seconds"),
    }


def _history_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        entry.get("submitted_at"),
        entry.get("status"),
        entry.get("most_likely_score"),
        json.dumps(entry.get("win_probs") or {}, sort_keys=True),
    )


def write_live_prediction(record: dict[str, Any]) -> Path:
    wca_id = record["fixture_id"]
    model_id = record["model_id"]
    out_dir = LIVE_PREDICTIONS_DIR / wca_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{model_id}__LIVE.json"

    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            previous = json.loads(path.read_text())
            history = list(previous.get("history") or [])
            if not history and previous.get("submitted_at"):
                history.append(_live_history_entry(previous))
        except Exception:
            history = []

    history.append(_live_history_entry(record))
    deduped: list[dict[str, Any]] = []
    seen = set()
    for entry in history:
        key = _history_key(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    record["history"] = deduped[-LIVE_HISTORY_LIMIT:]

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return path


def build_site() -> None:
    from ..leaderboard import build_site as site_builder

    site_builder.main()


def _normalized_status(value: Any) -> str:
    return str(value or "").strip().casefold()


def _is_halftime_status(value: Any) -> bool:
    status = _normalized_status(value)
    return status in HALFTIME_STATUSES or status.replace(" ", "") == "halftime"


def _is_live_for_prediction(summary: dict[str, Any]) -> bool:
    status = summary.get("status")
    return status not in NON_LIVE_STATUSES and not _is_halftime_status(status)


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    models = _load_models()
    selected = args.models or DEFAULT_LIVE_MODELS
    unknown = [model_id for model_id in selected if model_id not in models]
    if unknown:
        raise SystemExit(f"Unknown model id(s): {', '.join(unknown)}")

    provider = _provider_for_fixture(args.wca_id, args.provider)
    raw = fetch_live_fixture(args.fixture_id, args.wca_id, provider=provider)
    summary = _live_summary(raw)
    print(
        f"[live_predict] {args.wca_id}: "
        f"{summary.get('home')} {summary.get('score', {}).get('home')} - "
        f"{summary.get('score', {}).get('away')} {summary.get('away')} "
        f"provider={provider} status={summary.get('status')!r} elapsed={summary.get('elapsed')!r}"
    )

    if _is_halftime_status(summary.get("status")):
        print(f"  [live_predict] skip model calls because status={summary.get('status')!r} is halftime")
        return {
            "status": summary.get("status"),
            "predicted": False,
            "finished": summary.get("status") in FINISHED_STATUSES,
        }

    if getattr(args, "only_live", False) and not getattr(args, "predict_every_cycle", False) and not _is_live_for_prediction(summary):
        print(f"  [live_predict] skip model calls because status={summary.get('status')!r} and --only-live is set")
        return {
            "status": summary.get("status"),
            "predicted": False,
            "finished": summary.get("status") in FINISHED_STATUSES,
        }

    for model_id in selected:
        record = run_live_prediction(
            raw=raw,
            fixture_id=args.fixture_id,
            wca_id=args.wca_id,
            model_cfg=models[model_id],
        )
        path = write_live_prediction(record)
        status = "failed" if record.get("error") else "ok"
        tokens = record.get("tokens") or {}
        print(
            f"  [live_predict] {model_id}: {status} -> {path} "
            f"tokens={tokens.get('input', 0)}/{tokens.get('output', 0)} "
            f"cost=${float(record.get('cost_usd') or 0.0):.4f}"
        )
        if record.get("error"):
            print(f"    error: {record['error']}")

    if not args.no_build_site:
        build_site()

    return {
        "status": summary.get("status"),
        "predicted": True,
        "finished": summary.get("status") in FINISHED_STATUSES,
    }


def run_daemon(args: argparse.Namespace) -> None:
    interval = max(30, int(args.interval_seconds))
    print(f"[live_predict] daemon interval={interval}s models={','.join(args.models or DEFAULT_LIVE_MODELS)}")
    while True:
        try:
            result = run_once(args)
            if getattr(args, "stop_after_finished", False) and result.get("finished"):
                print("[live_predict] stop-after-finished reached; daemon exiting")
                return
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[live_predict] cycle failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local in-play model predictions.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--fixture-id", required=True, help="football provider numeric fixture id")
        p.add_argument("--wca-id", required=True, help="WorldCupArena fixture id")
        p.add_argument("--provider", default=None, help="football API provider; defaults to configs/fixtures.yaml")
        p.add_argument("--models", nargs="*", default=None, help="model ids from configs/models.yaml")
        p.add_argument("--only-live", action="store_true", help="skip model calls until the fixture is in play")
        p.add_argument("--predict-every-cycle", action="store_true", help="always create a fresh live prediction on each cycle, even before kickoff")
        p.add_argument("--no-build-site", action="store_true", help="write JSON but skip docs/site data rebuild")

    p_once = sub.add_parser("once", help="run one live prediction cycle")
    add_common(p_once)
    p_once.set_defaults(func=run_once)

    p_daemon = sub.add_parser("daemon", help="run live predictions repeatedly")
    add_common(p_daemon)
    p_daemon.add_argument("--interval-seconds", type=int, default=300)
    p_daemon.add_argument("--stop-after-finished", action="store_true", help="exit the daemon once the fixture is finished")
    p_daemon.set_defaults(func=run_daemon)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
