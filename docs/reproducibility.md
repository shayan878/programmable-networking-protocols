# Reproducibility and validation

## P4 compilation

Record the compiler version and target before comparing outputs:

```bash
p4c --version
mkdir -p build
p4c --target bmv2 --arch v1model --std p4-16 \
  -o build/main.json p4src/main.p4
```

The command should produce `build/main.json`. The repository CI does not install `p4c`; P4 compilation is therefore a local/manual check until a pinned compiler/container environment is added.

## BMv2 execution requirements

Compilation alone does not define an experiment. A reproducible execution also needs:

1. A documented BMv2 version and switch launch configuration.
2. A topology (for example, a Mininet topology) with interface and IP/MAC assignments.
3. Control-plane commands that populate `ipv4_lpm`.
4. A traffic generator and exact packet-flow definitions.
5. A counter initialization/reset procedure, or a fresh switch process for each run.
6. Captured logs and traffic parameters (packet sizes, offered load, duration, repetitions, and seed where applicable).

These artifacts are not currently part of this repository. No throughput, loss-rate, latency, or fairness result is reported here.

## Python checks

The launcher and static source-contract tests require Python 3.10+:

```bash
python -m pip install -r requirements-dev.txt
make test
make lint
```

The unit tests check Python launcher behavior and important source-level invariants. They do not substitute for P4 compilation, BMv2 execution, control-plane validation, or network measurements.
