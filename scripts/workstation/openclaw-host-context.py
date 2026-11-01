#!/usr/bin/env python3
"""Non-secret host fingerprint for homelab diagnostic routing."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openclaw_runtime import detect_host  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", action="store_true", help="Print only the host classification")
    args = parser.parse_args(argv)
    host = detect_host()
    if args.kind:
        print(host)
    else:
        print("host_context=" + host)
        print("cross_host_openclaw_probe=" + {"truenas": "not_applicable",
                                               "workstation": "workstation_only"}.get(
                                                   host, "blocked_unknown_host"))
    return 0 if host != "unknown" else 2


if __name__ == "__main__":
    raise SystemExit(main())
