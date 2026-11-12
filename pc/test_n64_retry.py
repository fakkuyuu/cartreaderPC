import binascii
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from gba_retry import HEADER, MAGIC, receive_dump
from protocol import ProtocolError


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        self.value += 0.5
        return self.value


class FakeEvent:
    def is_set(self):
        return False


class FakeWire:
    def __init__(self):
        self.baudrate = 1_000_000
        self.timeout = 0.125
        self._in_waiting = 0
        self.writes = []

    @property
    def in_waiting(self):
        return self._in_waiting

    def read(self, _count):
        return b""

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        pass


class FakeStore:
    def __init__(self):
        self.calls = []

    def dispatch(self, op, payload):
        self.calls.append((op, payload))
        raise AssertionError("no file data may be written before the 2M ready marker")


def retry_frame(index, round_number, end, payload=b""):
    body = HEADER.pack(index, round_number, int(end)) + payload
    return MAGIC + body + struct.pack("<H", binascii.crc_hqx(body, 0xffff))


class ScriptedWire(FakeWire):
    def __init__(self, marker, round_zero, round_one, provide_handoff=False):
        super().__init__()
        self.baudrate = 250_000
        self.stream = bytearray(marker)
        self.round_zero = round_zero
        self.round_one = round_one
        self.provide_handoff = provide_handoff
        self.handoff_acks = []

    @property
    def in_waiting(self):
        return len(self.stream)

    def read(self, count):
        count = min(count, len(self.stream))
        result = bytes(self.stream[:count])
        del self.stream[:count]
        return result

    def write(self, data):
        self.writes.append(bytes(data))
        if data.startswith(b"N64A"):
            self.handoff_acks.append(bytes(data))
        elif len(data) >= 2 and data[0] == 0xA7:
            if data[1] == 0xFF:
                self.stream.extend(self.round_zero)
            elif data[1] == 0:
                self.stream.extend(self.round_one)
            elif data[1] == 1 and self.provide_handoff:
                marker = b"N64D"
                self.stream.extend(marker + struct.pack(
                    "<H", binascii.crc_hqx(marker, 0xffff)))
        return len(data)


class RecordingStore:
    def __init__(self):
        self.calls = []

    def dispatch(self, op, payload):
        self.calls.append((op, bytes(payload)))
        return struct.pack("<BH", 0, 512)


