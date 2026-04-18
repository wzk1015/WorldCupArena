"""Build the static leaderboard page from data/results."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data" / "results"
OUT = ROOT / "docs" / "leaderboard"


def collect() -> list[dict]:
    rows = []
    for fid_dir in RESULTS.glob("*"):
        for f in fid_dir.glob("*.json"):
            r = json.loads(f.read_text())
            rows.append({
                "fixture_id": fid_dir.name,
                "model_id": r["model_id"],
                "setting": r["setting"],
                "composite": r.get("composite", 0.0),
                "layers": r.get("layers", {}),
                "leaked": bool(r.get("leakage_audit", {}).get("leaked")),
            })
    return rows


def aggregate(rows: list[dict]) -> dict:
    by_model: dict[str, list[float]] = defaultdict(list)
    by_model_setting: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        if r["leaked"]:
            continue
        by_model[r["model_id"]].append(r["composite"])
        by_model_setting[(r["model_id"], r["setting"])].append(r["composite"])

    main = sorted(
        [{"model_id": m, "mean": sum(v) / len(v), "n": len(v)} for m, v in by_model.items()],
        key=lambda x: -x["mean"],
    )

    # Research uplift: S2 (tool-using agent) minus S1 (best context-fed LLM).
    # Only defined for models where the same provider ships both an LLM-only
    # variant (S1) and a tool-using / agent variant (S2). Pairing is by shared
    # prefix — e.g. `claude-sonnet-4-6` (S1) vs `claude-sonnet-4-6-search` (S2)
    # or `claude-research` (S2). Downstream dashboards do the pairing; here we
    # just emit the per-(model, setting) means.
    by_setting: dict[str, dict[str, float]] = {}
    for (m, s), v in by_model_setting.items():
        by_setting.setdefault(m, {})[s] = sum(v) / len(v)

    return {"main": main, "by_model_setting": by_setting, "rows": rows}


def write_markdown(agg: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# WorldCupArena Leaderboard", "",
             "## Main (higher = better, 0–100 composite)", "",
             "| Rank | Model | Composite | N |", "|---|---|---|---|"]
    for i, r in enumerate(agg["main"], 1):
        lines.append(f"| {i} | {r['model_id']} | {r['mean']:.2f} | {r['n']} |")
    lines += ["", "## Per-model × setting mean (S1 = context-fed LLM, S2 = tool-using)", "",
              "| Model | S1 | S2 |", "|---|---|---|"]
    for m, per_s in sorted(agg["by_model_setting"].items()):
        s1 = f"{per_s['S1']:.2f}" if "S1" in per_s else "—"
        s2 = f"{per_s['S2']:.2f}" if "S2" in per_s else "—"
        lines.append(f"| {m} | {s1} | {s2} |")
    (OUT / "README.md").write_text("\n".join(lines))


def main() -> None:
    rows = collect()
    agg = aggregate(rows)
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / "raw.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2))
    write_markdown(agg)
    print(f"wrote {len(rows)} rows")


if __name__ == "__main__":
    main()
