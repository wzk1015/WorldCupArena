"""Top-level orchestrator for a single fixture prediction round.

Usage:
    python -m src.pipeline.orchestrator predict     --fixture data/snapshots/ucl_sf1_l1/fixture.json
    python -m src.pipeline.orchestrator grade       --fixture-dir data/snapshots/ucl_sf1_l1
    python -m src.pipeline.orchestrator live_update --fixture-id 12345 --wca-id ucl_sf1_l1

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
import time

import yaml

from ..runners import build_runner_chain
from ..graders import grade_match
from ..graders.grade_match import SCORING_VERSION
from ..ingest.api_football import normalize_fixture, normalize_to_truth, populate_context_pack, get_football_client, football_api_provider
from ..ingest.news import populate_news
from .prompt_build import build_prompt
from .prediction_derivatives import strip_generated_score_fields
from .reasoning_localization import localize_prediction_reasoning
from .score_calibration import SCORE_CALIBRATION_METHOD, calibrate_score_prediction, diversify_prediction_records
from .validate import validate, validate_or_repair

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
PREDICTIONS_DIR = DATA / "predictions"
RESULTS_DIR = DATA / "results"
SEARCH_LOGS_DIR = DATA / "search_logs"
LIVE_DIR = DATA / "live"


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
            model_cfg = {**m, "model_category": category}
            for s_id in m.get("settings_supported", []):
                yield model_cfg, settings_by_id[s_id]


def _leak_audit(sources: list[dict[str, Any]], lock_at: str) -> dict[str, Any]:
    leaks: list[dict[str, Any]] = []
    for s in sources or []:
        pub = s.get("published_at")
        if pub and pub > lock_at:
            leaks.append({"url": s.get("url"), "published_at": pub})
    return {"leaked": bool(leaks), "leaked_sources": leaks}


def cmd_predict(
    fixture_path: Path,
    parallel: int = 8,
    model_ids: set[str] | None = None,
    force: bool = False,
) -> None:
    fixture = _load_fixture(fixture_path)
    models_cfg = _load_yaml(CONFIGS / "models.yaml")
    settings_cfg = _load_yaml(CONFIGS / "settings.yaml")

    fid = fixture["fixture_id"]
    out_dir = PREDICTIONS_DIR / fid
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = list(_iter_model_setting_pairs(models_cfg, settings_cfg))
    if model_ids:
        jobs = [job for job in jobs if job[0].get("id") in model_ids]
    print(f"[predict] {fid}: {len(jobs)} model×setting runs")

    policy = settings_cfg.get("policy", {})
    tol = float(policy.get("probability_sum_tolerance", 0.01))
    max_retries = int(policy.get("max_format_retries", 2))
    scoreline_policy = policy.get("scoreline_calibration") or {}
    calibrate_scorelines = bool(scoreline_policy.get("enabled", False))
    calibration_max_goals = int(scoreline_policy.get("max_goals", 7))
    calibration_max_scorelines = int(scoreline_policy.get("max_scorelines", 20))
    calibration_model_weight = float(scoreline_policy.get("model_weight", 0.62))
    calibration_favorite_margin = float(scoreline_policy.get("favorite_margin", 0.15))
    diversification_policy = policy.get("fixture_diversification") or {}
    diversify_fixture = bool(diversification_policy.get("enabled", True))

    MAX_RUN_RETRIES = 3

    def _maybe_calibrate_record(record: dict[str, Any], setting_id: str) -> tuple[dict[str, Any], bool]:
        if not calibrate_scorelines or record.get("error") or not record.get("prediction"):
            return record, False
        before_localization = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if (record.get("score_calibration") or {}).get("method") == SCORE_CALIBRATION_METHOD:
            localize_prediction_reasoning(record["prediction"], fixture=fixture)
            if record.get("raw_prediction"):
                localize_prediction_reasoning(record["raw_prediction"], fixture=fixture)
            report = validate(
                record["prediction"],
                fixture_id=fid,
                setting_id=setting_id,
                tol=tol,
            )
            record["validation_errors"] = report.errors
            return record, json.dumps(record, ensure_ascii=False, sort_keys=True) != before_localization

        calibration_source = record.get("raw_prediction") or record["prediction"]
        localize_prediction_reasoning(calibration_source, fixture=fixture)

        prediction, score_calibration = calibrate_score_prediction(
            calibration_source,
            max_goals=calibration_max_goals,
            max_scorelines=calibration_max_scorelines,
            model_weight=calibration_model_weight,
            favorite_margin=calibration_favorite_margin,
        )
        calibration_report = validate(
            prediction,
            fixture_id=fid,
            setting_id=setting_id,
            tol=tol,
        )
        out = dict(record)
        out["prediction"] = prediction
        out["validation_errors"] = calibration_report.errors
        out["score_calibration"] = score_calibration
        out.pop("fixture_diversification", None)
        out.pop("pre_diversity_prediction", None)
        return out, True

    def _one(job):
        model_cfg, setting = job
        path = out_dir / f"{model_cfg['id']}__{setting['id']}.json"
        if path.exists() and not force:
            with open(path) as f:
                prev_ret = json.load(f)
                prev_ret, calibrated_existing = _maybe_calibrate_record(prev_ret, setting["id"])
                if calibrated_existing:
                    path.write_text(json.dumps(prev_ret, ensure_ascii=False, indent=2))
                    if prev_ret.get("validation_errors"):
                        print(f"[predict] {fid}: calibrated existing result but validation failed, rerunning: {path}")
                    else:
                        return {"model": model_cfg["id"], "setting": setting["id"], "skipped": "Calibrated"}
                if prev_ret["error"] or prev_ret["validation_errors"] or (not prev_ret["prediction"]):
                    print(f"[predict] {fid}: result exists but has errors, rerunning: {path}")
                else:
                    return {"model": model_cfg["id"], "setting": setting["id"], "skipped": "Done"}

        sys_p, usr_p = build_prompt(fixture, setting)
        try:
            runner_chain = build_runner_chain(model_cfg)
        except NotImplementedError as e:
            return {"model": model_cfg["id"], "setting": setting["id"], "skipped": str(e)}

        def _validate(pred, retry_fn):
            model_max_retries = int(model_cfg.get("max_format_retries", max_retries))
            return validate_or_repair(
                pred,
                fixture_id=fid,
                setting_id=setting["id"],
                retry_fn=retry_fn,
                max_retries=model_max_retries,
                tol=tol,
            )

        record = None
        total_cost = 0.0
        max_run_retries = int(model_cfg.get("max_run_retries", MAX_RUN_RETRIES))
        # Ordered attempt plan: each source (primary + configured fallbacks) gets its
        # retry budget, tried in order. The first source to yield a usable prediction
        # wins; switching to the next source happens immediately (no inter-source sleep).
        n_sources = len(runner_chain)
        attempt_plan = [(lbl, rn, n)
                        for (lbl, rn) in runner_chain
                        for n in range(1, max_run_retries + 1)]
        res = None
        for (src_label, runner, attempt) in attempt_plan:
            tail = "" if n_sources == 1 else f" via {src_label}"
            if attempt == 1:
                print(f"[predict] {fid}: running {model_cfg['id']} on setting {setting['id']}{tail}")
            else:
                print(f"[predict] {fid}: retry {attempt}/{max_run_retries} for {model_cfg['id']} ({setting['id']}){tail}")
            res = runner.run(fixture, setting, sys_p, usr_p, validate_fn=_validate)
            total_cost += res.cost_usd
            audit = _leak_audit(res.sources, fixture["lock_at_utc"])
            prediction = localize_prediction_reasoning(res.prediction, fixture=fixture) if res.prediction else {}
            raw_prediction = strip_generated_score_fields(prediction) if prediction else {}
            validation_errors = res.validation_errors
            score_calibration = None
            if calibrate_scorelines and not res.error and prediction:
                prediction, score_calibration = calibrate_score_prediction(
                    prediction,
                    max_goals=calibration_max_goals,
                    max_scorelines=calibration_max_scorelines,
                    model_weight=calibration_model_weight,
                    favorite_margin=calibration_favorite_margin,
                )
                calibration_report = validate(
                    prediction,
                    fixture_id=fid,
                    setting_id=setting["id"],
                    tol=tol,
                )
                validation_errors = calibration_report.errors
            elif not res.error and prediction:
                post_localization_report = validate(
                    prediction,
                    fixture_id=fid,
                    setting_id=setting["id"],
                    tol=tol,
                )
                validation_errors = post_localization_report.errors
            record = {
                "fixture_id": fid,
                "model_id": res.model_id,
                "setting": res.setting,
                "source": src_label,
                "submitted_at": res.submitted_at,
                "prediction": prediction,
                "raw_prediction": raw_prediction,
                "sources": res.sources,
                "leakage_audit": audit,
                "cost_usd": total_cost,
                "tokens": {"input": res.input_tokens, "output": res.output_tokens},
                "tool_calls": res.tool_calls,
                "wall_seconds": res.wall_seconds,
                "repair_retries": res.repair_retries,
                "validation_errors": validation_errors,
                "error": res.error,
                "raw_text": res.raw_text,
                "thinking_text": res.thinking_text,
            }
            if score_calibration:
                record["score_calibration"] = score_calibration
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2))

            if not res.error and not validation_errors and prediction:
                break  # success
            
            if attempt < max_run_retries:
                print(f"  [predict] attempt {attempt} failed (err={res.error!r}, "
                      f"validation_errors={validation_errors}), retrying after sleeping 60s…")
                time.sleep(60)

        # Persist search sources for S2 runs so they can be reviewed later
        if res.sources and setting.get("id", "").startswith("S2"):
            log_dir = SEARCH_LOGS_DIR / fid
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"{model_cfg['id']}__{setting['id']}.json"
            log_path.write_text(json.dumps({
                "fixture_id": fid,
                "model_id": res.model_id,
                "setting": res.setting,
                "submitted_at": res.submitted_at,
                "sources": res.sources,
            }, ensure_ascii=False, indent=2))

        still_failed = res.error or validation_errors or not prediction
        if still_failed:
            print(f"\n{'='*60}")
            print(f"  *** WARNING: {model_cfg['id']} ({setting['id']}) FAILED after {max_run_retries} attempts ***")
            print(f"  error            : {res.error}")
            print(f"  validation_errors: {validation_errors}")
            print(f"  prediction empty : {not prediction}")
            print(f"{'='*60}\n")

        return {
            "model": res.model_id, "setting": res.setting,
            "cost": total_cost, "retries": res.repair_retries,
            "err": res.error,
        }

    with cf.ThreadPoolExecutor(max_workers=parallel) as ex:
        for r in ex.map(_one, jobs):
            print(" ", r)

    if calibrate_scorelines and diversify_fixture:
        _diversify_fixture_prediction_files(out_dir, fid, tol, fixture)


def _diversify_fixture_prediction_files(out_dir: Path, fixture_id: str, tol: float, fixture: dict[str, Any]) -> None:
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(out_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if record.get("error") or record.get("validation_errors") or not record.get("prediction"):
            continue
        records.append((path, record))
    if len(records) < 2:
        return

    diversified = diversify_prediction_records([record for _, record in records])
    changed = 0
    for (path, old_record), new_record in zip(records, diversified):
        if new_record.get("prediction"):
            localize_prediction_reasoning(new_record["prediction"], fixture=fixture)
        if new_record.get("raw_prediction"):
            localize_prediction_reasoning(new_record["raw_prediction"], fixture=fixture)
        report = validate(
            new_record.get("prediction") or {},
            fixture_id=fixture_id,
            setting_id=new_record["setting"],
            tol=tol,
        )
        new_record["validation_errors"] = report.errors
        if new_record != old_record:
            path.write_text(json.dumps(new_record, ensure_ascii=False, indent=2))
            changed += 1
    if changed:
        print(f"[predict] {fixture_id}: diversified {changed} prediction files")


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
        result_path = out_dir / pred_file.name
        if result_path.exists():
            try:
                existing = json.loads(result_path.read_text())
            except Exception:  # noqa: BLE001
                existing = {}
            if existing.get("scoring_version") == SCORING_VERSION:
                print(f"[grade] skip current result {result_path}")
                continue
            print(f"[grade] refresh scoring version for {result_path}")
        record = json.loads(pred_file.read_text())
        if record.get("error"):
            continue
        scored = grade_match(record.get("prediction", {}), truth)
        scored["model_id"] = record["model_id"]
        scored["setting"] = record["setting"]
        scored["leakage_audit"] = record.get("leakage_audit", {})
        result_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2))
    print(f"[grade] {fid}: done")


# def cmd_leaderboard() -> None:
#     # Aggregate all results/*/ files into a single table.
#     rows: list[dict[str, Any]] = []
#     for fid_dir in RESULTS_DIR.glob("*"):
#         for f in fid_dir.glob("*.json"):
#             r = json.loads(f.read_text())
#             rows.append({
#                 "fixture_id": fid_dir.name,
#                 "model_id": r["model_id"],
#                 "setting": r["setting"],
#                 "composite": r.get("composite", 0.0),
#                 **{f"layer_{k}": v for k, v in r.get("layers", {}).items()},
#             })
#     out = ROOT / "docs" / "leaderboard" / "raw.json"
#     out.parent.mkdir(parents=True, exist_ok=True)
#     out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
#     print(f"[leaderboard] wrote {len(rows)} rows -> {out}")


def cmd_live_update(fixture_id: str, wca_id: str, provider: str | None = None) -> None:
    """Fetch the current live score from the configured football API.

    If the match status is "Match Finished", also writes truth.json and grades
    all predictions (same as truth_grade phase), so results appear immediately
    without waiting for the T+3h window.
    """
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    live_path = LIVE_DIR / f"{wca_id}.json"

    selected_provider = football_api_provider(provider)
    client = get_football_client(selected_provider)
    raw = client.fixture(int(fixture_id))
    raw["fixture_id"] = wca_id
    raw["lock_at_utc"] = ""
    raw.setdefault("context_pack", {})
    live_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))

    try:
        status = raw["response"][0]["fixture"]["status"].get("long")
    except (KeyError, IndexError):
        status = None

    print(f"[live_update] {wca_id}: provider={selected_provider} status={status!r} -> {live_path}")

    if status == "Match Finished":
        print(f"[live_update] match finished — running truth_grade")
        fx_dir = DATA / "snapshots" / wca_id
        truth_path = fx_dir / "truth.json"
        if not truth_path.exists():
            truth_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
            print(f"[live_update] wrote truth.json from live response")
        cmd_grade(fx_dir)


def cmd_populate(
    fixture_path: Path,
    recent_n: int = 10,
    with_news: bool = True,
    news_cap: int = 20,
    news_window_days: int = 7,
    provider: str | None = None,
) -> None:
    """Fetch squads + recent form + stats and write them into fixture.json.

    The provider defaults to FOOTBALL_API_PROVIDER / WCA_FOOTBALL_API_PROVIDER,
    with API-Football as the backward-compatible default.
    """
    selected_provider = football_api_provider(provider)
    client = get_football_client(selected_provider)
    populate_context_pack(fixture_path, client, recent_n=recent_n)
    if with_news:
        populate_news(fixture_path, cap=news_cap, window_days=news_window_days)
    print(
        f"[populate] {fixture_path}: context_pack updated "
        f"(provider={selected_provider}, recent_n={recent_n}, news={with_news})"
    )


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

    p = sub.add_parser("predict")
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--parallel", type=int, default=8)
    p.add_argument("--models", nargs="*", help="optional model ids to run")
    p.add_argument("--force", action="store_true", help="rerun even if a prediction file already exists")
    p = sub.add_parser("grade");   p.add_argument("--fixture-dir", type=Path, required=True)
    p = sub.add_parser("lock");    p.add_argument("--fixture", type=Path, required=True)
    p = sub.add_parser("populate")
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--recent-n", type=int, default=10)
    p.add_argument("--no-news", action="store_true", help="skip news_headlines ingest")
    p.add_argument("--news-cap", type=int, default=20)
    p.add_argument("--news-window-days", type=int, default=7)
    p.add_argument("--provider", default=None, help="football API provider: api_football or sportmonks")
    p = sub.add_parser("live_update", help="fetch live score; grade immediately if finished")
    p.add_argument("--fixture-id", required=True, help="provider fixture id")
    p.add_argument("--wca-id", required=True, help="internal wca_id (snapshot dir name)")
    p.add_argument("--provider", default=None, help="football API provider: api_football or sportmonks")

    args = ap.parse_args()
    if args.cmd == "predict":
        cmd_predict(args.fixture, args.parallel, set(args.models or []) or None, args.force)
    elif args.cmd == "grade":
        cmd_grade(args.fixture_dir)
    elif args.cmd == "lock":
        lock_fixture(args.fixture)
    elif args.cmd == "populate":
        cmd_populate(
            args.fixture,
            args.recent_n,
            with_news=not args.no_news,
            news_cap=args.news_cap,
            news_window_days=args.news_window_days,
            provider=args.provider,
        )
    elif args.cmd == "live_update":
        cmd_live_update(args.fixture_id, args.wca_id, provider=args.provider)


if __name__ == "__main__":
    main()
