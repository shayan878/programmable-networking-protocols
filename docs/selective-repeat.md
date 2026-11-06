# Selective Repeat ARQ over UDP

## Design

The Python implementation provides a simple application-layer reliable file transfer using the Selective Repeat sliding-window protocol.

### Sender

1. Sends a `START` datagram containing file metadata, including size, segment size, requested window, filename, and SHA-256 digest.
2. Retries the START handshake until the receiver responds with `READY` or the retry limit is reached.
3. Transmits up to the negotiated window of DATA segments.
4. Tracks an independent send timestamp and retry count for every unacknowledged segment.
5. Retransmits only a segment whose own timer expires.
6. Slides the sending window as individual acknowledgements arrive.
7. Sends `FIN` after every data segment has been acknowledged and retries until `FIN_ACK` is received.
8. Sends `CLOSE` after receiving FIN_ACK so the receiver can release its socket promptly.

### Receiver

1. Validates START metadata and negotiates a window no larger than its configured receive window.
2. Buffers in-window segments that arrive out of order.
3. Acknowledges each accepted segment independently.
4. Writes buffered payloads to a temporary file only when all preceding segments are present.
5. On FIN, verifies the final byte count and SHA-256 digest.
6. Atomically renames the temporary file into the output directory and sends FIN_ACK.
7. Answers duplicate FIN datagrams during a short linger interval, then closes on CLOSE or when the interval expires.

An old duplicate segment is acknowledged again so a lost ACK can be recovered. Segments beyond the current receive window are ignored and will be retransmitted by the sender if still needed.

## Wire format

Each UDP datagram contains a fixed header, a payload, and a CRC-32 trailer.

| Field | Size | Meaning |
|---|---:|---|
| Magic | 4 bytes | Identifies this protocol (`SRAR`) |
| Version | 1 byte | Protocol version (currently 1) |
| Type | 1 byte | START, READY, DATA, ACK, FIN, FIN_ACK, ERROR, or CLOSE |
| Session ID | 8 bytes | Random transfer identifier |
| Sequence | 4 bytes | Monotonic segment index |
| Payload length | 4 bytes | Exact payload byte count |
| Payload | Variable | JSON metadata or segment bytes |
| CRC-32 | 4 bytes | Integrity check over header and payload |

Sequence numbers are 32-bit unsigned integers that do not wrap inside one file transfer. This avoids old-ACK ambiguity at the cost of a maximum of (2^{32}-1) data segments per transfer. The segment size is capped so that a single datagram remains within the UDP payload limit.

## Running

Install the local package with `python -m pip install -e .`.

Start the receiver:

```bash
python scripts/sr_receiver.py --bind 0.0.0.0 --port 1002 --output-dir received
```

Send a file from another terminal:

```bash
python scripts/sr_sender.py \
  --input path/to/file.bin \
  --host RECEIVER_IP \
  --port 1002 \
  --window-size 8 \
  --segment-size 1200 \
  --timeout 0.25 \
  --max-retries 20
```

The `scripts/run_selective_repeat.py` helper launches both endpoints locally. Its `--data-loss` and `--ack-loss` options simulate sender-side DATA loss and receiver-side ACK loss, respectively, using seeded pseudorandom generators.

## Parameters and constraints

- `window-size`: positive sender window; receiver negotiates the smaller configured value.
- `segment-size`: payload bytes per DATA segment; default 1,200 to avoid common Ethernet MTU fragmentation.
- `timeout`: retransmission timeout in seconds, applied independently to each outstanding segment.
- `max-retries`: maximum retransmissions for each data segment and control handshake phase.
- `data-loss` / `ack-loss`: optional simulated loss probabilities in ([0,1)).

The receiver processes one transfer at a time. The output filename is taken from the START metadata and is restricted to a single path component. If a file with the same name already exists, it is replaced only after size and digest verification succeeds.

## Validation

The automated suite covers wire-format round trips, corrupted/truncated packet rejection, empty files, and a localhost transfer with both DATA and ACK loss. It does not validate performance on a physical network or across arbitrary NAT/firewall configurations.

## Security considerations

CRC-32 detects accidental corruption but is not a cryptographic message authentication code. A random session ID is not authentication. SHA-256 verifies the received content against metadata supplied by the sender, not against a trusted signature. Do not run the receiver as a public file-upload service without authentication, resource limits, transfer quotas, and filesystem isolation.
