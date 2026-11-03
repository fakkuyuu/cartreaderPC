import ast
import unittest
from dump_result import DumpResult


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.r = DumpResult()

    def feed(self, *lines):
        for line in lines:
            self.r.feed(line)

    def test_success_waits_for_end(self):
        self.feed("[+] Read ROM", "[VERIFY] CRC32=98E4F096  DB=game.gba")
        self.assertEqual(self.r.state, "idle")
        self.feed("Press Button...")
        self.assertEqual(self.r.state, "success")

    def test_automatic_menu_does_not_clear_success(self):
        self.test_success_waits_for_end()
        self.feed("GBA Cart Reader", "0)Read ROM", "[Reader] input ready")
        self.assertEqual(self.r.state, "success")

    def test_user_reset_clears(self):
        self.test_success_waits_for_end()
        self.r.reset()
        self.assertEqual(self.r.state, "idle")

    def test_mismatch_stays_red_after_saved_and_end(self):
        self.feed("[+] Read ROM", "[VERIFY] CRC32=12345678  SNES-CHECKSUM=1234 MISMATCH header=5678", "Press Button...", "0)Read ROM")
        self.assertEqual(self.r.state, "failure")

    def test_late_reader_checksum_failure(self):
        self.feed("[+] Read ROM", "[VERIFY] CRC32=12345678  DB=game.md", "Internal checksum...Error", "Press Button...")
        self.assertEqual(self.r.state, "failure")

    def test_batch_rom_is_not_final_success(self):
        self.r.begin_batch()
        self.feed("[+] Read ROM", "[VERIFY] CRC32=12345678", "Press Button...")
        self.assertEqual(self.r.state, "idle")
        self.feed("[+] Read Save", "[SAVED] N64/SAVE/a.eep (512 bytes) SHA256=abcd", "Press Button...")
        self.assertEqual(self.r.state, "idle")
        self.r.finish_batch(True)
        self.assertEqual(self.r.state, "success")

    def test_save_failure_makes_batch_red(self):
        self.r.begin_batch()
        self.feed("[+] Read Save", "Error: no data received", "[SAVED] N64/SAVE/a.eep (0 bytes) SHA256=abcd")
        self.r.finish_batch(False)
        self.assertEqual(self.r.state, "failure")
        self.assertFalse(self.r.blinking)

    def test_verified_rom_then_explicit_save_failure_alternates_colors(self):
        self.r.begin_batch()
        self.feed("[+] Read ROM", "[VERIFY] CRC32=12345678 DB=Known Game")
        self.feed("[+] Read Save", "Error: read timeout")
        self.r.finish_batch(False, save_failure_after_rom=True)
        self.assertEqual(self.r.state, "save_failure_green")
        self.assertTrue(self.r.blinking)
        self.assertTrue(self.r.advance_blink())
        self.assertEqual(self.r.state, "save_failure_red")
        self.assertTrue(self.r.advance_blink())
        self.assertEqual(self.r.state, "save_failure_green")

    def test_success_does_not_override_batch_mismatch(self):
        self.r.begin_batch()
        self.feed("Checksum: 69 != 68 -> MISMATCH (GBA header)")
        self.r.finish_batch(True)
        self.assertEqual(self.r.state, "failure")

    def test_filenames_are_not_error_messages(self):
        self.feed("[+] Read ROM", "[SAVED] GB/ROM/ERROR.gb (32768 bytes) SHA256=abcd", "Press Button...")
        self.assertEqual(self.r.state, "success")

    def test_rom_checksum_error_cannot_be_overridden_by_partial_save_blink(self):
        self.r.begin_batch()
        self.feed(
            "[+] Read ROM",
            "[VERIFY] CRC32=12345678 DB=Known Game",
            "Internal checksum...Error",
            "[+] Read Save",
            "Error: read timeout",
        )
        self.r.finish_batch(False, save_failure_after_rom=True)
        self.assertEqual(self.r.state, "failure")
        self.assertFalse(self.r.blinking)

    def test_error_in_filename_or_database_title_is_not_a_read_error(self):
        self.feed(
            "[+] Read ROM",
            "[SAVED] MD/ROM/Error Title/1/Error.md (131072 bytes) SHA256=abcd",
            "[VERIFY] CRC32=12345678 DB=Error In Database",
            "Press Button...",
        )
        self.assertEqual(self.r.state, "success")

    def test_usb_loss_does_not_clear_completed_partial_success_blink(self):
        self.r.begin_batch()
        self.feed(
            "[+] Read ROM",
            "[VERIFY] CRC32=12345678 DB=Known Game",
            "[+] Read Save",
            "Error: read timeout",
        )
        self.r.finish_batch(False, save_failure_after_rom=True)
        self.assertEqual(self.r.state, "save_failure_green")
        self.feed("[Disconnected: COM5]", "[RECONNECT] WAIT")
        self.assertEqual(self.r.state, "save_failure_green")
        self.assertTrue(self.r.blinking)

    def test_new_connection_clears_partial_success_blink(self):
        from pathlib import Path
        source = (Path(__file__).with_name("cartreader_pc.py")
                  .read_text(encoding="utf-8"))
        tree = ast.parse(source)
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "line.startswith('[Connected:')")
        self.r.state = "save_failure_green"
        self.r.active = False
        exec(compile(ast.Module(body=[branch.body[0]], type_ignores=[]), "connect", "exec"),
             {"reset_dump_result": self.r.reset})
        self.assertEqual(self.r.state, "idle")
        self.assertFalse(self.r.blinking)

    def test_copy_and_tx_test_do_not_claim_dump_success(self):
        self.feed("[SAVED] __diagnostics__/tx-test.crpctest (1048576 bytes) SHA256=abcd", "[VERIFY] CRC32=12345678", "Press Button...")
        self.assertEqual(self.r.state, "idle")

    def test_cancel_is_not_success(self):
        self.feed("[+] Read ROM", "[CANCELLED] removed incomplete file", "Press Button...")
        self.assertEqual(self.r.state, "idle")

    def test_sd_checksum_success(self):
        self.feed("[+] Read ROM", "Checksum: 69 -> OK", "Press Button...")
        self.assertEqual(self.r.state, "success")

    def test_real_error_without_saved_file(self):
        self.feed("[+] Read ROM", "SD Error", "Press Button...")
        self.assertEqual(self.r.state, "failure")

    def test_new_connection_resets_previous_result(self):
        import ast
        from pathlib import Path
        source = (Path(__file__).parent / "cartreader_pc.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "line.startswith('[Connected:')")
        self.r.state = "success"
        exec(compile(ast.Module(body=[branch.body[0]], type_ignores=[]), "connect", "exec"),
             {"reset_dump_result": self.r.reset})
        self.assertEqual(self.r.state, "idle")
