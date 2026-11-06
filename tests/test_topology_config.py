import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TopologyConfigurationTests(unittest.TestCase):
    def test_cli_commands_cover_both_subnets_and_expected_ports(self) -> None:
        commands = (ROOT / "topology" / "commands.txt").read_text(encoding="utf-8")
        self.assertIn("10.0.2.2/32", commands)
        self.assertIn("10.0.1.1/32", commands)
        self.assertIn("00:aa:bb:00:00:02 00:00:00:00:02:02 2", commands)
        self.assertIn("00:aa:bb:00:00:01 00:00:00:00:01:01 1", commands)

    def test_topology_uses_p4utils_bmv2_switch_and_two_hosts(self) -> None:
        source = (ROOT / "topology" / "run_mininet.py").read_text(encoding="utf-8")
        self.assertIn("P4Switch", source)
        self.assertIn("simple_switch_CLI", source)
        self.assertIn('net.addHost("h1"', source)
        self.assertIn('net.addHost("h2"', source)


if __name__ == "__main__":
    unittest.main()
