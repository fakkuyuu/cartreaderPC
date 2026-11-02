"""Unit tests for #029 menu-drive decisions. Run: python -m unittest discover -s pc -p 'test_batch_dump.py'"""
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
        run.on_line("Save Type: None/Unknown")
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
        run.on_line("Save Type: None/Unknown")
        self.assertFalse(run.save)
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

    def test_snes_no_save(self):
        run = BatchDump()
        run.begin("SNES")
        self.assertEqual(run.on_menu("Select Cart Type",
                                    (("0", "SNES/SFC cartridge"),)), "0")
        run.on_line("Save Size: 0 KB")
        self.assertEqual(run.on_menu("SNES Cart Reader",
                                    (("0", "Read ROM"), ("1", "Read SRAM"))), "0")
        run.on_line("[SAVED] SNES/ROM/Test/1/Test.sfc (1024 bytes) SHA256=abcd")
        run.on_line("[VERIFY] CRC32=12345678 SNES-CHECKSUM=ABCD OK DB=no match")
        self.assertIsNone(run.on_menu("SNES Cart Reader",
                                      (("0", "Read ROM"), ("1", "Read SRAM"))))
        self.assertEqual(run.reason, "一括吸出し完了: ROM（DB照合なし）")

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
