"""Calibrate evals/judge.py against hand labels on the same CV samples.

Usage: python -m evals.calibrate_judge
Requires evals/cv_samples.jsonl (see generate_cv_samples.py) and
evals/cv_judge_labels.jsonl (hand labels, same resume_id/job_id keys).
"""
import asyncio
import json
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

from evals.judge import judge_cv

SAMPLES = Path(__file__).parent / "cv_samples.jsonl"
LABELS = Path(__file__).parent / "cv_judge_labels.jsonl"
OUT = Path(__file__).parent / "results" / "judge_calibration.json"

DIMENSIONS = ("relevance", "factuality", "specificity")


def _load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


async def run() -> dict:
    samples = _load_jsonl(SAMPLES)
    hand_labels = {(l["resume_id"], l["job_id"]): l for l in _load_jsonl(LABELS)}

    rows = []
    for s in samples:
        key = (s["resume_id"], s["job_id"])
        if key not in hand_labels:
            print(f"skipping {key}: no hand label")
            continue
        judgement = await judge_cv(s["resume_content"], s["job_description"], s["generated_cv"])
        rows.append({"key": key, "hand": hand_labels[key], "judge": judgement.model_dump()})

    kappas = {}
    for dim in DIMENSIONS:
        mine = [r["hand"][dim] for r in rows]
        judged = [r["judge"][dim] for r in rows]
        kappas[dim] = cohen_kappa_score(mine, judged, weights="quadratic")

    return {"n": len(rows), "kappas": kappas, "rows": rows}


def main() -> None:
    result = asyncio.run(run())
    print(json.dumps(result["kappas"], indent=2))
    for dim, k in result["kappas"].items():
        flag = "OK" if k > 0.6 else "BELOW 0.6 TARGET"
        print(f"  {dim}: kappa={k:.3f} [{flag}]")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
