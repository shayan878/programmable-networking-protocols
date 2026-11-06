# Programmable Data Plane and Reliable Transport

A small networking coursework repository containing two related but independent artifacts:

1. **P4 / BMv2 data plane** — an IPv4 forwarding pipeline with a two-hash, register-based approximate flow counter and threshold-based packet dropping.
2. **Selective Repeat process launcher** — a Python utility that starts an external receiver and sender pair. The receiver and sender implementations are **not included** in this repository.

The repository is explicit about what is implemented and what still needs an environment or additional source files. It does not currently contain a Mininet topology, a P4Runtime controller, complete Selective Repeat endpoints, or measured performance results.

## Repository layout

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── architecture.md
│   ├── reproducibility.md
│   └── selective-repeat.md
├── p4src/
│   └── main.p4
├── scripts/
│   └── run_selective_repeat.py
├── tests/
│   ├── test_p4_source.py
│   └── test_selective_repeat_runner.py
├── .gitignore
├── CONTRIBUTING.md
├── Makefile
├── pyproject.toml
└── requirements-dev.txt
```

## 1. P4 data plane

The P4 program targets the **BMv2 v1model architecture** and is written in P4_16. Its pipeline:

- Parses Ethernet, IPv4, and TCP headers.
- Verifies the IPv4 header checksum.
- For IPv4/TCP packets, hashes the source IPv4 address, destination IPv4 address, and TCP destination port into two register indices.
- Increments the two counters and drops the packet when both counters exceed the configured threshold.
- Applies an IPv4 longest-prefix-match table for forwarding.
- Recomputes the IPv4 header checksum after processing.

The two-register structure is an approximate frequency counter (count-min-style); it is **not a conventional Bloom filter**. The flow key is the three-field tuple described above, not the full TCP five-tuple.

### Build

Install a P4_16 compiler with the BMv2 backend (commonly `p4c`) and run:

```bash
make p4-compile
```

Or compile directly:

```bash
mkdir -p build
p4c --target bmv2 --arch v1model --std p4-16 \
  -o build/main.json p4src/main.p4
```

This produces a BMv2 JSON pipeline artifact. It does **not** start a switch or install forwarding entries.

## 2. Selective Repeat launcher

The launcher starts these two external scripts, in this order:

- `receive.py` — expected at the repository root by default; it should start the receiver.
- `send.py` — expected at the repository root by default; it receives the destination host and port as positional arguments.

Those endpoint scripts are not currently tracked here. The launcher reports the missing files rather than pretending that a simulation can run.

Once the endpoint implementations are available:

```bash
python scripts/run_selective_repeat.py \
  --receiver-script receive.py \
  --sender-script send.py \
  --host 10.0.2.2 \
  --port 1002
```

See [the launcher contract](docs/selective-repeat.md) before integrating endpoint implementations.

## Development

Python 3.10 or newer is required for the launcher and tests. The launcher uses only the Python standard library.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
make test
make lint
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

## Validation scope

GitHub Actions runs Python unit tests and Ruff linting on Python 3.10, 3.11, and 3.12. These checks validate the launcher and repository-level source contracts; they do not compile P4 or execute BMv2.

A real data-plane experiment additionally requires a compatible `p4c` compiler, BMv2, a configured topology, runtime table entries, and documented traffic-generation parameters. See [reproducibility notes](docs/reproducibility.md).

## Known limitations

- No Mininet topology, P4Runtime controller, or table-entry script is included.
- The IPv4 LPM table has a `NoAction` default; forwarding behavior depends on installing appropriate entries.
- The counter key omits the TCP source port and protocol number. It therefore aggregates packets by source IPv4, destination IPv4, and destination TCP port.
- The register counters are 32-bit and are not reset by this program. Counter wraparound and target-specific register read/write atomicity should be considered before interpreting results.
- The pipeline drops packets after the counter threshold is crossed; it does not generate ICMP errors.
- The Selective Repeat sender and receiver implementations are external and absent from this repository.
- No throughput, loss, latency, or fairness results are claimed by the current source tree.

## License

No license has been selected for this repository yet. Until one is added, the source should not be assumed to grant general reuse or redistribution rights.
