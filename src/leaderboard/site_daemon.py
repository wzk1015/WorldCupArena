"""Keep the WorldCupArena static site fresh for MatchMate /predict/.

This process is intentionally file-based: it updates docs/site/ in-place, and
MatchMate serves that directory directly at /predict/. No HTTP server is needed
inside WorldCupArena.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd: list[str], *, env: dict[str, str], strict: bool) -> int:
    print(f"[{_ts()}] $ {' '.join(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, env=env)
    if completed.returncode:
        print(f"[{_ts()}] command exited {completed.returncode}: {' '.join(cmd)}", flush=True)
        if strict:
            raise subprocess.CalledProcessError(completed.returncode, cmd)
    return completed.returncode


def run_once(args: argparse.Namespace) -> bool:
    env = os.environ.copy()
    if args.disable_translation_llm:
        env["SITE_TRANSLATION_DISABLE_LLM"] = "1"

    ok = True
    if args.git_pull:
        ok = _run(["git", "pull", "--ff-only"], env=env, strict=args.strict) == 0 and ok

    if args.pipeline:
        cmd = [sys.executable, "-m", "src.pipeline.scheduler", "tick"]
        if args.phase:
            cmd.extend(["--phase", args.phase])
        ok = _run(cmd, env=env, strict=args.strict) == 0 and ok

    if args.live_predict:
        cmd = [
            sys.executable, "-m", "src.pipeline.live_predict", "once",
            "--fixture-id", args.live_fixture_id,
            "--wca-id", args.live_wca_id,
            "--no-build-site",
        ]
        if args.live_provider:
            cmd.extend(["--provider", args.live_provider])
        if args.live_models:
            cmd.append("--models")
            cmd.extend(args.live_models)
        if args.always_predict_live:
            cmd.append("--predict-every-cycle")
        else:
            cmd.append("--only-live")
        ok = _run(cmd, env=env, strict=args.strict) == 0 and ok

    if args.build_site:
        ok = _run([sys.executable, "-m", "src.leaderboard.build_site"], env=env, strict=args.strict) == 0 and ok

    return ok


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> None:
    ap = argparse.ArgumentParser(description="Maintain WorldCupArena docs/site for MatchMate /predict/.")
    ap.add_argument("--interval-seconds", type=positive_int, default=300)
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    ap.add_argument("--no-pipeline", dest="pipeline", action="store_false", help="skip scheduler tick")
    ap.add_argument("--no-build-site", dest="build_site", action="store_false", help="skip docs/site data rebuild")
    ap.add_argument("--phase", choices=["ingest", "populate", "lock_predict", "live_update", "truth_grade"], default=None)
    ap.add_argument("--git-pull", action="store_true", help="pull WorldCupArena before each cycle")
    ap.add_argument("--disable-translation-llm", action="store_true", help="use cached/fallback Chinese translations only")
    ap.add_argument("--live-predict", action="store_true", help="run one live prediction cycle before rebuilding the site")
    ap.add_argument("--live-fixture-id", default=None, help="football provider fixture id for --live-predict")
    ap.add_argument("--live-wca-id", default=None, help="WorldCupArena fixture id for --live-predict")
    ap.add_argument("--live-provider", default=None, help="football API provider override for --live-predict")
    ap.add_argument("--live-models", nargs="*", default=None, help="model ids to use for --live-predict")
    ap.add_argument("--always-predict-live", action="store_true", help="if true, create a fresh live prediction every cycle even before kickoff")
    ap.add_argument("--strict", action="store_true", help="exit on the first failed command")
    ap.set_defaults(pipeline=True, build_site=True)
    args = ap.parse_args()
    if args.live_predict and (not args.live_fixture_id or not args.live_wca_id):
        ap.error("--live-predict requires --live-fixture-id and --live-wca-id")

    print(f"[{_ts()}] WorldCupArena site daemon root={ROOT}", flush=True)
    while True:
        run_once(args)
        if args.once:
            return
        print(f"[{_ts()}] sleeping {args.interval_seconds}s", flush=True)
        try:
            time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            print(f"[{_ts()}] stopped", flush=True)
            return


if __name__ == "__main__":
    main()
