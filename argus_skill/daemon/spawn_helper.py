"""Single-threaded exec boundary for detached daemon spawning."""

from __future__ import annotations

import json
import sys

from .config import config_from_payload
from .life_worker import spawn_detached_daemon


def main() -> int:
    config = config_from_payload(json.load(sys.stdin))
    # This helper's stdio is captured by ``spawn_detached_daemon_clean``.  Keep
    # failure output enabled so the parent WebAPI can return an actionable
    # diagnostic instead of reducing every failure to an opaque ``rc=1``.
    return spawn_detached_daemon(config, quiet=False)


if __name__ == "__main__":
    raise SystemExit(main())
