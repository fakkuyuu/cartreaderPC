"""Regression tests for CRC16-valid 2M frames with a broken byte boundary.

Synthetic 512-byte data reproduces the exact failure class observed at
GBA ROM block 0x016C4C00: a dropped payload byte makes the low CRC byte
become payload and makes the high CRC byte plus the next frame's 'G'
look like a valid CRC16. No copyrighted ROM data is included.
"""
import binascii
import struct
import unittest
from unittest.mock import patch

from gba_retry import HEADER, MAGIC, receive_dump, receive_window
from protocol import ProtocolError


BLOCK = 0x016C4C00 // 512
DROP_OFFSET = 379


def frame(index, round_number, payload=None):
    body = HEADER.pack(index, round_number, int(payload is None))
    if payload is not None:
        body += payload
    return MAGIC + body + struct.pack("<H", binascii.crc_hqx(body, 0xffff))


def collision_payload(index=BLOCK):
    payload = bytearray((37 * i + 13) & 255 for i in range(512))
    # Both indexes give CRC16 0x6176, and the 1-byte-loss CRC 0x4761.
    payload[:2] = {BLOCK: b"\x45\x51", 0: b"\x1e\x03"}[index]
    return bytes(payload)


def damaged_frame(index=BLOCK):
    original = frame(index, 0, collision_payload(index))
    assert original[-2:] == b"\x76\x61"
    # One payload byte is missing, including when the CRC16 happens to match.
    return original[:10 + DROP_OFFSET] + original[11 + DROP_OFFSET:]


class Event:
    def is_set(self):
        return False


class Clock:
    def __init__(self):
        self.value = 0

    def monotonic(self):
        self.value += 0.001
        return self.value


class Wire:
    def __init__(self, initial=b"", rounds=()):
        self.buffer = bytearray(initial)
        self.rounds = list(rounds)
        self.baudrate = 250000
        self.timeout = 0.125
        self.writes = []

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, size):
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def write(self, payload):
        self.writes.append(bytes(payload))
        if payload[:1] == b"\xa7" and payload[1] == 0xff:
            if self.rounds:
                self.buffer.extend(self.rounds.pop(0))
        elif payload[:1] == b"\xa7" and self.rounds:
            self.buffer.extend(self.rounds.pop(0))
        return len(payload)

    def flush(self):
        pass


class Store:
    def __init__(self):
        self.contents = {}

    def dispatch(self, op, payload):
        assert op == 22
        index = int.from_bytes(payload[1:5], "little")
        self.contents[index] = payload[5:]
        return struct.pack("<BH", 0, len(payload) - 5)


class BoundaryTests(unittest.TestCase):
    def read_round(self, raw, first=BLOCK, count=1, block_size=512):
        wire = Wire(raw)
        blocks = {}
        with patch("gba_retry.time.monotonic", Clock().monotonic):
            _, ended = receive_window(
                wire, first, count, 0, blocks, Event(), None, block_size)
        return blocks, ended

    def test_exact_dropped_byte_collision_must_not_be_accepted(self):
        bad = damaged_frame()
        # The packet CRC still passes if the next marker's first byte is
        # treated as the high checksum byte: 0x61 0x47 -> 0x4761.
        forged = bad + frame(BLOCK, 0)
        checksum = binascii.crc_hqx(forged[4:4 + HEADER.size + 512], 0xffff)
        observed = int.from_bytes(forged[4 + HEADER.size + 512:
                                         4 + HEADER.size + 514], "little")
        self.assertEqual(checksum, 0x4761)
        self.assertEqual(checksum, observed)
        blocks, ended = self.read_round(forged)
        self.assertNotIn(BLOCK, blocks)
        # The complete end marker is still on the wire; resync may find it.
        self.assertTrue(ended)

    def test_corrupted_middle_frame_does_not_poison_other_blocks(self):
        final_payload = bytes([0x5a]) * 512
        raw = (damaged_frame() +
               frame(BLOCK + 1, 0, bytes([0x21]) * 512) +
               frame(BLOCK + 2, 0, final_payload) +
               frame(BLOCK, 0))
        blocks, ended = self.read_round(raw, count=3)
        self.assertTrue(ended)
        # Reject only the corrupt block; valid later frames can be rescued.
        self.assertEqual(blocks, {
            BLOCK + 1: bytes([0x21]) * 512,
            BLOCK + 2: final_payload,
        })

    def test_valid_magic_inside_payload_never_triggers_false_boundary(self):
        for size in (256, 512, 1024):
            with self.subTest(size=size):
                payload = bytearray((i * 17) & 255 for i in range(size))
                payload[3:7] = MAGIC
                payload[size // 2:size // 2 + 4] = MAGIC
                payload[-4:] = MAGIC
                blocks, ended = self.read_round(
                    frame(BLOCK, 0, bytes(payload)) + frame(BLOCK, 0),
                    block_size=size)
                self.assertTrue(ended)
                self.assertEqual(blocks[BLOCK], bytes(payload))

    def test_last_data_frame_requires_valid_end_marker(self):
        good = frame(BLOCK, 0, collision_payload())
        bad_end = bytearray(frame(BLOCK, 0))
        bad_end[-1] ^= 1
        blocks, ended = self.read_round(good + bad_end)
        self.assertFalse(ended)
        self.assertNotIn(BLOCK, blocks)

    def test_missing_end_marker_does_not_commit_last_frame(self):
        blocks, ended = self.read_round(frame(BLOCK, 0, collision_payload()))
        self.assertFalse(ended)
        self.assertNotIn(BLOCK, blocks)

    def run_transfer(self, rounds, store=None):
        wire = Wire(frame(0xffffffff, 0xff), rounds=rounds)
        if store is None:
            store = Store()
        log = []
        with patch("gba_retry.time.monotonic", Clock().monotonic), patch(
                "gba_retry.time.sleep", lambda _: None):
            result = receive_dump(
                wire, store, 1, 512, log.append, Event(), None,
                block_size=512, window=1, label="GBA")
        return wire, store, result, "".join(log)

    def test_selective_retry_repairs_crc16_valid_dropped_byte(self):
        bad_round = damaged_frame(0) + frame(0, 0)
        good_round = frame(0, 1, collision_payload(0)) + frame(0, 1)
        # Real CRC16 collision in round zero must trigger a selective
        # retransmit rather than persist the shifted bytes to the ROM.
        wire, store, result, log = self.run_transfer([bad_round, good_round])
        self.assertEqual(result[1], 1)
        self.assertEqual(store.contents, {0: collision_payload(0)})
        self.assertIn("retransmitted 1 blocks", log)

    def test_retry_limit_fails_closed_without_saving_rom(self):
        rounds = [frame(0, n, bytes([0x42]) * 512) for n in range(10)]
        store = Store()
        with self.assertRaisesRegex(ProtocolError, "retry limit"):
            self.run_transfer(rounds, store=store)
        self.assertEqual(store.contents, {})


if __name__ == "__main__":
    unittest.main()
