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
    ap.add_argument("--strict", action="store_true", help="exit on the first failed command")
    ap.set_defaults(pipeline=True, build_site=True)
    args = ap.parse_args()

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
