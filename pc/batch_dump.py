"""Conservative one-click ROM then SAVE operation for the PC88 GUI.

The firmware remains the authority for cartridge recognition and read operations.
Only named, observed menu choices are sent; manual selection is never guessed.
"""

import re


class BatchDump:
    ROOT_NAMES = {
        "GB": "Game Boy", "GBA": "Game Boy",
        "SNES": "Super Nintendo/SFC", "MD": "Mega Drive/Genesis",
        "NES": "NES/Famicom", "PCE_SWAP": "PC Engine/TG16",
        "PCE_RAW": "PC Engine/TG16",
    }
    READ_MENUS = {
        "GB": "GB Cart Reader",
        "GBA": "GBA Cart Reader",
        "SNES": "SNES Cart Reader",
        "MD": "MEGA DRIVE Reader",
        "NES": "NES CART READER",
        "PCE_SWAP": "PCE HuCARD menu",
        "PCE_RAW": "PCE HuCARD menu",
    }

    def __init__(self):
        self.active = False
        self.phase = "idle"
        self.target = ""
        self.save = None
        self.rom_saved = False
        self.rom_verified = False
        self.save_saved = False
        self.save_expected_bytes = None
        self.reason = ""
        self.db_match = None

    def begin(self, target):
        if target not in self.ROOT_NAMES:
            raise ValueError("unsupported batch target")
        self.active = True
        self.target = target
        self.phase = "entry"
        self.save = None
        self.rom_saved = False
        self.rom_verified = False
        self.save_saved = False
        self.save_expected_bytes = None
        self.reason = ""
        self.db_match = None

    def stop(self, reason):
        self.active = False
        self.phase = "idle"
        self.reason = reason
        return None

    def complete(self):
        detail = "ROM + SAVE" if self.save_saved else "ROM"
        if self.db_match is False:
            detail += "（DB照合なし）"
        return self.stop(f"一括吸出し完了: {detail}")

    @staticmethod
    def _choice(options, name):
        for number, label in options:
            if label.casefold() == name.casefold():
                return number
        return None

    def on_line(self, line):
        if not self.active:
            return
        if line.startswith(("[Disconnected", "[RECONNECT]", "[CANCELLED]")):
            return self.stop("通信切断・キャンセルのため一括停止")
        if (line.startswith(("Error:", "[ERROR", "HEADER CHECKSUM ERROR", "Fatal error"))
                or ("MISMATCH" in line and (line.startswith("[VERIFY]") or line.startswith("Checksum:")))
                or line.startswith("No data found.")):
            return self.stop(f"読み取り異常のため一括停止: {line[:100]}")
        if self.phase in ("entry", "rom_menu"):
            if line.startswith("Save Size:"):
                value = line.partition(":")[2].strip().lower()
                if value == "none" or value.startswith("0 kb"):
                    self.save = False
                elif value and value[0].isdigit():
                    self.save = True
                    amount = re.match(r"(\d+)\s*(kb|byte)", value)
                    if amount:
                        count = int(amount.group(1))
                        self.save_expected_bytes = count * (1024 if amount.group(2) == "kb" else 1)
            elif line.startswith("Save Type:"):
                value = line.partition(":")[2].strip().lower()
                if value == "none/unknown":
                    self.save = None
                elif value:
                    self.save = True
                    for prefix, expected in (
                        ("4k eeprom", 512), ("64k eeprom", 8192),
                        ("256k sram", 32768), ("512k sram", 65536),
                        ("512k flash", 65536), ("1m flash", 131072),
                    ):
                        if value.startswith(prefix):
                            self.save_expected_bytes = expected
                            break
            elif line.startswith("Save Lib:"):
                if line.partition(":")[2].strip().lower() == "none":
                    self.save = False
            elif line.startswith("Sram:"):
                value = line.partition(":")[2].strip().lower()
                self.save = False if value == "none" or value == "0 kbit" else True
            elif line.startswith("PcConsole EEPROM:"):
                self.save = True
            elif line.startswith("RAM SIZE:") and self.target == "NES":
                # NES database-derived iNES 2.0 PRG nonvolatile RAM size.
                value = line.partition(":")[2].strip().lower()
                size = re.match(r"(\d+)\s*k", value)
                if size:
                    self.save = int(size.group(1)) > 0
        if self.phase == "rom_read":
            if line.startswith("[SAVED] ") and "/ROM/" in line.upper():
                size = re.search(r"\((\d+) bytes\)", line)
                self.rom_saved = bool(size and int(size.group(1)) > 0)
            elif line.startswith("[VERIFY] CRC32="):
                self.rom_verified = True
                if "DB=no match" in line or "DB=not installed" in line:
                    self.db_match = False
                elif "DB=" in line:
                    self.db_match = True
        elif self.phase == "save_read":
            if line.startswith("[SAVED] ") and "/SAVE/" in line.upper():
                size = re.search(r"\((\d+) bytes\)", line)
                if size:
                    actual = int(size.group(1))
                    if actual <= 0:
                        return self.stop("セーブファイルが0バイトでした")
                    if (self.save_expected_bytes is not None
                            and actual != self.save_expected_bytes):
                        return self.stop(
                            f"セーブサイズ不一致: {actual} bytes "
                            f"(想定 {self.save_expected_bytes} bytes)")
                    self.save_saved = True

    def on_menu(self, title, options):
        if not self.active:
            return None
        if self.phase == "entry":
            if title == "Select Game Boy" and self.target in ("GB", "GBA"):
                return self._choice_or_stop(options,
                                            "Game Boy (Color)" if self.target == "GB" else "GB Advance (3V)")
            if self.target == "SNES" and self._choice(options, "SNES/SFC cartridge") is not None:
                return self._choice_or_stop(options, "SNES/SFC cartridge")
            if title == "Select MD device" and self.target == "MD":
                return self._choice_or_stop(options, "Game Cartridge")
            if title == "Select device" and self.target.startswith("PCE_"):
                return self._choice_or_stop(options,
                    "HuCARD(swapped)" if self.target == "PCE_SWAP" else "HuCARD(not swapped)")
            if title == self.READ_MENUS[self.target]:
                self.phase = "rom_menu"
            else:
                return self.stop("想定外のメニューです。以降は手動操作してください")
        if self.phase == "rom_menu":
            if title != self.READ_MENUS[self.target]:
                return self.stop("読出しメニューを確認できません。手動操作へ切替")
            name = "Read iNES Rom" if self.target == "NES" else "Read ROM"
            value = self._choice(options, name)
            if value is None:
                return self.stop("ROM読出し項目が見つかりません")
            self.phase = "rom_read"
            return value
        if self.phase == "rom_read":
            if title != self.READ_MENUS[self.target]:
                return self.stop("ROM完了後のメニューが想定外です")
            if not self.rom_saved or not self.rom_verified:
                return self.stop("ROMの保存・検証完了を確認できません")
            return self._after_rom(options)
        if self.phase == "save_menu":
            if title != self.READ_MENUS[self.target]:
                return self.stop("セーブ読出しメニューが想定外です")
            return self._after_rom(options)
        if self.phase == "save_read":
            if title != self.READ_MENUS[self.target]:
                return self.stop("セーブ読出し後のメニューが想定外です")
            if not self.save_saved:
                return self.stop("セーブファイル保存を確認できません")
            return self.complete()
        if self.phase == "final_menu":
            return self.complete()
        return None

    def _choice_or_stop(self, options, name):
        value = self._choice(options, name)
        if value is None:
            return self.stop("指定された機種の項目がありません")
        self.phase = "rom_menu"
        return value

    def _after_rom(self, options):
        if self.target.startswith("PCE_"):
            self.save = False
        if self.save is None:
            return self.stop("ROM保存完了。セーブ有無が不明なため以降は手動操作")
        if self.save is False:
            return self.complete()
        value = self._choice(options, "Read SRAM" if self.target == "SNES" else "Read Save")
        if value is None:
            return self.stop("セーブ読出し項目を確認できません")
        self.phase = "save_read"
        return value

    def on_press(self):
        if not self.active:
            return None
        if self.phase in ("entry", "rom_menu"):
            return " "
        if self.phase == "rom_read":
            if not (self.rom_saved and self.rom_verified):
                return self.stop("ROMの保存・検証が未完了です。自動で先へ進めません")
            self.phase = "save_menu"
            return " "
        if self.phase == "save_read":
            if not self.save_saved:
                return self.stop("セーブ保存を確認できません")
            self.phase = "final_menu"
            return " "
        return None
