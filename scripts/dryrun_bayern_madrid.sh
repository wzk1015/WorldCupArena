#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WorldCupBench dry-run — Bayern vs Real Madrid (UCL 25/26 QF leg 2)
#
# Purpose: exercise the full lock -> predict -> grade -> leaderboard pipeline
# on a fixture whose result is already known. Result leakage does NOT matter
# here; this is a plumbing test, not a benchmark entry.
#
# What it does:
#   1. (Optional) filters configs/models.yaml to a single cheap model so the
#      dry-run costs cents, not dollars. Override with DRYRUN_MODELS="all" to
#      run every configured model.
#   2. locks the fixture snapshot (writes snapshot_hash).
#   3. runs `predict` for every (model, setting) pair supported.
#   4. runs `grade` against the synthetic truth.json.
#   5. rebuilds the static leaderboard.
#
# Requirements:
#   - Python venv activated with requirements.txt installed.
#   - At least one API key exported in .env (default: DEEPSEEK_API_KEY).
#   - Run from repo root.
#
# Usage:
#   bash scripts/dryrun_bayern_madrid.sh            # cheap: deepseek-r1 only
#   DRYRUN_MODELS=all bash scripts/dryrun_bayern_madrid.sh
#   DRYRUN_MODELS=gpt-5.4,claude-sonnet-4-6 bash scripts/dryrun_bayern_madrid.sh
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FIXTURE_DIR="data/snapshots/bayern_madrid_ucl_qf_l2"
FIXTURE="$FIXTURE_DIR/fixture.json"
TRUTH="$FIXTURE_DIR/truth.json"
DRYRUN_MODELS="${DRYRUN_MODELS:-deepseek-r1}"
PARALLEL="${PARALLEL:-4}"

echo "============================================================"
echo " WorldCupBench dry-run: Real Madrid vs Bayern (UCL QF L2)"
echo "   fixture:      $FIXTURE"
echo "   models:       $DRYRUN_MODELS"
echo "   parallel:     $PARALLEL"
echo "============================================================"

# --- sanity checks --------------------------------------------------------
[[ -f "$FIXTURE" ]] || { echo "missing $FIXTURE"; exit 1; }
[[ -f "$TRUTH"   ]] || { echo "missing $TRUTH (dry-run needs a truth file)"; exit 1; }

if [[ -f ".env" ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source .env
  set +o allexport
fi

python3 -c "import yaml, jsonschema, anthropic, openai" >/dev/null 2>&1 || {
  echo "[fatal] missing Python deps. Run: pip install -r requirements.txt"
  exit 1
}

# --- optional filter of models.yaml --------------------------------------
MODELS_CFG="configs/models.yaml"
ORIG_MODELS="$MODELS_CFG"
FILTERED_MODELS=""
if [[ "$DRYRUN_MODELS" != "all" ]]; then
  FILTERED_MODELS="$(mktemp -t worldcupbench_models.XXXX.yaml)"
  python3 - "$ORIG_MODELS" "$FILTERED_MODELS" "$DRYRUN_MODELS" <<'PY'
import sys, yaml
src, dst, keep_csv = sys.argv[1], sys.argv[2], sys.argv[3]
keep = {m.strip() for m in keep_csv.split(",") if m.strip()}
cfg = yaml.safe_load(open(src))
for cat, entries in list(cfg.items()):
    if cat == "baselines" or not isinstance(entries, list):
        continue
    cfg[cat] = [m for m in entries if m.get("id") in keep]
yaml.safe_dump(cfg, open(dst, "w"), sort_keys=False)
print(f"[filter] kept models: {keep}", file=sys.stderr)
PY
  cp "$FILTERED_MODELS" "$MODELS_CFG.dryrun"
  # orchestrator always reads configs/models.yaml; swap it in temporarily.
  cp "$MODELS_CFG" "$MODELS_CFG.bak"
  cp "$MODELS_CFG.dryrun" "$MODELS_CFG"
  trap 'mv -f "$MODELS_CFG.bak" "$MODELS_CFG" 2>/dev/null; rm -f "$MODELS_CFG.dryrun" "$FILTERED_MODELS"' EXIT
fi

# --- 1. lock --------------------------------------------------------------
echo; echo "[1/4] lock"
python3 -m src.pipeline.orchestrator lock --fixture "$FIXTURE"

# --- 2. predict -----------------------------------------------------------
echo; echo "[2/4] predict"
python3 -m src.pipeline.orchestrator predict --fixture "$FIXTURE" --parallel "$PARALLEL"

# --- 3. grade -------------------------------------------------------------
echo; echo "[3/4] grade"
python3 -m src.pipeline.orchestrator grade --fixture-dir "$FIXTURE_DIR"

# --- 4. leaderboard -------------------------------------------------------
echo; echo "[4/4] leaderboard"
python3 -m src.pipeline.orchestrator leaderboard

echo
echo "============================================================"
echo " Dry-run complete. Artifacts:"
echo "   predictions: data/predictions/bayern_madrid_ucl_qf_l2/"
echo "   scored:      data/results/bayern_madrid_ucl_qf_l2/"
echo "   leaderboard: docs/leaderboard/raw.json"
echo "============================================================"
