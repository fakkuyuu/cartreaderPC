import unittest
import binascii
import struct
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from sd_browser_2m import browser_transfer_allowed, browser_progress
from gba_retry import receive_dump, N64_HANDOFF_MAGIC
from storage import Storage
from browser_request import TOKEN
from test_2m_boundary import Wire, Event, Clock, frame


class Browser2MTests(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(host_state={"browser_request": {"action": "C", "path": "/a.bin"}},
                                     path=lambda raw: Path(raw.decode()))
        self.entry = {"write": True, "browser_copy": True, "path": Path("/a.bin")}

    def test_exact_and_partial_last_sector(self):
        for length in (8192, 128 * 1024**2, 128 * 1024**2 + 512, 0xfffffe00):
            for tail in (0, 1, 511):
                self.assertTrue(browser_transfer_allowed(self.store, self.entry, length, length + tail))

    def test_bad_lengths_and_wrong_handle(self):
        for length, total in ((0, 0), (7680, 7680), (8193, 8193), (8192, 8191), (8192, 8704),
                              (0x100000000, 0x100000000), (0xfffffe00, 0x100000000)):
            self.assertFalse(browser_transfer_allowed(self.store, self.entry, length, total))
        self.assertFalse(browser_transfer_allowed(self.store, {"write": True, "browser_copy": True, "path": Path("/b.bin")}, 8192, 8192))
        self.assertFalse(browser_transfer_allowed(self.store, {"write": False, "browser_copy": True, "path": Path("/a.bin")}, 8192, 8192))
        self.store.host_state["browser_request"]["action"] = "L"
        self.assertFalse(browser_transfer_allowed(self.store, self.entry, 8192, 8192))

    def test_progress_uses_original_total(self):
        messages = []
        with patch("sd_browser_2m.time.monotonic", side_effect=[2.0, 2.1, 3.2]):
            report = browser_progress(messages.append, 16385)
            report(8192)
            report(12288)
            report(16384)
        self.assertEqual(messages, ["[SD Progress]\t8192\t16385\n", "[SD Progress]\t16384\t16385\n"])


    def test_aligned_prefix_and_ordinary_tail_preserve_file(self):
        data = bytes((i * 13) & 255 for i in range(8193))
        raw = b"".join(frame(i, 0, data[i * 512:(i + 1) * 512]) for i in range(16)) + frame(0, 0)
        handoff = N64_HANDOFF_MAGIC + struct.pack("<H", binascii.crc_hqx(N64_HANDOFF_MAGIC, 0xffff))
        wire = Wire(frame(0xffffffff, 0xff), rounds=[raw, handoff])
        messages = []
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(directory, log=messages.append,
                            host_state={"browser_request": {"action": "C", "path": "/sample.dat"}})
            store.dispatch(1, b"")
            target = Path(directory) / "sample.dat"
            handle = store.dispatch(2, bytes([14]) + TOKEN)[1]
            with patch("gba_retry.time.monotonic", Clock().monotonic), patch("gba_retry.time.sleep", lambda _: None):
                result = receive_dump(wire, store, handle, 8192, messages.append, Event(), None,
                                      block_size=512, window=16, label="SD Browser",
                                      completion_handshake=True,
                                      progress_callback=lambda done: messages.append(f"[SD Progress]\t{done}\t8193\n"))
            self.assertEqual(result[1], 0)
            self.assertEqual(store.dispatch(22, struct.pack("<BI", handle, 8192) + data[-1:]), struct.pack("<BH", 0, 1))
            self.assertEqual(store.dispatch(3, struct.pack("<BBI", handle, 1, len(data))), b"\x00\xb2\x00")
            self.assertEqual(target.read_bytes(), data)
            self.assertIn("[SD Progress]\t8192\t8193\n", messages)
            self.assertNotIn("[", messages)
            self.assertEqual(wire.baudrate, 250000)

    def test_existing_destination_is_never_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "sample.dat"
            target.write_bytes(b"original")
            store = Storage(directory, log=lambda _: None,
                            host_state={"browser_request": {"action": "C", "path": "/sample.dat"}})
            store.dispatch(1, b"")
            self.assertEqual(store.dispatch(2, bytes([14]) + TOKEN), b"\x01")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertFalse(store.handles)

    def test_explicit_abort_late_cancel_and_inexact_close_remove_copy(self):
        for success, cancelled, total, status in ((0, False, 3, 2), (1, True, 3, 1), (1, False, 4, 2)):
            with self.subTest(success=success, cancelled=cancelled, total=total):
                with tempfile.TemporaryDirectory() as directory:
                    event = threading.Event()
                    store = Storage(directory, log=lambda _: None, cancel_event=event,
                                    host_state={"browser_request": {"action": "C", "path": "/sample.dat"}})
                    store.dispatch(1, b"")
                    handle = store.dispatch(2, bytes([14]) + TOKEN)[1]
                    self.assertEqual(store.dispatch(22, struct.pack("<BI", handle, 0) + b"abc"), b"\x00\x03\x00")
                    if cancelled:
                        event.set()
                    self.assertEqual(store.dispatch(3, struct.pack("<BBI", handle, success, total)), bytes((0, 0xb2, status)))
                    self.assertFalse((Path(directory) / "sample.dat").exists())
                    self.assertFalse(store.manifest)

    def test_disconnect_removes_incomplete_browser_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(directory, log=lambda _: None,
                            host_state={"browser_request": {"action": "C", "path": "/sample.dat"}})
            store.dispatch(1, b"")
            handle = store.dispatch(2, bytes([14]) + TOKEN)[1]
            store.dispatch(22, struct.pack("<BI", handle, 0) + b"abc")
            store.shutdown()
            self.assertFalse((Path(directory) / "sample.dat").exists())
            self.assertFalse(store.manifest)


if __name__ == "__main__":
    unittest.main()
