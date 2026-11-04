"""Unit tests for #029 menu-drive decisions. Run: python -m unittest discover -s pc -p 'test_batch_dump.py'"""
import ast
from pathlib import Path
import unittest

from batch_dump import BatchDump


ROOT = (("0", "Game Boy"), ("1", "NES/Famicom"), ("2", "Super Nintendo/SFC"))
GB_CHOICES = (("0", "Game Boy (Color)"), ("1", "GB Advance (3V)"))
GB_MENU = (("0", "Read ROM"), ("1", "Read Save"), ("2", "Write Save"), ("3", "Reset"))
GBA_MENU = GB_MENU
PCE_CHOICES = (("0", "HuCARD(swapped)"), ("1", "HuCARD(not swapped)"),
               ("2", "Turbochip"), ("3", "Flash Repro HuCARD"), ("4", "Reset"))
PCE_MENU = (("0", "Read ROM"), ("1", "Read RAM Bank 1"), ("2", "Write RAM Bank 1"),
            ("3", "Inc Bank Number"), ("4", "Dec Bank Number"),
            ("5", "Set 1024K ROM size"), ("6", "Reset"))


class BatchDumpTests(unittest.TestCase):
    @staticmethod
    def _snes_waiting_for_save_read():
        run = BatchDump()
        run.begin("SNES")
        menu = (("0", "Read ROM"), ("1", "Read Save"), ("2", "Write Save"))
        run.on_menu("Select Cart Type", (("0", "SNES/SFC cartridge"),))
        run.on_line("Save Size: 8 KB")
        run.on_press()
        run.on_menu("SNES Cart Reader", menu)
        run.on_line("[SAVED] SNES/ROM/Test/1/Test.sfc (1048576 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678  SNES-CHECKSUM=ABCD OK DB=Known Test")
        run.on_press()
        run.on_menu("SNES Cart Reader", menu)
        return run

    def test_verified_rom_followed_by_explicit_save_error_is_classified(self):
        run = self._snes_waiting_for_save_read()
        self.assertEqual(run.phase, "save_read")
        run.on_line("Error: read timeout")
        self.assertFalse(run.active)
        self.assertTrue(run.save_failure_after_rom)

    def test_verified_rom_followed_by_save_size_mismatch_is_classified(self):
        run = self._snes_waiting_for_save_read()
        run.on_line("[SAVED] SNES/SAVE/Test/1/Test.srm (4096 bytes) SHA256=abcd")
        self.assertFalse(run.active)
        self.assertTrue(run.save_failure_after_rom)
        self.assertIn("セーブサイズ不一致", run.reason)

    def test_disconnect_during_save_is_not_classified_as_explicit_save_error(self):
        run = self._snes_waiting_for_save_read()
        run.on_line("[RECONNECT] WAIT")
        self.assertFalse(run.save_failure_after_rom)
        self.assertIn("通信切断", run.reason)

    @staticmethod
    def _md_rom_verified_before_reader_checksum_result():
        run = BatchDump()
        run.begin("MD")
        menu = (("0", "Read ROM"), ("1", "Read Save"),
                ("2", "Write Save"), ("3", "Reset"))
        run.on_menu("Select MD device", (("0", "Game Cartridge"),))
        run.on_line("Save Type: SRAM")
        run.on_press()
        run.on_menu("MEGA DRIVE Reader", menu)
        run.on_line("[SAVED] MD/ROM/Test/1/Test.md (131072 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678  DB=Known Game")
        return run, menu

    def test_md_normal_rom_then_save_remains_automatic(self):
        run, menu = self._md_rom_verified_before_reader_checksum_result()
        self.assertTrue(run.active)
        self.assertEqual(run.phase, "rom_read")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("MEGA DRIVE Reader", menu), "1")
        run.on_line("[SAVED] MD/SAVE/Test/1/Test.srm (32768 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("MEGA DRIVE Reader", menu))
        self.assertFalse(run.active)
        self.assertFalse(run.save_failure_after_rom)
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_md_internal_checksum_error_after_saved_and_verified_rom_stops_before_save(self):
        run, menu = self._md_rom_verified_before_reader_checksum_result()
        run.on_line("Internal checksum...Error")
        self.assertFalse(run.active)
        self.assertFalse(run.save_failure_after_rom)
        self.assertIn("ROM内部チェックサム異常", run.reason)

        # Later save/verification notifications cannot revive the stopped batch.
        run.on_line("[SAVED] MD/SAVE/Test/1/Test.srm (32768 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=87654321  DB=Error Title")
        self.assertFalse(run.active)
        self.assertFalse(run.save_saved)
        self.assertIsNone(run.on_menu("MEGA DRIVE Reader", menu))

    def test_md_internal_checksum_status_does_not_stop_other_console_batches(self):
        for target in ("GB", "GBA", "SNES", "N64", "NES", "PCE_SWAP", "PCE_RAW"):
            with self.subTest(target=target):
                run = BatchDump()
                run.begin(target)
                run.phase = "rom_read"
                run.on_line("Internal checksum...Error")
                self.assertTrue(run.active)
                self.assertFalse(run.save_failure_after_rom)

    def test_gb_rom_then_save(self):
        run = BatchDump()
        run.begin("GB")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "0")
        run.on_line("Save Size: 8 KB")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GB Cart Reader", GB_MENU), "0")
        run.on_line("[SAVED] GB/ROM/Example/1/Test.gb (32768 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678  DB=no match")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GB Cart Reader", GB_MENU), "1")
        run.on_line("[SAVED] GB/SAVE/Example/2/Test.sav (8192 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("GB Cart Reader", GB_MENU))
        self.assertFalse(run.active)
        self.assertIn("ROM + SAVE", run.reason)

    def test_gba_unknown_save_never_guessed(self):
        run = BatchDump()
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        run.on_line("Save Lib: Unknown")
        self.assertEqual(run.on_physical(), " ")
        run.on_line("Save Type: None/Unknown")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GBA Cart Reader", GBA_MENU), "0")
        run.on_line("[SAVED] GBA/ROM/Test/1/Test.gba (1024 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=no match")
        self.assertEqual(run.on_press(), " ")
        self.assertIsNone(run.on_menu("GBA Cart Reader", GBA_MENU))
        self.assertFalse(run.active)
        self.assertIn("セーブ有無が不明", run.reason)

    def test_gba_database_explicit_no_save(self):
        run = BatchDump()
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        run.on_line("Save Lib: None")
        self.assertEqual(run.on_physical(), " ")
        run.on_line("Save Type: None/Unknown")
        self.assertFalse(run.save)
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GBA Cart Reader", GBA_MENU), "0")
        run.on_line("[SAVED] GBA/ROM/Test/1/Test.gba (1048576 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Test")
        self.assertEqual(run.on_press(), " ")
        self.assertIsNone(run.on_menu("GBA Cart Reader", GBA_MENU))
        self.assertEqual(run.reason, "一括吸出し完了: ROM")

    def test_nes_database_nvram(self):
        run = BatchDump()
        run.begin("NES")
        run.on_line("RAM SIZE: 8K")
        self.assertTrue(run.save)
        self.assertEqual(run.on_menu("NES CART READER",
                         (("0", "Read iNES Rom"), ("2", "Read Save"))), "0")
        run.on_line("[SAVED] NES/ROM/Test/1/Test.nes (32784 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Test")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("NES CART READER",
                         (("0", "Read iNES Rom"), ("2", "Read Save"))), "2")

    def test_nes_db_hit_candidate_confirmation_then_rom(self):
        # NES.ino getMapping: CRC matches nes.txt, checkCartSelection prints
        # "Select your cartridge", then [Control] cartridge-select.
        run = BatchDump()
        run.begin("NES")
        run.on_line("Searching database")
        run.on_line("for 12345678...")
        run.on_line("Select your cartridge")
        run.on_line("Known NES Game")
        run.on_line("[Control] cartridge-select")
        self.assertEqual(run.on_candidate(), " ")
        self.assertTrue(run.nes_candidate_selected)
        run.on_line("RAM SIZE: 0K")
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read iNES Rom"), ("2", "Read Save"),
                ("3", "Write Save"), ("6", "Reset"))
        self.assertEqual(run.on_menu("NES CART READER", menu), "0")
        run.on_line("[SAVED] NES/ROM/Known Game/1/Known Game.nes (32784 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known NES Game")
        self.assertEqual(run.on_press(), " ")
        self.assertIsNone(run.on_menu("NES CART READER", menu))
        self.assertFalse(run.active)
        self.assertEqual(run.reason, "一括吸出し完了: ROM")

    def test_nes_db_miss_manual_candidate_never_confirmed(self):
        # The same candidate widget can follow a manual alphabet/database
        # selection; a previous "Searching database" is not sufficient.
        run = BatchDump()
        run.begin("NES")
        run.on_line("Searching database")
        run.on_line("for 12345678...")
        run.on_line("CRC not found in database")
        run.on_line("Using manual selection")
        run.on_line("Select your cartridge")
        run.on_line("[Control] cartridge-select")
        self.assertIsNone(run.on_candidate())
        self.assertFalse(run.active)
        self.assertIn("DB一致を確認できません", run.reason)

    def test_nes_all_ff_manual_candidate_never_confirmed(self):
        run = BatchDump()
        run.begin("NES")
        run.on_line("No data found.")
        run.on_line("Using manual selection")
        run.on_line("Select your cartridge")
        run.on_line("[Control] cartridge-select")
        self.assertIsNone(run.on_candidate())
        self.assertFalse(run.active)
        self.assertIn("手動選択", run.reason)

    def test_nes_candidate_without_db_evidence_stops(self):
        for lines in ((), ("Searching database",),
                      ("Select your cartridge",)):
            with self.subTest(lines=lines):
                run = BatchDump()
                run.begin("NES")
                for line in lines:
                    run.on_line(line)
                self.assertIsNone(run.on_candidate())
                self.assertFalse(run.active)
        run = BatchDump()
        run.begin("NES")
        self.assertIsNone(run.on_press())
        self.assertIn("DB候補未確認", run.reason)

    def test_nes_candidate_confirmation_cannot_be_sent_twice(self):
        run = BatchDump()
        run.begin("NES")
        run.on_line("Searching database")
        run.on_line("Select your cartridge")
        self.assertEqual(run.on_candidate(), " ")
        self.assertIsNone(run.on_candidate())
        self.assertFalse(run.active)

    def test_other_console_candidate_screen_still_stops(self):
        run = BatchDump()
        run.begin("GB")
        self.assertIsNone(run.on_candidate())
        self.assertFalse(run.active)
        self.assertIn("手動選択", run.reason)

    def test_gui_nes_candidate_control_is_wired_to_batch(self):
        gui = Path(__file__).with_name("cartreader_pc.py").read_text(encoding="utf-8")
        tree = ast.parse(gui)
        def named_function(name):
            return next(node for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef) and node.name == name)
        handler = named_function("render_candidate_controls")
        parsed = named_function("parse_console")
        names = {ast.unparse(node.func) for node in ast.walk(handler)
                 if isinstance(node, ast.Call)}
        self.assertIn("batch.on_candidate", names)
        self.assertIn("batch_report", names)
        self.assertIn("batch_schedule", names)
        self.assertIn("[Control] cartridge-select", ast.get_source_segment(gui, parsed))

    def test_snes_with_save_uses_firmware_read_save_label(self):
        # The actual SNES menu uses FSTRING_READ_SAVE ("Read Save"), not "Read SRAM".
        run = BatchDump()
        run.begin("SNES")
        self.assertEqual(run.on_menu("Select Cart Type",
                         (("0", "SNES/SFC cartridge"),)), "0")
        run.on_line("Save Size: 8 KB")
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read ROM"), ("1", "Read Save"),
                ("2", "Write Save"), ("3", "Test SRAM"), ("6", "Reset"))
        self.assertEqual(run.on_menu("SNES Cart Reader", menu), "0")
        run.on_line("[SAVED] SNES/ROM/Test/1/Test.sfc (524288 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 SNES-CHECKSUM=ABCD OK DB=Known Game")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("SNES Cart Reader", menu), "1")
        self.assertEqual(run.phase, "save_read")
        run.on_line("[SAVED] SNES/SAVE/Test/1/Test.srm (8192 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("SNES Cart Reader", menu))
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_gba_real_database_confirmation_path(self):
        run = BatchDump()
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        # Database candidate displayed by getCartInfo_GBA, then
        # printInstructions() emits [Control] physical-buttons.
        run.on_line("Serial: AXVE")
        run.on_line("ROM Size: 8 MB")
        run.on_line("Save Lib: EEPROM_V120")
        self.assertEqual(run.on_physical(), " ")
        self.assertTrue(run.gba_candidate_selected)
        run.on_line("Save Type: 4K EEPROM")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GBA Cart Reader", GBA_MENU), "0")
        run.on_line("[SAVED] GBA/ROM/Test/1/Test.gba (8388608 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("GBA Cart Reader", GBA_MENU), "1")
        run.on_line("[SAVED] GBA/SAVE/Test/1/Test.srm (512 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("GBA Cart Reader", GBA_MENU))
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_gba_unknown_physical_screen_is_not_confirmed(self):
        run = BatchDump()
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        self.assertIsNone(run.on_physical())
        self.assertFalse(run.active)
        self.assertIn("想定外", run.reason)
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        run.on_line("CARTRIDGE ERROR")
        self.assertFalse(run.active)
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        self.assertIsNone(run.on_press())
        self.assertFalse(run.active)
        self.assertIn("ゲーム情報確定前", run.reason)

    def test_gui_physical_control_is_wired_to_batch_handler(self):
        # Regression for a green state-machine suite while the GUI forgot to
        # call the handler on [Control] physical-buttons.
        gui = Path(__file__).with_name("cartreader_pc.py").read_text(encoding="utf-8")
        tree = ast.parse(gui)
        def function_named(name):
            return next(node for node in ast.walk(tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == name)
        handler = function_named("render_physical_fallback")
        parsed = function_named("parse_console")
        handler_calls = {
            ast.unparse(node.func)
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
        }
        self.assertIn("batch.on_physical", handler_calls)
        self.assertIn("batch_schedule", handler_calls)
        self.assertIn("batch_report", handler_calls)
        self.assertIn("render_physical_fallback", {
            ast.unparse(node.func) for node in ast.walk(parsed)
            if isinstance(node, ast.Call)
        })
        self.assertIn("[Control] physical-buttons", ast.get_source_segment(
            gui, parsed))

    def test_snes_no_save(self):
        run = BatchDump()
        run.begin("SNES")
        self.assertEqual(run.on_menu("Select Cart Type",
                                    (("0", "SNES/SFC cartridge"),)), "0")
        run.on_line("Save Size: 0 KB")
        self.assertEqual(run.on_menu("SNES Cart Reader",
                                    (("0", "Read ROM"), ("1", "Read Save"))), "0")
        run.on_line("[SAVED] SNES/ROM/Test/1/Test.sfc (1024 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 SNES-CHECKSUM=ABCD OK DB=no match")
        self.assertIsNone(run.on_menu("SNES Cart Reader",
                                      (("0", "Read ROM"), ("1", "Read Save"))))
        self.assertEqual(run.reason, "一括吸出し完了: ROM（DB照合なし）")

    def test_n64_database_hit_rom_then_eeprom(self):
        # Exact N64.ino flow: Select N64 device -> Game Cartridge ->
        # n64.txt CRC1 match -> ROM Size / Save Type / CRC1 -> Press Button
        # -> N64 Cart Reader -> Read ROM -> Press Button -> Read Save.
        run = BatchDump()
        run.begin("N64")
        self.assertEqual(run.on_menu("Select N64 device",
                         (("0", "Game Cartridge"), ("1", "Controller"),
                          ("2", "Flash Repro"))), "0")
        run.on_line("Searching database...")
        run.on_line("ROM Size: 8 MB")
        run.on_line("Save Type: 4K EEPROM")
        run.on_line("CRC1: A1B2C3D4")
        self.assertEqual(run.save_expected_bytes, 512)
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read ROM"), ("1", "Read Save"),
                ("2", "Write Save"), ("3", "Force Savetype"),
                ("4", "Force ROM size"))
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "0")
        run.on_line("[SAVED] N64/ROM/TEST/1/TEST.Z64 (8388608 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678  DB=Known Game")
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "1")
        run.on_line("[SAVED] N64/SAVE/TEST/1/TEST.eep (512 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("N64 Cart Reader", menu))
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_n64_parentheses_in_rom_filename_and_folder(self):
        # Regression: splitting on the first " (" truncates this path.
        run = BatchDump()
        run.begin("N64")
        self.assertEqual(run.on_menu("Select N64 device",
                         (("0", "Game Cartridge"),)), "0")
        for line in ("ROM Size: 4 MB", "Save Type: SRAM", "CRC1: A1B2C3D4"):
            run.on_line(line)
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read ROM"), ("1", "Read Save"), ("2", "Write Save"))
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "0")
        run.on_line("[SAVED] N64/ROM/Archive (2026)/1/GAME (J).Z64 "
                    "(4194304 bytes) SHA256=abcd")
        self.assertTrue(run.rom_saved)
        self.assertTrue(run.active, run.reason)
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
        run.on_line("[SAVED] N64/ROM/Archive (2026)/1/GAME (J).txt "
                    "(927 bytes) SHA256=abcd")
        self.assertTrue(run.rom_saved)
        self.assertTrue(run.active)
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "1")
        run.on_line("[SAVED] N64/SAVE/Archive (2026)/1/GAME (J).sra "
                    "(32768 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("N64 Cart Reader", menu))
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_rom_saved_trailer_matches_rightmost_size_marker(self):
        # Also reject a misleading, earlier "(digits bytes)" segment in
        # the directory name. The final SHA256 trailer is authoritative.
        run = BatchDump()
        run.begin("N64")
        run.phase = "rom_read"
        run.n64_rom_bytes = 4 * 1024 * 1024
        run.on_line("[SAVED] N64/ROM/Archive (12 bytes)/GAME (J).z64 "
                    "(4194304 bytes) SHA256=abcd")
        self.assertTrue(run.rom_saved)
        self.assertTrue(run.active)
        run.on_line("[SAVED] N64/ROM/Archive (12 bytes)/GAME (J).txt "
                    "(999 bytes) SHA256=abcd")
        self.assertTrue(run.rom_saved)
        self.assertTrue(run.active)

    def test_n64_rom_companion_txt_does_not_trigger_size_mismatch(self):
        # storage.py emits [SAVED] both for the ROM payload and for the
        # post-verification companion TXT *under the same N64/ROM directory*.
        # Before the fix the TXT's byte count was compared to 4 MiB and
        # incorrectly stopped the batch.
        run = BatchDump()
        run.begin("N64")
        self.assertEqual(run.on_menu("Select N64 device",
                         (("0", "Game Cartridge"),)), "0")
        for line in ("ROM Size: 4 MB", "Save Type: SRAM", "CRC1: A1B2C3D4"):
            run.on_line(line)
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read ROM"), ("1", "Read Save"),
                ("2", "Write Save"), ("3", "Force Savetype"))
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "0")
        run.on_line("[SAVED] N64/ROM/TEST/1/TEST.z64 (4194304 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
        run.on_line("[SAVED] N64/ROM/TEST/1/TEST.txt (927 bytes) SHA256=abcd")
        self.assertTrue(run.active, run.reason)
        self.assertTrue(run.rom_saved)
        self.assertTrue(run.rom_verified)
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "1")
        run.on_line("[SAVED] N64/SAVE/TEST/1/TEST.sra (32768 bytes) SHA256=abcd")
        self.assertIsNone(run.on_menu("N64 Cart Reader", menu))
        self.assertEqual(run.reason, "一括吸出し完了: ROM + SAVE")

    def test_n64_companion_txt_alone_is_not_accepted_as_rom(self):
        run = BatchDump()
        run.begin("N64")
        run.on_menu("Select N64 device", (("0", "Game Cartridge"),))
        for line in ("ROM Size: 4 MB", "Save Type: SRAM", "CRC1: A1B2C3D4"):
            run.on_line(line)
        run.on_press()
        run.on_menu("N64 Cart Reader", (("0", "Read ROM"),))
        run.on_line("[SAVED] N64/ROM/TEST/1/TEST.txt (4194304 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
        self.assertFalse(run.rom_saved)
        self.assertIsNone(run.on_press())
        self.assertFalse(run.active)
        self.assertIn("ROMの保存・検証が未完了", run.reason)

    def test_companion_txt_is_ignored_for_every_batch_target(self):
        payloads = {
            "GB": ("GB", ".gb"), "GBA": ("GBA", ".gba"),
            "SNES": ("SNES", ".sfc"), "MD": ("MD", ".bin"),
            "N64": ("N64", ".Z64"), "NES": ("NES", ".nes"),
            "PCE_SWAP": ("PCE", ".pce"), "PCE_RAW": ("PCE", ".pce"),
        }
        for target, (folder, extension) in payloads.items():
            with self.subTest(target=target):
                run = BatchDump()
                run.begin(target)
                # Isolate SAVED-message parsing from the initial menu flow.
                run.phase = "rom_read"
                run.on_line(f"[SAVED] {folder}/ROM/T/1/T.txt (123 bytes) SHA256=abcd")
                self.assertFalse(run.rom_saved)
                self.assertTrue(run.active)
                run.on_line(f"[SAVED] {folder}/ROM/T/1/T{extension} (32768 bytes) SHA256=abcd")
                self.assertTrue(run.rom_saved)
                self.assertTrue(run.active)

    def test_n64_database_hit_no_save_rom_only(self):
        run = BatchDump()
        run.begin("N64")
        self.assertEqual(run.on_menu("Select N64 device", (("0", "Game Cartridge"),)), "0")
        run.on_line("ROM Size: 4 MB")
        run.on_line("Save Type: None/Unknown")
        run.on_line("CRC1: 0123ABCD")
        self.assertFalse(run.save)
        self.assertEqual(run.on_press(), " ")
        menu = (("0", "Read ROM"), ("1", "Read Save"), ("2", "Write Save"))
        self.assertEqual(run.on_menu("N64 Cart Reader", menu), "0")
        run.on_line("[SAVED] N64/ROM/TEST/1/TEST.z64 (4194304 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=no match")
        self.assertEqual(run.on_press(), " ")
        self.assertIsNone(run.on_menu("N64 Cart Reader", menu))
        self.assertEqual(run.reason, "一括吸出し完了: ROM（DB照合なし）")

    def test_n64_database_miss_stops_before_fallback_dump(self):
        # N64.ino shows GAMEPAK ERROR and waits, then sets cartSize=2.
        # The batch mode must not acknowledge that prompt automatically.
        run = BatchDump()
        run.begin("N64")
        self.assertEqual(run.on_menu("Select N64 device", (("0", "Game Cartridge"),)), "0")
        run.on_line("Searching database...")
        run.on_line("GAMEPAK ERROR")
        self.assertFalse(run.active)
        self.assertIn("GAMEPAK ERROR", run.reason)
        self.assertIsNone(run.on_press())
        self.assertIsNone(run.on_menu("N64 Cart Reader", (("0", "Read ROM"),)))

    def test_n64_unconfirmed_database_never_acknowledged(self):
        for lines in (
            ("ROM Size: 8 MB", "CRC1: A1B2C3D4"),
            ("Save Type: SRAM", "CRC1: A1B2C3D4"),
            ("ROM Size: Unknown", "Save Type: SRAM", "CRC1: A1B2C3D4"),
            ("ROM Size: 8 MB", "Save Type: SRAM", "CRC1: Not valid"),
        ):
            with self.subTest(lines=lines):
                run = BatchDump()
                run.begin("N64")
                run.on_menu("Select N64 device", (("0", "Game Cartridge"),))
                for line in lines:
                    run.on_line(line)
                self.assertIsNone(run.on_press())
                self.assertFalse(run.active)
                self.assertIn("DB照合が未完了", run.reason)

    def test_n64_save_types_and_dump_size_guards(self):
        for value, expected in (
            ("SRAM", 32768), ("SRAM 768", 98304),
            ("FLASH", 131072), ("4K EEPROM", 512), ("16K EEPROM", 2048),
        ):
            with self.subTest(value=value):
                run = BatchDump()
                run.begin("N64")
                run.on_menu("Select N64 device", (("0", "Game Cartridge"),))
                run.on_line("ROM Size: 4 MB")
                run.on_line("Save Type: " + value)
                run.on_line("CRC1: A1B2C3D4")
                self.assertTrue(run.save)
                self.assertEqual(run.save_expected_bytes, expected)
                self.assertEqual(run.on_press(), " ")
                self.assertEqual(run.on_menu("N64 Cart Reader", (("0", "Read ROM"),)), "0")
                run.on_line("[SAVED] N64/ROM/T/1/T.z64 (4194304 bytes) SHA256=abcd")
                run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
                self.assertEqual(run.on_press(), " ")
                self.assertEqual(run.on_menu("N64 Cart Reader",
                                 (("0", "Read ROM"), ("1", "Read Save"),
                                  ("2", "Write Save"))), "1")
                run.on_line(f"[SAVED] N64/SAVE/T/1/T.eep ({expected} bytes) SHA256=abcd")
                self.assertIsNone(run.on_menu("N64 Cart Reader", (("0", "Read ROM"), ("1", "Read Save"))))
                self.assertTrue(run.reason.startswith("一括吸出し完了"))

    def test_n64_wrong_rom_size_or_save_size_stops(self):
        run = BatchDump()
        run.begin("N64")
        run.on_menu("Select N64 device", (("0", "Game Cartridge"),))
        for line in ("ROM Size: 8 MB", "Save Type: SRAM", "CRC1: A1B2C3D4"):
            run.on_line(line)
        self.assertEqual(run.on_press(), " ")
        self.assertEqual(run.on_menu("N64 Cart Reader", (("0", "Read ROM"),)), "0")
        run.on_line("[SAVED] N64/ROM/T/1/T.z64 (4194304 bytes) SHA256=abcd")
        self.assertFalse(run.active)
        self.assertIn("ROMサイズ不一致", run.reason)

        run.begin("N64")
        run.on_menu("Select N64 device", (("0", "Game Cartridge"),))
        for line in ("ROM Size: 4 MB", "Save Type: 4K EEPROM", "CRC1: A1B2C3D4"):
            run.on_line(line)
        run.on_press()
        run.on_menu("N64 Cart Reader", (("0", "Read ROM"),))
        run.on_line("[SAVED] N64/ROM/T/1/T.z64 (4194304 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=Known Game")
        run.on_press()
        self.assertEqual(run.on_menu("N64 Cart Reader",
                         (("0", "Read ROM"), ("1", "Read Save"))), "1")
        run.on_line("[SAVED] N64/SAVE/T/1/T.eep (128 bytes) SHA256=abcd")
        self.assertFalse(run.active)
        self.assertIn("セーブサイズ不一致", run.reason)

    def test_gui_uses_compact_auto_panel_with_one_click_actions(self):
        gui = Path(__file__).with_name("cartreader_pc.py").read_text(encoding="utf-8")
        self.assertIn("auto_entries = build_auto_entries(title, options)", gui)
        self.assertIn('text=button_label', gui)
        self.assertIn("command=lambda t=target, n=number: start_batch(t, n)", gui)
        self.assertIn('text="自動吸出し（0を押しながら1〜8）"', gui)
        self.assertNotIn('"Nintendo 64 (3V)": (("一括吸出し", "N64"),)', gui)

    def test_pce_variants_never_read_ram(self):
        for target, expected in (("PCE_SWAP", "0"), ("PCE_RAW", "1")):
            with self.subTest(target=target):
                run = BatchDump()
                run.begin(target)
                self.assertEqual(run.on_menu("Select device", PCE_CHOICES), expected)
                self.assertEqual(run.on_menu("PCE HuCARD menu", PCE_MENU), "0")
                run.on_line("[SAVED] PCE/ROM/PCEROM/1/PCEROM.pce (262144 bytes) SHA256=abcd")
                run.on_line("[VERIFY] CRC32=12345678  DB=no match")
                self.assertEqual(run.on_press(), " ")
                self.assertIsNone(run.on_menu("PCE HuCARD menu", PCE_MENU))
                self.assertFalse(run.active)
                self.assertIn("一括吸出し完了", run.reason)

    def test_unknown_menu_and_checksum_error_stop(self):
        run = BatchDump()
        run.begin("MD")
        self.assertIsNone(run.on_menu("Unknown menu", (("0", "Write Save"),)))
        self.assertFalse(run.active)
        run.begin("GBA")
        self.assertEqual(run.on_menu("Select Game Boy", GB_CHOICES), "1")
        run.on_line("HEADER CHECKSUM ERROR")
        self.assertFalse(run.active)

    def test_nes_no_data_can_reach_safe_reset_screen(self):
        run = BatchDump()
        run.begin("NES")
        run.on_line("No data found.")
        run.on_line("Using manual selection")
        self.assertTrue(run.active)
        self.assertEqual(run.phase, "entry")

    def test_no_auto_writing(self):
        run = BatchDump()
        run.begin("NES")
        self.assertEqual(run.on_menu("NES CART READER",
                         (("0", "Read iNES Rom"), ("3", "Write Save"),
                          ("5", "Flash Repro"), ("6", "Reset"))), "0")
        run.on_line("[SAVED] NES/ROM/Test/1/Test.nes (32784 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 DB=no match")
        self.assertEqual(run.on_press(), " ")
        self.assertIsNone(run.on_menu("NES CART READER",
                          (("0", "Read iNES Rom"), ("3", "Write Save"),
                           ("5", "Flash Repro"), ("6", "Reset"))))
        self.assertFalse(run.active)


if __name__ == "__main__":
    unittest.main()
