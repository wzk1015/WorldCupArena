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
from .prompt_build import build_prompt
from .validate import validate_or_repair

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
PREDICTIONS_DIR = DATA / "predictions"
RESULTS_DIR = DATA / "results"


def _load_yaml(p: Path) -> Any:
    return yaml.safe_load(p.read_text())


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
    fixture = json.loads(fixture_path.read_text())
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
    fixture = json.loads((fixture_dir / "fixture.json").read_text())
    truth = json.loads((fixture_dir / "truth.json").read_text())
    fid = fixture["fixture_id"]
    pred_dir = PREDICTIONS_DIR / fid
    out_dir = RESULTS_DIR / fid
    out_dir.mkdir(parents=True, exist_ok=True)

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
    p = sub.add_parser("lock");    p.add_argument("--fixture", type=Path, required=True)

    args = ap.parse_args()
    if args.cmd == "predict":
        cmd_predict(args.fixture, args.parallel)
    elif args.cmd == "grade":
        cmd_grade(args.fixture_dir)
    elif args.cmd == "leaderboard":
        cmd_leaderboard()
    elif args.cmd == "lock":
        lock_fixture(args.fixture)


if __name__ == "__main__":
    main()
