"""PC-side virtual SD, confined to the user-selected output directory."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import struct
import time
import zlib

ROM_DATABASES = {
    ".a52": ("5200.txt",),
    ".col": ("colv.txt",),
    ".u2": ("cps3.txt",),
    ".gb": ("gb.txt",), ".gbc": ("gb.txt",), ".gba": ("gba.txt",),
    ".int": ("intv.txt",), ".j64": ("jag.txt",), ".lnx": ("lynx.txt",),
    ".bin": ("md.txt", "32x.txt"), ".md": ("md.txt",), ".gen": ("md.txt",),
    ".z64": ("n64.txt",), ".n64": ("n64.txt",), ".v64": ("n64.txt",),
    ".nes": ("nes.txt",), ".min": ("pkmn.txt",), ".pcw": ("pcw.txt",),
    ".pce": ("pce.txt",), ".sms": ("sms.txt",), ".gg": ("gg.txt",),
    ".sg": ("sg1000.txt",), ".sfc": ("snes.txt",), ".smc": ("snes.txt",),
    ".st": ("st.txt",), ".vb": ("vb.txt",), ".ws": ("ws.txt",),
    ".wsc": ("ws.txt",), ".sv": ("wsv.txt",),
}


class Storage:
    def __init__(self, root, log=print, keys=None, preferred_baud=250000,
                 dump_baud=250000, cancel_event=None, progress=None,
                 host_state=None, transfer_block=512):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.cwd = self.root
        self.handles = {}
        self.log = log
        self.keys = keys if keys is not None else queue.Queue()
        self.manifest = {}
        self.hello = False
        self.pending_input = bytearray()
        self.input_backlog = bytearray()
        self.preferred_baud = preferred_baud
        self.dump_baud = dump_baud
        self.transfer_block = transfer_block if transfer_block in (512, 1024) else 512
        self.cancel_event = cancel_event
        self.progress = progress
        self.console_text = ""
        self.last_verification = ""
        self.last_rom_path = None
        self.host_state = host_state if host_state is not None else {}
        self.console_pending = ""

    @staticmethod
    def _companion_log_line(line):
        """Keep user-facing dump information; drop transport/UI telemetry."""
        stripped = line.lstrip("\r")
        internal = (
            "[LED]", "[LED Activity]", "[Control]", "[Benchmark]",
            "[Baud]", "[Storage Mode]", "[SD Browser]", "[SD Entry]",
            "[SD Progress]", "[Reader]", "[Input]",
        )
        return not stripped.startswith(internal)

    def append_console_log(self, text):
        self.console_pending += text
        while "\n" in self.console_pending:
            line, self.console_pending = self.console_pending.split("\n", 1)
            complete = line + "\n"
            if self._companion_log_line(complete):
                self.console_text = (self.console_text + complete)[-65536:]

    def path(self, raw):
        name = raw.decode("utf-8", errors="strict")
        if "\\" in name or ":" in name or "\x00" in name:
            raise ValueError("invalid path")
        relative = PurePosixPath(name)
        base = self.root if relative.is_absolute() else self.cwd
        target = base.joinpath(*[p for p in relative.parts if p != "/"]).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("path outside session")
        # Avoid Windows device/alternate-stream aliases and metadata collisions.
        for part in target.relative_to(self.root).parts:
            if part.endswith((".", " ")) or part.lower() in {".pc-manifest.json", ".pc-manifest.tmp", ".pc-session"}:
                raise ValueError("reserved path")
            stem = part.split(".")[0].upper()
            if stem in {"CON", "PRN", "AUX", "NUL"} or stem in {f"{s}{i}" for s in ("COM", "LPT") for i in range(1, 10)}:
                raise ValueError("reserved device")
        return target

    def record(self):
        tmp = self.root / ".pc-manifest.tmp"
        tmp.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.root / ".pc-manifest.json")

    @staticmethod
    def _snes_header(data):
        """Return (stored checksum, chip byte) from the most plausible SNES header."""
        candidates = []
        for start in (0x7FB0, 0xFFB0, 0x40FFB0):
            if start + 0x30 > len(data):
                continue
            complement = int.from_bytes(data[start + 0x2C:start + 0x2E], "little")
            checksum = int.from_bytes(data[start + 0x2E:start + 0x30], "little")
            map_mode = data[start + 0x25] & 0x0F
            score = 2 if ((complement + checksum) & 0xFFFF) == 0xFFFF else 0
            score += 1 if map_mode in (0, 1, 2, 3, 5, 10) else 0
            candidates.append((score, checksum, data[start + 0x26]))
        return max(candidates, default=(0, None, None), key=lambda item: item[0])[1:]

    @staticmethod
    def _snes_checksum(data, chips=None):
        """Match the firmware's mirrored-ROM checksum rules, without USB rereads."""
        size = len(data)
        mbit = size * 8 // 1024 // 1024
        total = sum(data)
        if mbit in (10, 12, 20, 24):
            base = 2 * 1024 * 1024 if mbit > 16 else 1024 * 1024
            mirror = size - base
            if mbit == 24 and chips == 245:
                total *= 2
            elif mirror > 0:
                total = sum(data[:base]) + (base // mirror) * sum(data[base:])
        elif mbit == 40 and chips == 85:
            total = sum(data[:4 * 1024 * 1024]) + 4 * sum(data[4 * 1024 * 1024:])
        elif mbit == 48:
            total = sum(data[:4 * 1024 * 1024]) + 2 * sum(data[4 * 1024 * 1024:])
        return total & 0xFFFF

    def verify_rom(self, path):
        """Verify a completed ROM and search its database entirely on the PC."""
        suffix = path.suffix.lower()
        database_names = ROM_DATABASES.get(suffix)
        if not database_names:
            return 0
        crc = 0
        rom_data = bytearray() if suffix in (".sfc", ".smc") else None
        offset = 16 if suffix == ".nes" else (64 if suffix == ".lnx" else 0)
        with path.open("rb") as source:
            if offset:
                source.seek(offset)
            for block in iter(lambda: source.read(1024 * 1024), b""):
                crc = zlib.crc32(block, crc)
                if rom_data is not None:
                    rom_data.extend(block)
        crc_text = f"{crc & 0xffffffff:08X}"
        match = None
        for database_name in database_names:
            database = self.root / database_name
            if not database.is_file():
                continue
            previous = ""
            with database.open("r", encoding="utf-8", errors="replace") as rows:
                for row in rows:
                    line = row.strip()
                    upper = line.upper()
                    if crc_text in upper.split(","):
                        match = previous
                        break
                    if line:
                        previous = line
            if match:
                break
        result = f"[VERIFY] CRC32={crc_text}"
        checksum_ok = True
        if rom_data is not None:
            stored, chips = self._snes_header(rom_data)
            calculated = self._snes_checksum(rom_data, chips)
            if stored is None:
                result += f"  SNES-CHECKSUM={calculated:04X} (header not found)"
            else:
                checksum_ok = calculated == stored
                state = "OK" if calculated == stored else f"MISMATCH header={stored:04X}"
                result += f"  SNES-CHECKSUM={calculated:04X} {state}"
        result += f"  DB={match}" if match else "  DB=no match"
        if match:
            safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(match).name).rstrip(". ")
            # Match the original firmware: a CRC database hit supplies the
            # complete canonical filename, including its extension.
            if safe_name:
                renamed = path.with_name(safe_name)
                if renamed != path:
                    if renamed.exists():
                        result += "  RENAME=skipped (target exists)"
                    else:
                        old_name = path.relative_to(self.root).as_posix()
                        path.rename(renamed)
                        new_name = renamed.relative_to(self.root).as_posix()
                        self.manifest[new_name] = self.manifest.pop(old_name)
                        self.record()
                        result += f"  RENAMED={new_name}"
                        path = renamed
        self.last_verification = result
        self.last_rom_path = path
        self.log(result + "\n")
        return 1 if match and checksum_ok else (3 if not checksum_ok else 2)

    def verify_msx(self, path):
        """Name an MSX dump from its selected database title and record CRC32."""
        crc = 0
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                crc = zlib.crc32(block, crc)
        result = f"[VERIFY] CRC32={crc & 0xffffffff:08X}  DB=not installed"
        title = self.host_state.pop("msx_title", "")
        if title:
            safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).rstrip(". ")
            if safe_name:
                renamed = path.with_name(safe_name + path.suffix.lower())
                if renamed != path and not renamed.exists():
                    old_name = path.relative_to(self.root).as_posix()
                    path.rename(renamed)
                    new_name = renamed.relative_to(self.root).as_posix()
                    self.manifest[new_name] = self.manifest.pop(old_name)
                    self.record()
                    result += f"  SELECTED={title}  RENAMED={new_name}"
                    path = renamed
                elif renamed.exists() and renamed != path:
                    result += "  RENAME=skipped (target exists)"
        self.last_verification = result
        self.last_rom_path = path
        self.log(result + "\n")
        return 2

    def write_companion_log(self, rom_path):
        """Create the dump TXT on the PC without a second reader-side stream."""
        path = self.last_rom_path if self.last_rom_path is not None else rom_path
        companion = path.with_suffix(".txt")
        if self.console_pending and self._companion_log_line(self.console_pending):
            self.console_text = (self.console_text + self.console_pending)[-65536:]
        self.console_pending = ""
        body = self.console_text.rstrip() + "\n\n" + self.last_verification + "\n"
        companion.write_text(body, encoding="utf-8")
        digest = hashlib.sha256(companion.read_bytes()).hexdigest()
        name = companion.relative_to(self.root).as_posix()
        self.manifest[name] = {"state": "closed", "bytes": companion.stat().st_size, "sha256": digest}
        self.record()
        self.log(f"\n[SAVED] {name} ({companion.stat().st_size} bytes) SHA256={digest}\n")
        self.console_text = ""

    def allocate(self, path, flags=1):
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("directory entry outside session")
        if len(self.handles) >= 16:
            raise OSError("too many open files")
        write = bool(flags & 2)
        if path.is_dir():
            if write:
                raise IsADirectoryError(path)
            entry = {"path": path, "file": None, "entries": sorted(path.iterdir()), "index": 0, "write": False}
        else:
            if flags & 8 and not write:
                raise ValueError("truncate requires write")
            if not path.exists() and not (flags & 4 and write):
                raise FileNotFoundError(path)
            mode = "w+b" if write and (flags & 8 or not path.exists()) else ("r+b" if write else "rb")
            f = path.open(mode)
            entry = {"path": path, "file": f, "write": write,
                     "transfer_start": None, "transfer_bytes": 0,
                     "transfer_last_time": None, "transfer_last_bytes": 0}
            if write:
                name = path.relative_to(self.root).as_posix()
                self.manifest[name] = {"state": "incomplete"}
                try:
                    self.record()
                except Exception:
                    f.close()
                    raise
        handle = next(i for i in range(1, 256) if i not in self.handles)
        self.handles[handle] = entry
        size = path.stat().st_size if entry["file"] else 0
        if size > 0xffffffff:
            self.close_handle(handle)
            raise ValueError("file too large")
        kind = (0 if entry["file"] else 1) | (2 if path.name.startswith(".") else 0)
        return bytes((handle, kind)) + struct.pack("<I", size)

    def close_handle(self, handle, complete=True):
        entry = self.handles[handle]
        f = entry["file"]
        if f:
            if entry["write"]:
                f.flush()
                os.fsync(f.fileno())
            f.close()
        if entry["write"] and complete:
            path = entry["path"]
            if entry["transfer_start"] is not None:
                elapsed = max(time.monotonic() - entry["transfer_start"], 0.001)
                average = entry["transfer_bytes"] / elapsed / 1024
                self.log(f"[Transfer complete]\t{entry['transfer_bytes']}\t{elapsed:.3f}\t{average:.1f}\n")
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            name = path.relative_to(self.root).as_posix()
            self.manifest[name] = {"state": "closed", "bytes": path.stat().st_size, "sha256": digest}
            self.record()
            self.log(f"\n[SAVED] {name} ({path.stat().st_size} bytes) SHA256={digest}\n")
            relative_parts = path.relative_to(self.root).parts
            is_msx_rom = (relative_parts and relative_parts[0].upper() == "MSX" and
                          path.suffix.lower() == ".bin")
            verify_code = self.verify_msx(path) if is_msx_rom else self.verify_rom(path)
            if path.suffix.lower() in ROM_DATABASES or is_msx_rom:
                self.write_companion_log(path)
        else:
            verify_code = 0
        del self.handles[handle]
        return verify_code

    def track_write(self, entry, count):
        now = time.monotonic()
        if entry["transfer_start"] is None:
            entry["transfer_start"] = now
            entry["transfer_last_time"] = now
        entry["transfer_bytes"] += count
        interval = now - entry["transfer_last_time"]
        if interval >= 5.0:
            delta = entry["transfer_bytes"] - entry["transfer_last_bytes"]
            current = delta / interval / 1024
            elapsed = max(now - entry["transfer_start"], 0.001)
            average = entry["transfer_bytes"] / elapsed / 1024
            if self.progress is not None:
                self.progress(entry["transfer_bytes"], current, average)
            entry["transfer_last_time"] = now
            entry["transfer_last_bytes"] = entry["transfer_bytes"]

    def dispatch(self, op, p):
        if op == 10 and p and p[0] in self.handles:
            e = self.handles[p[0]]
            if e["file"] is None and e["index"] >= len(e["entries"]):
                return b"\1"  # normal directory EOF
        try:
            return b"\0" + self.execute(op, p)
        except FileNotFoundError as exc:
            if op == 8:  # exists() returning false is normal, not an error log.
                return b"\1"
            self.log(f"\n[ERROR op={op}] {exc}\n")
            return b"\1"
        except (OSError, ValueError, KeyError, UnicodeError, struct.error) as exc:
            self.log(f"\n[ERROR op={op}] {exc}\n")
            return b"\1"

    def execute(self, op, p):
        if op == 1:
            if self.hello or p:
                raise ValueError("reset detected: reconnect to create a fresh session")
            self.hello = True
            self.log("[Connected: CRPC v1 / 250000 baud]\n")
            # Keep checkpoints near 16 KiB for either negotiated frame size.
            checkpoint_blocks = 16 if self.transfer_block == 1024 else 32
            self.log(f"[Transfer block] {self.transfer_block} bytes\n")
            return struct.pack("<IIBH", self.preferred_baud, self.dump_baud,
                               checkpoint_blocks, self.transfer_block)
        if not self.hello:
            raise ValueError("HELLO required")
        if op == 2:
            if not p or p[0] & ~31 or not p[0] & 3:
                raise ValueError("invalid open flags")
            return self.allocate(self.path(p[1:]), p[0])
        if op in (6, 7, 8, 9):
            path = self.path(p)
            if op == 6:
                if not path.is_dir():
                    raise NotADirectoryError(path)
                self.cwd = path
            elif op == 7:
                path.mkdir(parents=True, exist_ok=True)
            elif op == 8:
                if not path.exists():
                    raise FileNotFoundError(path)
            else:
                path.unlink()
                self.manifest.pop(path.relative_to(self.root).as_posix(), None)
                self.record()
            return b""
        if op == 13:
            text = p.decode("utf-8", errors="replace")
            self.append_console_log(text)
            self.log(text)
            return b""
        if op == 14:
            if self.pending_input:
                return bytes(self.pending_input)
            while len(self.input_backlog) < 64:
                try:
                    item = self.keys.get_nowait()
                except queue.Empty:
                    break
                if isinstance(item, int):
                    self.input_backlog.append(item)
                else:
                    self.input_backlog.extend(bytes(item))
            data = self.input_backlog[:64]
            del self.input_backlog[:len(data)]
            self.pending_input = bytearray(data)
            return bytes(data)
        if op == 19:
            if p and self.pending_input[:len(p)] == p:
                del self.pending_input[:len(p)]
                shown = ("<detach>" if p == b"\x04" else
                         p.decode("ascii", errors="replace").replace("\r", "\\r").replace("\n", "\\n"))
                self.log(f"[Input] acknowledged by reader: {shown}\n")
            return b""
        if op == 20:
            self.log("[Reader] input ready\n")
            return b""
        if op == 23:
            self.log("[Reader] press button ready\n")
            return b""
        if op == 21:
            if len(p) < 4:
                raise ValueError("invalid database search")
            entry = self.handles[p[0]]
            f = entry["file"]
            if f is None or entry["write"]:
                raise ValueError("database search requires readable file")
            field = p[1]
            keys = [part for part in p[2:].split(b"\0") if part]
            if not keys:
                raise ValueError("database search key missing")
            f.seek(0)
            found = 0xffffffff
            while True:
                record_start = f.tell()
                name = f.readline()
                if not name:
                    break
                data = f.readline().rstrip(b"\r\n")
                f.readline()
                if field == 255:
                    matched = any(key in data for key in keys)
                else:
                    fields = data.split(b",")
                    matched = field < len(fields) and any(fields[field] == key for key in keys)
                if matched:
                    found = record_start
                    break
            self.log(f"[PC DB] {entry['path'].name}: {'found' if found != 0xffffffff else 'not found'}\n")
            return struct.pack("<I", found)
        if op == 18:
            return p
        if op == 24:
            if len(p) != 512:
                raise ValueError("invalid dump-path benchmark length")
            pattern = p[0] ^ 0x5A
            if any(value != ((index ^ pattern ^ 0x5A) & 0xff)
                   for index, value in enumerate(p)):
                raise ValueError("dump-path benchmark data mismatch")
            return b""
        if op == 17:
            if len(p) not in (4, 5) or int.from_bytes(p[:4], "little") not in (250000, 285714, 333333, 400000, 500000, 666667, 1000000, 2000000):
                raise ValueError("unsupported baud")
            if len(p) == 5 and p[4] != 1:
                raise ValueError("invalid baud switch mode")
            return b""
        if not p:
            raise ValueError("missing handle")
        entry = self.handles[p[0]]
        f = entry["file"]
        if op == 3:
            return bytes((self.close_handle(p[0]),))
        elif op == 4:
            if len(p) != 7 or f is None:
                raise ValueError("invalid read")
            offset, count = struct.unpack("<IH", p[1:])
            if count > 512:
                raise ValueError("read too large")
            f.seek(offset)
            return f.read(count)
        elif op in (5, 22):
            if not 5 <= len(p) <= 1029 or not entry["write"]:
                raise ValueError("invalid write")
            offset, = struct.unpack("<I", p[1:5])
            f.seek(offset)
            count = f.write(p[5:])
            self.track_write(entry, count)
            response = struct.pack("<H", count)
            if op == 5:
                cancelled = bool(self.cancel_event and self.cancel_event.is_set())
                if cancelled:
                    self.cancel_event.clear()
                    # PC38 understands the optional cancellation byte.  Keep
                    # ordinary acknowledgements byte-for-byte compatible with
                    # PC37 and older firmware.
                    response += b"\x01"
            return response
        elif op == 25:
            if len(p) != 5 or not entry["write"] or f is None:
                raise ValueError("invalid stream checkpoint")
            expected, = struct.unpack("<I", p[1:5])
            f.flush()
            committed = f.tell()
            if committed != expected:
                raise OSError(f"stream checkpoint mismatch expected={expected} committed={committed}")
            cancelled = bool(self.cancel_event and self.cancel_event.is_set())
            if cancelled:
                self.cancel_event.clear()
            return struct.pack("<I", committed) + bytes((cancelled,))
        elif op == 10:
            if f is not None:
                raise ValueError("directory required")
            index = entry["index"]
            if index >= len(entry["entries"]):
                raise FileNotFoundError("end of directory")
            entry["index"] += 1
            return self.allocate(entry["entries"][index])
        elif op == 11:
            entry["index"] = 0
        elif op == 15:
            return entry["path"].name.encode("utf-8")[:260]
        elif op == 16:
            target = self.path(p[1:])
            if target.exists():
                raise FileExistsError(target)
            previous = entry["path"]
            if f:
                f.flush()
                f.close()
            try:
                previous.rename(target)
            except OSError:
                if f:
                    entry["file"] = previous.open("r+b" if entry["write"] else "rb")
                raise
            entry["path"] = target
            if f:
                entry["file"] = target.open("r+b" if entry["write"] else "rb")
            old = previous.relative_to(self.root).as_posix()
            if old in self.manifest:
                self.manifest[target.relative_to(self.root).as_posix()] = self.manifest.pop(old)
                self.record()
        else:
            raise ValueError("unknown opcode")
        return b""

    def shutdown(self):
        had_incomplete = any(entry.get("write") for entry in self.handles.values())
        for handle in list(self.handles):
            try:
                self.close_handle(handle, complete=False)
            except OSError as exc:
                self.log(f"[close error] {exc}\n")
        return had_incomplete
