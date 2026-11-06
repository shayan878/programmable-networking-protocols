# Selective Repeat launcher contract

The repository contains a launcher, not the Selective Repeat ARQ protocol endpoints.

## Expected endpoint interface

The launcher defaults to these paths:

| Script | Invocation | Expected responsibility |
|---|---|---|
| `receive.py` | `python receive.py` | Bind/listen and receive the data stream |
| `send.py` | `python send.py HOST PORT` | Connect/send to the receiver |

Both scripts must be supplied separately. The launcher checks that both files exist before it starts either process. It uses the active Python interpreter, passes arguments as an argument vector (no shell), waits for both processes, and terminates remaining children on interruption or failure.

## Run with supplied endpoints

```bash
python scripts/run_selective_repeat.py \
  --receiver-script ./receive.py \
  --sender-script ./send.py \
  --host 10.0.2.2 \
  --port 1002
```

The receiver is started first so it can initialize before the sender connects. This does not provide a formal readiness handshake; the receiver implementation should bind/listen promptly or implement its own readiness mechanism.

## What is not provided

The source tree does not define packet formats, sequence-number width, sender/receiver windows, timeout policy, ACK/NACK behavior, retransmission buffering, or a network fault model. Those choices belong to the missing endpoint implementations and cannot be inferred from the launcher. Consequently, this repository does not currently claim a complete or tested Selective Repeat implementation.
