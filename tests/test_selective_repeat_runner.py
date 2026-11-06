from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_selective_repeat.py"
SENDER = ROOT / "scripts" / "sr_sender.py"
RECEIVER = ROOT / "scripts" / "sr_receiver.py"


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SelectiveRepeatCommandTests(unittest.TestCase):
    def test_endpoint_help_commands(self) -> None:
        for script in (SENDER, RECEIVER, RUNNER):
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_local_two_process_launcher_transfers_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payload.txt"
            output = root / "received"
            content = b"Selective Repeat command-line integration test\n" * 300
            source.write_bytes(content)
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--input",
                    str(source),
                    "--port",
                    str(free_udp_port()),
                    "--output-dir",
                    str(output),
                    "--timeout",
                    "0.05",
                    "--max-retries",
                    "20",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )

        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertEqual((output / "payload.txt").read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
