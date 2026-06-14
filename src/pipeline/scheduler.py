"""Cron-friendly fixture scheduler.

Reads configs/fixtures.yaml and fires every pipeline phase whose window is
open for each fixture. Intended to be driven by a short-interval GitHub
Actions cron (every 10 minutes) — each invocation is idempotent, so missed
ticks catch up on the next run and running two back-to-back is a no-op.

Phases (windows relative to kickoff):

    ingest       : T-7d  → T-24h   pull fixture.json from the configured football API
    populate     : T-48h → T-24h   fill context_pack (squads/form/news/stats)
    lock_predict : T-24h → T+0h    lock snapshot + run all model predictions
    repredict_24h: T-24h → T-1h    [opt-in] re-ingest fresh data + re-predict the models in
                                   WCA_REPREDICT_MODELS (e.g. frontier families) on a later snapshot
    repredict_1h : T-1h  → T+0h    [opt-in] once more right before kickoff (confirmed lineups)
    live_update  : T+0h  → T+3h    fetch live score every tick → data/live/<id>.json;
                                   immediately triggers truth_grade if "Match Finished"
    truth_grade  : T+3h  → T+48h   pull truth, grade, rebuild leaderboard

The two repredict_* phases exist only when WCA_REPREDICT_MODELS is set (else the
default benchmark — every model on ONE frozen T-LEAD snapshot — is unchanged).

At each tick, for each fixture, every phase whose window is open runs in
order. Every phase checks "is my work already done?" before acting:

    ingest       — skip if fixture.json exists
    populate     — skip if context_pack already has squads
    lock_predict — if fixture.json is missing (fixture added late, inside the
                   24h window), runs ingest + populate inline before locking;
                   skip lock if snapshot_hash is set;
                   skip predict if predictions/<wca_id>/ has any json
    repredict_*  — skip unless WCA_REPREDICT_MODELS set + lock_predict already ran;
                   fires once per window (marker .repredict_<tag>), --force overwrites
                   only that subset's files
    live_update  — always overwrites data/live/<id>.json with latest provider response;
                   if status == "Match Finished", calls _phase_truth_grade immediately
    truth_grade  — skip truth download if truth.json exists;
                   grade is always safe to rerun

Usage:
    python -m src.pipeline.scheduler tick                      # run every due phase
    python -m src.pipeline.scheduler tick --phase live_update  # only live score fetch
    python -m src.pipeline.scheduler show                      # dry-run status table
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
LIVE_DIR  = ROOT / "data" / "live"
FIXTURES_YAML = ROOT / "configs" / "fixtures.yaml"


# Prediction lead time (hours before kickoff): when the snapshot is locked and
# every model prediction runs. This is ALSO the anti-leakage information horizon
# (lock_at) — sources published after kickoff-LEAD are flagged as leaks, so all
# models predict on the same frozen pre-match info. Override per environment with
# WCA_PREDICT_LEAD_H (prod can bump it without a code change). Default 48h.
# Going earlier than ~48h risks missing predicted lineups / late team news, which
# weakens predictions; 24h was the historical value.
PREDICT_LEAD_H: int = int(os.environ.get("WCA_PREDICT_LEAD_H", "48"))
_POPULATE_LEAD_H = PREDICT_LEAD_H + 24  # populate fills context in the 24h before lock

# Optional near-kickoff re-prediction. Comma-separated model ids in WCA_REPREDICT_MODELS
# (e.g. the frontier families "gpt-5.4,gemini-3.1-pro-preview-thinking,claude-opus-4-7-thinking");
# empty/unset DISABLES the feature, leaving the default benchmark untouched (every model on one
# frozen T-LEAD snapshot). When set, those models re-ingest fresh data → re-lock → predict
# --force at T-24h and T-1h, so they predict on confirmed lineups / late news — i.e. a LATER
# information horizon than the rest of the field. Use it to measure how much a near-kickoff
# snapshot helps; those models' scores are then not directly comparable to the T-LEAD models.
REPREDICT_MODELS: list[str] = [m.strip() for m in os.environ.get("WCA_REPREDICT_MODELS", "").split(",") if m.strip()]
REPREDICT_OFFSETS_H = (24, 1)  # re-predict windows: [KO-24h, KO-1h) then [KO-1h, KO)

# (phase_name, start_offset_from_kickoff, end_offset_from_kickoff)
PHASES: list[tuple[str, timedelta, timedelta]] = [
    ("ingest",       timedelta(days=-7),                 timedelta(hours=-PREDICT_LEAD_H)),
    ("populate",     timedelta(hours=-_POPULATE_LEAD_H), timedelta(hours=-PREDICT_LEAD_H)),
    ("lock_predict", timedelta(hours=-PREDICT_LEAD_H),   timedelta(hours=0)),
    ("live_update",  timedelta(hours=0),                 timedelta(hours=3)),
    ("truth_grade",  timedelta(hours=3),                 timedelta(hours=48)),
]
# Opt-in near-kickoff re-prediction windows — appended only when WCA_REPREDICT_MODELS is set,
# so the default phase set (and benchmark behaviour) is unchanged when the feature is off.
if REPREDICT_MODELS:
    _r24, _r1 = REPREDICT_OFFSETS_H
    PHASES += [
        ("repredict_24h", timedelta(hours=-_r24), timedelta(hours=-_r1)),
        ("repredict_1h",  timedelta(hours=-_r1),  timedelta(hours=0)),
    ]
PHASE_NAMES = [p[0] for p in PHASES]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load_fixtures() -> list[dict]:
    cfg = yaml.safe_load(FIXTURES_YAML.read_text())
    return [f for f in (cfg.get("fixtures") or []) if f.get("enabled", True)]


def _fixture_provider(fx: dict) -> str:
    return (
        fx.get("provider")
        or os.environ.get("FOOTBALL_API_PROVIDER")
        or os.environ.get("WCA_FOOTBALL_API_PROVIDER")
        or "api_football"
    )


def _active_phases(kickoff: datetime, now: datetime) -> list[str]:
    """All phases whose window is currently open for this fixture."""
    return [name for (name, a, b) in PHASES if kickoff + a <= now < kickoff + b]


def _run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Phase handlers (each idempotent)
# ---------------------------------------------------------------------------

def _phase_ingest(fx: dict, fx_dir: Path) -> None:
    """Pull fixture.json from the configured football provider. No-op if already downloaded."""
    fixture_path = fx_dir / "fixture.json"
    if fixture_path.exists():
        print(f"  [ingest] skip — {fixture_path} exists")
        return
    fx_dir.mkdir(parents=True, exist_ok=True)
    lock_at = (_parse_iso(fx["kickoff_utc"]) - timedelta(hours=PREDICT_LEAD_H)).isoformat()
    _run([sys.executable, "-m", "src.ingest.api_football",
          "--provider", _fixture_provider(fx),
          "--fixture-id", str(fx["provider_id"]),
          "--wca-id", fx["wca_id"],
          "--lock-at", lock_at,
          "--out", str(fixture_path)])


def _phase_populate(fx: dict, fx_dir: Path) -> None:
    """Fill context_pack (squads + form + stats + news). No-op if squads set."""
    fixture_path = fx_dir / "fixture.json"
    if not fixture_path.exists():
        print(f"  [populate] skip — no fixture.json yet")
        return
    raw = json.loads(fixture_path.read_text())
    cp = raw.get("context_pack") or {}
    if cp.get("squads"):
        print(f"  [populate] skip — context_pack.squads already populated")
        return
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "populate",
          "--provider", _fixture_provider(fx),
          "--fixture", str(fixture_path)])


def _phase_lock_predict(fx: dict, fx_dir: Path) -> None:
    """Lock the snapshot then run every (model × setting) prediction."""
    fixture_path = fx_dir / "fixture.json"
    if not fixture_path.exists():
        # Fixture added late (inside the 24h window) — run ingest + populate now
        # before locking and predicting.
        print(f"  [lock_predict] fixture.json missing — running late ingest + populate")
        _phase_ingest(fx, fx_dir)
        if not fixture_path.exists():
            print(f"  [lock_predict] ingest failed, aborting")
            return
        _phase_populate(fx, fx_dir)
    raw = json.loads(fixture_path.read_text())
    if not raw.get("snapshot_hash"):
        _run([sys.executable, "-m", "src.pipeline.orchestrator", "lock",
              "--fixture", str(fixture_path)])
    else:
        print(f"  [lock_predict] skip lock — snapshot_hash already set")
    pred_dir = ROOT / "data" / "predictions" / fx["wca_id"]
    # if pred_dir.exists() and any(pred_dir.glob("*.json")):
    #     print(f"  [lock_predict] skip predict — predictions already exist")
    #     return
    parallel = os.environ.get("PREDICT_PARALLEL", "4")
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "predict",
          "--fixture", str(fixture_path), "--parallel", parallel])


def _phase_repredict(fx: dict, fx_dir: Path, tag: str) -> None:
    """Re-predict WCA_REPREDICT_MODELS close to kickoff, on a freshly re-ingested snapshot.

    Fires once per window (marker .repredict_<tag>) and only after the T-LEAD lock_predict
    has produced predictions. Re-ingest (lock_at=now) → populate → lock → predict --models
    <subset> --force, overwriting ONLY those models' files so they predict on later info
    (confirmed lineups / late news) than the rest of the field. No-op if the subset is empty.
    """
    if not REPREDICT_MODELS:
        return
    pred_dir = ROOT / "data" / "predictions" / fx["wca_id"]
    if not (pred_dir.exists() and any(pred_dir.glob("*.json"))):
        print(f"  [repredict_{tag}] skip — no T-LEAD predictions yet")
        return
    marker = pred_dir / f".repredict_{tag}"
    if marker.exists():
        print(f"  [repredict_{tag}] skip — already re-predicted")
        return
    fixture_path = fx_dir / "fixture.json"
    fx_dir.mkdir(parents=True, exist_ok=True)
    lock_at = _now().isoformat()
    _run([sys.executable, "-m", "src.ingest.api_football",
          "--provider", _fixture_provider(fx),
          "--fixture-id", str(fx["provider_id"]), "--wca-id", fx["wca_id"],
          "--lock-at", lock_at, "--out", str(fixture_path)])
    raw = json.loads(fixture_path.read_text())
    if not (raw.get("context_pack") or {}).get("squads"):
        _run([sys.executable, "-m", "src.pipeline.orchestrator", "populate",
              "--provider", _fixture_provider(fx), "--fixture", str(fixture_path)])
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "lock",
          "--fixture", str(fixture_path)])
    parallel = os.environ.get("PREDICT_PARALLEL", "4")
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "predict",
          "--fixture", str(fixture_path), "--parallel", parallel,
          "--models", *REPREDICT_MODELS, "--force"])
    marker.touch()
    print(f"  [repredict_{tag}] re-predicted {len(REPREDICT_MODELS)} model(s) on a fresh snapshot")


def _live_status(wca_id: str) -> str | None:
    """Return the status.long string from data/live/<wca_id>.json, or None."""
    path = LIVE_DIR / f"{wca_id}.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        r0 = raw["response"][0]
        return (r0["fixture"]["status"] or {}).get("long")
    except Exception:
        return None


def _phase_live_update(fx: dict, fx_dir: Path) -> None:
    """Fetch live match state and overwrite data/live/<wca_id>.json (T+0h → T+3h).

    If the fetched status is "Match Finished", immediately triggers truth_grade
    so the result is persisted and scored without waiting for the T+3h window.
    Kept outside the snapshot dir so it never interferes with fixture.json /
    truth.json and can be safely deleted without affecting grading.
    """
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    live_path = LIVE_DIR / f"{fx['wca_id']}.json"
    _run([sys.executable, "-m", "src.ingest.api_football",
          "--provider", _fixture_provider(fx),
          "--fixture-id", str(fx["provider_id"]),
          "--wca-id", fx["wca_id"],
          "--lock-at", "",
          "--out", str(live_path)])

    status = _live_status(fx["wca_id"])
    if status == "Match Finished":
        print(f"  [live_update] match finished — triggering truth_grade early")
        _phase_truth_grade(fx, fx_dir)


def _phase_truth_grade(fx: dict, fx_dir: Path) -> None:
    """Fetch truth, grade every prediction, rebuild leaderboard."""
    truth_path = fx_dir / "truth.json"
    if not truth_path.exists():
        _run([sys.executable, "-m", "src.ingest.api_football",
              "--provider", _fixture_provider(fx),
              "--fixture-id", str(fx["provider_id"]),
              "--wca-id", fx["wca_id"],
              "--lock-at", "",
              "--out", str(truth_path)])
    else:
        print(f"  [truth_grade] skip truth download — {truth_path} exists")
    _run([sys.executable, "-m", "src.pipeline.orchestrator", "grade",
          "--fixture-dir", str(fx_dir)])
    _run([sys.executable, "-m", "src.leaderboard.build"])


_DISPATCH = {
    "ingest":        _phase_ingest,
    "populate":      _phase_populate,
    "lock_predict":  _phase_lock_predict,
    "repredict_24h": lambda fx, d: _phase_repredict(fx, d, "24h"),
    "repredict_1h":  lambda fx, d: _phase_repredict(fx, d, "1h"),
    "live_update":   _phase_live_update,
    "truth_grade":   _phase_truth_grade,
}


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_tick(phase_filter: str | None) -> None:
    now = _now()
    for fx in _load_fixtures():
        kickoff = _parse_iso(fx["kickoff_utc"])
        active = _active_phases(kickoff, now)
        if not active:
            continue
        if phase_filter:
            active = [p for p in active if p == phase_filter]
            if not active:
                continue
        fx_dir = SNAPSHOTS / fx["wca_id"]
        print(f"[{fx['wca_id']}] kickoff={kickoff.isoformat()} phases={active}")
        for phase in active:
            try:
                _DISPATCH[phase](fx, fx_dir)
            except subprocess.CalledProcessError as e:
                print(f"  [error] {phase} failed: {e}")


def cmd_show() -> None:
    now = _now()
    print(f"{'wca_id':<40} {'kickoff_utc':<28} {'delta':<22} active_phases")
    for fx in _load_fixtures():
        kickoff = _parse_iso(fx["kickoff_utc"])
        active = _active_phases(kickoff, now)
        delta = kickoff - now
        print(f"{fx['wca_id']:<40} {kickoff.isoformat():<28} {str(delta):<22} {','.join(active) or '-'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tick")
    p.add_argument("--phase", choices=PHASE_NAMES, default=None)
    sub.add_parser("show")
    args = ap.parse_args()
    if args.cmd == "tick":
        cmd_tick(args.phase)
    elif args.cmd == "show":
        cmd_show()


if __name__ == "__main__":
    main()
