"""Presentation-only dump outcome; never drives cartridge or storage operations."""
import re


class DumpResult:
    COLORS = {"idle": "white", "success": "#86EFAC", "failure": "#FCA5A5"}

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "idle"
        self.active = False
        self.batch = False
        self.saved = False
        self.failed = False

    def begin_batch(self):
        self.reset()
        self.batch = True

    def finish_batch(self, success):
        self.batch = False
        self.active = False
        self.state = "success" if success and not self.failed else "failure"

    def feed(self, line):
        line = line.strip()
        if line in ("[+] Read ROM", "[+] Read iNES Rom", "[+] Read Cart", "[+] Read Save", "[+] Read SRAM"):
            if not self.batch:
                self.reset()
            self.active = True
            self.saved = False
        if not (self.active or self.batch):
            return
        if (line.startswith(("[CANCELLED]", "[Disconnected", "[RECONNECT]"))
                or line == "[SD Browser] copy cancelled"):
            if self.batch:
                self.failed = True
                self.state = "failure"
            else:
                self.active = False
                self.state = "idle"
            return
        # Restrict error matching to status lines: filenames may contain ERROR.
        if (line.startswith(("[ERROR", "Error:", "Fatal error", "SD Error", "Cartridge Error", "GAMEPAK ERROR", "HEADER CHECKSUM ERROR"))
                or (line.startswith(("[VERIFY]", "Checksum:", "Internal checksum", "Checksum", "CRC32"))
                    and re.search(r"MISMATCH|\bError\b|\bERROR\b|\bFAIL(?:ED)?\b", line))):
            self.failed = True
            self.state = "failure"
        if line.startswith("[SAVED] "):
            match = re.fullmatch(r"\[SAVED\] (.+) \((\d+) bytes\) SHA256=[0-9a-fA-F]+", line)
            if match and not match[1].lower().endswith(".txt"):
                if int(match[2]) > 0:
                    self.saved = True
                else:
                    self.failed = True
                    self.state = "failure"
        if line.startswith("[VERIFY] CRC32=") or line.startswith("CRC32..."):
            self.saved = True
        if line.startswith(("Checksum:", "Checksum", "Internal checksum")) and re.search(r"\bOK\b", line):
            self.saved = True
        if line == "Press Button..." or line == "[Reader] press button ready":
            if not self.batch:
                if self.failed:
                    self.state = "failure"
                elif self.saved:
                    self.state = "success"
                self.active = False
