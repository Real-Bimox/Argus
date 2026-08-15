"""Render the pentagon testbed's event stream as a readable trace.

``--follow`` exists, but this run is a feature audit rather than a demo: what
matters is which vertical resolved, which stage the Manager moved to and on
whose verdict, whether the proof-graph and Lean gates fired, and whether any
role errored — so the events are filtered and annotated toward those questions
rather than pretty-printed in full.

Run::

    ./.venv/bin/python math-docs/testbed_watch.py            # replay + follow
    ./.venv/bin/python math-docs/testbed_watch.py --once     # replay and exit
    ./.venv/bin/python math-docs/testbed_watch.py --raw TYPE # dump one type in full
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

# Same override as the launcher, so a watcher always follows the campaign that
# was actually started rather than whichever one ran first.
PROJECT = Path(
    os.environ.get("ARGUS_TESTBED_PROJECT")
    or (Path.home() / "argus-testbed-pentagon")
).expanduser()
PIN = PROJECT / ".testbed_session"

# Anything matching these is printed with its payload; everything else gets a
# one-line summary. These are the seams the run is meant to exercise.
LOUD = (
    "error", "failed", "failure", "refus", "reject", "block", "stall",
    "vertical", "stage_decision", "planner", "review", "lean", "graph",
    "objective", "auth", "policy", "route", "citation",
)


def _sid() -> str:
    return json.loads(PIN.read_text(encoding="utf-8"))["sid"]


def _events_path() -> Path:
    from argus_skill.core import paths as core_paths

    return core_paths.session_state_root(_sid()) / "events.jsonl"


def _summarize(ev: dict) -> str:
    kind = str(ev.get("type") or "?")
    bits = []
    for key in ("stage", "from_stage", "to_stage", "decision", "status", "verdict",
                "vertical", "role", "reason", "error", "text", "title", "objective",
                "profile", "mode", "count", "rounds", "next_action"):
        val = ev.get(key)
        if val in (None, "", [], {}):
            continue
        rendered = " ".join(str(val).split())
        bits.append(f"{key}={rendered[:220]}")
    return f"{kind}  " + "  ".join(bits) if bits else kind


def _render(ev: dict, *, raw_type: str = "") -> None:
    kind = str(ev.get("type") or "?")
    stamp = time.strftime("%H:%M:%S", time.localtime(ev.get("ts") or time.time()))
    if raw_type and raw_type in kind:
        print(f"\n[{stamp}] === {kind} ===")
        print(json.dumps(ev, indent=2, ensure_ascii=False, default=str)[:6000])
        return
    loud = any(token in kind.lower() for token in LOUD)
    marker = "!!" if loud else "  "
    print(f"[{stamp}]{marker} {_summarize(ev)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="replay and exit")
    parser.add_argument("--raw", default="", metavar="TYPE",
                        help="dump full payloads for event types containing TYPE")
    parser.add_argument("--tail", type=int, default=0,
                        help="start from the last N events instead of the beginning")
    args = parser.parse_args(argv)

    path = _events_path()
    print(f"# {path}", flush=True)
    offset = 0
    seen: list[dict] = []
    while True:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                handle.seek(offset)
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        seen.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"  !! unparseable event line: {line[:160]}", flush=True)
                offset = handle.tell()
        if seen:
            batch = seen[-args.tail:] if args.tail and len(seen) > args.tail else seen
            for ev in batch:
                _render(ev, raw_type=args.raw)
            args.tail = 0
            seen = []
        if args.once:
            return 0
        time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())
