#!/usr/bin/env python3
"""Run a two-subnet Mininet topology through a BMv2 v1model switch."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

H1_IP = "10.0.1.1/24"
H2_IP = "10.0.2.2/24"
H1_MAC = "00:00:00:00:01:01"
H2_MAC = "00:00:00:00:02:02"
GATEWAY_1 = "10.0.1.254"
GATEWAY_2 = "10.0.2.254"
SWITCH_MAC_1 = "00:aa:bb:00:00:01"
SWITCH_MAC_2 = "00:aa:bb:00:00:02"
THRIFT_PORT = 9090


def configure_switch(cli: str) -> None:
    commands = (ROOT / "topology" / "commands.txt").read_text(encoding="utf-8")
    result = subprocess.run(
        [cli, "--thrift-port", str(THRIFT_PORT)],
        input=commands,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0 or "Invalid" in output or "Error" in output:
        raise RuntimeError(f"BMv2 table programming failed:\n{output}")
    print(output)


def run(args: argparse.Namespace) -> int:
    if os.geteuid() != 0:
        raise SystemExit("Mininet must be run as root (for example: sudo make mininet)")
    try:
        from mininet.cli import CLI
        from mininet.link import TCLink
        from mininet.log import setLogLevel
        from mininet.net import Mininet
        from p4utils.mininetlib.node import P4Host, P4Switch
    except ImportError as exc:
        raise SystemExit(
            "Mininet and p4-utils are required. See docs/reproducibility.md."
        ) from exc

    switch_json = Path(args.json).expanduser().resolve()
    if not switch_json.is_file():
        raise SystemExit(f"compiled BMv2 JSON not found: {switch_json}; run make p4-compile")

    setLogLevel("info")
    net = Mininet(
        controller=None,
        host=P4Host,
        switch=P4Switch,
        link=TCLink,
        autoSetMacs=False,
        autoStaticArp=False,
    )
    try:
        net.addSwitch(
            "s1",
            cls=P4Switch,
            sw_path=args.bmv2,
            json_path=str(switch_json),
            thrift_port=THRIFT_PORT,
            log_console=True,
        )
        host_1 = net.addHost("h1", cls=P4Host, ip=H1_IP, mac=H1_MAC)
        host_2 = net.addHost("h2", cls=P4Host, ip=H2_IP, mac=H2_MAC)

        link_options = {
            "delay": args.delay,
            "bw": args.bandwidth,
            "loss": args.link_loss,
        }
        net.addLink(host_1, "s1", port1=0, port2=1, **link_options)
        net.addLink(host_2, "s1", port1=0, port2=2, **link_options)
        net.start()

        host_1.setARP(GATEWAY_1, SWITCH_MAC_1)
        host_2.setARP(GATEWAY_2, SWITCH_MAC_2)
        host_1.setDefaultRoute(f"via {GATEWAY_1}")
        host_2.setDefaultRoute(f"via {GATEWAY_2}")
        configure_switch(args.cli)

        print("Topology ready: h1 (10.0.1.1) <-> s1:BMv2 <-> h2 (10.0.2.2)")
        print("Try: h1 ping -c 3 10.0.2.2")
        print(
            "For Selective Repeat, start scripts/sr_receiver.py on h2, "
            "then scripts/sr_sender.py on h1."
        )

        if args.test:
            result = host_1.cmd("ping -c 3 -W 2 10.0.2.2")
            print(result)
            if "0% packet loss" not in result:
                return 1
            return 0

        CLI(net)
        return 0
    finally:
        net.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default=str(ROOT / "build" / "main.json"))
    parser.add_argument("--bmv2", default="simple_switch")
    parser.add_argument("--cli", default="simple_switch_CLI")
    parser.add_argument("--delay", default="5ms")
    parser.add_argument("--bandwidth", type=float, default=100.0)
    parser.add_argument("--link-loss", type=float, default=0.0)
    parser.add_argument("--test", action="store_true", help="run a ping smoke test and exit")
    args = parser.parse_args()
    if args.bandwidth <= 0 or not 0.0 <= args.link_loss < 100.0:
        parser.error("bandwidth must be positive and link loss must be in [0, 100)")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
