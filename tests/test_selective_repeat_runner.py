from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_selective_repeat.py"


class SelectiveRepeatRunnerTests(unittest.TestCase):
    def test_missing_endpoint_scripts_fail_before_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--receiver-script",
                    str(base / "missing_receive.py"),
                    "--sender-script",
                    str(base / "missing_send.py"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("required endpoint script(s) not found", result.stderr)

    def test_runs_supplied_endpoint_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            receiver = base / "receive.py"
            sender = base / "send.py"
            receiver.write_text("raise SystemExit(0)\n", encoding="utf-8")
            sender.write_text(
                "import sys\n"
                "assert sys.argv[1:] == ['127.0.0.1', '9000']\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--receiver-script",
                    str(receiver),
                    "--sender-script",
                    str(sender),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "9000",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_rejects_out_of_range_port(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--port", "70000"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("between 1 and 65535", result.stderr)


if __name__ == "__main__":
    unittest.main()
