"""Automatic-dump row mapping and keyboard navigation for the PC UI."""

ROOT_MENU_TITLE = "OPEN SOURCE CART READER"

AUTO_TARGETS_BY_MENU = {
    "Game Boy": (
        ("GB", "Game Boy (Color)"),
        ("GBA", "GB Advance (3V)"),
    ),
    "NES/Famicom": (("NES", "NES/Famicom"),),
    "Super Nintendo/SFC": (("SNES", "Super Nintendo/SFC"),),
    "Nintendo 64 (3V)": (("N64", "Nintendo 64 (3V)"),),
    "Mega Drive/Genesis": (("MD", "Mega Drive/Genesis"),),
    "PC Engine/TG16": (
        ("PCE_SWAP", "HuCARD(swapped)"),
        ("PCE_RAW", "HuCARD(not swapped)"),
    ),
}


def is_main_menu(title):
    return title == ROOT_MENU_TITLE


def build_menu_rows(title, options, paged=False):
    """Build UI rows without changing the reader's original option numbers."""
    root_menu = is_main_menu(title)
    rows = []
    next_shortcut = 1
    display_digits = [
        str(number) for number in range(1, 10)
        if not (paged and number in (7, 8))
    ]
    for position, (reader_number, label) in enumerate(options):
        auto_entries = []
        if root_menu:
            for target, display_name in AUTO_TARGETS_BY_MENU.get(label, ()):
                if next_shortcut <= 8:
                    shortcut = str(next_shortcut)
                    auto_entries.append((
                        shortcut, target, str(reader_number),
                        f"Auto: {display_name}",
                    ))
                    next_shortcut += 1
        rows.append({
            "reader_number": str(reader_number),
            "display_number": (
                display_digits[position] if root_menu and position < len(display_digits)
                else ("" if root_menu else str(reader_number))
            ),
            "label": str(label),
            "auto_entries": tuple(auto_entries),
        })
    return tuple(rows)


def build_auto_entries(title, options, paged=False):
    """Return Auto shortcuts in visible row order for the existing 0+digit chord."""
    return tuple(
        entry
        for row in build_menu_rows(title, options, paged)
        for entry in row["auto_entries"]
    )


def resolve_menu_number(title, options, digit, paged=False):
    """Map a displayed digit to the reader command; None means no direct command."""
    digit = str(digit or "")
    if not digit or digit not in "0123456789":
        return None
    if is_main_menu(title):
        if digit == "0":
            return None
        if paged and digit == "7":
            return "["
        if paged and digit == "8":
            return "]"
        rows = build_menu_rows(title, options, paged)
        for row in rows:
            if row["display_number"] == digit:
                return row["reader_number"]
        return None
    if paged and digit == "7":
        return "["
    if paged and digit == "8":
        return "]"
    for number, _label in options:
        if str(number) == digit:
            return digit
    return None


