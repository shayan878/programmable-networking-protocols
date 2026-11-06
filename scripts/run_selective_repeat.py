#!/usr/bin/env python3
"""Start the external Selective Repeat receiver and sender scripts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def valid_port(value: str) -> int:
    """Parse a TCP/UDP port number."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def stop_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Terminate any child processes that are still running."""
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Start an external Selective Repeat receiver, then its sender. "
            "The endpoint scripts are not included in this repository."
        )
    )
    parser.add_argument(
        "--receiver-script",
        type=Path,
        default=ROOT / "receive.py",
        help="receiver script path (default: ./receive.py)",
    )
    parser.add_argument(
        "--sender-script",
        type=Path,
        default=ROOT / "send.py",
        help="sender script path (default: ./send.py)",
    )
    parser.add_argument("--host", default="10.0.2.2", help="destination host")
    parser.add_argument("--port", type=valid_port, default=1002, help="destination port")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    receiver_script = args.receiver_script.expanduser().resolve()
    sender_script = args.sender_script.expanduser().resolve()

    missing = [
        str(path)
        for path in (receiver_script, sender_script)
        if not path.is_file()
    ]
    if missing:
        parser.error(
            "required endpoint script(s) not found: "
            + ", ".join(missing)
            + ". Add the endpoint implementations or pass their paths explicitly."
        )

    processes: list[subprocess.Popen[bytes]] = []
    try:
        receiver = subprocess.Popen([sys.executable, str(receiver_script)])
        processes.append(receiver)

        # Keep the positional host/port contract of the original launcher.
        sender = subprocess.Popen(
            [sys.executable, str(sender_script), args.host, str(args.port)]
        )
        processes.append(sender)

        sender_status = sender.wait()
        if sender_status != 0:
            return sender_status
        return receiver.wait()
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"failed to start endpoint process: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
