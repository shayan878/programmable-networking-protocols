from pathlib import Path
import unittest

P4_SOURCE = Path(__file__).resolve().parents[1] / "p4src" / "main.p4"


class P4SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = P4_SOURCE.read_text(encoding="utf-8")

    def test_declares_v1model_pipeline(self) -> None:
        self.assertIn("#include <v1model.p4>", self.source)
        self.assertIn("V1Switch(", self.source)
        self.assertIn("control MyIngress(", self.source)

    def test_checks_ipv4_checksum(self) -> None:
        self.assertIn("verify_checksum(", self.source)
        self.assertIn("update_checksum(", self.source)

    def test_uses_two_hash_counter_and_threshold(self) -> None:
        self.assertIn("FLOW_COUNTER_ENTRIES", self.source)
        self.assertIn("HashAlgorithm.crc16", self.source)
        self.assertIn("HashAlgorithm.crc32", self.source)
        self.assertIn("meta.counter_one > FLOW_PACKET_THRESHOLD", self.source)
        self.assertIn("meta.counter_two > FLOW_PACKET_THRESHOLD", self.source)

    def test_does_not_mislabel_counter_as_bloom_filter(self) -> None:
        self.assertNotIn("BLOOM_FILTER", self.source)
        self.assertNotIn("bloom_filter", self.source)


if __name__ == "__main__":
    unittest.main()
