"""Cron-friendly fixture scheduler.

Reads configs/fixtures.yaml and fires the appropriate pipeline phase for any
fixture whose kickoff time crosses a phase boundary. Intended to be driven by
a single GitHub Actions cron that runs every hour — each invocation is
idempotent, so missed ticks just catch up on the next run.

Phase boundaries (relative to kickoff):
    ingest_populate : T-48h → T-1h    (snapshot + context_pack if missing)
    lock_predict    : T-1h  → T+0h    (lock + predict if unlocked)
    truth_grade     : T+3h  → T+48h   (truth ingest + grade + leaderboard)

Usage:
    python -m src.pipeline.scheduler tick            # run all due phases
    python -m src.pipeline.scheduler tick --phase predict
    python -m src.pipeline.scheduler show            # dry-run status table
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "data" / "snapshots"
FIXTURES_YAML = ROOT / "configs" / "fixtures.yaml"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load_fixtures() -> list[dict]:
    cfg = yaml.safe_load(FIXTURES_YAML.read_text())
    return [f for f in (cfg.get("fixtures") or []) if f.get("enabled", True)]


def _phase_for(kickoff: datetime, now: datetime) -> str | None:
    """Which phase should run for a fixture with this kickoff time, at `now`?"""
    if kickoff - timedelta(hours=48) <= now < kickoff - timedelta(hours=1):
        return "ingest_populate"
    if kickoff - timedelta(hours=1) <= now < kickoff:
        return "lock_predict"
    if kickoff + timedelta(hours=3) <= now < kickoff + timedelta(hours=48):
        return "truth_grade"
    return None


def _run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _ingest_populate(fx: dict, fx_dir: Path) -> None:
    fixture_path = fx_dir / "fixture.json"
    lock_at = (_parse_iso(fx["kickoff_utc"]) - timedelta(hours=1)).isoformat()
    if not fixture_path.exists():
        fx_dir.mkdir(parents=True, exist_ok=True)
        _run([sys.executable, "-m", "src.ingest.api_football",
              "--fixture-id", str(fx["provider_id"]),
              "--wca-id", fx["wca_id"],
              "--lock-at", lock_at,
              "--out", str(fixture_path)])
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "populate",
          "--fixture", str(fixture_path)])


def _lock_predict(fx: dict, fx_dir: Path) -> None:
    fixture_path = fx_dir / "fixture.json"
    if not fixture_path.exists():
        print(f"  [skip] no fixture.json at {fixture_path}")
        return
    raw = json.loads(fixture_path.read_text())
    if not raw.get("snapshot_hash"):
        _run([sys.executable, "-m", "src.pipeline.orchestrator", "lock",
              "--fixture", str(fixture_path)])
    pred_dir = ROOT / "data" / "predictions" / fx["wca_id"]
    if pred_dir.exists() and any(pred_dir.glob("*.json")):
        print(f"  [skip] predictions already exist at {pred_dir}")
        return
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "predict",
          "--fixture", str(fixture_path), "--parallel", "8"])


def _truth_grade(fx: dict, fx_dir: Path) -> None:
    truth_path = fx_dir / "truth.json"
    if not truth_path.exists():
        _run([sys.executable, "-m", "src.ingest.api_football",
              "--fixture-id", str(fx["provider_id"]),
              "--wca-id", fx["wca_id"],
              "--lock-at", "",
              "--out", str(truth_path)])
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "grade",
          "--fixture-dir", str(fx_dir)])
    _run([sys.executable, "-m", "src.leaderboard.build"])


_DISPATCH = {
    "ingest_populate": _ingest_populate,
    "lock_predict":    _lock_predict,
    "truth_grade":     _truth_grade,
}


def cmd_tick(phase_filter: str | None) -> None:
    now = _now()
    for fx in _load_fixtures():
        kickoff = _parse_iso(fx["kickoff_utc"])
        phase = _phase_for(kickoff, now)
        if phase is None:
            continue
        if phase_filter and phase != phase_filter:
            continue
        fx_dir = SNAPSHOTS / fx["wca_id"]
        print(f"[{fx['wca_id']}] phase={phase} kickoff={kickoff.isoformat()}")
        try:
            _DISPATCH[phase](fx, fx_dir)
        except subprocess.CalledProcessError as e:
            print(f"  [error] {phase} failed: {e}")


def cmd_show() -> None:
    now = _now()
    print(f"{'wca_id':<30} {'kickoff_utc':<28} {'phase':<18} {'delta':<10}")
    for fx in _load_fixtures():
        kickoff = _parse_iso(fx["kickoff_utc"])
        phase = _phase_for(kickoff, now) or "-"
        delta = kickoff - now
        kstr = kickoff.isoformat()
        print(f"{fx['wca_id']:<30} {kstr:<28} {phase:<18} {delta}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tick")
    p.add_argument("--phase", choices=list(_DISPATCH.keys()), default=None)
    sub.add_parser("show")
    args = ap.parse_args()
    if args.cmd == "tick":
        cmd_tick(args.phase)
    elif args.cmd == "show":
        cmd_show()


if __name__ == "__main__":
    main()
