import tempfile
import unittest
from pathlib import Path

from storage import Storage


class N64ClosePhaseTests(unittest.TestCase):
    def test_close_reports_each_finalization_phase_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            messages = []
            store = Storage(directory, log=messages.append)
            target = Path(directory) / "N64" / "ROM" / "PowerLeague64" / "PowerLeague64.z64"
            target.parent.mkdir(parents=True)
            handle = store.allocate(target, flags=2 | 4 | 8)[0]
            payload = bytes(range(256)) * 32
            store.handles[handle]["file"].write(payload)
            store.track_write(store.handles[handle], len(payload))
            response = store.dispatch(3, bytes((handle,)))

            self.assertEqual(response[0], 0)
            self.assertEqual(target.stat().st_size, len(payload))
            self.assertEqual(store.manifest["N64/ROM/PowerLeague64/PowerLeague64.z64"]["state"], "closed")
            trace = "".join(messages)
            phases = (
                "begin handle=", "file flush complete", "file fsync complete",
                "file handle closed", "SHA-256 complete", "manifest marked closed",
                "ROM database verification begin", "ROM database verification complete",
                "companion log complete",
            )
            offsets = [trace.index(phase) for phase in phases]
            self.assertEqual(offsets, sorted(offsets))
            self.assertIn("[SAVED]", trace)
            self.assertIn("[VERIFY] CRC32=", trace)


if __name__ == "__main__":
    unittest.main()
