import unittest
from unittest.mock import patch

from gba_retry import receive_dump
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
        self.in_waiting = 0
        self.writes = []

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


class N64RetryNegotiationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
