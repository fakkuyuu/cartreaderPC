import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from sd_browser_2m import browser_transfer_allowed, browser_progress


class Browser2MTests(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(host_state={"browser_request": {"action": "C", "path": "/a.bin"}},
                                     path=lambda raw: Path(raw.decode()))
        self.entry = {"write": True, "path": Path("/a.bin")}

    def test_exact_and_partial_last_sector(self):
        for tail in (0, 1, 511):
            self.assertTrue(browser_transfer_allowed(self.store, self.entry, 8192, 8192 + tail))

    def test_bad_lengths_and_wrong_handle(self):
        for length, total in ((0, 0), (7680, 7680), (8193, 8193), (8192, 8191), (8192, 8704),
                              (128 * 1024**2 + 512, 128 * 1024**2 + 512)):
            self.assertFalse(browser_transfer_allowed(self.store, self.entry, length, total))
        self.assertFalse(browser_transfer_allowed(self.store, {"write": True, "path": Path("/b.bin")}, 8192, 8192))
        self.assertFalse(browser_transfer_allowed(self.store, {"write": False, "path": Path("/a.bin")}, 8192, 8192))
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


if __name__ == "__main__":
    unittest.main()
