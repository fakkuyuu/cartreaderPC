"""Conservative one-click ROM then SAVE operation for the PC88 GUI.

The firmware remains the authority for cartridge recognition and read operations.
Only named, observed menu choices are sent; manual selection is never guessed.
"""

import re


class BatchDump:
    # Explicitly distinguish a ROM payload from its companion .txt report.
    # Storage emits [SAVED] for BOTH; directory alone is insufficient.
    ROM_EXTENSIONS = {
        "GB": (".gb", ".gbc"), "GBA": (".gba",),
        "SNES": (".sfc", ".smc"), "MD": (".md", ".bin", ".gen"),
        "N64": (".z64", ".n64", ".v64"), "NES": (".nes",),
        "PCE_SWAP": (".pce",), "PCE_RAW": (".pce",),
        "WS": (".ws", ".wsc"),
    }
    ROOT_NAMES = {
        "GB": "Game Boy", "GBA": "Game Boy",
        "SNES": "Super Nintendo/SFC", "MD": "Mega Drive/Genesis",
        "N64": "Nintendo 64 (3V)", "NES": "NES/Famicom",
        "PCE_SWAP": "PC Engine/TG16",
        "PCE_RAW": "PC Engine/TG16",
        "WS": "WonderSwan (3V)",
    }
    READ_MENUS = {
        "GB": "GB Cart Reader",
        "GBA": "GBA Cart Reader",
        "SNES": "SNES Cart Reader",
        "MD": "MEGA DRIVE Reader",
        "N64": "N64 Cart Reader",
        "NES": "NES CART READER",
        "PCE_SWAP": "PCE HuCARD menu",
        "PCE_RAW": "PCE HuCARD menu",
        "WS": "WS Menu",
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
        self.db_says_no_save = False
        self.gba_candidate_seen = False
        self.gba_candidate_selected = False
        self.nes_database_search_seen = False
        self.nes_manual_selection = False
        self.nes_candidate_seen = False
        self.nes_candidate_selected = False
        self.n64_rom_bytes = None
        self.n64_save_type_seen = False
        self.n64_crc1_seen = False
        self.ws_checksum_matches = False
        self.reason = ""
        self.db_match = None
        self.save_failure_after_rom = False

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
        self.db_says_no_save = False
        self.gba_candidate_seen = False
        self.gba_candidate_selected = False
        self.nes_database_search_seen = False
        self.nes_manual_selection = False
        self.nes_candidate_seen = False
        self.nes_candidate_selected = False
        self.n64_rom_bytes = None
        self.n64_save_type_seen = False
        self.n64_crc1_seen = False
        self.ws_checksum_matches = False
        self.reason = ""
        self.db_match = None
        self.save_failure_after_rom = False

    def stop(self, reason):
        self.active = False
        self.phase = "idle"
        self.reason = reason
        return None

    def _stop_for_read_error(self, reason):
        # Only signal partial success when a verified ROM is already saved
        # and a known save type is currently being read. Disconnects,
        # cancellations, unexpected menus, and missing completion messages
        # deliberately remain ordinary fixed failures.
        if (self.phase == "save_read" and self.rom_saved and self.rom_verified
                and self.save is True and not self.save_saved):
            self.save_failure_after_rom = True
        return self.stop(reason)

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

    @staticmethod
    def _is_md_internal_checksum_error(line):
        # This is an explicit Mega Drive reader status, not a substring test:
        # filenames and database titles may legitimately contain "Error".
        return re.fullmatch(
            r"Internal checksum\s*\.{3}\s*Error",
            line.strip(),
            re.IGNORECASE,
        ) is not None

    def on_line(self, line):
        if not self.active:
            return
        if (self.target == "MD" and self.phase == "rom_read"
                and self._is_md_internal_checksum_error(line)):
            return self._stop_for_read_error(
                f"MD ROM内部チェックサム異常のため一括停止: {line[:100]}")
        if self.target == "WS" and self.phase == "rom_read":
            result = re.fullmatch(r"Result: ([0-9A-F]{4})\(([0-9A-F]{4})\) matches\.", line, re.I)
            if result:
                self.ws_checksum_matches = result.group(1).upper() == result.group(2).upper()
        if line.startswith(("[Disconnected", "[RECONNECT]", "[CANCELLED]")):
            return self.stop("通信切断・キャンセルのため一括停止")
        if (line.startswith(("Error:", "[ERROR", "HEADER CHECKSUM ERROR",
                             "Fatal error", "SD Error", "Cartridge Error"))
                or ("MISMATCH" in line and (line.startswith("[VERIFY]") or line.startswith("Checksum:")))
                or (line.startswith("No data found.") and
                    (self.target != "NES" or self.phase == "save_read"))
                or "CARTRIDGE ERROR" in line or "Checksum Error" in line
                or (self.target == "N64" and
                    ("GAMEPAK ERROR" in line or "Cartridge unknown" in line))):
            return self._stop_for_read_error(
                f"読み取り異常のため一括停止: {line[:100]}")
        if self.target == "NES" and self.phase == "entry":
            # A successful NES CRC lookup reaches the candidate browser
            # directly. Misses first print "Using manual selection" (or
            # "No data found.") before opening the alphabet/database browser.
            if line == "Searching database":
                self.nes_database_search_seen = True
            elif line in ("No data found.", "CRC not found in database",
                          "Using manual selection"):
                self.nes_manual_selection = True
                self.nes_candidate_seen = False
            elif line == "Select your cartridge":
                self.nes_candidate_seen = (
                    self.nes_database_search_seen and not self.nes_manual_selection)
        if self.phase in ("entry", "rom_menu"):
            if self.target == "N64" and self.phase == "rom_menu":
                if line.startswith("ROM Size:"):
                    found = re.fullmatch(r"(\d+)\s*MB", line.partition(":")[2].strip(), re.I)
                    if found and 0 < int(found.group(1)) <= 128:
                        # N64's ROM size is obtained from its CRC1 lookup in
                        # n64.txt. Never use the error path's fallback 2 MB.
                        self.n64_rom_bytes = int(found.group(1)) * 1024 * 1024
                elif line.startswith("CRC1:"):
                    self.n64_crc1_seen = bool(re.fullmatch(
                        r"[0-9a-fA-F]{8}", line.partition(":")[2].strip()))
            if self.target == "WS" and line.startswith("Save:"):
                value = line.partition(":")[2].strip()
                amount = re.fullmatch(r"(?:Sram|Eeprom) (\d+) Kb", value, re.I)
                self.save = False if value.casefold() == "none" else None
                self.save_expected_bytes = None
                if amount and int(amount.group(1)) > 0:
                    self.save = True
                    self.save_expected_bytes = int(amount.group(1)) * 128
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
                if self.target == "N64":
                    # N64.ino displays this only after a successful n64.txt
                    # ROM-size lookup. DB type 0 means no save.
                    known = {
                        "none/unknown": (False, None),
                        "sram": (True, 32768),
                        "sram 768": (True, 98304),
                        "flash": (True, 131072),
                        "4k eeprom": (True, 512),
                        "16k eeprom": (True, 2048),
                    }
                    if value in known:
                        self.n64_save_type_seen = True
                        self.save, self.save_expected_bytes = known[value]
                    else:
                        self.stop("N64のセーブ形式が未対応のため自動操作を停止")
                        return
                elif value == "none/unknown":
                    # GBA reports "None/Unknown" for both cases. A specific
                    # database Save Lib=None means no save is expected.
                    self.save = False if self.db_says_no_save else None
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
                if self.target == "GBA" and self.phase == "rom_menu":
                    # getCartInfo_GBA prints this field immediately before
                    # printInstructions() and [Control] physical-buttons.
                    self.gba_candidate_seen = bool(line.partition(":")[2].strip())
                if line.partition(":")[2].strip().lower() == "none":
                    self.db_says_no_save = True
                    self.save = False
            elif line.startswith("Sram:"):
                value = line.partition(":")[2].strip().lower()
                self.save = False if value == "none" or value == "0 kbit" else True
            elif line.startswith("PcConsole EEPROM:"):
                self.save = True
            elif line.startswith("RAM SIZE:") and self.target == "NES":
                # NES database-derived iNES 2.0 PRG nonvolatile RAM size.
                value = line.partition(":")[2].strip().lower()
                size = re.fullmatch(r"(\d+)\s*[bk]", value)
                if size:
                    self.save = int(size.group(1)) > 0
        if self.phase == "rom_read":
            if line.startswith("[SAVED] ") and "/ROM/" in line.upper():
                # storage.py also reports the companion .txt with [SAVED]
                # under the same /ROM/ directory. Ignore it entirely, rather
                # than replacing rom_saved or comparing its size to the ROM.
                # Match the final size/hash trailer, never an earlier
                # " (" inside a ROM filename or its parent directories.
                saved = re.fullmatch(
                    r"\[SAVED\] (?P<path>.+) \((?P<size>\d+) bytes\) SHA256=[0-9a-fA-F]+",
                    line)
                if saved is None:
                    return
                saved_path = saved.group("path")
                if not saved_path.lower().endswith(self.ROM_EXTENSIONS[self.target]):
                    return
                actual_size = int(saved.group("size"))
                self.rom_saved = actual_size > 0
                if (self.target == "N64" and self.n64_rom_bytes
                        and actual_size != self.n64_rom_bytes):
                    return self.stop("N64 ROMサイズ不一致。自動操作を停止")
            elif line.startswith("[VERIFY] CRC32="):
                self.rom_verified = True
                if line.endswith(" DB=no match"):
                    return self._stop_for_read_error("ROMのCRCがDBに一致しないため自動吸出しを停止")
                if "DB=not installed" in line:
                    self.db_match = False
                elif "DB=" in line:
                    self.db_match = True
        elif self.phase == "save_read":
            if line.startswith("[SAVED] ") and "/SAVE/" in line.upper() and not re.search(r"\.txt \(\d+ bytes\)", line, re.IGNORECASE):
                if self.target == "GBA":
                    # GBA's DB save helper also emits a metadata report. It
                    # can appear as an extensionless [SAVED] entry; its size
                    # must not overwrite the already-valid EEPROM save result.
                    saved = re.fullmatch(
                        r"\[SAVED\] (?P<path>.+) \((?P<size>\d+) bytes\) SHA256=[0-9a-fA-F]+",
                        line)
                    if (saved is None or
                            not saved.group("path").lower().endswith((".eep", ".srm", ".fla"))):
                        return
                size = re.search(r"\((\d+) bytes\)", line)
                if size:
                    actual = int(size.group(1))
                    if actual <= 0:
                        return self._stop_for_read_error("セーブファイルが0バイトでした")
                    if (self.save_expected_bytes is not None
                            and actual != self.save_expected_bytes):
                        return self._stop_for_read_error(
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
            if title == "Select N64 device" and self.target == "N64":
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
        return None

    def _choice_or_stop(self, options, name):
        value = self._choice(options, name)
        if value is None:
            return self.stop("指定された機種の項目がありません")
        self.phase = "rom_menu"
        return value

    def _after_rom(self, options):
        if self.target == "WS" and not self.ws_checksum_matches:
            return self.stop("WS ROMの内部チェックサム一致を確認できません")
        if self.target.startswith("PCE_"):
            self.save = False
        if self.save is None:
            return self.stop("ROM保存完了。セーブ有無が不明なため以降は手動操作")
        if self.save is False:
            return self.complete()
        value = self._choice(options, "Read Save")
        if value is None:
            return self.stop("セーブ読出し項目を確認できません")
        self.phase = "save_read"
        return value

    def on_candidate(self):
        """Accept a NES CRC-matched DB candidate once; never choose manually."""
        if not self.active:
            return None
        if (self.target == "NES" and self.phase == "entry"
                and self.nes_database_search_seen
                and self.nes_candidate_seen
                and not self.nes_manual_selection
                and not self.nes_candidate_selected):
            self.nes_candidate_selected = True
            return " "
        if self.target == "NES":
            return self.stop("NESのDB一致を確認できません。候補は手動選択してください")
        return self.stop("カートリッジの手動選択が必要です")

    def on_physical(self):
        """Confirm only an identified GBA database candidate; never guess elsewhere."""
        if not self.active:
            return None
        if (self.target == "GBA" and self.phase == "rom_menu"
                and self.gba_candidate_seen and not self.gba_candidate_selected):
            self.gba_candidate_selected = True
            return " "
        return self.stop("想定外の本体操作画面です。手動操作に切り替えてください")

    def on_press(self):
        if not self.active:
            return None
        if self.phase in ("entry", "rom_menu"):
            if (self.target == "NES" and self.phase == "entry"
                    and not self.nes_candidate_selected):
                return self.stop("NESのDB候補未確認。手動で確認してください")
            if (self.target == "GBA" and self.phase == "rom_menu"
                    and not self.gba_candidate_selected):
                return self.stop("GBAのゲーム情報確定前に操作待ちが発生しました。手動確認してください")
            if (self.target == "N64" and self.phase == "rom_menu"
                    and not (self.n64_rom_bytes is not None
                             and self.n64_save_type_seen and self.n64_crc1_seen)):
                # On n64.txt lookup failure N64.ino shows GAMEPAK ERROR,
                # waits, then supplies a provisional cartSize=2.
                # Do not acknowledge that error screen automatically.
                return self.stop("N64のDB照合が未完了。ROMサイズ・セーブ形式を手動確認してください")
            return " "
        if self.phase == "rom_read":
            if not (self.rom_saved and self.rom_verified):
                return self.stop("ROMの保存・検証が未完了です。自動で先へ進めません")
            if self.target == "WS" and not self.ws_checksum_matches:
                return self.stop("WS ROMの内部チェックサム一致を確認できません")
            if self.target.startswith("PCE_") or self.save is False:
                return self.complete()
            if self.save is None:
                return self.stop("ROM保存完了。セーブ有無が不明なため以降は手動操作")
            self.phase = "save_menu"
            return " "
        if self.phase == "save_read":
            if not self.save_saved:
                return self.stop("セーブ保存を確認できません")
            return self.complete()
        return None
