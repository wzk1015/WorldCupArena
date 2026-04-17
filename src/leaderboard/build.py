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

    # Research uplift: S1 minus S0
    uplift = {}
    for (m, s), v in by_model_setting.items():
        uplift.setdefault(m, {})[s] = sum(v) / len(v)
    uplift_list = []
    for m, per_s in uplift.items():
        if "S0" in per_s and "S1" in per_s:
            uplift_list.append({"model_id": m, "s0": per_s["S0"], "s1": per_s["S1"],
                                "uplift": per_s["S1"] - per_s["S0"]})
    uplift_list.sort(key=lambda x: -x["uplift"])

    return {"main": main, "research_uplift": uplift_list, "rows": rows}


def write_markdown(agg: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# WorldCupBench Leaderboard", "",
             "## Main (higher = better, 0–100 composite)", "",
             "| Rank | Model | Composite | N |", "|---|---|---|---|"]
    for i, r in enumerate(agg["main"], 1):
        lines.append(f"| {i} | {r['model_id']} | {r['mean']:.2f} | {r['n']} |")
    lines += ["", "## Research Uplift (S1 − S0)", "",
              "| Rank | Model | S0 | S1 | Uplift |", "|---|---|---|---|---|"]
    for i, r in enumerate(agg["research_uplift"], 1):
        lines.append(f"| {i} | {r['model_id']} | {r['s0']:.2f} | {r['s1']:.2f} | {r['uplift']:+.2f} |")
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
