from __future__ import annotations

import os
from collections.abc import Iterable

REQUIRED_RUN_TYPES = {"llm", "chain", "tool"}


def check_trajectory(run_types: Iterable[str]) -> list[str]:
    """Return structural errors for a LangSmith trace's observed run types."""
    observed = set(run_types)
    return [f"missing run type: {run_type}" for run_type in sorted(REQUIRED_RUN_TYPES - observed)]


def evaluate_recent_traces(limit: int = 20) -> dict:
    """Inspect recent LangSmith traces when credentials are configured.

    The function is intentionally import-safe in CI and local environments without
    LangSmith credentials; callers receive a skipped result instead of a fake pass.
    """
    if not os.getenv("LANGSMITH_API_KEY"):
        return {"status": "skipped", "reason": "LANGSMITH_API_KEY is not configured", "traces": 0}
    from langsmith import Client
    client = Client()
    runs = list(client.list_runs(project_name=os.getenv("LANGSMITH_PROJECT", "jobscout"), is_root=True, limit=limit))
    failures = []
    for run in runs:
        child_types = [child.run_type for child in client.list_runs(parent_run_id=run.id, limit=100)]
        failures.extend({"run_id": str(run.id), "error": error} for error in check_trajectory(child_types))
    return {"status": "ok" if not failures else "failed", "traces": len(runs), "failures": failures}


if __name__ == "__main__":
    result = evaluate_recent_traces()
    print(result)
    raise SystemExit(1 if result.get("status") == "failed" else 0)
