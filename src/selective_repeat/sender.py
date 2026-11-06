"""Selective Repeat sender with independent packet timers and retransmissions."""

from __future__ import annotations

import hashlib
import json
import math
import random
import secrets
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .protocol import (
    MAX_PAYLOAD_SIZE,
    MAX_SEQUENCE,
    PacketType,
    ProtocolError,
    decode_packet,
    encode_packet,
)


class TransferError(RuntimeError):
    """Raised when a file transfer cannot complete reliably."""


@dataclass(frozen=True, slots=True)
class TransferResult:
    file_name: str
    bytes_transferred: int
    segments: int
    data_transmissions: int
    retransmissions: int
    simulated_data_drops: int
    elapsed_seconds: float
    throughput_mbps: float

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receive_control(
    sock: socket.socket,
    session_id: int,
    accepted: set[PacketType],
    deadline: float,
) -> tuple[PacketType, int, bytes] | None:
    """Receive a valid control response from the connected peer before deadline."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        sock.settimeout(remaining)
        try:
            raw = sock.recv(65_507)
        except TimeoutError:
            return None
        except ConnectionRefusedError:
            # A UDP ICMP port-unreachable can arrive while the receiver is
            # starting. Stay within this attempt's deadline so transient startup
            # races do not consume the entire retry budget immediately.
            time.sleep(min(remaining, 0.02))
            continue
        try:
            packet = decode_packet(raw)
        except ProtocolError:
            continue
        if packet.session_id != session_id:
            continue
        if packet.kind == PacketType.ERROR:
            raise TransferError(packet.payload.decode("utf-8", errors="replace"))
        if packet.kind in accepted:
            return packet.kind, packet.sequence, packet.payload


def send_file(
    source_path: str | Path,
    destination: tuple[str, int],
    *,
    window_size: int = 8,
    segment_size: int = 1200,
    timeout: float = 0.25,
    max_retries: int = 20,
    loss_probability: float = 0.0,
    random_seed: int | None = None,
) -> TransferResult:
    """Send a file over UDP using Selective Repeat.

    Sequence numbers are monotonically increasing 32-bit values and do not wrap
    within a transfer. The receiver negotiates the effective window size.
    """
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if window_size < 1:
        raise ValueError("window_size must be at least 1")
    if not 1 <= segment_size <= MAX_PAYLOAD_SIZE:
        raise ValueError(f"segment_size must be in [1, {MAX_PAYLOAD_SIZE}]")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    if not 0.0 <= loss_probability < 1.0:
        raise ValueError("loss_probability must be in [0, 1)")

    total_bytes = source.stat().st_size
    total_segments = math.ceil(total_bytes / segment_size)
    if total_segments > MAX_SEQUENCE:
        raise ValueError("file requires more than 2^32 - 1 segments")

    metadata = {
        "filename": source.name,
        "size": total_bytes,
        "segments": total_segments,
        "segment_size": segment_size,
        "window_size": window_size,
        "sha256": _sha256_file(source),
    }
    start_payload = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
    session_id = secrets.randbits(64)
    rng = random.Random(random_seed)
    started = time.monotonic()
    data_transmissions = 0
    retransmissions = 0
    simulated_drops = 0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # A connected UDP socket resolves hostnames and filters datagrams from
        # unrelated source addresses before protocol/session validation.
        sock.connect(destination)
        start_packet = encode_packet(PacketType.START, session_id, payload=start_payload)
        negotiated_window: int | None = None

        for attempt in range(max_retries + 1):
            sock.send(start_packet)
            response = _receive_control(
                sock,
                session_id,
                {PacketType.READY},
                time.monotonic() + timeout,
            )
            if response is not None:
                try:
                    ready_info = json.loads(response[2].decode("utf-8"))
                    negotiated_window = int(ready_info["window_size"])
                except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
                    raise TransferError("receiver returned an invalid READY message") from exc
                break
            if attempt == max_retries:
                raise TransferError("receiver did not respond to START after all retries")

        if negotiated_window is None or negotiated_window < 1:
            raise TransferError("receiver negotiated an invalid window size")

        base = 0
        next_sequence = 0
        acknowledged: set[int] = set()
        pending: dict[int, dict[str, object]] = {}

        def transmit(packet_bytes: bytes, *, retry: bool) -> None:
            nonlocal data_transmissions, retransmissions, simulated_drops
            data_transmissions += 1
            if retry:
                retransmissions += 1
            if rng.random() < loss_probability:
                simulated_drops += 1
            else:
                sock.send(packet_bytes)

        with source.open("rb") as input_file:
            while base < total_segments:
                while (
                    next_sequence < total_segments
                    and next_sequence < base + negotiated_window
                ):
                    payload = input_file.read(segment_size)
                    packet_bytes = encode_packet(
                        PacketType.DATA, session_id, next_sequence, payload
                    )
                    pending[next_sequence] = {
                        "packet": packet_bytes,
                        "sent_at": time.monotonic(),
                        "retries": 0,
                    }
                    transmit(packet_bytes, retry=False)
                    next_sequence += 1

                if not pending:
                    raise TransferError("sender window stalled with unacknowledged data")

                now = time.monotonic()
                expired = [
                    sequence
                    for sequence, item in pending.items()
                    if now - float(item["sent_at"]) >= timeout
                ]
                for sequence in expired:
                    item = pending[sequence]
                    retries = int(item["retries"])
                    if retries >= max_retries:
                        raise TransferError(
                            f"segment {sequence} exceeded the retry limit ({max_retries})"
                        )
                    packet_bytes = item["packet"]
                    assert isinstance(packet_bytes, bytes)
                    transmit(packet_bytes, retry=True)
                    item["retries"] = retries + 1
                    item["sent_at"] = time.monotonic()

                if expired:
                    continue

                next_deadline = min(
                    float(item["sent_at"]) + timeout for item in pending.values()
                )
                response = _receive_control(
                    sock,
                    session_id,
                    {PacketType.ACK},
                    next_deadline,
                )
                if response is None:
                    continue

                _kind, acknowledged_sequence, _payload = response
                if acknowledged_sequence in pending:
                    del pending[acknowledged_sequence]
                    acknowledged.add(acknowledged_sequence)
                    while base in acknowledged:
                        acknowledged.remove(base)
                        base += 1

        fin_packet = encode_packet(PacketType.FIN, session_id, total_segments)
        for attempt in range(max_retries + 1):
            sock.send(fin_packet)
            response = _receive_control(
                sock,
                session_id,
                {PacketType.FIN_ACK},
                time.monotonic() + timeout,
            )
            if response is not None:
                sock.send(encode_packet(PacketType.CLOSE, session_id, total_segments))
                elapsed = max(time.monotonic() - started, 1e-9)
                return TransferResult(
                    file_name=source.name,
                    bytes_transferred=total_bytes,
                    segments=total_segments,
                    data_transmissions=data_transmissions,
                    retransmissions=retransmissions,
                    simulated_data_drops=simulated_drops,
                    elapsed_seconds=elapsed,
                    throughput_mbps=(total_bytes * 8) / (elapsed * 1_000_000),
                )
            if attempt == max_retries:
                raise TransferError("receiver did not acknowledge FIN after all retries")

    raise TransferError("transfer ended unexpectedly")
