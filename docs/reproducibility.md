# Reproducibility and experiment guide

## 1. Toolchain

The BMv2 integration is Linux-only and requires the following external tools:

- `p4c` with the BMv2 backend and v1model architecture support.
- BMv2 executables: `simple_switch` and `simple_switch_CLI`.
- Mininet.
- P4-Utils, including `p4utils.mininetlib.node.P4Host` and `P4Switch`.

Use the upstream installation guides and record the exact versions used:

- [P4 compiler](https://github.com/p4lang/p4c)
- [Behavioral Model (BMv2)](https://github.com/p4lang/behavioral-model)
- [Mininet](https://github.com/mininet/mininet)
- [P4-Utils](https://github.com/nsg-ethz/p4-utils) and its [documentation](https://nsg-ethz.github.io/p4-utils/)

P4-Utils depends on BMv2, p4c, and Mininet and is designed for Linux. A dedicated VM is recommended to isolate Mininet's network namespaces and virtual interfaces.

## 2. Compile P4

From the repository root:

```bash
p4c --version
simple_switch --help
simple_switch_CLI --help
make p4-compile
```

The compiler command is:

```bash
p4c --target bmv2 --arch v1model --std p4-16 \
  -o build/main.json p4src/main.p4
```

Successful compilation produces `build/main.json`. Compilation is distinct from starting BMv2 or programming its tables.

## 3. Start the BMv2 / Mininet topology

Run the topology with root privileges:

```bash
sudo python3 topology/run_mininet.py
```

The topology creates two hosts on different IPv4 subnets, connects them to BMv2 ports 1 and 2, adds static ARP entries, and installs the LPM forwarding rules from `topology/commands.txt`.

Run the non-interactive connectivity smoke test:

```bash
sudo python3 topology/run_mininet.py --test
```

Optional traffic-control parameters:

```bash
sudo python3 topology/run_mininet.py \
  --delay 10ms \
  --bandwidth 50 \
  --link-loss 1.0
```

- `--delay`: per-link one-way delay accepted by Mininet's TCLink (for example, `10ms`).
- `--bandwidth`: per-link bandwidth in Mbit/s.
- `--link-loss`: per-link loss percentage in ([0,100)).

When finished, stop Mininet and clean stale virtual interfaces with `sudo mn -c`.

## 4. Transfer a file through the P4 switch

Create a sample payload on the host filesystem:

```bash
mkdir -p examples
dd if=/dev/urandom of=examples/payload.bin bs=1024 count=256
sha256sum examples/payload.bin
```

Start the receiver in the Mininet CLI:

```text
mininet> h2 python3 scripts/sr_receiver.py --bind 10.0.2.2 --port 1002 --output-dir /tmp/received &
```

Start the sender from h1:

```text
mininet> h1 python3 scripts/sr_sender.py --input examples/payload.bin --host 10.0.2.2 --port 1002 --window-size 8 --segment-size 1200
```

Verify the file on the destination host:

```text
mininet> h2 sha256sum /tmp/received/payload.bin
```

The resulting digest should match the source file's digest. The sender prints JSON statistics including transferred bytes, data transmissions, retransmissions, elapsed time, and application-level throughput.

## 5. Repeatable loss experiments

For local protocol testing, the launcher can inject pseudorandom DATA and ACK loss:

```bash
python scripts/run_selective_repeat.py \
  --input examples/payload.bin \
  --data-loss 0.05 \
  --ack-loss 0.05 \
  --seed 7 \
  --port 1002
```

Record at least:

| Parameter | Value to record |
|---|---|
| Python version | `python --version` |
| P4 compiler | `p4c --version` |
| BMv2 | version/commit used |
| Mininet / P4-Utils | installed versions |
| Payload | filename, byte count, SHA-256 |
| SR protocol | window, segment size, timeout, retry limit |
| Link model | delay, bandwidth, link loss |
| Simulated loss | DATA loss, ACK loss, random seed |
| Result | elapsed time, retransmissions, throughput, verified digest |

Application-level loss simulation and Mininet link loss are different experimental mechanisms. Do not combine or compare them without describing the distinction.

## 6. Validation boundary

GitHub Actions tests the Python packet format, sender/receiver transfer over localhost, error handling, CLI behavior, topology command consistency, and Ruff linting on Python 3.10–3.12.

The hosted CI runner does not install or execute BMv2, p4c, Mininet, or P4-Utils. Therefore, a green Python CI result is **not** a claim that the P4 compiler or Mininet integration has passed. Run the commands in sections 2–4 in a configured Linux P4 environment and retain their logs before reporting an end-to-end P4 result.
