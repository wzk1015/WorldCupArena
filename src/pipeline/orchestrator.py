"""Top-level orchestrator for a single fixture prediction round.

Usage:
    python -m src.pipeline.orchestrator predict  --fixture data/snapshots/ucl_sf1_l1/fixture.json
    python -m src.pipeline.orchestrator grade    --fixture-dir data/snapshots/ucl_sf1_l1
    python -m src.pipeline.orchestrator leaderboard

Design:
    1. Load fixture snapshot (must already be locked; snapshot_hash required).
    2. For each (model, setting) pair supported by the model, build prompt, run.
    3. Persist raw response + parsed prediction to data/predictions/.
    4. Audit sources[].accessed_at <= lock_at_utc, otherwise mark task-level leakage.
    5. Grading step (separate) reads predictions + ground truth and writes results.duckdb.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import hashlib
from pathlib import Path
from typing import Any

import yaml

from ..runners import build_runner
from ..graders import grade_match
from ..ingest.api_football import normalize_fixture, normalize_to_truth, populate_context_pack, APIFootballClient
from ..ingest.news import populate_news
from .prompt_build import build_prompt
from .validate import validate_or_repair

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
PREDICTIONS_DIR = DATA / "predictions"
RESULTS_DIR = DATA / "results"


def _load_yaml(p: Path) -> Any:
    return yaml.safe_load(p.read_text())


def _load_fixture(path: Path) -> dict:
    """Load a fixture snapshot and normalise it to the internal WCA format.

    On-disk files are raw API-Football responses with WCA extras at the root
    (fixture_id, lock_at_utc, context_pack). If the file already looks like
    the internal flat format (has 'home' as a dict with an 'id' string field
    rather than an integer inside 'response'), use it as-is for backwards
    compatibility with hand-crafted fixtures.
    """
    raw = json.loads(path.read_text())
    if "response" in raw:
        return normalize_fixture(raw)
    return raw  # already in flat internal format


def _load_truth(path: Path) -> dict:
    """Load a truth snapshot and normalise it to the WCA grader format.

    Same raw-vs-internal detection: if 'response' key is present it's the
    raw API-Football format; otherwise it's already normalised.
    """
    raw = json.loads(path.read_text())
    if "response" in raw:
        return normalize_to_truth(raw)
    return raw


def _iter_model_setting_pairs(models_cfg: dict, settings_cfg: dict):
    settings_by_id = {s_id: {"id": s_id, **body} for s_id, body in settings_cfg["settings"].items()}
    for category, entries in models_cfg.items():
        if category == "baselines":
            continue
        for m in entries or []:
            for s_id in m.get("settings_supported", []):
                yield m, settings_by_id[s_id]


def _leak_audit(sources: list[dict[str, Any]], lock_at: str) -> dict[str, Any]:
    leaks: list[dict[str, Any]] = []
    for s in sources or []:
        pub = s.get("published_at")
        if pub and pub > lock_at:
            leaks.append({"url": s.get("url"), "published_at": pub})
    return {"leaked": bool(leaks), "leaked_sources": leaks}


def cmd_predict(fixture_path: Path, parallel: int = 8) -> None:
    fixture = _load_fixture(fixture_path)
    models_cfg = _load_yaml(CONFIGS / "models.yaml")
    settings_cfg = _load_yaml(CONFIGS / "settings.yaml")

    fid = fixture["fixture_id"]
    out_dir = PREDICTIONS_DIR / fid
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = list(_iter_model_setting_pairs(models_cfg, settings_cfg))
    print(f"[predict] {fid}: {len(jobs)} model×setting runs")

    policy = settings_cfg.get("policy", {})
    tol = float(policy.get("probability_sum_tolerance", 0.01))
    max_retries = int(policy.get("max_format_retries", 2))

    def _one(job):
        model_cfg, setting = job
        sys_p, usr_p = build_prompt(fixture, setting)
        try:
            runner = build_runner(model_cfg)
        except NotImplementedError as e:
            return {"model": model_cfg["id"], "setting": setting["id"], "skipped": str(e)}

        def _validate(pred, retry_fn):
            return validate_or_repair(
                pred,
                fixture_id=fid,
                setting_id=setting["id"],
                retry_fn=retry_fn,
                max_retries=max_retries,
                tol=tol,
            )

        res = runner.run(fixture, setting, sys_p, usr_p, validate_fn=_validate)
        audit = _leak_audit(res.sources, fixture["lock_at_utc"])
        record = {
            "fixture_id": fid,
            "model_id": res.model_id,
            "setting": res.setting,
            "submitted_at": res.submitted_at,
            "prediction": res.prediction,
            "sources": res.sources,
            "leakage_audit": audit,
            "cost_usd": res.cost_usd,
            "tokens": {"input": res.input_tokens, "output": res.output_tokens},
            "tool_calls": res.tool_calls,
            "wall_seconds": res.wall_seconds,
            "repair_retries": res.repair_retries,
            "validation_errors": res.validation_errors,
            "error": res.error,
        }
        path = out_dir / f"{res.model_id}__{res.setting}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        return {
            "model": res.model_id, "setting": res.setting,
            "cost": res.cost_usd, "retries": res.repair_retries,
            "err": res.error,
        }

    with cf.ThreadPoolExecutor(max_workers=parallel) as ex:
        for r in ex.map(_one, jobs):
            print(" ", r)


def cmd_grade(fixture_dir: Path) -> None:
    fixture = _load_fixture(fixture_dir / "fixture.json")
    truth = _load_truth(fixture_dir / "truth.json")
    fid = fixture["fixture_id"]
    pred_dir = PREDICTIONS_DIR / fid
    out_dir = RESULTS_DIR / fid
    out_dir.mkdir(parents=True, exist_ok=True)

    # print(list(pred_dir.glob("*.json")))
    # print(pred_dir)
    for pred_file in sorted(pred_dir.glob("*.json")):
        record = json.loads(pred_file.read_text())
        if record.get("error"):
            continue
        scored = grade_match(record.get("prediction", {}), truth)
        scored["model_id"] = record["model_id"]
        scored["setting"] = record["setting"]
        scored["leakage_audit"] = record.get("leakage_audit", {})
        (out_dir / pred_file.name).write_text(json.dumps(scored, ensure_ascii=False, indent=2))
    print(f"[grade] {fid}: done")


def cmd_leaderboard() -> None:
    # Aggregate all results/*/ files into a single table.
    rows: list[dict[str, Any]] = []
    for fid_dir in RESULTS_DIR.glob("*"):
        for f in fid_dir.glob("*.json"):
            r = json.loads(f.read_text())
            rows.append({
                "fixture_id": fid_dir.name,
                "model_id": r["model_id"],
                "setting": r["setting"],
                "composite": r.get("composite", 0.0),
                **{f"layer_{k}": v for k, v in r.get("layers", {}).items()},
            })
    out = ROOT / "docs" / "leaderboard" / "raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"[leaderboard] wrote {len(rows)} rows -> {out}")


def cmd_populate(
    fixture_path: Path,
    recent_n: int = 10,
    with_news: bool = True,
    news_cap: int = 20,
    news_window_days: int = 7,
) -> None:
    """Fetch squads + recent form + stats from API-Football and write into fixture.json.

    Reads APIFOOTBALL_API_KEY from the environment (same convention as other keys).
    Run this before `lock` so the snapshot hash covers the populated context_pack.

    When with_news is True, also populates context_pack.news_headlines via
    ingest.news (NewsAPI / GNews / Google News RSS fallback).
    """
    import os
    api_key = os.environ.get("APIFOOTBALL_API_KEY") or os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        raise RuntimeError("Set APIFOOTBALL_API_KEY (or API_FOOTBALL_KEY) in your .env")
    client = APIFootballClient(api_key)
    populate_context_pack(fixture_path, client, recent_n=recent_n)
    if with_news:
        populate_news(fixture_path, cap=news_cap, window_days=news_window_days)
    print(f"[populate] {fixture_path}: context_pack updated (recent_n={recent_n}, news={with_news})")


def canonicalize_fixture(fixture: dict[str, Any]) -> str:
    """Stable JSON for snapshot_hash."""
    return json.dumps(fixture, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def lock_fixture(fixture_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text())
    fixture.pop("snapshot_hash", None)
    canon = canonicalize_fixture(fixture)
    fixture["snapshot_hash"] = hashlib.sha256(canon.encode()).hexdigest()
    fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2))
    print(f"[lock] {fixture['fixture_id']} hash={fixture['snapshot_hash'][:12]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("predict"); p.add_argument("--fixture", type=Path, required=True); p.add_argument("--parallel", type=int, default=8)
    p = sub.add_parser("grade");   p.add_argument("--fixture-dir", type=Path, required=True)
    sub.add_parser("leaderboard")
    p = sub.add_parser("lock");     p.add_argument("--fixture", type=Path, required=True)
    p = sub.add_parser("populate")
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--recent-n", type=int, default=10)
    p.add_argument("--no-news", action="store_true", help="skip news_headlines ingest")
    p.add_argument("--news-cap", type=int, default=20)
    p.add_argument("--news-window-days", type=int, default=7)

    args = ap.parse_args()
    if args.cmd == "predict":
        cmd_predict(args.fixture, args.parallel)
    elif args.cmd == "grade":
        cmd_grade(args.fixture_dir)
    elif args.cmd == "leaderboard":
        cmd_leaderboard()
    elif args.cmd == "lock":
        lock_fixture(args.fixture)
    elif args.cmd == "populate":
        cmd_populate(
            args.fixture,
            args.recent_n,
            with_news=not args.no_news,
            news_cap=args.news_cap,
            news_window_days=args.news_window_days,
        )


if __name__ == "__main__":
    main()
