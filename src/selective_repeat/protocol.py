"""Wire format and validation for the Selective Repeat UDP protocol."""

from __future__ import annotations

import enum
import struct
import zlib
from dataclasses import dataclass

MAGIC = b"SRAR"
VERSION = 1
HEADER = struct.Struct("!4sBBQII")
CHECKSUM = struct.Struct("!I")
MAX_UDP_DATAGRAM_SIZE = 65_507
MAX_PAYLOAD_SIZE = MAX_UDP_DATAGRAM_SIZE - HEADER.size - CHECKSUM.size
MAX_SEQUENCE = (1 << 32) - 1


class PacketType(enum.IntEnum):
    START = 1
    READY = 2
    DATA = 3
    ACK = 4
    FIN = 5
    FIN_ACK = 6
    ERROR = 7
    CLOSE = 8


class ProtocolError(ValueError):
    """Raised when a received datagram is malformed or fails integrity checks."""


@dataclass(frozen=True, slots=True)
class Packet:
    kind: PacketType
    session_id: int
    sequence: int
    payload: bytes


def encode_packet(
    kind: PacketType,
    session_id: int,
    sequence: int = 0,
    payload: bytes = b"",
) -> bytes:
    """Encode a packet and append a CRC-32 integrity check."""
    if not 0 <= session_id < (1 << 64):
        raise ValueError("session_id must fit in an unsigned 64-bit integer")
    if not 0 <= sequence <= MAX_SEQUENCE:
        raise ValueError("sequence must fit in an unsigned 32-bit integer")
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError(f"payload exceeds UDP datagram limit ({MAX_PAYLOAD_SIZE} bytes)")

    header = HEADER.pack(MAGIC, VERSION, int(kind), session_id, sequence, len(payload))
    body = header + payload
    return body + CHECKSUM.pack(zlib.crc32(body) & 0xFFFFFFFF)


def decode_packet(datagram: bytes) -> Packet:
    """Decode a datagram, rejecting unsupported, truncated, or corrupt packets."""
    if len(datagram) < HEADER.size + CHECKSUM.size:
        raise ProtocolError("datagram is shorter than the protocol header")

    magic, version, raw_kind, session_id, sequence, payload_length = HEADER.unpack_from(
        datagram
    )
    if magic != MAGIC:
        raise ProtocolError("invalid protocol magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version: {version}")

    expected_length = HEADER.size + payload_length + CHECKSUM.size
    if len(datagram) != expected_length:
        raise ProtocolError("payload length does not match datagram length")

    body = datagram[:-CHECKSUM.size]
    received_checksum = CHECKSUM.unpack_from(datagram, len(body))[0]
    calculated_checksum = zlib.crc32(body) & 0xFFFFFFFF
    if received_checksum != calculated_checksum:
        raise ProtocolError("CRC-32 checksum mismatch")

    try:
        kind = PacketType(raw_kind)
    except ValueError as exc:
        raise ProtocolError(f"unknown packet type: {raw_kind}") from exc

    payload = datagram[HEADER.size:-CHECKSUM.size]
    return Packet(kind, session_id, sequence, payload)
