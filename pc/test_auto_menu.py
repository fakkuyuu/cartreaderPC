import unittest

from auto_menu import (
    ROOT_MENU_TITLE,
    ZeroChord,
    build_auto_entries,
    display_auto_reason,
)


ROOT_OPTIONS = (
    ("0", "Game Boy"),
    ("1", "NES/Famicom"),
    ("2", "Super Nintendo/SFC"),
    ("3", "Nintendo 64 (3V)"),
    ("4", "Mega Drive/Genesis"),
    ("5", "PC Engine/TG16"),
)


class AutoMenuTests(unittest.TestCase):
    def setUp(self):
        self.entries = build_auto_entries(ROOT_MENU_TITLE, ROOT_OPTIONS)

    def test_main_menu_assigns_all_eight_auto_targets_in_visible_order(self):
        self.assertEqual(
            [(entry[0], entry[1], entry[2]) for entry in self.entries],
            [
                ("1", "GB", "0"),
                ("2", "GBA", "0"),
                ("3", "NES", "1"),
                ("4", "SNES", "2"),
                ("5", "N64", "3"),
                ("6", "MD", "4"),
                ("7", "PCE_SWAP", "5"),
                ("8", "PCE_RAW", "5"),
            ],
        )
        self.assertEqual(self.entries[0][3], "Auto: Game Boy (Color)")
        self.assertEqual(self.entries[-2][3], "Auto: HuCARD(swapped)")
        self.assertEqual(self.entries[-1][3], "Auto: HuCARD(not swapped)")

    def test_only_visible_menu_targets_get_shortcuts(self):
        pce = build_auto_entries(
            ROOT_MENU_TITLE, (("5", "PC Engine/TG16"),))
        self.assertEqual(
            [(entry[0], entry[1]) for entry in pce],
            [("1", "PCE_SWAP"), ("2", "PCE_RAW")],
        )

    def test_other_screens_do_not_reserve_zero(self):
        self.assertEqual(build_auto_entries("Game Boy", (("0", "Read ROM"),)), ())
        chord = ZeroChord()
        self.assertEqual(chord.key_down("0", ()), (False, None))
        self.assertFalse(chord.zero_pressed)

    def test_zero_chord_selects_auto_without_changing_normal_numbers(self):
        chord = ZeroChord()
        consumed, selected = chord.key_down("0", self.entries)
        self.assertTrue(consumed)
        self.assertIsNone(selected)
        consumed, selected = chord.key_down("1", self.entries)
        self.assertTrue(consumed)
        self.assertEqual(selected, self.entries[0])
        self.assertFalse(chord.zero_pressed)

    def test_7_and_8_remain_normal_page_keys_without_zero_modifier(self):
        chord = ZeroChord()
        self.assertEqual(chord.key_down("7", self.entries), (False, None))
        self.assertEqual(chord.key_down("8", self.entries), (False, None))

    def test_zero_plus_7_and_8_takes_priority_over_page_keys(self):
        chord = ZeroChord()
        chord.key_down("0", self.entries)
        self.assertEqual(chord.key_down("7", self.entries), (True, self.entries[6]))
        chord.key_down("0", self.entries)
        self.assertEqual(chord.key_down("8", self.entries), (True, self.entries[7]))

    def test_releasing_zero_cancels_a_pending_chord(self):
        chord = ZeroChord()
        chord.key_down("0", self.entries)
        chord.key_up("0")
        self.assertEqual(chord.key_down("1", self.entries), (False, None))

    def test_unassigned_chord_digit_is_consumed(self):
        chord = ZeroChord()
        chord.key_down("0", self.entries)
        self.assertEqual(chord.key_down("9", self.entries), (True, None))

    def test_display_copy_uses_auto_wording_without_mutating_internal_reason(self):
        internal = "一括吸出し完了: Game (DB照合なし)"
        displayed = display_auto_reason(internal)
        self.assertEqual(displayed, "自動吸出し完了: Game (DB照合なし)")
        self.assertEqual(internal, "一括吸出し完了: Game (DB照合なし)")
        self.assertEqual(
            display_auto_reason("通信切断・キャンセルのため一括停止"),
            "通信切断・キャンセルのため自動吸出し停止",
        )


if __name__ == "__main__":
    unittest.main()
