import unittest
from pathlib import Path

from auto_menu import (
    ROOT_MENU_TITLE,
    MenuNavigator,
    ZeroChord,
    build_auto_entries,
    build_menu_rows,
    display_auto_reason,
    is_widget_within,
    normalize_digit,
    resolve_menu_number,
)
from i18n import UiTranslator


class FakeLanguage:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeWidget:
    def __init__(self, master=None):
        self.master = master


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
        self.rows = build_menu_rows(ROOT_MENU_TITLE, ROOT_OPTIONS, paged=True)

    def test_main_menu_displays_one_based_numbers_but_keeps_reader_numbers(self):
        self.assertEqual(
            [(row["display_number"], row["reader_number"]) for row in self.rows],
            [("1", "0"), ("2", "1"), ("3", "2"),
             ("4", "3"), ("5", "4"), ("6", "5")],
        )
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, ROOT_OPTIONS, "1"), "0")
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, ROOT_OPTIONS, "6"), "5")
        self.assertIsNone(resolve_menu_number(ROOT_MENU_TITLE, ROOT_OPTIONS, "0"))

    def test_page_keys_7_and_8_are_reserved_without_number_collision(self):
        options = ROOT_OPTIONS + (("6", "Other console"),)
        rows = build_menu_rows(ROOT_MENU_TITLE, options, paged=True)
        self.assertEqual(
            [row["display_number"] for row in rows],
            ["1", "2", "3", "4", "5", "6", "9"],
        )
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, options, "7", paged=True), "[")
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, options, "8", paged=True), "]")
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, options, "9", paged=True), "6")

    def test_submenu_numbers_are_not_renumbered(self):
        submenu = (("0", "Read ROM"), ("1", "Read Save"), ("2", "Reset"))
        rows = build_menu_rows("Game Boy Cart Reader", submenu, paged=False)
        self.assertEqual([row["display_number"] for row in rows], ["0", "1", "2"])
        self.assertEqual(resolve_menu_number("Game Boy Cart Reader", submenu, "0"), "0")
        self.assertEqual(resolve_menu_number("Game Boy Cart Reader", submenu, "1"), "1")

    def test_top_row_fullwidth_and_numpad_digits_normalize_equally(self):
        self.assertEqual(normalize_digit("1", "1", 49), "1")
        self.assertEqual(normalize_digit("kp_end", "", 97, windows=True), "1")
        self.assertEqual(normalize_digit("kp_1"), "1")
        self.assertEqual(normalize_digit("2", "２"), "2")
        self.assertEqual(normalize_digit("7", "", 103, windows=True), "7")

    def test_number_and_numpad_both_resolve_display_digit_to_reader_number(self):
        for keysym, char, keycode, windows in (
            ("1", "1", 49, False),
            ("kp_end", "", 97, True),
        ):
            digit = normalize_digit(keysym, char, keycode, windows=windows)
            self.assertEqual(
                resolve_menu_number(ROOT_MENU_TITLE, ROOT_OPTIONS, digit),
                "0",
            )

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

    def test_auto_buttons_are_attached_to_their_corresponding_rows(self):
        self.assertEqual(
            [(row["label"], [entry[1] for entry in row["auto_entries"]])
             for row in self.rows],
            [
                ("Game Boy", ["GB", "GBA"]),
                ("NES/Famicom", ["NES"]),
                ("Super Nintendo/SFC", ["SNES"]),
                ("Nintendo 64 (3V)", ["N64"]),
                ("Mega Drive/Genesis", ["MD"]),
                ("PC Engine/TG16", ["PCE_SWAP", "PCE_RAW"]),
            ],
        )

    def test_only_visible_menu_targets_get_shortcuts(self):
        pce = build_auto_entries(
            ROOT_MENU_TITLE, (("5", "PC Engine/TG16"),))
        self.assertEqual(
            [(entry[0], entry[1]) for entry in pce],
            [("1", "PCE_SWAP"), ("2", "PCE_RAW")],
        )

    def test_right_moves_from_row_to_gb_then_gba_and_left_returns(self):
        navigator = MenuNavigator(self.rows, paged=True)
        self.assertEqual(navigator.current_action(), ("reader", "0"))
        self.assertIsNone(navigator.move_horizontal(1))
        self.assertEqual(navigator.current_action()[1][1], "GB")
        self.assertIsNone(navigator.move_horizontal(1))
        self.assertEqual(navigator.current_action()[1][1], "GBA")
        self.assertIsNone(navigator.move_horizontal(-1))
        self.assertEqual(navigator.current_action()[1][1], "GB")
        self.assertIsNone(navigator.move_horizontal(-1))
        self.assertEqual(navigator.current_action(), ("reader", "0"))
        self.assertEqual(navigator.move_horizontal(-1), "previous-page")

    def test_right_from_rightmost_pce_auto_moves_to_next_page(self):
        navigator = MenuNavigator(self.rows, paged=True)
        navigator.select_row(5)
        self.assertIsNone(navigator.move_horizontal(1))
        self.assertEqual(navigator.current_action()[1][1], "PCE_SWAP")
        self.assertIsNone(navigator.move_horizontal(1))
        self.assertEqual(navigator.current_action()[1][1], "PCE_RAW")
        self.assertEqual(navigator.move_horizontal(1), "next-page")

    def test_vertical_navigation_retains_auto_column_when_possible(self):
        navigator = MenuNavigator(self.rows, paged=True)
        self.assertTrue(navigator.select_auto(0, 1))
        navigator.move_vertical(1)
        self.assertEqual(navigator.current_action(), ("reader", "1"))
        navigator.move_vertical(1)
        navigator.move_vertical(1)
        navigator.move_vertical(1)
        navigator.move_vertical(1)
        self.assertEqual(navigator.current_action()[0], "auto")
        self.assertEqual(navigator.current_action()[1][1], "PCE_RAW")

    def test_enter_reports_reader_option_or_auto_action(self):
        navigator = MenuNavigator(self.rows, paged=True)
        self.assertEqual(navigator.current_action(), ("reader", "0"))
        navigator.select_auto(0, 0)
        action, entry = navigator.current_action()
        self.assertEqual(action, "auto")
        self.assertEqual((entry[1], entry[2]), ("GB", "0"))

    def test_zero_chord_selects_auto_without_changing_normal_numbers(self):
        chord = ZeroChord()
        consumed, selected = chord.key_down("0", self.entries)
        self.assertTrue(consumed)
        self.assertIsNone(selected)
        consumed, selected = chord.key_down("1", self.entries)
        self.assertTrue(consumed)
        self.assertEqual(selected, self.entries[0])
        self.assertFalse(chord.zero_pressed)

    def test_zero_plus_7_and_8_still_selects_auto_not_page(self):
        chord = ZeroChord()
        chord.key_down("0", self.entries)
        self.assertEqual(chord.key_down("7", self.entries), (True, self.entries[6]))
        chord.key_down("0", self.entries)
        self.assertEqual(chord.key_down("8", self.entries), (True, self.entries[7]))

    def test_unmodified_7_and_8_are_left_for_page_mapping(self):
        chord = ZeroChord()
        self.assertEqual(chord.key_down("7", self.entries), (False, None))
        self.assertEqual(chord.key_down("8", self.entries), (False, None))
        self.assertEqual(resolve_menu_number(ROOT_MENU_TITLE, ROOT_OPTIONS, "7", paged=True), "[")

    def test_non_numeric_key_does_not_cancel_held_zero_modifier(self):
        chord = ZeroChord()
        self.assertEqual(chord.key_down("0", self.entries), (True, None))
        self.assertEqual(chord.key_down("", self.entries), (False, None))
        self.assertTrue(chord.zero_pressed)
        self.assertEqual(chord.key_down("4", self.entries), (True, self.entries[3]))
        self.assertFalse(chord.zero_pressed)

    def test_releasing_zero_cancels_a_pending_chord(self):
        chord = ZeroChord()
        chord.key_down("0", self.entries)
        chord.key_up("0")
        self.assertEqual(chord.key_down("1", self.entries), (False, None))

    def test_other_screens_do_not_reserve_zero(self):
        self.assertEqual(build_auto_entries("Game Boy", (("0", "Read ROM"),)), ())
        chord = ZeroChord()
        self.assertEqual(chord.key_down("0", ()), (False, None))
        self.assertFalse(chord.zero_pressed)

    def test_arrow_key_focus_scope_is_limited_to_operation_menu_group(self):
        menu = FakeWidget()
        row = FakeWidget(menu)
        external_button = FakeWidget()
        self.assertTrue(is_widget_within(menu, menu))
        self.assertTrue(is_widget_within(row, menu))
        self.assertFalse(is_widget_within(external_button, menu))

    def test_gui_uses_one_tab_stop_for_the_operation_menu(self):
        gui = (Path(__file__).with_name("cartreader_pc.py")
               .read_text(encoding="utf-8"))
        self.assertIn("menu_items = ttk.Frame(menu_panel, takefocus=1)", gui)
        self.assertIn("menu_items.configure(takefocus=1)", gui)
        self.assertIn("is_widget_within(event.widget, menu_items)", gui)
        self.assertIn("takefocus=0", gui)
        self.assertIn('if key == "tab":', gui)

    def test_gui_keeps_one_click_auto_buttons_inline_and_single_highlight(self):
        gui = (Path(__file__).with_name("cartreader_pc.py")
               .read_text(encoding="utf-8"))
        self.assertIn('button = tk.Button(\n                    row_frame, text=f"0+{shortcut}  {button_label}"', gui)
        self.assertIn("command=lambda e=entry, r=position, a=auto_index:", gui)
        self.assertIn("if auto_index is None:", gui)
        self.assertIn("elif root_menu and navigator is not None:", gui)
        self.assertNotIn("auto_panel = ttk.LabelFrame", gui)

    def test_page_buttons_drop_left_right_parenthetical_hints(self):
        gui = (Path(__file__).with_name("cartreader_pc.py")
               .read_text(encoding="utf-8"))
        self.assertIn('text="7  ◀ 前のページ"', gui)
        self.assertIn('text="8  次のページ ▶"', gui)
        self.assertNotIn("前のページ (←)", gui)
        self.assertNotIn("次のページ (→)", gui)

    def test_page_and_auto_labels_translate_for_english(self):
        translator = UiTranslator(None, FakeLanguage("English"))
        self.assertEqual(translator.translate("7  ◀ 前のページ"), "7  ◀ Previous page")
        self.assertEqual(translator.translate("8  次のページ ▶"), "8  Next page ▶")
        self.assertEqual(
            translator.translate("[自動吸出し] GB 自動吸出しを開始"),
            "[Auto dump] GB Auto dump started",
        )

    def test_auto_hint_and_user_logs_remain_japanese_in_japanese_mode(self):
        translator = UiTranslator(None, FakeLanguage("Japanese"))
        self.assertEqual(translator.translate("自動吸出し（0を押しながら1〜8）"),
                         "自動吸出し（0を押しながら1〜8）")
        self.assertEqual(translator.translate("◀ 前のページ"), "◀ 前のページ")

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
