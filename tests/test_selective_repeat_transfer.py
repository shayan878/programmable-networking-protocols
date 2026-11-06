from __future__ import annotations

import socket
import tempfile
import threading
import unittest
from pathlib import Path

from selective_repeat.receiver import receive_file
from selective_repeat.sender import send_file


class SelectiveRepeatIntegrationTests(unittest.TestCase):
    def test_file_transfer_survives_simulated_data_and_ack_loss(self) -> None:
        payload = bytes(range(256)) * 37 + b"selective-repeat"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            output_dir = root / "received"
            source.write_bytes(payload)

            receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver_socket.bind(("127.0.0.1", 0))
            receiver_socket.settimeout(10)
            port = receiver_socket.getsockname()[1]
            received: list[Path] = []
            failures: list[BaseException] = []

            def receiver_worker() -> None:
                try:
                    received.append(
                        receive_file(
                            receiver_socket,
                            output_dir,
                            window_size=5,
                            ack_loss_probability=0.15,
                            random_seed=22,
                            idle_timeout=10,
                        )
                    )
                except BaseException as exc:
                    failures.append(exc)
                finally:
                    receiver_socket.close()

            thread = threading.Thread(target=receiver_worker, daemon=True)
            thread.start()
            result = send_file(
                source,
                ("127.0.0.1", port),
                window_size=7,
                segment_size=500,
                timeout=0.04,
                max_retries=40,
                loss_probability=0.12,
                random_seed=11,
            )
            thread.join(timeout=10)

            self.assertFalse(thread.is_alive(), "receiver thread did not finish")
            self.assertEqual(failures, [])
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].read_bytes(), payload)
            self.assertEqual(result.bytes_transferred, len(payload))
            self.assertGreater(result.retransmissions, 0)
            self.assertGreater(result.simulated_data_drops, 0)
            self.assertGreater(result.elapsed_seconds, 0)

    def test_zero_length_file_transfers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "empty.dat"
            output_dir = root / "received"
            source.write_bytes(b"")

            receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver_socket.bind(("127.0.0.1", 0))
            receiver_socket.settimeout(5)
            port = receiver_socket.getsockname()[1]
            received: list[Path] = []

            thread = threading.Thread(
                target=lambda: received.append(
                    receive_file(
                        receiver_socket,
                        output_dir,
                        window_size=4,
                        idle_timeout=5,
                    )
                ),
                daemon=True,
            )
            thread.start()
            result = send_file(
                source,
                ("127.0.0.1", port),
                window_size=4,
                timeout=0.05,
                max_retries=10,
            )
            thread.join(timeout=5)
            receiver_socket.close()

            self.assertFalse(thread.is_alive())
            self.assertEqual(received[0].read_bytes(), b"")
            self.assertEqual(result.bytes_transferred, 0)
            self.assertEqual(result.segments, 0)


if __name__ == "__main__":
    unittest.main()
