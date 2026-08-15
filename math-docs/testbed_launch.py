"""Start the pentagon testbed campaign through the real operator front door.

This is a harness for watching the math vertical run, not a fixture. Every step
below is the same call the cockpit makes; nothing is stubbed, and in particular
the vertical, workflow mode, and research target level are NOT set here — the
Manager reads them out of the request, and whether it reads them correctly is
part of what this run is checking.

The one thing set ahead of the Manager is the objective mode, because that is
the operator's decision by construction (see
``argus_skill.verticals.math.objective_mode``) and because leaving it unset
blocks every math stage including ``scope``, so the run would stall on turn one
with nothing to observe. Written before the first message so the campaign never
observes a project without it; ``persist_vertical`` merges rather than replaces,
so the Manager's own decision lands on top without losing it.

Run::

    ./.venv/bin/python math-docs/testbed_launch.py            # start
    ./.venv/bin/python math-docs/testbed_launch.py --show     # print sid/paths
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Each campaign gets its own directory. A previous run's PIPELINE_STATE.json is
# the run's history, not scaffolding to be reused — and a corrupt one (run 5's
# is, see the canary rollback in tests/skills/test_stale_framework_stage_write.py)
# would silently spend the next campaign on recovery instead of on the problem.
PROJECT = Path(
    os.environ.get("ARGUS_TESTBED_PROJECT")
    or (Path.home() / "argus-testbed-pentagon")
).expanduser()
PIN = PROJECT / ".testbed_session"

PROBLEM = (REPO / "testbed.md").read_text(encoding="utf-8").strip()

# The statement alone, without the "Prove or disprove" instruction wrapper: this
# is what every gap measurement and the proof graph's root are checked against,
# so it has to be the mathematical claim rather than the task framing.
GOAL = (
    "Let z_1,...,z_5 be complex numbers with sum_{i=1}^5 |z_i|^2 = 5. "
    "Then prod_{1<=i<j<=5} |z_i - z_j|^2 <= 5^5, with equality if and only if "
    "z_1,...,z_5 are the vertices of a regular pentagon centered at the origin."
)


def _load_pin() -> str:
    try:
        return json.loads(PIN.read_text(encoding="utf-8"))["sid"]
    except (OSError, json.JSONDecodeError, KeyError):
        return ""


def _paths(sid: str) -> dict[str, str]:
    from argus_skill.core import paths as core_paths

    life = core_paths.session_state_root(sid)
    return {
        "sid": sid,
        "project": str(PROJECT),
        "life_dir": str(life),
        "events": str(life / "events.jsonl"),
        "pipeline_state": str(PROJECT / "research" / "PIPELINE_STATE.json"),
        "math_state": str(PROJECT / "research" / "MATH_STATE.json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args(argv)

    if args.show:
        sid = _load_pin()
        if not sid:
            print("no pinned session yet", file=sys.stderr)
            return 1
        print(json.dumps(_paths(sid), indent=2))
        return 0

    from argus_skill.core.session import resolve_session
    from argus_skill.verticals.math.objective_mode import set_objective
    from argus_skill.webapi import manager_bridge

    PROJECT.mkdir(parents=True, exist_ok=True)
    objective = set_objective(PROJECT, mode="targeted", goal=GOAL)
    if not objective.resolved:
        print(f"objective not resolved: {objective.note}", file=sys.stderr)
        return 1

    sid, _is_new = resolve_session(global_root=None, mode="new", cwd=PROJECT)
    PIN.write_text(json.dumps({"sid": sid, "started": time.time()}), encoding="utf-8")
    paths = _paths(sid)
    print(json.dumps(paths, indent=2), flush=True)

    # Streamed so the Manager's own reasoning is on the record too — the first
    # thing worth checking is whether it routes this to the math vertical at
    # all, and that decision happens inside this call.
    def _fragment(kind: str, payload: dict) -> None:
        text = payload.get("text") or payload.get("phase") or ""
        if text:
            print(f"[manager.{kind}] {str(text)[:400]}", flush=True)

    result = manager_bridge.manager_message(
        sid, PROBLEM, on_fragment=_fragment, source_channel="testbed"
    )
    print("\n=== front door result ===", flush=True)
    print(json.dumps(result, indent=2, default=str)[:4000], flush=True)

    # The cockpit spawns this from its own endpoint; headless, the mission just
    # sits in the backlog with nothing to execute it (the first run reported
    # ``daemon_alive: false`` and never started).
    if result.get("kind") == "task":
        from argus_skill.webapi.daemon_lifecycle import start_project_daemon

        started = start_project_daemon(sid, resume_continuous=True)
        daemon = (started or {}).get("daemon") or {}
        print(
            f"\n=== daemon === alive={daemon.get('alive')} pid={daemon.get('pid')} "
            f"backend={daemon.get('backend')}",
            flush=True,
        )

    state = Path(paths["pipeline_state"])
    if state.exists():
        print("\n=== PIPELINE_STATE.json ===", flush=True)
        print(state.read_text(encoding="utf-8"), flush=True)
    return 0 if result.get("kind") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
