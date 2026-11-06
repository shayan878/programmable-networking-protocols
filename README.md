# Programmable Data Plane and Reliable Transport

[![CI](https://github.com/shayan878/P4/actions/workflows/ci.yml/badge.svg)](https://github.com/shayan878/P4/actions/workflows/ci.yml)

A networking project that brings together two independently testable components:

- **P4_16 / BMv2 IPv4 forwarding:** an IPv4 forwarding pipeline with an approximate two-hash packet-frequency counter and threshold-based TCP packet dropping.
- **Selective Repeat ARQ over UDP:** a reliable file-transfer implementation with a sliding sender window, per-segment retransmission, receiver-side out-of-order buffering, CRC-protected datagrams, and end-to-end SHA-256 verification.

A reproducible **Mininet + BMv2** topology connects two IP subnets through the P4 switch. The Selective Repeat transfer can be exercised across that data plane.

## Highlights

- Modular Python package under `src/selective_repeat/`.
- Independent packet timers and selective retransmission (not Go-Back-N).
- Receiver buffers in-window out-of-order data and writes the file in order.
- Session identifiers, protocol versioning, CRC-32 packet integrity, and final SHA-256 verification.
- Atomic output-file replacement after successful verification.
- Configurable window, segment size, timeout, retry limit, and simulated endpoint loss.
- BMv2 v1model IPv4 LPM rules with an explicit Mininet topology.
- Python unit and localhost integration tests on Python 3.10–3.12.

## Repository structure

```text
.
├── .github/workflows/ci.yml
├── docs/
│   ├── architecture.md
│   ├── reproducibility.md
│   └── selective-repeat.md
├── p4src/main.p4
├── scripts/
│   ├── run_selective_repeat.py
│   ├── sr_receiver.py
│   └── sr_sender.py
├── src/selective_repeat/
│   ├── __init__.py
│   ├── protocol.py
│   ├── receiver.py
│   └── sender.py
├── tests/
├── topology/
│   ├── commands.txt
│   └── run_mininet.py
├── CONTRIBUTING.md
├── Makefile
├── pyproject.toml
└── requirements-dev.txt
```

## Quick start: Selective Repeat over localhost

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Create a small file and run the two-process demo:

```bash
mkdir -p examples
printf 'Reliable transfer with Selective Repeat.\\n' > examples/payload.txt

python scripts/run_selective_repeat.py \
  --input examples/payload.txt \
  --port 1002 \
  --output-dir received
```

The demo starts the receiver, waits for the sender's START/READY handshake, transfers the file, verifies its SHA-256 digest, and exits. The receiver writes the completed file under `received/`.

### Run sender and receiver separately

Terminal 1:

```bash
python scripts/sr_receiver.py --bind 127.0.0.1 --port 1002 --output-dir received
```

Terminal 2:

```bash
python scripts/sr_sender.py \
  --input examples/payload.txt \
  --host 127.0.0.1 \
  --port 1002 \
  --window-size 8 \
  --segment-size 1200
```

To exercise retransmission on localhost, use the demo's `--data-loss 0.05 --ack-loss 0.05 --seed 7` options. These two options inject reproducible application-level simulated losses; they are not measurements of physical network loss.

## Build and run the P4 / Mininet topology

The P4 experiment requires a Linux environment with:

- P4_16 compiler `p4c` with BMv2 v1model backend.
- BMv2 `simple_switch` and `simple_switch_CLI`.
- Mininet.
- P4-Utils (provides the BMv2-aware Mininet switch and host classes).

Install and version these tools following their upstream documentation; see [reproducibility](docs/reproducibility.md).

Compile the P4 program:

```bash
make p4-compile
```

Start the interactive network (root privileges are required):

```bash
sudo make mininet
```

Run the connectivity smoke test instead of opening the Mininet CLI:

```bash
sudo make mininet-test
```

The topology is:

```text
h1 (10.0.1.1/24) -- port 1 [ s1: BMv2 / P4 ] port 2 -- h2 (10.0.2.2/24)
```

The script installs static ARP entries and two IPv4 LPM entries. To transfer a file through the P4 switch, from the Mininet CLI:

```text
mininet> h2 python3 scripts/sr_receiver.py --bind 10.0.2.2 --port 1002 --output-dir /tmp/received &
mininet> h1 python3 scripts/sr_sender.py --input examples/payload.txt --host 10.0.2.2 --port 1002
```

Optional link shaping is available:

```bash
sudo python3 topology/run_mininet.py --delay 10ms --bandwidth 50 --link-loss 1.0
```

Here, bandwidth is in Mbit/s and link loss is a percentage applied by Mininet's traffic-control links.

## Development

```bash
python -m pip install -e . -r requirements-dev.txt
make test
make lint
```

To clean local BMv2/Mininet and Python outputs:

```bash
make clean
sudo mn -c
```

## Scope and limitations

### P4 data plane

- The program targets BMv2's v1model architecture; other targets may require changes.
- IPv4 LPM entries are installed by the included two-host topology. Other topologies need their own table entries.
- The packet-frequency key is `(IPv4 source, IPv4 destination, TCP destination port)`; it is not a TCP five-tuple.
- The two 32-bit registers form an approximate frequency counter, not a conventional Bloom filter. Collisions can cause overestimation.
- The threshold applies to TCP packets only. The Selective Repeat transport uses UDP and is not subject to that TCP-specific counter.
- Counter reset, overflow, and target-specific register atomicity need consideration in long-running experiments.
- IPv4 options are not parsed; the parser extracts the fixed 20-byte IPv4 header.
- The topology is an emulation for functional experiments, not a physical-network performance benchmark.

### Selective Repeat

- This is an educational application-layer reliable transfer protocol over UDP, not a replacement for TCP.
- Sequence numbers are monotonic unsigned 32-bit values and do not wrap during a transfer.
- The receiver accepts one active transfer at a time and overwrites an existing file with the same output name after successful verification.
- CRC-32 detects accidental datagram corruption; it is not cryptographic authentication. SHA-256 verifies the completed file contents but does not authenticate the sender.
- Do not expose the receiver to untrusted networks without adding authentication, quotas, and stricter resource limits.

No throughput figures are claimed by default. Use the included commands and record tool versions, topology settings, file size, window, segment size, timeout, retry count, and loss settings when reporting experimental results.

## License

A license has not been selected for this repository. Until one is added, do not assume the code is licensed for general reuse or redistribution.
