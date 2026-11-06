#!/usr/bin/env python3
"""CLI entry point for the Selective Repeat receiver."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from selective_repeat.receiver import receive_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Receive one Selective Repeat UDP file.")
    parser.add_argument("--bind", default="0.0.0.0", help="local address to bind")
    parser.add_argument("--port", type=int, default=1002)
    parser.add_argument("--output-dir", type=Path, default=Path("received"))
    parser.add_argument("--window-size", type=int, default=8)
    parser.add_argument(
        "--ack-loss-probability",
        type=float,
        default=0.0,
        help="test hook: probability of simulating a dropped DATA ACK",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--fin-linger", type=float, default=10.0)
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((args.bind, args.port))
        address, port = server.getsockname()
        print(f"Selective Repeat receiver listening on {address}:{port}", flush=True)
        output = receive_file(
            server,
            args.output_dir,
            window_size=args.window_size,
            ack_loss_probability=args.ack_loss_probability,
            random_seed=args.seed,
            fin_linger=args.fin_linger,
        )
    print(f"Received and verified: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