class MenuNavigator:
    """Arrow-key selection across ordinary rows and their inline Auto actions."""
    def __init__(self, rows, paged=False):
        self.rows = tuple(rows)
        self.paged = bool(paged)
        self.row = 0
        self.auto_index = None
        self.preferred_auto_index = None

    def select_row(self, row_index):
        if self.rows:
            self.row = max(0, min(int(row_index), len(self.rows) - 1))
        self.auto_index = None
        self.preferred_auto_index = None

    def select_auto(self, row_index, auto_index):
        if not self.rows:
            return False
        row_index = max(0, min(int(row_index), len(self.rows) - 1))
        entries = self.rows[row_index]["auto_entries"]
        if not entries:
            return False
        self.row = row_index
        self.auto_index = max(0, min(int(auto_index), len(entries) - 1))
        self.preferred_auto_index = self.auto_index
        return True

    def select_auto_shortcut(self, shortcut):
        for row_index, row in enumerate(self.rows):
            for auto_index, entry in enumerate(row["auto_entries"]):
                if entry[0] == str(shortcut):
                    self.select_auto(row_index, auto_index)
                    return entry
        return None

    def current(self):
        return self.row, self.auto_index

    def current_action(self):
        if not self.rows:
            return None
        row = self.rows[self.row]
        if self.auto_index is None:
            return "reader", row["reader_number"]
        return "auto", row["auto_entries"][self.auto_index]

    def move_vertical(self, delta):
        if not self.rows:
            return
        self.row = (self.row + (1 if delta > 0 else -1)) % len(self.rows)
        if self.preferred_auto_index is not None:
            entries = self.rows[self.row]["auto_entries"]
            self.auto_index = (
                min(self.preferred_auto_index, len(entries) - 1) if entries else None
            )

    def move_horizontal(self, delta):
        if not self.rows:
            return None
        row_entries = self.rows[self.row]["auto_entries"]
        if delta < 0:
            if self.auto_index is not None:
                if self.auto_index > 0:
                    self.auto_index -= 1
                    self.preferred_auto_index = self.auto_index
                else:
                    self.auto_index = None
                    self.preferred_auto_index = None
            elif self.row == 0 and self.paged:
                return "previous-page"
            return None

        if self.auto_index is None:
            if row_entries:
                self.auto_index = 0
                self.preferred_auto_index = 0
            elif self.row == len(self.rows) - 1 and self.paged:
                return "next-page"
            return None

        if self.auto_index < len(row_entries) - 1:
            self.auto_index += 1
            self.preferred_auto_index = self.auto_index
        elif self.row == len(self.rows) - 1 and self.paged:
            return "next-page"
        return None


def normalize_digit(keysym, char="", keycode=None, windows=False):
    """Normalize top-row, full-width and numeric-keypad digits to one string."""
    key = str(keysym or "").lower()
    char = str(char or "")
    keypad = {f"kp_{number}": str(number) for number in range(10)}
    keypad.update({
        "kp_insert": "0", "kp_end": "1", "kp_down": "2",
        "kp_next": "3", "kp_left": "4", "kp_begin": "5",
        "kp_right": "6", "kp_home": "7", "kp_up": "8",
        "kp_prior": "9",
    })
    if windows and keycode is not None and 96 <= int(keycode) <= 105:
        return str(int(keycode) - 96)
    if windows and keycode is not None and 48 <= int(keycode) <= 57:
        return str(int(keycode) - 48)
    if char and char in "0123456789":
        return char
    fullwidth = "０１２３４５６７８９"
    if char and char in fullwidth:
        return str(fullwidth.index(char))
    if key and key in "0123456789":
        return key
    return keypad.get(key, "")


def move_focus_from_group(group_widget, backwards=False):
    """Move Tab focus to the next/previous widget outside a grouped menu."""
    target = (
        group_widget.tk_focusPrev() if backwards
        else group_widget.tk_focusNext()
    )
    if target is not None:
        target.focus_set()
    return target


def is_widget_within(widget, ancestor):
    """Return whether a Tk widget is the group itself or one of its descendants."""
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "master", None)
    return False


def display_auto_reason(reason):
    """Rename legacy internal batch wording only in the user-facing copy."""
    return (str(reason)
            .replace("一括吸出し", "自動吸出し")
            .replace("一括停止", "自動吸出し停止")
            .replace("一括操作", "自動吸出し"))


class ZeroChord:
    """Use a held 0 key as an Auto modifier without changing other menus."""
    def __init__(self):
        self.zero_pressed = False

    def reset(self):
        self.zero_pressed = False

    def key_down(self, digit, entries):
        digit = str(digit or "")
        if digit == "0" and entries:
            self.zero_pressed = True
            return True, None
        if self.zero_pressed:
            if not digit or digit not in "123456789":
                # Navigation keys pass through without cancelling a held 0.
                return False, None
            self.zero_pressed = False
            for entry in entries:
                if entry[0] == digit:
                    return True, entry
            return True, None
        return False, None

    def key_up(self, digit):
        if str(digit or "") == "0":
            self.zero_pressed = False
