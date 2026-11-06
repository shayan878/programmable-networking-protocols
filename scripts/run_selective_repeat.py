#!/usr/bin/env python3
"""Start the Selective Repeat receiver and sender as a local two-process demo."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = ROOT / "scripts" / "sr_receiver.py"
SENDER = ROOT / "scripts" / "sr_sender.py"


def stop_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="file to transfer")
    parser.add_argument("--host", default="127.0.0.1", help="receiver address")
    parser.add_argument("--bind", default="127.0.0.1", help="receiver bind address")
    parser.add_argument("--port", type=int, default=1002)
    parser.add_argument("--output-dir", type=Path, default=Path("received"))
    parser.add_argument("--window-size", type=int, default=8)
    parser.add_argument("--segment-size", type=int, default=1200)
    parser.add_argument("--timeout", type=float, default=0.25)
    parser.add_argument("--max-retries", type=int, default=20)
    parser.add_argument("--data-loss", type=float, default=0.0)
    parser.add_argument("--ack-loss", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    source = args.input.expanduser().resolve()
    if not source.is_file():
        parser.error(f"input file does not exist: {source}")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 0.0 <= args.data_loss < 1.0 or not 0.0 <= args.ack_loss < 1.0:
        parser.error("--data-loss and --ack-loss must be in [0, 1)")
    if args.window_size < 1 or args.segment_size < 1:
        parser.error("--window-size and --segment-size must be positive")
    if args.timeout <= 0 or args.max_retries < 0:
        parser.error("--timeout must be positive and --max-retries cannot be negative")

    processes: list[subprocess.Popen[bytes]] = []
    try:
        receiver = subprocess.Popen(
            [
                sys.executable,
                str(RECEIVER),
                "--bind",
                args.bind,
                "--port",
                str(args.port),
                "--output-dir",
                str(args.output_dir),
                "--window-size",
                str(args.window_size),
                "--ack-loss-probability",
                str(args.ack_loss),
                "--seed",
                str(args.seed + 1),
                "--fin-linger",
                str(max(2.0, (args.max_retries + 1) * args.timeout + 0.5)),
            ]
        )
        processes.append(receiver)

        sender = subprocess.Popen(
            [
                sys.executable,
                str(SENDER),
                "--input",
                str(source),
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--window-size",
                str(args.window_size),
                "--segment-size",
                str(args.segment_size),
                "--timeout",
                str(args.timeout),
                "--max-retries",
                str(args.max_retries),
                "--loss-probability",
                str(args.data_loss),
                "--seed",
                str(args.seed),
            ]
        )
        processes.append(sender)
        sender_status = sender.wait()
        receiver_status = receiver.wait(timeout=10) if sender_status == 0 else receiver.poll()
        if sender_status != 0:
            return sender_status
        return 0 if receiver_status == 0 else 1
    except KeyboardInterrupt:
        return 130
    except subprocess.TimeoutExpired:
        print("receiver did not exit after sender completed", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"failed to start transfer process: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
