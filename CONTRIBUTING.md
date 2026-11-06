# Contributing

Thanks for considering a contribution.

## Scope

Keep the two artifacts distinct:

- P4 data-plane changes belong in `p4src/`.
- Selective Repeat orchestration belongs in `scripts/`.
- Architecture, assumptions, and experiment procedures belong in `docs/`.

Do not add performance claims without reproducible measurements and the exact environment used to obtain them. Do not describe the launcher as a full Selective Repeat implementation unless the endpoint protocol code and tests are included.

## Development setup

Use Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
make test
make lint
```

## Pull requests

Please include:

- A concise description of the problem and change.
- Tests or a clear explanation of how the change was validated.
- Compiler and target versions for P4 changes.
- Updated documentation for changed packet-processing behavior, parameters, or limitations.

Keep changes focused and avoid committing generated BMv2 JSON, build output, packet captures, or local environment files.
