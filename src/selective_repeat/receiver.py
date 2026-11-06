"""Selective Repeat receiver with out-of-order buffering and atomic file output."""

from __future__ import annotations

import hashlib
import json
import os
import random
import socket
import tempfile
import time
from pathlib import Path

from .protocol import PacketType, ProtocolError, decode_packet, encode_packet
from .sender import TransferError


def _send_packet(
    sock: socket.socket,
    peer: tuple[str, int],
    kind: PacketType,
    session_id: int,
    sequence: int = 0,
    payload: bytes = b"",
) -> None:
    sock.sendto(encode_packet(kind, session_id, sequence, payload), peer)


def _parse_start(payload: bytes, receiver_window: int) -> dict[str, int | str]:
    try:
        metadata = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransferError("START metadata is not valid UTF-8 JSON") from exc
    if not isinstance(metadata, dict):
        raise TransferError("START metadata must be a JSON object")

    filename = metadata.get("filename")
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise TransferError("START contains an unsafe output filename")

    try:
        total_bytes = int(metadata["size"])
        total_segments = int(metadata["segments"])
        segment_size = int(metadata["segment_size"])
        sender_window = int(metadata["window_size"])
        digest = str(metadata["sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TransferError("START metadata is missing required numeric fields") from exc

    if total_bytes < 0 or total_segments < 0 or segment_size < 1:
        raise TransferError("START metadata contains negative or zero dimensions")
    expected_segments = (total_bytes + segment_size - 1) // segment_size
    if total_segments != expected_segments:
        raise TransferError("START segment count is inconsistent with file size")
    if sender_window < 1 or len(digest) != 64:
        raise TransferError("START metadata contains an invalid window or SHA-256")
    if any(character not in "0123456789abcdef" for character in digest.lower()):
        raise TransferError("START SHA-256 is malformed")

    return {
        "filename": filename,
        "size": total_bytes,
        "segments": total_segments,
        "segment_size": segment_size,
        "window_size": min(receiver_window, sender_window),
        "sha256": digest.lower(),
    }


def receive_file(
    sock: socket.socket,
    output_directory: str | Path,
    *,
    window_size: int = 8,
    ack_loss_probability: float = 0.0,
    random_seed: int | None = None,
    idle_timeout: float | None = None,
    fin_linger: float = 10.0,
) -> Path:
    """Receive one file on an already-bound UDP socket and return its final path.

    After FIN_ACK, the receiver waits briefly for CLOSE and answers duplicate FIN
    packets during this interval. This protects a sender from a lost final ACK.
    """
    if window_size < 1:
        raise ValueError("window_size must be at least 1")
    if not 0.0 <= ack_loss_probability < 1.0:
        raise ValueError("ack_loss_probability must be in [0, 1)")
    if idle_timeout is not None and idle_timeout <= 0:
        raise ValueError("idle_timeout must be positive")
    if fin_linger <= 0:
        raise ValueError("fin_linger must be positive")

    output_dir = Path(output_directory).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(random_seed)
    if idle_timeout is not None:
        sock.settimeout(idle_timeout)

    session_id: int | None = None
    peer: tuple[str, int] | None = None
    transfer: dict[str, int | str] | None = None
    ready_payload = b""
    while session_id is None:
        raw, remote = sock.recvfrom(65_507)
        try:
            packet = decode_packet(raw)
        except ProtocolError:
            continue
        if packet.kind != PacketType.START:
            continue
        try:
            transfer = _parse_start(packet.payload, window_size)
        except TransferError as exc:
            _send_packet(
                sock, remote, PacketType.ERROR, packet.session_id, payload=str(exc).encode()
            )
            continue
        session_id = packet.session_id
        peer = remote
        ready_payload = json.dumps(
            {"window_size": transfer["window_size"]}, separators=(",", ":")
        ).encode("utf-8")
        break

    assert session_id is not None and peer is not None and transfer is not None
    filename = str(transfer["filename"])
    final_path = output_dir / filename
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{filename}.", suffix=".part", dir=output_dir
    )
    temporary_path = Path(temporary_name)
    output_file = os.fdopen(file_descriptor, "wb")
    committed = False
    total_segments = int(transfer["segments"])
    total_bytes = int(transfer["size"])
    segment_size = int(transfer["segment_size"])
    accepted_window = int(transfer["window_size"])
    expected_digest = str(transfer["sha256"])
    base = 0
    buffered: dict[int, bytes] = {}
    bytes_written = 0
    digest = hashlib.sha256()

    try:
        _send_packet(sock, peer, PacketType.READY, session_id, payload=ready_payload)
        while True:
            raw, remote = sock.recvfrom(65_507)
            if remote != peer:
                continue
            try:
                packet = decode_packet(raw)
            except ProtocolError:
                continue
            if packet.session_id != session_id:
                continue

            if packet.kind == PacketType.START:
                _send_packet(sock, peer, PacketType.READY, session_id, payload=ready_payload)
                continue

            if packet.kind == PacketType.DATA:
                sequence = packet.sequence
                if sequence < base:
                    _send_packet(sock, peer, PacketType.ACK, session_id, sequence)
                    continue
                if sequence >= total_segments or sequence >= base + accepted_window:
                    continue

                expected_length = min(segment_size, total_bytes - sequence * segment_size)
                if len(packet.payload) != expected_length:
                    message = f"segment {sequence} has an invalid payload length"
                    _send_packet(
                        sock, peer, PacketType.ERROR, session_id, sequence, message.encode()
                    )
                    raise TransferError(message)

                buffered.setdefault(sequence, packet.payload)
                if rng.random() >= ack_loss_probability:
                    _send_packet(sock, peer, PacketType.ACK, session_id, sequence)

                while base in buffered:
                    payload = buffered.pop(base)
                    output_file.write(payload)
                    digest.update(payload)
                    bytes_written += len(payload)
                    base += 1
                continue

            if packet.kind == PacketType.FIN:
                if packet.sequence != total_segments or base != total_segments:
                    continue
                output_file.flush()
                os.fsync(output_file.fileno())
                if bytes_written != total_bytes or digest.hexdigest() != expected_digest:
                    message = "received file failed size or SHA-256 verification"
                    _send_packet(
                        sock, peer, PacketType.ERROR, session_id, total_segments, message.encode()
                    )
                    raise TransferError(message)

                output_file.close()
                os.replace(temporary_path, final_path)
                committed = True
                _send_packet(sock, peer, PacketType.FIN_ACK, session_id, total_segments)

                deadline = time.monotonic() + fin_linger
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return final_path
                    sock.settimeout(remaining)
                    try:
                        final_raw, final_peer = sock.recvfrom(65_507)
                    except TimeoutError:
                        return final_path
                    if final_peer != peer:
                        continue
                    try:
                        final_packet = decode_packet(final_raw)
                    except ProtocolError:
                        continue
                    if final_packet.session_id != session_id:
                        continue
                    if (
                        final_packet.kind == PacketType.CLOSE
                        and final_packet.sequence == total_segments
                    ):
                        return final_path
                    if (
                        final_packet.kind == PacketType.FIN
                        and final_packet.sequence == total_segments
                    ):
                        _send_packet(
                            sock, peer, PacketType.FIN_ACK, session_id, total_segments
                        )
    finally:
        if not output_file.closed:
            output_file.close()
        if not committed:
            temporary_path.unlink(missing_ok=True)
