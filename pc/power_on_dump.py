"""One pending automatic dump per observed reader startup, never per menu."""
from batch_dump import BatchDump

TARGETS = (
    ("GB", "Game Boy (Color)"),
    ("GBA", "GB Advance (3V)"),
    ("NES", "NES/Famicom"),
    ("SNES", "Super Nintendo/SFC"),
    ("N64", "Nintendo 64 (3V)"),
    ("MD", "Mega Drive/Genesis"),
    ("PCE_SWAP", "PC Engine/TG16 - HuCARD(swapped)"),
    ("PCE_RAW", "PC Engine/TG16 - HuCARD(not swapped)"),
)


class PowerOnDump:
    def __init__(self, settings):
        self.enabled = settings.get("power_on_dump_enabled") is True
        target = settings.get("power_on_dump_target", "GB")
        self.target = target if isinstance(target, str) and target in dict(TARGETS) else "GB"
        self.pending = False
        self.seen_pages = set()

    def configure(self, enabled, target):
        self.enabled = bool(enabled)
        self.target = target if isinstance(target, str) and target in dict(TARGETS) else "GB"
        self.cancel()  # Settings changes apply to the next startup only.

    def settings(self):
        return {"power_on_dump_enabled": self.enabled,
                "power_on_dump_target": self.target}

    def reader_started(self, suppressed=False):
        self.cancel()
        self.pending = self.enabled and not suppressed

    def disconnected(self):
        self.cancel()

    def cancel(self):
        self.pending = False
        self.seen_pages.clear()

    def menu_action(self, title, options, paged, storage="PC"):
        if not self.pending or title != "OPEN SOURCE CART READER":
            return None
        if storage != "PC":
            self.cancel()
            return ("stop", "BootDumpにはPC保存を選択してください。")
        signature = tuple(options)
        if signature in self.seen_pages:
            self.cancel()
            return ("stop", "指定機種が本体メニューに見つかりません。")
        self.seen_pages.add(signature)
        wanted = BatchDump.ROOT_NAMES[self.target]
        for number, label in options:
            if label == wanted:
                target = self.target
                self.cancel()  # Consume before starting, including errors.
                return ("start", target, number)
        if paged:
            return ("page", "]")
        self.cancel()
        return ("stop", "指定機種が本体メニューに見つかりません。")
