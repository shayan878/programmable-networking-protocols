# Contributing

Thank you for considering a contribution.

## Project boundaries

- P4 data-plane behavior belongs in `p4src/`.
- BMv2 / Mininet topology and table programming belong in `topology/`.
- Selective Repeat protocol logic belongs in `src/selective_repeat/`.
- Command-line entry points belong in `scripts/`.
- Protocol, architecture, and experiment assumptions belong in `docs/`.

## Development setup

Use Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
make test
make lint
```

## Pull request expectations

- Include focused unit or integration tests for Python changes.
- Include compiler version and target details for P4 changes.
- Update documentation when packet formats, protocol semantics, topology settings, or defaults change.
- Keep experiments reproducible: record payload digest, parameters, random seeds, and relevant tool versions.
- Do not report BMv2/Mininet validation unless those tools were actually used.
- Do not commit generated BMv2 JSON, received files, packet captures, logs, or virtual-environment directories.

## Protocol changes

The Selective Repeat protocol has versioned datagrams. A wire-format change should update the protocol version and its tests. Preserve independent per-segment retransmission; retransmitting every outstanding segment would change the protocol into Go-Back-N behavior.
