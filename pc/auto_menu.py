"""Compact Auto-dump menu shortcuts and key-chord routing."""

ROOT_MENU_TITLE = "OPEN SOURCE CART READER"

# Existing reader menu labels are the source of the names shown on Auto buttons.
# The order here is only a fallback/order aid; visible menu order determines slots.
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


def build_auto_entries(title, options):
    """Return (shortcut, target, menu_number, label) entries for visible rows."""
    if title != ROOT_MENU_TITLE:
        return ()
    entries = []
    for number, label in options:
        for target, display_name in AUTO_TARGETS_BY_MENU.get(label, ()):
            if len(entries) >= 9:
                return tuple(entries)
            shortcut = str(len(entries) + 1)
            entries.append((shortcut, target, str(number), f"Auto: {display_name}"))
    return tuple(entries)


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
            if digit not in "123456789":
                # Non-numeric navigation keys remain ordinary operations and
                # must not cancel a held modifier.
                return False, None
            self.zero_pressed = False
            for entry in entries:
                if entry[0] == digit:
                    return True, entry
            # A chord with an unassigned digit is consumed, not sent as a
            # normal reader menu number.
            return True, None
        return False, None

    def key_up(self, digit):
        if str(digit or "") == "0":
            self.zero_pressed = False
