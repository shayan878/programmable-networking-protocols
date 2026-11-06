import unittest

from selective_repeat.protocol import PacketType, ProtocolError, decode_packet, encode_packet


class ProtocolTests(unittest.TestCase):
    def test_round_trip_preserves_packet_fields(self) -> None:
        original = encode_packet(PacketType.DATA, 123456, 42, b"payload")
        decoded = decode_packet(original)
        self.assertEqual(decoded.kind, PacketType.DATA)
        self.assertEqual(decoded.session_id, 123456)
        self.assertEqual(decoded.sequence, 42)
        self.assertEqual(decoded.payload, b"payload")

    def test_close_packet_round_trip(self) -> None:
        decoded = decode_packet(encode_packet(PacketType.CLOSE, 123, 9))
        self.assertEqual(decoded.kind, PacketType.CLOSE)
        self.assertEqual(decoded.sequence, 9)

    def test_corrupt_packet_is_rejected(self) -> None:
        original = bytearray(encode_packet(PacketType.ACK, 10, 3))
        original[-1] ^= 0xFF
        with self.assertRaises(ProtocolError):
            decode_packet(bytes(original))

    def test_truncated_packet_is_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_packet(b"short")


if __name__ == "__main__":
    unittest.main()