class N64RetryTests(unittest.TestCase):
    def _run_without_ready_marker(self, *, fallback):
        wire = FakeWire()
        store = FakeStore()
        messages = []
        clock = FakeClock()
        with patch("gba_retry.time.monotonic", clock.monotonic):
            result = receive_dump(
                wire, store, 7, 4096, messages.append, FakeEvent(), None,
                block_size=512, window=16, label="N64",
                fallback_before_payload=fallback,
            )
        self.assertEqual(wire.baudrate, 1_000_000)
        self.assertEqual(wire.timeout, 0.125)
        self.assertEqual(store.calls, [])
        self.assertEqual(wire.writes, [])
        return result, "".join(messages)

    def test_n64_no_ready_marker_returns_to_legacy_transfer(self):
        result, log = self._run_without_ready_marker(fallback=True)
        self.assertIsNone(result)
        self.assertIn("no ROM payload sent", log)

    def test_other_retry_profiles_still_fail_on_missing_ready_marker(self):
        with self.assertRaises(ProtocolError):
            self._run_without_ready_marker(fallback=False)

    def test_selective_retry_restores_missing_frame_and_writes_exact_offsets(self):
        blocks = [bytes([i]) * 512 for i in range(4)]
        round_zero = bytearray()
        # Round 0 deliberately omits block 2 and sends the rest out of order.
        round_zero.extend(retry_frame(3, 0, False, blocks[3]))
        round_zero.extend(retry_frame(1, 0, False, blocks[1]))
        round_zero.extend(retry_frame(0, 0, False, blocks[0]))
        round_zero.extend(retry_frame(0, 0, True))
        # Round 1 returns only the missing block.
        round_one = bytearray(retry_frame(2, 1, False, blocks[2]))
        round_one.extend(retry_frame(0, 1, True))
        wire = ScriptedWire(retry_frame(0xffffffff, 0xff, True), round_zero, round_one)
        store = RecordingStore()
        messages = []
        tick = [0.0]

        def monotonic():
            tick[0] += 0.05
            return tick[0]

        with patch("gba_retry.time.monotonic", monotonic), patch("gba_retry.time.sleep", lambda _s: None):
            elapsed, retransmitted = receive_dump(
                wire, store, 7, 2048, messages.append, FakeEvent(), None,
                block_size=512, window=4, label="N64",
            )

        self.assertEqual(retransmitted, 1)
        self.assertEqual([op for op, _ in store.calls], [22] * 4)
        self.assertEqual([int.from_bytes(p[1:5], "little") for _, p in store.calls],
                         [0, 512, 1024, 1536])
        self.assertEqual([p[5:] for _, p in store.calls], blocks)
        self.assertIn("retransmitted 1 blocks", "".join(messages))
        self.assertGreaterEqual(elapsed, 0)

    def test_n64_final_handoff_is_acknowledged_before_validated(self):
        blocks = [bytes([i]) * 512 for i in range(4)]
        round_zero = bytearray()
        round_zero.extend(retry_frame(3, 0, False, blocks[3]))
        round_zero.extend(retry_frame(1, 0, False, blocks[1]))
        round_zero.extend(retry_frame(0, 0, False, blocks[0]))
        round_zero.extend(retry_frame(0, 0, True))
        round_one = bytearray(retry_frame(2, 1, False, blocks[2]))
        round_one.extend(retry_frame(0, 1, True))
        wire = ScriptedWire(retry_frame(0xffffffff, 0xff, True),
                            round_zero, round_one, provide_handoff=True)
        store = RecordingStore()
        messages = []
        tick = [0.0]

        def monotonic():
            tick[0] += 0.05
            return tick[0]

        with patch("gba_retry.time.monotonic", monotonic), patch("gba_retry.time.sleep", lambda _s: None):
            receive_dump(
                wire, store, 7, 2048, messages.append, FakeEvent(), None,
                block_size=512, window=4, label="N64",
                completion_handshake=True,
            )

        expected_ack = b"N64A" + struct.pack(
            "<H", binascii.crc_hqx(b"N64A", 0xffff))
        self.assertEqual(wire.handoff_acks, [expected_ack])
        self.assertEqual(wire.baudrate, 250_000)
        self.assertIn("Reader handoff marker received", "".join(messages))
        self.assertIn("Validated 2048 bytes", "".join(messages))

    def test_n64_missing_final_handoff_marker_fails_closed(self):
        blocks = [bytes([i]) * 512 for i in range(4)]
        round_zero = bytearray()
        round_zero.extend(retry_frame(0, 0, False, blocks[0]))
        round_zero.extend(retry_frame(1, 0, False, blocks[1]))
        round_zero.extend(retry_frame(3, 0, False, blocks[3]))
        round_zero.extend(retry_frame(0, 0, True))
        round_one = bytearray(retry_frame(2, 1, False, blocks[2]))
        round_one.extend(retry_frame(0, 1, True))
        wire = ScriptedWire(retry_frame(0xffffffff, 0xff, True),
                            round_zero, round_one, provide_handoff=False)
        store = RecordingStore()
        messages = []
        tick = [0.0]

        def monotonic():
            tick[0] += 0.05
            return tick[0]

        with patch("gba_retry.time.monotonic", monotonic), patch("gba_retry.time.sleep", lambda _s: None):
            with self.assertRaisesRegex(ProtocolError, "final N64 2M handoff marker"):
                receive_dump(
                    wire, store, 7, 2048, messages.append, FakeEvent(), None,
                    block_size=512, window=4, label="N64",
                    completion_handshake=True,
                )
        log = "".join(messages)
        self.assertIn("Failed while waiting for final N64 2M handoff marker", log)
        self.assertNotIn("Validated 2048 bytes", log)
        self.assertEqual(wire.handoff_acks, [])

    def test_invalid_n64_handoff_marker_reports_received_bytes(self):
        wire = ScriptedWire(bytes.fromhex("43 52 50 43 01 0d"), b"", b"")
        from gba_retry import complete_n64_handoff
        with self.assertRaisesRegex(
                ProtocolError, r"bytes=43 52 50 43 01 0d"):
            complete_n64_handoff(wire, FakeEvent(), None)

    def test_firmware_callback_restores_absolute_offset_and_z64_byte_order(self):
        source = (Path(__file__).resolve().parents[1] / "Cart_Reader" / "N64.ino").read_text(encoding="utf-8")
        self.assertIn("setAddress_N64(romBase + byteOffset);", source)
        callback = source.split("static void readN64RetryWord(uint8_t* output)", 1)[1].split("}", 1)[0]
        self.assertLess(callback.index("output[0] = PINK"), callback.index("output[1] = PINF"))
        self.assertIn("n64PcRetryKnownCart && !n64SpecialDeviceMode", source)
        progress = source.split("static void n64RetryProgress(uint32_t completedBytes)", 1)[1].split("}", 1)[0]
        self.assertIn("draw_progressbar(completedBytes, totalBytes, false);", progress)
        self.assertIn("blinkLEDLocal();", progress)
        self.assertNotIn("blinkLED();", progress)
        reader = (Path(__file__).resolve().parents[1] / "Cart_Reader" / "Cart_Reader.ino").read_text(encoding="utf-8")
        self.assertIn("void draw_progressbar(uint32_t processed, uint32_t total, bool reportToPc)", reader)
        self.assertIn("static void updateProgressDisplayLocal()", reader)
        self.assertIn("void blinkLEDLocal()", reader)
        local_blink = reader.rsplit("void blinkLEDLocal()", 1)[1].split("}", 1)[0]
        self.assertNotIn("PcLink::activityBlinking()", local_blink)
        storage = (Path(__file__).resolve().parents[1] / "Cart_Reader" / "PcStorage.cpp").read_text(encoding="utf-8")
        self.assertIn("if (mode == PcLink::RETRY_PROFILE_N64) gbaN64Handoff();", storage)
        self.assertIn("static void gbaN64Handoff()", storage)
        self.assertIn("const uint8_t marker[] = {'N', '6', '4', 'D'};", storage)


if __name__ == "__main__":
    unittest.main()
