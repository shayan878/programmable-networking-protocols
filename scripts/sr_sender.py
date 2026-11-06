#!/usr/bin/env python3
"""CLI entry point for the Selective Repeat sender."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from selective_repeat.sender import send_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a file using Selective Repeat over UDP.")
    parser.add_argument("--input", type=Path, required=True, help="file to transfer")
    parser.add_argument("--host", required=True, help="receiver IP address or hostname")
    parser.add_argument("--port", type=int, default=1002, help="receiver UDP port")
    parser.add_argument("--window-size", type=int, default=8)
    parser.add_argument("--segment-size", type=int, default=1200)
    parser.add_argument("--timeout", type=float, default=0.25, help="per-segment timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=20)
    parser.add_argument(
        "--loss-probability",
        type=float,
        default=0.0,
        help="test hook: probability of simulating a dropped DATA send",
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed for simulated loss")
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    result = send_file(
        args.input,
        (args.host, args.port),
        window_size=args.window_size,
        segment_size=args.segment_size,
        timeout=args.timeout,
        max_retries=args.max_retries,
        loss_probability=args.loss_probability,
        random_seed=args.seed,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
