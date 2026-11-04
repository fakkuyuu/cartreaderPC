import unittest
from power_on_dump import PowerOnDump, TARGETS

ROOT = "OPEN SOURCE CART READER"
PAGE = (("0", "Game Boy"), ("1", "NES/Famicom"),
        ("2", "Super Nintendo/SFC"), ("3", "Nintendo 64 (3V)"),
        ("4", "Mega Drive/Genesis"), ("6", "PC Engine/TG16"))


class PowerOnTests(unittest.TestCase):
    def test_default_disabled_and_invalid_saved_values(self):
        for settings in ({}, {"power_on_dump_enabled": "false", "power_on_dump_target": []}):
            auto = PowerOnDump(settings)
            auto.reader_started()
            self.assertIsNone(auto.menu_action(ROOT, PAGE, True))

    def enabled(self, target="GBA"):
        return PowerOnDump({"power_on_dump_enabled": True, "power_on_dump_target": target})

    def test_enable_does_not_start_until_next_reader_boot(self):
        auto = PowerOnDump({})
        auto.configure(True, "GBA")
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))
        auto.reader_started()
        self.assertEqual(auto.menu_action(ROOT, PAGE, True), ("start", "GBA", "0"))

    def test_one_start_per_boot_and_checkbox_stays_enabled(self):
        auto = self.enabled()
        for _ in range(3):
            auto.reader_started()
            self.assertEqual(auto.menu_action(ROOT, PAGE, True), ("start", "GBA", "0"))
            self.assertIsNone(auto.menu_action(ROOT, PAGE, True))
            self.assertTrue(auto.enabled)

    def test_non_root_menu_never_triggers(self):
        auto = self.enabled()
        auto.reader_started()
        self.assertIsNone(auto.menu_action("GBA Cart Reader", (("0", "Read ROM"),), False))

    def test_disabled_after_boot_cancels_pending(self):
        auto = self.enabled()
        auto.reader_started()
        auto.configure(False, "GBA")
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))

    def test_target_change_waits_for_next_boot(self):
        auto = self.enabled()
        auto.reader_started()
        auto.configure(True, "MD")
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))
        auto.reader_started()
        self.assertEqual(auto.menu_action(ROOT, PAGE, True), ("start", "MD", "4"))

    def test_user_action_cancels_this_boot_only(self):
        auto = self.enabled()
        auto.reader_started()
        auto.cancel()
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))
        auto.reader_started()
        self.assertEqual(auto.menu_action(ROOT, PAGE, True)[0], "start")

    def test_reset_or_benchmark_suppression(self):
        auto = self.enabled()
        auto.reader_started(suppressed=True)
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))
        self.assertTrue(auto.enabled)

    def test_pc_only_does_not_override_sd(self):
        auto = self.enabled()
        auto.reader_started()
        self.assertEqual(auto.menu_action(ROOT, PAGE, True, "SD")[0], "stop")
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))

    def test_pce_variants_use_same_root_but_distinct_batch_targets(self):
        for target in ("PCE_SWAP", "PCE_RAW"):
            auto = self.enabled(target)
            auto.reader_started()
            self.assertEqual(auto.menu_action(ROOT, PAGE, True), ("start", target, "6"))

    def test_later_page_and_missing_module_stop_without_loop(self):
        auto = self.enabled("MD")
        auto.reader_started()
        first = (("0", "Game Boy"),)
        self.assertEqual(auto.menu_action(ROOT, first, True), ("page", "]"))
        self.assertEqual(auto.menu_action(ROOT, PAGE, True), ("start", "MD", "4"))
        auto.reader_started()
        self.assertEqual(auto.menu_action(ROOT, first, True)[0], "page")
        self.assertEqual(auto.menu_action(ROOT, first, True)[0], "stop")
        self.assertFalse(auto.pending)

    def test_round_trip_settings_preserves_enabled_and_target(self):
        auto = self.enabled("PCE_RAW")
        restored = PowerOnDump(auto.settings())
        self.assertTrue(restored.enabled)
        self.assertEqual(restored.target, "PCE_RAW")
        self.assertFalse(restored.pending)

    def test_disconnect_does_not_resume_old_pending_batch(self):
        auto = self.enabled()
        auto.reader_started()
        auto.disconnected()
        self.assertIsNone(auto.menu_action(ROOT, PAGE, True))

    def test_all_choices_map_to_supported_batch_targets(self):
        from batch_dump import BatchDump
        for target, label in TARGETS:
            self.assertIn(target, BatchDump.ROOT_NAMES)
            self.assertTrue(label)
