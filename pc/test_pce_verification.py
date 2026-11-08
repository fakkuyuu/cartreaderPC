import tempfile
import unittest
import zlib
from pathlib import Path
from storage import Storage
from dump_result import DumpResult
from batch_dump import BatchDump

class PceVerificationTests(unittest.TestCase):
    def check_rom(self, extension, payload, database=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / ("game" + extension)
            path.write_bytes(payload)
            if database:
                (root / "pce.txt").write_text("game.pce\n" + f"{zlib.crc32(payload):08X}" + "\n", encoding="utf-8")
            logs = []
            storage = Storage(root, logs.append)
            code = storage.verify_rom(path)
            result = DumpResult()
            result.feed("[+] Read ROM")
            result.feed(f"[SAVED] game{extension} ({len(payload)} bytes) SHA256=abcd")
            result.feed(storage.last_verification)
            result.feed("Press Button...")
            return code, storage.last_verification, result.state

    def test_empty_slot_red(self):
        code, log, state = self.check_rom(".pce", b"\xff" * 16384)
        self.assertIn("CRC32=690B37D3", log)
        self.assertIn("PCE-CHECK=MISMATCH", log)
        self.assertEqual((code, state), (3, "failure"))

    def test_nonuniform_unknown_red(self):
        self.assertEqual(self.check_rom(".pce", bytes(range(256)) * 64)[2], "failure")

    def test_known_pce_green(self):
        code, log, state = self.check_rom(".pce", bytes(range(256)) * 64, True)
        self.assertIn("PCE-CHECK=OK", log)
        self.assertEqual((code, state), (1, "success"))

    def test_other_console_db_miss_is_failure(self):
        self.assertEqual(self.check_rom(".gb", bytes(range(256)) * 64)[::2], (3, "failure"))

    def test_batch_stops_on_pce_miss(self):
        batch = BatchDump()
        batch.begin("PCE_SWAP")
        batch.on_line("[VERIFY] CRC32=5EC9EF40  PCE-CHECK=MISMATCH  DB=no match")
        self.assertFalse(batch.active)
        self.assertFalse(batch.save_failure_after_rom)

if __name__ == "__main__":
    unittest.main()
