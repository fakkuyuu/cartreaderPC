#!/usr/bin/env python3
"""USB-only Cart Reader 15.5 host, terminal or Tk GUI. GPL-3.0-or-later."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import re
import shutil
import sys
import threading
import time

from protocol import ProtocolError, encode, receive
from storage import Storage
from batch_dump import BatchDump
from power_on_dump import PowerOnDump, TARGETS as POWER_ON_TARGETS
from dump_result import DumpResult
from connection_status import ConnectionFeedback
from i18n import UiTranslator
from ram_status import ram_labels
from browser_request import make_request
from auto_menu import (
    ZeroChord, build_menu_rows, resolve_menu_number,
    MenuNavigator, is_main_menu, is_widget_within, normalize_digit,
    move_focus_from_group,
    display_auto_reason,
)

BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
PROFILE_FILE = BASE / "baud_profiles.json"
UI_SETTINGS_FILE = BASE / "ui_settings.json"
TRANSFER_SETTINGS_FILE = BASE / "transfer_settings.json"
RAM_LOG_FILE = BASE / "ram_diagnostics.log"
ALLOWED_BAUDS = (250000, 285714, 333333, 400000, 500000, 666667, 1000000, 2000000)
_SINGLE_INSTANCE_HANDLE = None


def record_ram_diagnostic(message, port):
    # PC disk only. Preserve the last readings even if the reader resets.
    # Bound growth; this is deliberately separate from ROM companion TXT.
    if RAM_LOG_FILE.exists() and RAM_LOG_FILE.stat().st_size > 2 * 1024 * 1024:
        RAM_LOG_FILE.replace(RAM_LOG_FILE.with_suffix(".previous.log"))
    with RAM_LOG_FILE.open("a", encoding="utf-8") as target:
        target.write(time.strftime("%Y-%m-%d %H:%M:%S ") + port + " " + message.rstrip() + "\n")


def append_oscr_log(output_directory, message):
    """Append console output, with local timestamps at operation milestones."""
    if not message:
        return
    path = Path(output_directory).expanduser() / "OSCR_LOGPC.txt"
    with path.open("a", encoding="utf-8", newline="") as target:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        target.write(re.sub(
            r"(?m)^(?=\[\+\] Read (?:ROM|Cart|iNES Rom|PRG/CHR|Save|SRAM)\b|"
            r"\[Transfer complete\]|\[VERIFY\]|\[Connection\]|\[ERROR\b|Saved to )",
            f"[{stamp}] ", message))


def ensure_settings():
    """Create missing user settings; never replace an existing file."""
    defaults = {
        "baud_profiles.json": {},
        "ui_settings.json": {},
        "transfer_settings.json": {"block_size": 512, "sd_copy_read_size": 512, "sd_copy_dedicated_spi": True},
    }
    for name, content in defaults.items():
        try:
            with (BASE / name).open("x", encoding="utf-8") as target:
                json.dump(content, target, ensure_ascii=False, indent=2)
        except FileExistsError:
            pass
        except OSError as exc:
            print(f"[Settings] {name}: {exc}", file=sys.stderr)
    try:
        with (BASE / "config.txt").open("x", encoding="utf-8") as target:
            target.write("oscr.logging=1\nmd.saveType=0\n")
    except FileExistsError:
        pass
    except OSError as exc:
        print(f"[Settings] config.txt: {exc}", file=sys.stderr)


def load_transfer_block():
    try:
        data = json.loads(TRANSFER_SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 512
        value = int(data.get("block_size", 512))
        return value if value in (512, 1024) else 512
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 512


def load_ui_settings():
    try:
        data = json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def load_checkpoint_kib():
    return 16


def reader_firmware_status(line):
    match = re.match(r"OSCR\s+(HW\d+)\s+(V\S+)", line)
    if match:
        return f"本体ファーム：{match.group(2)} / {match.group(1)}"
    if line.startswith(("[Port]", "[Connected:")):
        return "本体ファーム：確認中"
    if line.startswith(("[Disconnected", "[RECONNECT]")):
        return "本体ファーム：未接続"
    return None


def save_ui_settings(settings):
    temporary = UI_SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(UI_SETTINGS_FILE)


def port_identity(port_name):
    try:
        from serial.tools import list_ports
    except (ImportError, ModuleNotFoundError):
        return f"PORT:{port_name.casefold()}"
    for item in list_ports.comports():
        if item.device.casefold() == port_name.casefold():
            stable = item.serial_number or item.location or item.hwid or port_name
            return f"{item.vid or 0:04X}:{item.pid or 0:04X}:{stable}"
    return f"PORT:{port_name.casefold()}"


def load_profile(identity):
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        if not isinstance(profiles, dict):
            return 250000, 250000
        value = profiles.get(identity, 250000)
        if isinstance(value, dict):
            safe = int(value.get("safe", 500000))
            dump = int(value.get("dump", safe))
        else:
            dump = int(value)
            safe = min(dump, 500000)
        return (safe if safe in ALLOWED_BAUDS else 250000,
                dump if dump in ALLOWED_BAUDS else 250000)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 250000, 250000


def profile_benchmark_complete(record):
    if isinstance(record, dict):
        return bool(record.get("benchmark_complete", record.get("passed")))
    return isinstance(record, int) and record in ALLOWED_BAUDS


def has_completed_benchmark(identity):
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        return isinstance(profiles, dict) and profile_benchmark_complete(profiles.get(identity))
    except (OSError, ValueError):
        return False


def save_profile(identity, baud, passed=None, *, benchmark_complete=None):
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        if not isinstance(profiles, dict):
            profiles = {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        profiles = {}
    previous = profiles.get(identity, {})
    if benchmark_complete is None:
        benchmark_complete = profile_benchmark_complete(previous)
    if passed is None and isinstance(previous, dict):
        passed = previous.get("passed", [])
    passed = sorted({int(value) for value in (passed or []) if int(value) in ALLOWED_BAUDS})
    profiles[identity] = {
        "safe": min(int(baud), 500000), "dump": int(baud), "passed": passed,
        "benchmark_complete": benchmark_complete}
    temporary = PROFILE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(PROFILE_FILE)


def checkpoint_profile(identity, baud):
    """Record a passed candidate without losing earlier successful rates."""
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        record = profiles.get(identity, {}) if isinstance(profiles, dict) else {}
        passed = record.get("passed", []) if isinstance(record, dict) else []
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        passed = []
    passed = list(passed) + [int(baud)]
    save_profile(identity, baud, passed)


def reset_profile_candidates(identity):
    safe, dump = load_profile(identity)
    save_profile(identity, dump, [])


def demote_profile(identity, failed):
    """Reject a failed runtime rate and select the highest lower proven rate."""
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        record = profiles.get(identity, {}) if isinstance(profiles, dict) else {}
        passed = record.get("passed", []) if isinstance(record, dict) else []
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        passed = []
    lower = sorted({int(value) for value in passed
                    if int(value) in ALLOWED_BAUDS and int(value) < int(failed)})
    selected = lower[-1] if lower else min(500000, int(failed))
    save_profile(identity, selected, lower)
    return selected


def acquire_single_instance():
    """Allow one GUI instance; a PyInstaller one-file parent is not a second UI."""
    global _SINGLE_INSTANCE_HANDLE
    if os.name != "nt":
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (
        ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.CreateMutexW(None, False, "Local\\OSCR_CartReaderPC_V155")
    if not handle:
        return True
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        ctypes.windll.user32.MessageBoxW(
            None, "CartReaderPC is already running. / 既に起動しています。", "Cart Reader", 0x30)
        return False
    _SINGLE_INSTANCE_HANDLE = handle
    return True


def new_session(parent, seed):
    # The selected folder is the virtual SD root. Keep the same directory
    # layout as a physical OSCR SD card instead of adding timestamp folders.
    root = Path(parent).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if seed:
        source = Path(seed).resolve()
        if not source.is_dir():
            # Release packages keep databases next to the executable. An
            # optional seed directory must not prevent that layout starting.
            return root
        # Do not follow symlinks from an arbitrary seed tree.
        for path in source.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"seed symlink rejected: {path}")
        if source != root:
            shutil.copytree(source, root, dirs_exist_ok=True)
    return root


def serve(port, sessions, seed, keys, log, stop, reconnect=None, cancel_event=None,
          progress=None, host_state=None):
    import serial
    identity = port_identity(port)
    preferred_baud, dump_baud = load_profile(identity)
    transfer_block = load_transfer_block()
    checkpoint_kib = load_checkpoint_kib()
    store = None
    tx2m = None
    try:
        # A manual connection pulses DTR so a reader already in standalone
        # mode reboots into PC mode.  After a menu/benchmark reset, the reader
        # is already rebooting and a second DTR pulse would reset it twice.
        suppress_dtr_reset = bool(
            host_state and host_state.pop("suppress_dtr_reset_once", False))
        wire = serial.Serial(baudrate=250000, timeout=1, write_timeout=5)
        try:
            wire.dtr = False
            wire.port = port
            wire.open()
            try:
                wire.reset_input_buffer()
                if not suppress_dtr_reset:
                    wire.dtr = True
            except (AttributeError, OSError):
                pass
            log(f"[Port] {port} @ 250000 baud; waiting for CRPC HELLO\n")
            waiting = time.monotonic()
            last_seq = None
            pending_baud = None
            recovery_until = None
            force_sync = False
            while not stop.is_set():
                if reconnect is not None and reconnect.is_set():
                    reconnect.clear()
                    raise ConnectionError("benchmark next rate")
                if host_state is not None and host_state.pop(
                        "expected_reader_reset", False):
                    # The reader has already announced Reset/benchmark
                    # completion. Keep the CH340 handle open and wait for its
                    # watchdog restart at the boot baud instead of reopening
                    # COM and causing a second DTR reset.
                    wire.baudrate = 250000
                    try:
                        wire.reset_input_buffer()
                    except (AttributeError, OSError):
                        pass
                    if store is not None:
                        incomplete = store.shutdown()
                        if incomplete:
                            log("\n[Reset] open files remain incomplete.\n")
                    store = None
                    last_seq = None
                    pending_baud = None
                    force_sync = True
                    waiting = time.monotonic()
                    log("[Reset] keeping COM open; waiting for HELLO at 250000 baud\n")
                    continue
                if recovery_until is not None:
                    if time.monotonic() < recovery_until:
                        # Preserve bytes arriving after the one-time cleanup.
                        # The reader's valid failure notice can arrive near the
                        # end of this window; force_sync will skip any garbage.
                        time.sleep(.01)
                        continue
                    recovery_until = None
                    force_sync = True
                # If the driver rejected the requested rate, do not parse the
                # reader's temporary traffic at a different speed. It will
                # time out and return to the previous rate by itself.
                if pending_baud and not pending_baud[3] and time.monotonic() < pending_baud[2]:
                    time.sleep(.01)
                    continue
                if not wire.in_waiting:
                    if tx2m is not None and time.monotonic() >= tx2m["deadline"]:
                        raise TimeoutError("no diagnostic frame received for 5 seconds")
                    if pending_baud and time.monotonic() >= pending_baud[2]:
                        failed, previous, recovery_base, switched = pending_baud
                        wire.baudrate = previous
                        wire.reset_input_buffer()
                        log(f"[Baud] {failed} FAILED; restored {previous}\n")
                        pending_baud = None
                        last_seq = None  # the failed echo frame was intentionally lost
                        # Firmware restores after its 2.5 s echo timeout and
                        # emits the failure notice 3.2 s later. Anchor this to
                        # the original switch deadline, not detection time.
                        recovery_until = recovery_base + 2.8
                    if store is None and time.monotonic() - waiting > 20:
                        raise TimeoutError("No HELLO. Check firmware/port and press RESET on the reader.")
                    time.sleep(.005)
                    continue
                # Only the first frame scans for CRPC. Later frames stay strict
                # so actual transport corruption still stops the session.
                try:
                    op, seq, payload = receive(wire, synchronize=force_sync or store is None,
                                               sync_timeout=8 if force_sync else 20)
                    force_sync = False
                except (OSError, ValueError, ProtocolError, serial.SerialException) as exc:
                    if not pending_baud:
                        if host_state is not None and host_state.pop(
                                "expected_reader_reset", False):
                            # Keep COM open during an intentional reader reset.
                            # Reopening a CH340 port pulses DTR and resets the
                            # Mega a second time.
                            wire.baudrate = 250000
                            try:
                                wire.reset_input_buffer()
                            except (AttributeError, OSError):
                                pass
                            if store is not None:
                                incomplete = store.shutdown()
                                if incomplete:
                                    log("\n[Reset] open files remain incomplete.\n")
                            store = None
                            last_seq = None
                            force_sync = True
                            waiting = time.monotonic()
                            log("[Reset] keeping COM open; waiting for HELLO at 250000 baud\n")
                            continue
                        raise
                    failed, previous, recovery_base, _ = pending_baud
                    wire.baudrate = previous
                    log(f"[Baud] {failed} transport error: {exc}; waiting for reader recovery\n")
                    wire.reset_input_buffer()
                    log(f"[Baud] {failed} FAILED; restored {previous}\n")
                    pending_baud = None
                    last_seq = None
                    recovery_until = recovery_base + 2.8
                    continue
                if store is None:
                    if op != 1 or payload:
                        raise ValueError("first CRPC frame is not HELLO")
                    root = new_session(sessions, seed)
                    store = Storage(root, log, keys, preferred_baud, dump_baud,
                                    cancel_event, progress, host_state, transfer_block, checkpoint_kib)
                    log(f"[Storage] {root}\n")
                if pending_baud and op in (18, 24):
                    pending_baud = (pending_baud[0], pending_baud[1], time.monotonic() + 2.6, pending_baud[3])
                elif pending_baud and op == 17:
                    log(f"[Baud] {pending_baud[0]} passed\n")
                    pending_baud = None
                elif pending_baud and op == 13:
                    # Receiving a valid console frame at the requested rate is
                    # enough to confirm a saved-profile switch.
                    log(f"[Baud] {pending_baud[0]} passed\n")
                    pending_baud = None
                if op == 13:
                    stable = re.search(rb"\[Benchmark\] stable baud=(\d+)", payload)
                    passed = re.search(rb"\[Benchmark\] passed baud=(\d+)", payload)
                    if stable:
                        selected = int(stable.group(1))
                        save_profile(identity, selected, benchmark_complete=True)
                        log(f"[Baud] saved {selected} for {identity}\n")
                    elif passed:
                        selected = int(passed.group(1))
                        checkpoint_profile(identity, selected)
                        log(f"[Baud] checkpoint saved {selected} for {identity}\n")
                if last_seq is not None and seq != ((last_seq + 1) & 0xffff):
                    raise ValueError("unexpected sequence/reset; reconnect reader")
                last_seq = seq
                if op == 13 and b"[TX test] diagnostic 2M" in payload:
                    tx2m = {"bytes": 0, "frames": 0, "checkpoints": 0,
                            "phase": "waiting for baud switch",
                            "deadline": time.monotonic() + 5}
                if tx2m is not None:
                    tx2m["deadline"] = time.monotonic() + 5
                    if op == 25:
                        tx2m["phase"] = "checkpoint"
                    elif op == 3:
                        tx2m["phase"] = "file close / pattern verification"
                if op == 30:
                    from gba_retry import receive_dump
                    snes = len(payload) == 6 and payload[5] == 11
                    md = len(payload) == 6 and payload[5] == 12
                    enabled = False
                    block_size = 512
                    try:
                        settings = json.loads(TRANSFER_SETTINGS_FILE.read_text(encoding="utf-8"))
                        setting_key = "snes_retry_2m" if snes else "md_retry_2m" if md else "gba_retry_2m"
                        size_key = "md_2m_frame_size" if md else "gba_2m_frame_size"
                        enabled = settings.get(setting_key) is True
                        configured = settings.get(size_key, 512)
                        if type(configured) is int and configured in (256, 512, 1024):
                            block_size = configured
                        else:
                            log(f"[{'MD' if md else 'GBA'} 2M] Invalid {size_key}; using 512 B\n")
                    except (OSError, ValueError, AttributeError):
                        pass
                    selectable = len(payload) == 6 and payload[5] == 0
                    legacy = len(payload) == 6 and payload[5] == 9
                    if legacy or snes:
                        block_size = 512
                    handle = payload[0] if selectable or legacy or snes or md else 0
                    length = int.from_bytes(payload[1:5], "little")
                    entry = store.handles.get(handle)
                    allowed = bool(enabled and entry and entry["write"]
                                   and 0 < length <= 32 * 1024**2 and length % block_size == 0)
                    answer = bytes([not allowed])
                    if allowed and (selectable or snes or md):
                        answer += bytes([block_size.bit_length() - 1])
                    reply = encode(op | 0x80, seq, answer)
                    if wire.write(reply) != len(reply):
                        raise ProtocolError("GBA 2M negotiation reply was not sent")
                    wire.flush()
                    if allowed:
                        # Preserve the old-baud ACK before changing the port, as op=17 does.
                        time.sleep(.05)
                        label = "SNES" if snes else "MD" if md else "GBA"
                        log(f"[{label} 2M] Starting CRC16 transfer with selective retransmission\n")
                        log(f"[{label} 2M] Frame size {block_size} B, reply window 8192 B\n")
                        receive_dump(wire, store, handle, length, log, stop, cancel_event,
                                     block_size, 8192 // block_size, label)
                    continue
                response = store.dispatch(op, payload)
                if tx2m is not None:
                    if op in (3, 17, 25) and response[0]:
                        raise OSError(f"diagnostic request rejected (op={op})")
                    if op == 22 and not response[0]:
                        tx2m["frames"] += 1
                        tx2m["bytes"] += len(payload) - 5
                        tx2m["phase"] = "waiting for stream or checkpoint"
                    elif op == 25:
                        tx2m["checkpoints"] += 1
                    elif op == 13 and b"[TX test] complete" in payload:
                        tx2m = None
                if response[0] and op == 22:
                    raise OSError("streamed host file write failed; transfer stopped")
                if pending_baud and op == 13 and b"[Benchmark] stable baud=" in payload:
                    log(f"[Baud] {pending_baud[0]} passed\n")
                    pending_baud = None
                # Console output is intentionally one-way. A lost ACK must not
                # freeze the reader between benchmark status lines.
                if op in (13, 19, 20, 22, 23, 26):
                    continue
                frame = encode(op | 0x80, seq, response)
                if wire.write(frame) != len(frame):
                    raise OSError("short serial write")
                wire.flush()
                if op == 14 and len(response) > 1:
                    shown = response[1:].decode("ascii", errors="replace").replace("\r", "\\r").replace("\n", "\\n")
                    log(f"[Input] sent to reader: {shown}\n")
                if op == 17 and not response[0]:
                    requested = int.from_bytes(payload[:4], "little")
                    if requested not in (250000, 285714, 333333, 400000, 500000, 666667, 1000000, 2000000):
                        raise ValueError("unsupported baud request")
                    previous = wire.baudrate
                    time.sleep(.05)
                    switched = False
                    try:
                        wire.baudrate = requested
                        switched = True
                        if len(payload) == 5 and payload[4] == 1:
                            log(f"[Baud] host runtime switch to {requested}\n")
                        else:
                            frames = 128 if requested > 500000 else 16
                            log(
                                f"[Baud] host switched to {requested}; "
                                f"testing dump path 512 bytes x{frames}\n")
                    except (OSError, ValueError, serial.SerialException) as exc:
                        wire.baudrate = previous
                        log(f"[Baud] USB serial driver rejected {requested}: {exc}\n")
                    runtime_switch = len(payload) == 5 and payload[4] == 1
                    if runtime_switch:
                        if tx2m is not None:
                            tx2m["phase"] = f"baud switch to {requested}"
                            if not switched:
                                raise OSError(f"USB serial driver rejected {requested}")
                            tx2m["phase"] = ("waiting for first stream frame" if requested == 2000000
                                             else "waiting for completion at normal baud")
                        pending_baud = None
                        if host_state is not None:
                            host_state["runtime_baud"] = requested
                        if tx2m is None:
                            log(f"[Baud] runtime switched to {requested}\n")
                    else:
                        # Reader needs up to 2.5 seconds to time out at the rejected
                        # speed, then 300 ms to restore the previous speed.
                        pending_baud = (requested, previous, time.monotonic() + 2.6, switched)
                if response[0] and op in (1, 3, 5):
                    raise OSError("fatal host file error; transfer stopped")
        finally:
            wire.close()
    except (OSError, ValueError, ProtocolError, serial.SerialException) as exc:
        if tx2m is not None:
            log(f"[TX test] 2M FAILED: {tx2m['phase']}; received {tx2m['bytes']} bytes "
                f"in {tx2m['frames']} frames; {tx2m['checkpoints']} checkpoints; {exc}\n")
        raise
    finally:
        if store is not None:
            incomplete = store.shutdown()
            if incomplete:
                log("\n[Disconnected. Check .pc-manifest.json; open files remain incomplete.]\n")
            else:
                log("\n[Disconnected.]\n")


def terminal(args):
    keys, stop = queue.Queue(), threading.Event()
    def keyboard():
        for line in sys.stdin:
            for b in line.encode("ascii", errors="replace"):
                keys.put(b)
    threading.Thread(target=keyboard, daemon=True).start()
    log_error_reported = False
    def console_log(message):
        nonlocal log_error_reported
        print(message, end="", flush=True)
        try:
            append_oscr_log(args.output, message)
        except OSError as exc:
            if not log_error_reported:
                print(f"[OSCR_LOGPC.txt] Cannot write log: {exc}", file=sys.stderr)
                log_error_reported = True
    try:
        serve(args.port, args.output, args.sd, keys, console_log, stop)
    except KeyboardInterrupt:
        stop.set()


def gui(args):
    import tkinter as tk
    from tkinter import ttk, filedialog
    from tkinter.scrolledtext import ScrolledText
    from serial.tools import list_ports
    window = tk.Tk()
    ui_settings = load_ui_settings()
    power_on = PowerOnDump(ui_settings)
    power_on_guard = {"reset": False, "benchmark": False}
    power_on_enabled = tk.BooleanVar(value=power_on.enabled)
    power_on_target = tk.StringVar(value=dict(POWER_ON_TARGETS)[power_on.target])
    _saved_lang = ui_settings.get("language", "English")
    language = tk.StringVar(value="Japanese" if _saved_lang in ("日本語", "JAPANESE") else _saved_lang)
    translator = UiTranslator(window, language)
    window.title("cartreaderPC PC133 — Disconnected")
    saved_geometry = ui_settings.get("window_geometry", "1120x720")
    if not re.fullmatch(r"\d+x\d+(?:[+-]\d+){0,2}", str(saved_geometry)):
        saved_geometry = "1120x720"
    window.geometry(saved_geometry)
    window.minsize(980, 620)
    normal_geometry = {"value": saved_geometry}
    if ui_settings.get("window_maximized"):
        window.after_idle(lambda: window.state("zoomed"))
    row = ttk.Frame(window, padding=8)
    row.pack(fill="x")
    port = tk.StringVar(value=args.port or "")
    ttk.Label(row, text="USBポート").pack(side="left")
    ports = ttk.Combobox(row, textvariable=port, width=18)
    ports.pack(side="left", padx=6)
    def refresh():
        ports["values"] = [p.device for p in list_ports.comports()]
        if not port.get() and ports["values"]:
            port.set(ports["values"][0])
    ttk.Button(row, text="更新", command=refresh).pack(side="left")
    output = tk.StringVar(value=str(Path(args.output or ui_settings.get("output_directory") or BASE).resolve()))
    folder = ttk.Frame(window, padding=8)
    folder.pack(fill="x")
    ttk.Label(folder, text="保存先").pack(side="left")
    output_entry = ttk.Entry(folder, textvariable=output)
    output_entry.pack(side="left", fill="x", expand=True, padx=8)
    def choose():
        selected = filedialog.askdirectory()
        if selected:
            output.set(selected)
    output_button = ttk.Button(folder, text="選択", command=choose)
    output_button.pack(side="left")
    def open_output_folder():
        from tkinter import messagebox
        selected = output.get().strip()
        if not selected:
            messagebox.showwarning(
                translator.translate("保存先"),
                translator.translate("保存先フォルダを指定してください。"), parent=window)
            return
        path = Path(selected)
        try:
            if not path.is_dir():
                messagebox.showwarning(
                    translator.translate("保存先"),
                    translator.translate("保存先フォルダが存在しません。") + "\n" + str(path),
                    parent=window)
                return
            os.startfile(str(path.resolve()))
        except OSError as exc:
            messagebox.showerror(
                translator.translate("保存先"),
                translator.translate("フォルダを開けませんでした。") + "\n" + str(exc),
                parent=window)
    ttk.Button(folder, text="開く", command=open_output_folder).pack(side="left", padx=(6, 0))
    def persist_output(*unused):
        ui_settings["output_directory"] = output.get()
        try:
            save_ui_settings(ui_settings)
        except OSError:
            pass
    output.trace_add("write", persist_output)
    info_row = ttk.Frame(window, padding=(8, 3, 8, 5))
    info_row.pack(fill="x")
    info_left = ttk.Frame(info_row)
    info_left.pack(side="left", anchor="nw")
    ttk.Label(info_left, text="本体ボタン、下のメニュー、数字キーのどれでも操作できます。").pack(anchor="w")
    firmware_state = tk.StringVar(value="本体ファーム：未接続")
    ttk.Label(info_left, textvariable=firmware_state).pack(anchor="w")
    ram_state = tk.StringVar(value="RAM：未受信（PC87以降の対応ファームが必要）")
    ram_detail = tk.StringVar(value="空き＝ヒープとスタックの間隔。瞬間的な最小値は未保証。")
    ttk.Label(info_left, textvariable=ram_state).pack(anchor="w")
    ttk.Label(info_left, textvariable=ram_detail, wraplength=460).pack(anchor="w")
    menu_panel = ttk.LabelFrame(window, text="操作メニュー", padding=8)
    menu_panel.pack(fill="x", padx=8, pady=(0, 8))
    text = ScrolledText(window, wrap="word", font=("Consolas", 10), state="disabled")
    oscr_log_error = {"reported": False}
    inbox, keys = queue.Queue(), queue.Queue()
    transfer_updates = queue.Queue()
    stop = threading.Event()
    detach_ack = threading.Event()
    copy_cancel = threading.Event()
    worker = None
    host_state = {}
    def remember_power_on(event=None):
        labels = {label: target for target, label in POWER_ON_TARGETS}
        power_on.configure(power_on_enabled.get(), labels.get(power_on_target.get(), "GB"))
        ui_settings.update(power_on.settings())
        try:
            save_ui_settings(ui_settings)
        except OSError as exc:
            inbox.put(f"[Settings] {exc}\n")
    power_on_row = ttk.Frame(menu_panel)
    power_on_row.pack(fill="x", pady=(0, 6))
    ttk.Checkbutton(power_on_row, text="BootDump", variable=power_on_enabled,
                    command=remember_power_on).pack(side="left")
    power_on_picker = ttk.Combobox(
        power_on_row, textvariable=power_on_target,
        values=tuple(label for target, label in POWER_ON_TARGETS),
        state="readonly", width=43)
    power_on_picker.pack(side="left", padx=(8, 0))
    power_on_picker.bind("<<ComboboxSelected>>", remember_power_on)
    menu_title = tk.StringVar(value="接続すると、ここに選択肢が表示されます")
    ttk.Label(menu_panel, textvariable=menu_title).pack(anchor="w")
    menu_items = ttk.Frame(menu_panel, takefocus=1)
    menu_items.pack(fill="x", pady=(5, 0))
    parser_buffer = ""
    pending_title = ""
    pending_options = []
    pending_paged = False
    normal_baud = tk.StringVar(value="通信速度（通常）：未接続")
    dump_baud = tk.StringVar(value="通信速度（吸い出し）：未接続")
    transfer_block_label = tk.StringVar(value=f"転送ブロック：{load_transfer_block()} bytes（設定）")
    checkpoint_label = tk.StringVar(value=f"確認間隔：{load_checkpoint_kib()} KiB（設定）")
    transfer_speed = tk.StringVar(value="転送: 待機")
    storage_mode = tk.StringVar(value="保存先: PC")
    storage_current = {"mode": "PC", "pending": None, "desired": "PC"}
    connection_state = tk.StringVar(value="未接続")
    connection_session = {"ever_connected": False}
    led_state = tk.StringVar(value="本体LED: 状態未取得")
    connection_widgets = {"button": None}
    storage_widgets = {"PC": None, "SD": None}
    connection_colors = {
        "未接続": ("#e5e7eb", "#111827"),
        "接続中…": ("#fde68a", "#78350f"),
        "接続済み": ("#86efac", "#14532d"),
        "接続待ち": ("#fdba74", "#7c2d12"),
        "接続エラー": ("#fca5a5", "#7f1d1d"),
    }
    def set_connection_state(value):
        connection_state.set(value)
        if value in ("接続中…", "接続済み"):
            ram_state.set("RAM：未受信（PC87以降の対応ファームが必要）")
            ram_detail.set("空き＝ヒープとスタックの間隔。瞬間的な最小値は未保証。")
        elif ram_state.get().startswith("RAM空き：") and not ram_state.get().endswith("（最終値）"):
            ram_state.set(ram_state.get() + "（最終値）")
        if value != "接続済み":
            firmware_state.set("本体ファーム：確認中" if value == "接続中…" else "本体ファーム：未接続")
        background, foreground = connection_colors.get(
            value, connection_colors["未接続"])
        for name, widget in connection_widgets.items():
            if widget is not None:
                widget.configure(background=background, foreground=foreground)
                if name == "button":
                    widget.configure(text="接続" if value == "未接続" else value)
    def set_storage_state(mode=None, pending=None):
        if mode in ("PC", "SD"):
            storage_current["mode"] = mode
        storage_current["pending"] = pending
        current = storage_current["mode"]
        if pending:
            storage_mode.set(f"保存先: {current}（次回: {pending}予約）")
        else:
            storage_mode.set(f"保存先: {current}")
        for name, widget in storage_widgets.items():
            if widget is None:
                continue
            if name == pending:
                widget.configure(background="#fde68a", foreground="#78350f")
            elif name == current:
                widget.configure(background="#86efac", foreground="#14532d")
            else:
                widget.configure(background="#e5e7eb", foreground="#111827")
    status_summary = ttk.Frame(info_row)
    status_summary.pack(side="right", anchor="ne")
    ttk.Label(status_summary, textvariable=normal_baud).grid(row=0, column=0, sticky="w")
    ttk.Label(status_summary, textvariable=dump_baud).grid(row=1, column=0, sticky="w")
    ttk.Label(status_summary, textvariable=transfer_block_label).grid(row=2, column=0, sticky="w")
    ttk.Label(status_summary, textvariable=checkpoint_label).grid(row=2, column=1, sticky="w")
    led_box = ttk.Frame(status_summary)
    led_box.grid(row=0, column=1, rowspan=2, padx=(14, 0), sticky="w")
    ttk.Label(led_box, textvariable=led_state).pack(side="left")
    led_swatch = tk.Canvas(led_box, width=24, height=16, highlightthickness=1,
                           highlightbackground="#666666")
    led_swatch.pack(side="left", padx=(5, 0))
    led_colors = {
        "blue": "#2563eb", "red": "#dc2626", "purple": "#9333ea",
        "green": "#16a34a", "turquoise": "#14b8a6", "yellow": "#facc15",
        "white": "#ffffff", "off": "#111111", "unknown": "#9ca3af",
    }
    led_runtime = {"reported": "unknown", "activity": False}
    led_names = {
        "blue": "青", "red": "赤", "purple": "紫", "green": "緑",
        "turquoise": "水色", "yellow": "黄", "white": "白",
        "off": "消灯", "unknown": "状態未取得",
    }
    def refresh_led_display():
        if led_runtime["activity"]:
            led_state.set("本体LED: 吸い出し中（点滅）")
            led_swatch.configure(background="#facc15")
            return
        value = led_runtime["reported"]
        led_state.set(f"本体LED: {led_names.get(value, value)}")
        led_swatch.configure(background=led_colors.get(value, led_colors["unknown"]))
    def set_led_state(value):
        led_runtime["reported"] = value
        refresh_led_display()
    def set_led_activity(active):
        led_runtime["activity"] = bool(active)
        refresh_led_display()
    set_led_state("unknown")
    input_ready = tk.BooleanVar(value=False)
    input_mode = tk.StringVar(value="menu")
    batch = BatchDump()
    auto_shortcut = ZeroChord()
    dump_result = DumpResult()
    dump_result_blink = {"after": None}
    def paint_dump_result():
        text.configure(background=DumpResult.COLORS[dump_result.state], foreground="black")
    def cancel_dump_result_blink():
        callback = dump_result_blink["after"]
        dump_result_blink["after"] = None
        if callback is not None:
            try:
                window.after_cancel(callback)
            except tk.TclError:
                pass
    def schedule_dump_result_blink():
        if dump_result.blinking and dump_result_blink["after"] is None:
            dump_result_blink["after"] = window.after(1000, tick_dump_result_blink)
    def tick_dump_result_blink():
        dump_result_blink["after"] = None
        if dump_result.advance_blink():
            paint_dump_result()
            schedule_dump_result_blink()
    def reset_dump_result():
        cancel_dump_result_blink()
        dump_result.reset()
        paint_dump_result()
    batch_pending = {"key": None}
    def batch_report(was_active):
        if was_active and not batch.active:
            batch_pending["key"] = None
            dump_result.finish_batch(
                batch.reason.startswith("一括吸出し完了:"),
                save_failure_after_rom=batch.save_failure_after_rom,
            )
            paint_dump_result()
            if dump_result.blinking:
                schedule_dump_result_blink()
            inbox.put(f"[自動吸出し] {display_auto_reason(batch.reason)}\n")
    def batch_stop(reason):
        active = batch.active
        batch.stop(reason)
        batch_report(active)
    def batch_schedule(value):
        if value is not None and batch.active:
            batch_pending["key"] = value
        batch_poll()
    def batch_poll():
        value = batch_pending["key"]
        if (value is not None and batch.active and worker and worker.is_alive()
                and input_ready.get() and not sd_browser["busy"]):
            batch_pending["key"] = None
            send_menu_key(value, "自動吸出し中...", automated=True)
    def power_on_poll():
        if (not power_on.pending or not worker or not worker.is_alive()
                or not input_ready.get() or input_mode.get() != "menu"
                or batch.active or sd_browser["busy"]
                or benchmark["index"] is not None or storage_current["pending"]):
            return
        action = power_on.menu_action(menu_navigation.get("title", ""),
            menu_navigation["options"], menu_navigation.get("paged", False),
            storage_current["mode"])
        if not action:
            return
        if action[0] == "start":
            inbox.put("[Auto start] BootDumpを開始します。\n")
            start_batch(action[1], action[2])
        elif action[0] == "page":
            send_menu_key(action[1], automated=True)
        else:
            inbox.put(f"[Auto start] {action[1]}\n")

    def start_batch(target, selected_number):
        if (not worker or not worker.is_alive() or not input_ready.get()
                or input_mode.get() != "menu" or sd_browser["busy"]
                or storage_current["mode"] != "PC" or storage_current["pending"]
                or benchmark["index"] is not None):
            inbox.put("[自動吸出し] 自動吸出しはPC保存・接続済みの機種選択メニューから開始してください\n")
            return
        reset_dump_result()
        power_on.cancel()
        dump_result.begin_batch()
        paint_dump_result()
        batch.begin(target)
        inbox.put(f"[自動吸出し] {target} 自動吸出しを開始\n")
        batch_schedule(selected_number)
    menu_navigation = {
        "items": [], "options": [], "selected": 0, "selected_auto": None,
        "auto_entries": (), "activate_auto": None, "navigator": None,
        "rows": (), "root_menu": False, "auto_buttons": {},
    }
    sd_browser = {"window": None, "tree": None, "path": "/", "pending": [],
                  "busy": False, "progress": None, "progress_text": None,
                  "status": None, "resort": None, "action": None,
                  "scan_active": False, "scan_queue": [],
                  "scan_current": None, "scan_entries": [],
                  "cancelled": False, "deferred": None}

    def browser_command(action, path):
        if not (worker and worker.is_alive()) or sd_browser["busy"]:
            return False
        if not host_state.get("component_browser"):
            if sd_browser["status"]:
                sd_browser["status"].set("SDブラウザにはPC88ファームが必要です")
            return False
        encoded = path.encode("utf-8")
        if not encoded or b"\n" in encoded:
            return False
        if not input_ready.get() or input_mode.get() != "menu":
            sd_browser["deferred"] = (action, path)
            if sd_browser["status"]:
                sd_browser["status"].set("数字メニューへ戻ってからSDを読み込みます")
            if input_ready.get() and input_mode.get() == "press":
                send_menu_key(" ")
            return False
        sd_browser["deferred"] = None
        power_on.cancel()
        reset_dump_result()
        input_ready.set(False)
        sd_browser["busy"] = True
        sd_browser["action"] = action
        sd_browser["cancelled"] = False
        if action == "C":
            copy_cancel.clear()
        try:
            settings=json.loads(TRANSFER_SETTINGS_FILE.read_text(encoding="utf-8"))
            request=make_request(action,path,int(settings.get("sd_copy_read_size",512)),
                                 bool(settings.get("sd_copy_dedicated_spi",True)))
        except (OSError,ValueError,TypeError) as exc:
            sd_browser["busy"]=False
            input_ready.set(True)
            inbox.put(f"[SD Browser] {exc}\n")
            return False
        host_state["browser_request"]=request
        keys.put(b"KQ\n")
        return True

    def browser_start_next():
        if batch.active or sd_browser["busy"] or not input_ready.get():
            return
        if sd_browser["deferred"]:
            action, path = sd_browser["deferred"]
            browser_command(action, path)
            return
        if input_mode.get() != "menu":
            return
        if sd_browser["scan_queue"]:
            path = sd_browser["scan_queue"].pop(0)
            sd_browser["scan_current"] = path
            sd_browser["scan_entries"] = []
            if sd_browser["status"]:
                sd_browser["status"].set(f"フォルダ確認中: {path}")
            browser_command("L", path)
            return
        if sd_browser["scan_active"]:
            sd_browser["scan_active"] = False
            if sd_browser["status"]:
                sd_browser["status"].set(f"{len(sd_browser['pending'])}ファイルをコピーします")
        if sd_browser["pending"]:
            path = sd_browser["pending"].pop(0)
            if sd_browser["status"]:
                sd_browser["status"].set(f"コピー中: {path}")
            browser_command("C", path)

    def send_key(value, automated=False):
        if not automated and value not in ("I", "J"):
            power_on.cancel()
        if batch.active and not automated:
            batch_stop("手動操作に切り替えました")
        if worker and worker.is_alive() and input_ready.get():
            if not automated:
                reset_dump_result()
            input_ready.set(False)
            keys.put(ord(value))

    def send_bytes(values):
        power_on.cancel()
        if worker and worker.is_alive() and input_ready.get():
            reset_dump_result()
            input_ready.set(False)
            keys.put(bytes(values))

    def clear_operation(message="処理中..."):
        input_mode.set("busy")
        menu_title.set(message)
        menu_navigation["items"] = []
        menu_navigation["options"] = []
        for child in menu_items.winfo_children():
            child.destroy()

    def send_menu_key(value, message="処理中...", automated=False):
        if batch.active and not automated:
            batch_stop("手動操作に切り替えました")
        if worker and worker.is_alive() and input_ready.get():
            # Page-boundary requests may only return input-ready, without
            # resending the menu. Keep its controls until a new menu arrives.
            # send_key still blocks repeated input while awaiting the reader.
            if value not in ("[", "]"):
                clear_operation(message)
            send_key(value, automated=automated)

    # Keep the actual left/right controls available on non-numbered screens.
    physical_visible = tk.BooleanVar(value=bool(ui_settings.get("physical_controls_visible", False)))
    physical_panel = ttk.LabelFrame(window, text="本体ボタン（補助操作）", padding=6)
    def toggle_physical_panel():
        if physical_visible.get():
            physical_panel.pack(fill="x", padx=8, pady=(0, 8), after=menu_panel)
        else:
            physical_panel.pack_forget()
    ttk.Checkbutton(info_row, text="本体ボタン操作を表示",
                    variable=physical_visible, command=toggle_physical_panel).pack(
                        side="left", padx=(14, 0), anchor="nw")
    if physical_visible.get():
        toggle_physical_panel()

    def bind_reader_hold(button, short_key, long_key=None, extra_long_key=None):
        press = {}

        def send_held():
            press.pop("timer", None)
            x, y = button.winfo_pointerxy()
            if (press.get("started") is not None and input_mode.get() == "about"
                    and input_ready.get()
                    and 0 <= x - button.winfo_rootx() < button.winfo_width()
                    and 0 <= y - button.winfo_rooty() < button.winfo_height()):
                press["sent"] = True
                send_key(long_key)

        def down(event):
            if input_ready.get():
                press["started"] = time.monotonic()
                press["mode"] = input_mode.get()
                press["sent"] = False
                button.state(["pressed"])
                if press["mode"] == "menu" or long_key is None:
                    press["sent"] = True
                    send_key(short_key)
                elif press["mode"] == "about" and short_key == " ":
                    press["timer"] = button.after(2000, send_held)
                return "break"

        def up(event):
            started = press.pop("started", None)
            if started is None:
                return None
            timer = press.pop("timer", None)
            if timer is not None:
                button.after_cancel(timer)
            button.state(["!pressed"])
            if (not press["sent"] and press["mode"] == input_mode.get() and input_ready.get()
                    and 0 <= event.x < button.winfo_width()
                    and 0 <= event.y < button.winfo_height()):
                seconds = time.monotonic() - started
                if extra_long_key is not None and seconds >= 5:
                    send_key(extra_long_key)
                else:
                    send_key(long_key if seconds >= 2 else short_key)
            return "break"

        button.bind("<ButtonPress-1>", down)
        button.bind("<ButtonRelease-1>", up)

    physical_controls = (
        ("左ボタン：次へ／変更 (d)", "d"),
        ("右ボタン：決定 (Space)", " "),
        ("左ボタン2回押し：前へ／戻る (u)", "u"),
    )
    for label, value in physical_controls:
        button = ttk.Button(physical_panel, text=label,
                            command=lambda key=value: send_key(key))
        button.pack(side="left", expand=True, fill="x", padx=2)
        if value == "d":
            bind_reader_hold(button, "d", " ", "l")
        elif value == " ":
            bind_reader_hold(button, " ", "l")
        else:
            bind_reader_hold(button, value)

    def render_menu(title, options, paged):
        auto_shortcut.reset()
        root_menu = is_main_menu(title)
        menu_navigation["title"] = title
        if root_menu and benchmark["index"] is None:
            power_on_guard["benchmark"] = False
        input_mode.set("menu")
        menu_title.set(title or "選択してください")
        for child in menu_items.winfo_children():
            child.destroy()

        rows = build_menu_rows(title, options, paged)
        navigator = MenuNavigator(rows, paged) if root_menu else None
        rendered = []
        auto_buttons = {}
        auto_button_frames = {}
        auto_entries = tuple(
            entry for row_data in rows for entry in row_data["auto_entries"]
        )

        def paint_selection(reader_header=False):
            menu_title.set(f"{title} / BootDump (Reader)" if reader_header else
                           title or "選択してください")
            for widget in rendered:
                widget.configure(
                    background="white", highlightbackground="white",
                    highlightthickness=0,
                )
            for frame in auto_button_frames.values():
                frame.configure(highlightthickness=0)
            if reader_header:
                return
            if root_menu and navigator is not None:
                row_index, auto_index = navigator.current()
                if auto_index is None:
                    widget = rendered[row_index]
                    widget.configure(
                        background="#dbeafe",
                        highlightbackground="#2563eb",
                        highlightthickness=2,
                    )
                else:
                    frame = auto_button_frames[(row_index, auto_index)]
                    frame.configure(
                        highlightbackground="#2563eb",
                        highlightcolor="#2563eb",
                        highlightthickness=2,
                    )
                menu_navigation["selected"] = row_index
                menu_navigation["selected_auto"] = auto_index
            elif rendered:
                selected = menu_navigation["selected"] % len(rendered)
                menu_navigation["selected"] = selected
                rendered[selected].configure(
                    background="#dbeafe", highlightbackground="#2563eb",
                    highlightthickness=2,
                )

        def select_row(index):
            if root_menu and navigator is not None:
                navigator.select_row(index)
            else:
                menu_navigation["selected"] = index % max(1, len(rendered))
            paint_selection()

        def select_reader_cursor(index):
            if index == -1:
                paint_selection(reader_header=True)
            elif 0 <= index < len(rendered):
                select_row(index)

        def select_auto(row_index, auto_index):
            if navigator is not None and navigator.select_auto(row_index, auto_index):
                paint_selection()

        def activate_auto(entry, row_index, auto_index):
            select_auto(row_index, auto_index)
            menu_items.focus_set()
            start_batch(entry[1], entry[2])

        def click_reader_option(index, reader_number):
            select_row(index)
            menu_items.focus_set()
            send_menu_key(reader_number)

        for position, row_data in enumerate(rows):
            row_frame = ttk.Frame(menu_items, takefocus=0)
            row_frame.pack(fill="x", pady=2)
            display_number = row_data["display_number"]
            prefix = f"{display_number}  " if display_number else "   "
            item = tk.Button(
                row_frame, text=f"{prefix}{row_data['label']}",
                anchor="w", padx=10, pady=5, relief="solid",
                borderwidth=1, background="white", cursor="hand2",
                takefocus=0, command=lambda i=position, n=row_data["reader_number"]:
                    click_reader_option(i, n),
            )
            item.pack(side="left", fill="x", expand=True)
            rendered.append(item)
            item.bind("<Enter>", lambda event, i=position: select_row(i))
            for auto_index, entry in enumerate(row_data["auto_entries"]):
                shortcut, _target, _reader_number, button_label = entry
                button_frame = tk.Frame(
                    row_frame, borderwidth=0, highlightthickness=0,
                    background=window.cget("background"), takefocus=0,
                )
                button_frame.pack(side="left", padx=(4, 0))
                button = ttk.Button(
                    button_frame, text=f"0+{shortcut}  {button_label}",
                    command=lambda e=entry, r=position, a=auto_index:
                        activate_auto(e, r, a),
                    takefocus=0,
                )
                button.pack()
                auto_buttons[(position, auto_index)] = button
                auto_button_frames[(position, auto_index)] = button_frame
                button.bind(
                    "<Enter>",
                    lambda event, r=position, a=auto_index: select_auto(r, a),
                )
                button.bind(
                    "<Button-1>",
                    lambda event: menu_items.focus_set(),
                    add="+",
                )

        menu_navigation["items"] = rendered
        menu_navigation["options"] = list(options)
        menu_navigation["paged"] = paged
        menu_navigation["selected"] = 0
        menu_navigation["selected_auto"] = None
        menu_navigation["root_menu"] = root_menu
        menu_navigation["rows"] = rows
        menu_navigation["navigator"] = navigator
        menu_navigation["auto_entries"] = auto_entries
        menu_navigation["auto_buttons"] = auto_buttons
        def activate_auto_shortcut(entry):
            for row_index, row_data in enumerate(rows):
                for auto_index, candidate in enumerate(row_data["auto_entries"]):
                    if candidate[0] == entry[0]:
                        activate_auto(candidate, row_index, auto_index)
                        return

        menu_navigation["activate_auto"] = (
            activate_auto_shortcut if root_menu and auto_entries else None
        )
        menu_navigation["select_row"] = select_row if rendered else None
        menu_navigation["select_reader_cursor"] = select_reader_cursor if rendered else None
        menu_navigation["paint_selection"] = paint_selection
        menu_items.configure(takefocus=1)
        paint_selection()
        if rendered:
            # The menu is one focus stop; its individual rows and Auto controls
            # are mouse targets, not separate Tab stops.
            menu_items.focus_set()
        if paged:
            nav = ttk.Frame(menu_items, takefocus=0)
            nav.pack(fill="x", pady=(5, 0))
            previous = ttk.Button(
                nav, text="7  ◀ 前のページ",
                command=lambda: send_menu_key("["),
                takefocus=0,
            )
            previous.pack(side="left")
            following = ttk.Button(
                nav, text="8  次のページ ▶",
                command=lambda: send_menu_key("]"),
                takefocus=0,
            )
            following.pack(side="right")
            previous.bind("<Button-1>", lambda event: menu_items.focus_set(), add="+")
            following.bind("<Button-1>", lambda event: menu_items.focus_set(), add="+")
        if batch.active:
            was_active = batch.active
            action = batch.on_menu(title, options)
            batch_report(was_active)
            batch_schedule(action)
        power_on_poll()

    def render_press_button():
        auto_shortcut.reset()
        input_mode.set("press")
        menu_title.set("Press Button...")
        for child in menu_items.winfo_children():
            child.destroy()
        item = tk.Button(menu_items, text="0  Press Button (Enter)", anchor="center",
                        padx=10, pady=8, relief="solid", borderwidth=1,
                        background="white", cursor="hand2",
                        command=lambda: send_menu_key(" "))
        item.pack(fill="x", pady=2)
        item.bind("<Enter>", lambda event: item.configure(background="#dbeafe", highlightbackground="#2563eb", highlightthickness=2))
        item.bind("<Leave>", lambda event: item.configure(background="white", highlightthickness=0))
        if batch.active:
            was_active = batch.active
            action = batch.on_press()
            batch_report(was_active)
            batch_schedule(action)

    simple_controls = {"buttons": [], "selected": 0}
    def select_simple(index):
        buttons = simple_controls["buttons"]
        if not buttons:
            return
        simple_controls["selected"] = index % len(buttons)
        for i, button in enumerate(buttons):
            button.configure(background="#dbeafe" if i == simple_controls["selected"] else "white")
    def add_simple_controls(controls, candidate=False):
        simple_controls["buttons"] = []
        for index, (label, value) in enumerate(controls):
            button = tk.Button(menu_items, text=f"{index}  {label}",
                command=lambda key=value: send_menu_key(key) if candidate and key == " " else send_key(key))
            button.pack(side="left", expand=True, fill="x", padx=2)
            button.bind("<Enter>", lambda event, i=index: select_simple(i))
            simple_controls["buttons"].append(button)
        select_simple(0)
    def render_candidate_controls():
        auto_shortcut.reset()
        input_mode.set("candidate")
        menu_title.set("カセット候補を選択")
        for child in menu_items.winfo_children():
            child.destroy()
        controls = (
            ("◀ 前の候補 (u)", "u"),
            ("次の候補 (d) ▶", "d"),
            ("この候補を選択 (Space)", " "),
        )
        add_simple_controls(controls, candidate=True)
        if batch.active:
            was_active = batch.active
            action = batch.on_candidate()
            batch_report(was_active)
            batch_schedule(action)

    def render_physical_fallback():
        auto_shortcut.reset()
        input_mode.set("physical")
        menu_title.set("本体画面の操作待ち")
        for child in menu_items.winfo_children():
            child.destroy()
        controls = (
            ("前へ／戻る", "u"),
            ("次へ／変更", "d"),
            ("決定", " "),
        )
        add_simple_controls(controls)
        if batch.active:
            was_active = batch.active
            action = batch.on_physical()
            batch_report(was_active)
            batch_schedule(action)

    def render_about():
        auto_shortcut.reset()
        input_mode.set("about")
        menu_title.set("About")
        for child in menu_items.winfo_children():
            child.destroy()
        add_simple_controls((
            ("メインメニューに戻る", " "),
            ("フォルダ番号を0に戻す", "l"),
        ))

    alphabet_state = {"selected": 0, "database": "", "buttons": []}
    def select_alphabet(index):
        buttons = alphabet_state["buttons"]
        alphabet_state["selected"] = index % len(buttons)
        for i, button in enumerate(buttons):
            active = i == alphabet_state["selected"]
            button.configure(background="#dbeafe" if active else "white", relief="sunken" if active else "raised")

    def database_candidates(database_name, letter):
        path = BASE / Path(database_name).name
        matches = []
        try:
            with path.open("rb") as database:
                while True:
                    offset = database.tell()
                    raw_name = database.readline()
                    if not raw_name:
                        break
                    database.readline()
                    database.readline()
                    name = raw_name.rstrip(b"\r\n").decode("utf-8", errors="replace")
                    first = name[:1].upper()
                    if (letter == "#" and first not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") or first == letter:
                        matches.append((name, offset))
        except OSError as exc:
            menu_title.set(f"データベースを開けません: {exc}")
        return matches

    def select_database_record(offset, title=""):
        if worker and worker.is_alive() and input_ready.get():
            if Path(alphabet_state["database"]).name.casefold() == "msxcart.txt":
                host_state["msx_title"] = title
            clear_operation("ゲーム情報を本体へ設定中...")
            send_bytes(b"@" + f"{offset:08X}".encode("ascii"))

    def render_nes_mapper(current, supported):
        if batch.active:
            batch_stop("Mapperの手動選択が必要です")
        input_mode.set("nes-mapper")
        menu_title.set("NES Mapperを指定")
        for child in menu_items.winfo_children():
            child.destroy()
        mapper_value = tk.StringVar(value=f"{current:03d}")
        form = ttk.Frame(menu_items)
        form.pack(fill="x")
        ttk.Label(form, text="Mapper:").pack(side="left")
        picker = ttk.Combobox(form, textvariable=mapper_value, width=12,
                              values=[f"{value:03d}" for value in supported])
        picker.pack(side="left", padx=8)
        status = tk.StringVar(value="数字を直接入力するか、一覧から選択してください")
        def submit(_event=None):
            try:
                value = int(mapper_value.get(), 10)
            except ValueError:
                status.set("Mapperは数字で入力してください")
                return "break"
            if value not in supported:
                status.set("このMapperはファームウェアで未対応です")
                return "break"
            if worker and worker.is_alive() and input_ready.get():
                clear_operation(f"Mapper {value:03d} を設定中...")
                send_bytes(b"M" + f"{value:03d}".encode("ascii"))
            return "break"
        ttk.Button(form, text="このMapperで決定", command=submit).pack(side="left")
        ttk.Label(menu_items, textvariable=status).pack(anchor="w", pady=(5, 0))
        picker.bind("<Return>", submit)
        picker.bind("<KP_Enter>", submit)
        picker.focus_set()
        picker.selection_range(0, "end")

    nes_option_state = {"buttons": [], "selected": 0}

    def render_nes_options(code, label, options):
        if batch.active:
            batch_stop("サイズなどの手動選択が必要です")
        input_mode.set("nes-options")
        menu_title.set(label)
        for child in menu_items.winfo_children():
            child.destroy()
        def choose(index):
            if worker and worker.is_alive() and input_ready.get():
                clear_operation(f"{label}を設定中...")
                send_bytes(code.encode("ascii") + f"{index:02X}".encode("ascii"))
        grid = ttk.Frame(menu_items)
        grid.pack(fill="x")
        buttons = []
        def select_option(position):
            if not buttons:
                return
            nes_option_state["selected"] = position % len(buttons)
            for item_position, item in enumerate(buttons):
                active = item_position == nes_option_state["selected"]
                item.configure(background="#dbeafe" if active else "white",
                               highlightbackground="#2563eb" if active else "white",
                               highlightthickness=2 if active else 0)
            buttons[nes_option_state["selected"]].focus_set()
        for position, (index, text_value) in enumerate(options):
            button = tk.Button(grid, text=f"{position}  {text_value}",
                               background="white",
                               command=lambda value=index: choose(value))
            button.grid(row=position // 4, column=position % 4,
                        sticky="nsew", padx=2, pady=2)
            button.bind("<Enter>", lambda event, i=position: select_option(i))
            buttons.append(button)
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1)
        nes_option_state["buttons"] = buttons
        nes_option_state["selected"] = 0
        if buttons:
            select_option(0)

    database_list_state = {}
    def render_database_candidates(letter):
        if batch.active:
            batch_stop("タイトルの手動選択が必要です")
        input_mode.set("database-list")
        menu_title.set(f"{letter} — ゲームを選択")
        for child in menu_items.winfo_children():
            child.destroy()
        matches = database_candidates(alphabet_state["database"], letter)
        body = ttk.Frame(menu_items)
        body.pack(fill="both", expand=True)
        listing = tk.Listbox(body, height=12, exportselection=False)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=listing.yview)
        listing.configure(yscrollcommand=scrollbar.set)
        listing.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for name, _offset in matches:
            listing.insert("end", name)
        def choose_record(_event=None):
            selected = listing.curselection()
            if selected:
                name, offset = matches[selected[0]]
                select_database_record(offset, name)
        listing.bind("<ButtonRelease-1>", choose_record)
        listing.bind("<Return>", choose_record)
        database_list_state.update(listing=listing, choose=choose_record)
        controls = ttk.Frame(menu_items)
        controls.pack(fill="x", pady=(5, 0))
        ttk.Button(controls, text="0  文字一覧へ戻る",
                   command=lambda: render_alphabet_controls(
                       alphabet_state["selected"], alphabet_state["database"])).pack(side="left")
        ttk.Button(controls, text="5  選択したゲームを決定 (Enter)",
                   command=choose_record).pack(side="right")
        if matches:
            listing.selection_set(0)
            listing.focus_set()
        else:
            listing.insert("end", "該当するゲームがありません")

    def render_alphabet_controls(selected_index=0, database_name=""):
        if batch.active:
            if batch.target == "NES" and database_name.lower() == "nes.txt":
                batch_stop("NES認識失敗。先頭文字から手動で選択してください")
            else:
                batch_stop("タイトルの手動選択が必要です")
        input_mode.set("alphabet")
        alphabet_state["selected"] = selected_index
        alphabet_state["database"] = database_name
        menu_title.set("先頭文字：矢印／テンキー8246で移動、Enter／5で決定、A–Zで直接選択")
        alphabet_state["buttons"] = []
        for child in menu_items.winfo_children():
            child.destroy()
        grid = ttk.Frame(menu_items)
        grid.pack(fill="x")
        labels = ["#"] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["?"]
        for index, label in enumerate(labels):
            button = tk.Button(
                grid, text=label, width=5, pady=5,
                relief="sunken" if index == selected_index else "raised",
                background="#dbeafe" if index == selected_index else "white",
                command=lambda value=label: (
                    send_menu_key("?") if value == "?" else render_database_candidates(value)))
            button.grid(row=index // 7, column=index % 7,
                        sticky="nsew", padx=2, pady=2)
            button.bind("<Enter>", lambda event, i=index: select_alphabet(i))
            alphabet_state["buttons"].append(button)
        for column in range(7):
            grid.grid_columnconfigure(column, weight=1)

    def parse_console(chunk):
        nonlocal parser_buffer, pending_title, pending_options, pending_paged
        parser_buffer += chunk.replace("\r", "")
        while "\n" in parser_buffer:
            line, parser_buffer = parser_buffer.split("\n", 1)
            if line == "[+] Reset":
                power_on_guard["reset"] = True
                power_on.cancel()
            dump_result.feed(line)
            paint_dump_result()
            was_active = batch.active
            batch.on_line(line)
            batch_report(was_active)
            firmware_update = reader_firmware_status(line)
            if firmware_update is not None:
                firmware_state.set(firmware_update)
            baud_match = re.search(r"\[Port\].* @ (\d+) baud", line)
            switched_match = re.search(r"\[Baud\] host switched to (\d+)", line)
            restored_match = re.search(r"\[Baud\] \d+ FAILED; restored (\d+)", line)
            passed_match = re.search(r"\[Baud\] (\d+) passed", line)
            stable_match = re.search(r"\[Benchmark\] stable baud=(\d+)", line)
            runtime_match = re.search(r"\[Baud\] runtime switched to (\d+)", line)
            demoted_match = re.search(
                r"\[Baud\] runtime \d+ failed; auto-demoted to (\d+)", line)
            transfer_match = re.match(r"\[Transfer\]\t(\d+)\t([0-9.]+)\t([0-9.]+)", line)
            transfer_done = re.match(r"\[Transfer complete\]\t(\d+)\t([0-9.]+)\t([0-9.]+)", line)
            storage_match = re.search(r"\[Storage Mode\] (PC|SD)$", line)
            version_match = re.match(r"OSCR\s+(HW\d+)\s+(V\S+)", line)
            led_match = re.match(r"\[LED\]\t(\w+)", line)
            led_activity_match = re.match(r"\[LED Activity\]\t(\w+)", line)
            msx_title_match = re.match(r"\[MSX Title\]\t(.+)", line)
            block_match = re.match(r"\[Transfer block\] (512|1024) bytes", line)
            if block_match:
                transfer_block_label.set(f"転送ブロック：{block_match.group(1)} bytes（PC要求）")
            firmware_block_match = re.match(r"\[Transfer block active\] (512|1024) bytes", line)
            if firmware_block_match:
                transfer_block_label.set(f"転送ブロック：{firmware_block_match.group(1)} bytes")
            checkpoint_match = re.match(r"\[Checkpoint active\] (\d+)", line)
            if checkpoint_match:
                checkpoint_label.set(f"確認間隔：{checkpoint_match.group(1)} KiB")
            if line.startswith("[Connected:"):
                reset_dump_result()
                power_on.reader_started(suppressed=(power_on_guard["reset"]
                    or power_on_guard["benchmark"] or benchmark["index"] is not None))
                power_on_guard["reset"] = False
                menu_navigation["title"] = ""
                if connection_state.get() != "接続済み":
                    notice = ("本体との接続が復旧しました。" if connection_session["ever_connected"]
                              else "本体に接続しました。")
                    inbox.put(f"[Connection] {notice}\n")
                connection_session["ever_connected"] = True
                set_connection_state("接続済み")
                # HELLO starts a new reader session in PC mode. Keep the
                # user's intent separate from the actual reader mode and
                # restore it only once the numbered menu is ready.
                desired = storage_current["desired"]
                set_storage_state("PC", desired if desired != "PC" else None)
            if version_match:
                window.title(
                    f"cartreaderPC PC133 — firmware {version_match.group(2)} / {version_match.group(1)}")
            if runtime_match:
                value = int(runtime_match.group(1))
                if value > 500000:
                    dump_baud.set(f"通信速度（吸い出し）：{value:,} baud")
                else:
                    normal_baud.set(f"通信速度（通常）：{value:,} baud")
            elif switched_match and benchmark["index"] is not None:
                dump_baud.set(f"通信速度（吸い出し）：速度ベンチ中 {int(switched_match.group(1)):,} baud")
            elif switched_match:
                normal_baud.set(f"通信速度（通常）：接続確認中 {int(switched_match.group(1)):,} baud")
            elif restored_match:
                normal_baud.set(f"通信速度（通常）：{int(restored_match.group(1)):,} baud")
            elif demoted_match:
                selected = int(demoted_match.group(1))
                normal_baud.set(f"通信速度（通常）：{min(selected, 500000):,} baud")
                dump_baud.set(f"通信速度（吸い出し）：{selected:,} baud")
            elif passed_match and benchmark["index"] is not None:
                dump_baud.set(
                    f"通信速度（吸い出し）：速度ベンチ中 "
                    f"{int(passed_match.group(1)):,} baud 合格")
            elif passed_match:
                normal_baud.set(f"通信速度（通常）：{int(passed_match.group(1)):,} baud")
                _, saved_dump = load_profile(port_identity(port.get()))
                dump_baud.set(f"通信速度（吸い出し）：{saved_dump:,} baud")
            elif stable_match:
                refresh_benchmark_hint()
                selected = int(stable_match.group(1))
                normal_baud.set(f"通信速度（通常）：{min(selected, 500000):,} baud")
                dump_baud.set(f"通信速度（吸い出し）：{selected:,} baud")
            if transfer_match:
                copied = int(transfer_match.group(1)) / 1048576
                transfer_speed.set(
                    f"転送: {float(transfer_match.group(2)):.1f} KiB/s "
                    f"(平均 {float(transfer_match.group(3)):.1f}) / {copied:.2f} MiB")
            elif transfer_done:
                copied = int(transfer_done.group(1)) / 1048576
                transfer_speed.set(
                    f"完了: 平均 {float(transfer_done.group(3)):.1f} KiB/s / "
                    f"{copied:.2f} MiB / {float(transfer_done.group(2)):.1f}秒")
            if storage_match:
                reported = storage_match.group(1)
                pending = storage_current["pending"]
                # An initial mode report after reconnect must not discard
                # a queued change to the other backend.
                set_storage_state(reported, pending if pending != reported else None)
                # The transfer label is separate from the storage buttons.
                # Clear a stale reservation only after confirmation, and do
                # not overwrite an active transfer/progress indication.
                if (pending is None or pending == reported) and \
                        transfer_speed.get().startswith("保存先変更予約:"):
                    transfer_speed.set("転送: 待機")
            if led_match:
                set_led_state(led_match.group(1))
            if led_activity_match:
                set_led_activity(led_activity_match.group(1) == "blinking")
            if msx_title_match:
                host_state["msx_title"] = msx_title_match.group(1).strip()
            if line.startswith("[RECONNECT]"):
                # Internal retry notifications are never raw user-facing logs.
                if stop.is_set():
                    set_connection_state("未接続")
                elif line == "[RECONNECT] ACTION_REQUIRED":
                    if connection_state.get() != "接続エラー":
                        set_connection_state("接続エラー")
                        inbox.put("[Connection] PC保存先への書込みに失敗しました。保存先を確認してください。\n")
                elif connection_state.get() not in ("接続待ち", "接続エラー"):
                    set_connection_state("接続待ち")
                    inbox.put("[Connection] 本体の接続を待っています。\n")
            elif line.startswith("[Disconnected") and stop.is_set():
                # During automatic recovery, the worker will classify the
                # failure before announcing a wait or actionable error.
                set_connection_state("未接続")
            if line.startswith(("[Disconnected", "[RECONNECT]")):
                # batch_report() above can mark an interrupted batch red.
                # Connection loss is the final event for result-color display.
                reset_dump_result()
                power_on.disconnected()
                set_led_activity(False)
                set_led_state("unknown")
                window.title("cartreaderPC PC133 — Disconnected")
                normal_baud.set("通信速度（通常）：未接続")
                dump_baud.set("通信速度（吸い出し）：未接続")
                transfer_speed.set("転送: 待機")
                input_ready.set(False)
                copy_cancel.clear()
                sd_browser["busy"] = False
                sd_browser["action"] = None
                sd_browser["pending"] = []
                sd_browser["scan_queue"] = []
                sd_browser["scan_active"] = False
                sd_browser["path"] = "/"
                sd_browser["deferred"] = ("L", "/") if sd_browser["window"] else None
                if sd_browser["tree"]:
                    sd_browser["tree"].delete(*sd_browser["tree"].get_children())
                if sd_browser["status"]:
                    sd_browser["status"].set("再接続後にSDを読み込みます")
            if line == "[Reader] input ready":
                input_ready.set(True)
                if input_mode.get() not in ("about", "candidate", "physical", "alphabet", "database-list",
                                             "nes-mapper", "nes-options"):
                    input_mode.set("menu")
                if storage_current["pending"] and input_mode.get() == "menu":
                    requested = storage_current["pending"]
                    storage_current["pending"] = None
                    code = "J" if requested == "PC" else "I"
                    storage_mode.set(f"保存先: {storage_current['mode']}（{requested}へ切替中）")
                    send_key(code)
                browser_start_next()
                batch_poll()
                power_on_poll()
            elif line == "[Reader] press button ready":
                input_ready.set(True)
                render_press_button()
                browser_start_next()
            elif line.startswith("[Input] acknowledged by reader:"):
                input_ready.set(False)
            if line.startswith("[SD Browser] list begin\t"):
                listed_path = line.split("\t", 1)[1]
                if sd_browser["scan_active"]:
                    sd_browser["scan_current"] = listed_path
                    sd_browser["scan_entries"] = []
                else:
                    sd_browser["path"] = listed_path
                    tree = sd_browser["tree"]
                    if tree:
                        tree.delete(*tree.get_children())
                    if sd_browser["status"]:
                        sd_browser["status"].set(f"読込中: {sd_browser['path']}")
            elif line.startswith("[SD Entry]\t"):
                parts = line.split("\t", 3)
                if len(parts) == 4 and sd_browser["scan_active"]:
                    sd_browser["scan_entries"].append(tuple(parts[1:]))
                elif len(parts) == 4 and sd_browser["tree"]:
                    kind, name, size = parts[1], parts[2], parts[3]
                    sd_browser["tree"].insert("", "end", values=(name, translator.translate("フォルダ" if kind == "D" else "ファイル"), "" if kind == "D" else size), tags=(kind,))
            elif line.startswith("[SD Browser] list complete\t"):
                sd_browser["busy"] = False
                sd_browser["action"] = None
                if sd_browser["scan_active"]:
                    base = (sd_browser["scan_current"] or "/").rstrip("/")
                    for kind, name, size in sd_browser["scan_entries"]:
                        child = (base + "/" + name) if base else "/" + name
                        if kind == "D":
                            sd_browser["scan_queue"].append(child)
                        else:
                            sd_browser["pending"].append(child)
                else:
                    if sd_browser["resort"]:
                        sd_browser["resort"]()
                    if sd_browser["status"]:
                        sd_browser["status"].set(f"{sd_browser['path']} — {len(sd_browser['tree'].get_children()) if sd_browser['tree'] else 0}項目")
            elif line == "[SD Browser] request failed":
                sd_browser["busy"] = False
                sd_browser["action"] = None
                sd_browser["pending"] = []
                sd_browser["scan_queue"] = []
                sd_browser["scan_active"] = False
                sd_browser["deferred"] = None
                if sd_browser["status"] and not sd_browser["cancelled"]:
                    sd_browser["status"].set("SD操作失敗。コンソールの理由を確認してください")
            elif line.startswith("[SD Progress]\t"):
                parts = line.split("\t")
                if len(parts) == 3:
                    done, total = int(parts[1]), int(parts[2])
                    if sd_browser["progress"]:
                        sd_browser["progress"].configure(maximum=max(1, total), value=done)
                    if sd_browser["progress_text"]:
                        percent = (100.0 * done / total) if total else 0.0
                        sd_browser["progress_text"].set(
                            f"{done / 1048576:.2f} MiB / {total / 1048576:.2f} MiB ({percent:.1f}%)")
            elif line.startswith(("[SD Browser] copy complete\t", "[SD Browser] copy failed\t")):
                sd_browser["busy"] = False
                sd_browser["action"] = None
                if sd_browser["progress"]:
                    sd_browser["progress"].configure(value=0)
                if sd_browser["status"] and not sd_browser["cancelled"]:
                    sd_browser["status"].set("コピー完了" if "complete" in line else "コピー失敗")
            elif line == "[SD Browser] copy cancelled":
                sd_browser["busy"] = False
                sd_browser["action"] = None
                sd_browser["cancelled"] = True
                sd_browser["pending"] = []
                sd_browser["scan_queue"] = []
                sd_browser["scan_active"] = False
                copy_cancel.clear()
                if sd_browser["status"]:
                    sd_browser["status"].set("キャンセルしました")
            elif line == "[Control] cartridge-select":
                render_candidate_controls()
            elif line.startswith("[Control] nes-mapper\t"):
                parts = line.split("\t")
                try:
                    current = int(parts[1])
                    supported = sorted({int(value) for value in parts[2:]})
                except (ValueError, IndexError):
                    current, supported = 0, []
                render_nes_mapper(current, supported)
            elif line.startswith("[Control] nes-options\t"):
                parts = line.split("\t")
                options = []
                if len(parts) >= 4:
                    for item in parts[3:]:
                        try:
                            index_text, value_text = item.split("=", 1)
                            options.append((int(index_text), value_text))
                        except (ValueError, IndexError):
                            continue
                    render_nes_options(parts[1], parts[2], options)
            elif line.startswith("[Control] msx-options\t"):
                parts = line.split("\t")
                options = []
                if len(parts) >= 4:
                    for item in parts[3:]:
                        try:
                            index_text, value_text = item.split("=", 1)
                            options.append((int(index_text, 16), value_text))
                        except (ValueError, IndexError):
                            continue
                    render_nes_options(parts[1], parts[2], options)
            elif line.startswith("[Control] alphabet\t"):
                try:
                    _marker, selected_text, database_name = line.split("\t", 2)
                    selected = int(selected_text)
                except (ValueError, IndexError):
                    selected = 0
                    database_name = ""
                render_alphabet_controls(max(0, min(27, selected)), database_name)
            elif line.startswith("[Control] menu-cursor "):
                cursor = re.fullmatch(r"\[Control\] menu-cursor (-1|[0-6])", line)
                select_cursor = menu_navigation.get("select_reader_cursor")
                if cursor and input_mode.get() == "menu" and select_cursor:
                    select_cursor(int(cursor.group(1)))
            elif line == "[Control] about":
                render_about()
            elif line == "[Control] physical-buttons":
                render_physical_fallback()
            elif line == "Set Mapper manually":
                clear_operation("Mapper設定を読み込み中...")
            match = re.match(r"^([0-6])\)(.*)$", line)
            if match:
                pending_options.append((match.group(1), match.group(2).strip()))
            elif re.match(r"^[ud]\)", line):
                pending_paged = True
            elif line.startswith(("Please browse pages", "and enter a selection", "Select on reader or PC")):
                if pending_options:
                    render_menu(pending_title, pending_options, pending_paged)
                    pending_options = []
                    pending_paged = False
            elif line and not line.startswith(("[", "OSCR")):
                pending_title = line
    benchmark = {"index": None, "waiting": False, "passed": []}
    benchmark_rates = (285714, 333333, 400000, 500000, 666667, 1000000, 2000000)
    reconnect = threading.Event()

    def queue_benchmark_rate():
        index = benchmark["index"]
        if index is None:
            return
        if index >= len(benchmark_rates):
            selected = max(benchmark["passed"], default=250000)
            save_profile(port_identity(port.get()), selected, benchmark["passed"],
                         benchmark_complete=True if benchmark["passed"] else None)
            inbox.put(f"[Benchmark] stable baud={selected}\n")
            benchmark["index"] = None
            benchmark["waiting"] = False
            return
        if not benchmark["waiting"]:
            keys.put(ord("A") + index)
            benchmark["waiting"] = True
            inbox.put(f"[Benchmark] independent test {index + 1}/{len(benchmark_rates)}\n")

    def run(selected_port, selected_output):
        feedback = ConnectionFeedback()
        ram_log_failed = False
        def service_log(message):
            nonlocal ram_log_failed
            if "[Browser protocol] 1" in message:
                host_state["component_browser"] = True
            if message.startswith("[Baud]") and (
                    " transport error: " in message
                    or "USB serial driver rejected" in message):
                # A driver exception during a baud-rate probe belongs in
                # detailed diagnostics, not the ordinary console.
                inbox.put(("connection_detail", message))
                inbox.put("[Connection] 通信速度の切替に失敗しました。詳細ログを確認してください。\n")
                return
            if message.startswith("[RAM]\t"):
                inbox.put(("ram", message))
                try:
                    record_ram_diagnostic(message, selected_port)
                except OSError as exc:
                    if not ram_log_failed:
                        inbox.put(f"[RAM log] {exc}\n")
                        ram_log_failed = True
                return
            if "[Connected:" in message:
                host_state["component_browser"] = False
                feedback.connected()
            if message.strip() == "[Input] acknowledged by reader: <detach>":
                detach_ack.set()
                # Close COM before the reader finishes its watchdog restart.
                # The firmware also skips PC detection once, so this is a
                # latency improvement rather than the only race protection.
                stop.set()
            if message.strip() == "[+] Reset":
                # Covers Reset selected using the reader's physical buttons.
                host_state["expected_reader_reset"] = True
            # Runtime speed changes happen while the reader is drawing its
            # original [*******************] bar.  Feed them to the parser but
            # do not insert them into the scrolling console, otherwise the bar
            # is split apart by host status text.
            if message.startswith(("[Baud] host runtime switch to ",
                                   "[Baud] runtime switched to ",
                                   "[LED]\t", "[LED Activity]\t")):
                inbox.put(("status", message))
            else:
                inbox.put(message)
            passed = re.search(r"\[Benchmark\] passed baud=(\d+)", message)
            failed = re.search(r"\[Baud\] (\d+) FAILED", message)
            if benchmark["index"] is not None and (passed or failed):
                tested = int((passed or failed).group(1))
                expected = benchmark_rates[benchmark["index"]]
                if tested == expected:
                    if passed:
                        benchmark["passed"].append(tested)
                    benchmark["index"] += 1
                    benchmark["waiting"] = False
                    host_state["expected_reader_reset"] = True
            if message.strip() == "[Reader] input ready":
                queue_benchmark_rate()
        while not stop.is_set():
            try:
                serve(selected_port, selected_output, args.sd, keys, service_log, stop,
                      reconnect, copy_cancel,
                      lambda transferred, current, average: transfer_updates.put(
                          (transferred, current, average)), host_state)
                if stop.is_set():
                    break
            except Exception as exc:
                message = str(exc)
                if message == "benchmark next rate":
                    feedback.connected()
                    inbox.put(("status", "[RECONNECT] WAIT\n"))
                    host_state["suppress_dtr_reset_once"] = True
                    stop.wait(1.0)
                    continue
                runtime_baud = host_state.pop("runtime_baud", None)
                transport_failure = any(token in message for token in (
                    "CRC mismatch", "frame magic mismatch", "unexpected sequence/reset"))
                if runtime_baud and runtime_baud > 500000 and transport_failure:
                    selected = demote_profile(port_identity(selected_port), runtime_baud)
                    inbox.put(
                        f"[Baud] runtime {runtime_baud} failed; auto-demoted to {selected}\n")
                event, detail = feedback.failure(exc)
                if detail is not None:
                    inbox.put(("connection_detail", detail))
                if event is not None:
                    inbox.put(("status", event))
            stop.wait(1.0)
    def connect():
        nonlocal worker
        if worker and worker.is_alive():
            return
        if not any(Path(output.get()).glob("*.txt")) or not any(
                (Path(output.get()) / name).is_file()
                for name in ("gb.txt", "gba.txt", "snes.txt", "md.txt", "n64.txt", "nes.txt")):
            from tkinter import messagebox
            messagebox.showwarning(
                translator.translate("データベース"),
                translator.translate("保存先にDBがありません。上流のsdフォルダ内の必要なTXTを配置してください。") + "\n"
                "https://github.com/sanni/cartreader/tree/master/sd")
        reset_dump_result()
        connection_session["ever_connected"] = False
        set_connection_state("接続待ち")
        inbox.put("[Connection] 本体の接続を待っています。\n")
        safe_rate, dump_rate = load_profile(port_identity(port.get()))
        normal_baud.set(f"通信速度（通常）：{safe_rate:,} baud")
        dump_baud.set(f"通信速度（吸い出し）：{dump_rate:,} baud")
        stop.clear()
        while not keys.empty():
            keys.get_nowait()
        worker = threading.Thread(target=run, args=(port.get(), output.get()), daemon=True)
        worker.start()
    def disconnect():
        power_on.disconnected()
        if batch.active:
            batch_stop("切断によって一括操作を終了しました")
        # Clear after batch_stop(), which may otherwise repaint a failure red.
        reset_dump_result()
        if worker and worker.is_alive():
            detach_ack.clear()
            keys.put(0x04)
            # The worker continues servicing CRPC while the GUI waits.  Menu
            # idle normally acknowledges immediately; active transfers fall
            # back to the firmware's host-loss watchdog after the port closes.
            detach_ack.wait(2.0)
        stop.set()
        set_connection_state("未接続")
    connect_button = tk.Button(row, text="接続", command=connect, padx=12)
    connect_button.pack(side="left", padx=8)
    connection_widgets["button"] = connect_button
    set_connection_state(connection_state.get())
    ttk.Button(row, text="切断", command=disconnect).pack(side="left")
    def request_benchmark():
        power_on.cancel()
        power_on_guard["benchmark"] = True
        inbox.put("[Benchmark] requested\n")
        if benchmark["index"] is not None:
            return
        reset_profile_candidates(port_identity(port.get()))
        benchmark["index"] = 0
        benchmark["waiting"] = False
        benchmark["passed"] = []
        if input_ready.get():
            queue_benchmark_rate()
    benchmark_frame = ttk.Frame(row)
    benchmark_frame.pack(side="left", padx=8)
    ttk.Button(benchmark_frame, text="速度ベンチ", command=request_benchmark).pack(anchor="w")
    benchmark_hint = ttk.Label(
        benchmark_frame, foreground="#b91c1c", wraplength=220,
        text="初めて吸い出す前に速度ベンチを実行してください。安定して使える最速の吸い出し速度を測り、自動で設定します。")

    def refresh_benchmark_hint(*_):
        if port.get() and has_completed_benchmark(port_identity(port.get())):
            benchmark_hint.pack_forget()
        elif not benchmark_hint.winfo_manager():
            benchmark_hint.pack(anchor="w")

    port.trace_add("write", refresh_benchmark_hint)
    refresh_benchmark_hint()
    def request_transmit_test(test_2m=False):
        if (not (worker and worker.is_alive()) or not input_ready.get()
                or input_mode.get() != "menu" or sd_browser["busy"]
                or benchmark["index"] is not None):
            inbox.put("[TX test] wait for a numbered menu before starting\n")
            return
        firmware = re.search(r"firmware V\S+-PC(\d+)\b", window.title())
        if test_2m and (firmware is None or int(firmware.group(1)) < 132):
            inbox.put("[TX test] 2M requires firmware PC132 or newer\n")
            return
        inbox.put("[TX test] 2M requested\n" if test_2m else "[TX test] requested\n")
        send_key("Y" if test_2m else "T")
    diagnostic_log = tk.BooleanVar(value=False)
    diagnostic_menu = tk.Menu(window, tearoff=False)
    diagnostic_menu.add_command(label="転送試験 1MiB", command=request_transmit_test)
    diagnostic_menu.add_command(label="転送試験 1MiB (2M)",
                                command=lambda: request_transmit_test(test_2m=True))
    diagnostic_menu.add_checkbutton(label="詳細ログを表示", variable=diagnostic_log)
    diagnostic_button = ttk.Menubutton(row, text="診断", menu=diagnostic_menu)
    diagnostic_button.pack(side="left")
    def open_sd_browser():
        if sd_browser["window"] and sd_browser["window"].winfo_exists():
            sd_browser["window"].lift()
            return
        dialog = tk.Toplevel(window)
        dialog.title(translator.translate("本体SDブラウザ — 読み取り専用"))
        dialog.geometry(ui_settings.get("sd_browser_geometry", "760x540"))
        sd_browser["window"] = dialog
        bar = ttk.Frame(dialog, padding=8)
        bar.pack(fill="x")
        path_label = tk.StringVar(value=sd_browser["path"])
        ttk.Label(bar, textvariable=path_label).pack(side="left", fill="x", expand=True)
        columns = ("name", "type", "size")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", selectmode="extended")
        saved_column = ui_settings.get("sd_sort_column")
        sort_state = {
            "column": saved_column if saved_column in columns else None,
            "reverse": bool(ui_settings.get("sd_sort_reverse", False)),
        }
        heading_text = {"name": "名前", "type": "種類", "size": "サイズ"}
        def apply_sort(column, reverse):
            def key(item):
                value = tree.set(item, column)
                if column == "size":
                    try:
                        return (0, int(value))
                    except ValueError:
                        return (-1, 0)
                return value.casefold()
            items = sorted(tree.get_children(""), key=key, reverse=reverse)
            for index, item in enumerate(items):
                tree.move(item, "", index)
            for name in columns:
                marker = (" ▼" if reverse else " ▲") if name == column else ""
                tree.heading(name, text=heading_text[name] + marker)
        def sort_tree(column):
            reverse = not sort_state["reverse"] if sort_state["column"] == column else False
            sort_state.update(column=column, reverse=reverse)
            apply_sort(column, reverse)
            ui_settings["sd_sort_column"] = column
            ui_settings["sd_sort_reverse"] = reverse
            try:
                save_ui_settings(ui_settings)
            except OSError as exc:
                inbox.put(f"[Settings] save failed: {exc}\n")
        def reapply_sort():
            if sort_state["column"]:
                apply_sort(sort_state["column"], sort_state["reverse"])
        sd_browser["resort"] = reapply_sort
        for column in columns:
            tree.heading(column, text=heading_text[column], command=lambda c=column: sort_tree(c))
        tree.column("name", width=430); tree.column("type", width=90); tree.column("size", width=120, anchor="e")
        tree.pack(fill="both", expand=True, padx=8)
        sd_browser["tree"] = tree
        status = tk.StringVar(value="SDを読み込みます")
        sd_browser["status"] = status
        ttk.Label(dialog, textvariable=status, padding=8).pack(anchor="w")
        progress = ttk.Progressbar(dialog, mode="determinate")
        progress.pack(fill="x", padx=8)
        sd_browser["progress"] = progress
        progress_text = tk.StringVar(value="0.00 MiB / 0.00 MiB (0.0%)")
        sd_browser["progress_text"] = progress_text
        ttk.Label(dialog, textvariable=progress_text, padding=(8, 2)).pack(anchor="w")
        buttons = ttk.Frame(dialog, padding=8)
        buttons.pack(fill="x")

        def join_path(name):
            base = sd_browser["path"].rstrip("/")
            return (base + "/" + name) if base else "/" + name
        def refresh_browser():
            if sd_browser["busy"]:
                return
            if browser_command("L", sd_browser["path"]):
                path_label.set(sd_browser["path"])
        def open_item(event=None):
            if sd_browser["busy"]:
                return
            selected = tree.selection()
            if len(selected) != 1 or "D" not in tree.item(selected[0], "tags"):
                return
            new_path = join_path(tree.item(selected[0], "values")[0])
            if browser_command("L", new_path):
                sd_browser["path"] = new_path
                path_label.set(new_path)
        def up():
            if sd_browser["busy"]:
                return
            current = sd_browser["path"].rstrip("/")
            new_path = current.rsplit("/", 1)[0] or "/"
            if browser_command("L", new_path):
                sd_browser["path"] = new_path
                path_label.set(new_path)
        def copy_selected():
            if sd_browser["busy"]:
                return
            selected = tree.selection()
            if not selected:
                return
            sd_browser["pending"] = []
            sd_browser["scan_queue"] = []
            for item in selected:
                path = join_path(tree.item(item, "values")[0])
                if "D" in tree.item(item, "tags"):
                    sd_browser["scan_queue"].append(path)
                else:
                    sd_browser["pending"].append(path)
            sd_browser["scan_active"] = bool(sd_browser["scan_queue"])
            browser_start_next()
        def cancel_copy():
            sd_browser["deferred"] = None
            sd_browser["pending"] = []
            sd_browser["scan_queue"] = []
            sd_browser["scan_active"] = False
            if sd_browser["busy"]:
                if sd_browser["action"] == "C":
                    copy_cancel.set()
                    status.set("キャンセル要求中...")
                else:
                    status.set("フォルダ確認を中止しました")
        def close_dialog():
            sd_browser["deferred"] = None
            ui_settings["sd_browser_geometry"] = dialog.geometry()
            try:
                save_ui_settings(ui_settings)
            except OSError:
                pass
            sd_browser["window"] = None
            sd_browser["tree"] = None
            sd_browser["progress"] = None
            sd_browser["progress_text"] = None
            sd_browser["status"] = None
            sd_browser["resort"] = None
            dialog.destroy()
        ttk.Button(buttons, text="上へ", command=up).pack(side="left")
        ttk.Button(buttons, text="開く", command=open_item).pack(side="left", padx=4)
        ttk.Button(buttons, text="更新", command=refresh_browser).pack(side="left")
        ttk.Button(buttons, text="選択をPCへコピー", command=copy_selected).pack(side="left", padx=12)
        ttk.Button(buttons, text="キャンセル", command=cancel_copy).pack(side="left")
        ttk.Button(buttons, text="閉じる", command=close_dialog).pack(side="right")
        tree.bind("<Double-1>", open_item)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.after(100, refresh_browser)
    ttk.Button(row, text="本体SDブラウザ", command=open_sd_browser).pack(side="left", padx=(0, 8))
    def choose_storage(code):
        power_on.cancel()
        requested = "PC" if code == "J" else "SD"
        storage_current["desired"] = requested
        if input_ready.get() and input_mode.get() == "menu":
            send_key(code)
            storage_mode.set(f"保存先: {storage_current['mode']}（{requested}へ切替中）")
        else:
            # An already-open dump cannot migrate safely between backends.
            # Queue the request for the next ordinary numbered menu instead.
            set_storage_state(pending=requested)
            transfer_speed.set(f"保存先変更予約: 次回の吸い出しから{requested}保存")
    pc_storage_button = tk.Button(row, text="PC保存", command=lambda: choose_storage("J"), padx=8)
    pc_storage_button.pack(side="left")
    sd_storage_button = tk.Button(row, text="SD保存", command=lambda: choose_storage("I"), padx=8)
    sd_storage_button.pack(side="left", padx=(2, 4))
    storage_widgets["PC"] = pc_storage_button
    storage_widgets["SD"] = sd_storage_button
    set_storage_state("PC", None)
    ttk.Label(window, textvariable=transfer_speed, anchor="w", padding=(8, 3)).pack(
        fill="x", padx=8, pady=(0, 4))
    text.pack(fill="both", expand=True, padx=8)
    def global_key(event):
        if event.widget.winfo_toplevel() is not window:
            return None
        # Application shortcuts must not become reader commands. Windows/Tk
        # may report Win+Shift+S with an empty char; '' is contained in every
        # Python string, so membership checks must also require a nonempty key.
        if os.name != "nt" and event.state & (0x0004 | 0x0008 | 0x0040 | 0x0080 | 0x20000):
            return None
        if os.name == "nt" and any(
                ctypes.windll.user32.GetAsyncKeyState(code) & 0x8000
                for code in (0x11, 0x12, 0x5B, 0x5C)):
            return None
        key = event.keysym.lower()
        typed_digit = normalize_digit(
            key, event.char, event.keycode, windows=(os.name == "nt"))
        if input_mode.get() == "nes-mapper":
            # The mapper combobox receives digits, Backspace and Enter itself.
            return None
        if input_mode.get() == "alphabet":
            delta = {"left": -1, "right": 1, "up": -7, "down": 7}.get(key)
            if typed_digit in ("8", "2", "4", "6"):
                delta = {"8": -7, "2": 7, "4": -1, "6": 1}[typed_digit]
            if delta is not None:
                select_alphabet(alphabet_state["selected"] + delta)
                return "break"
            if key in ("return", "space", "kp_enter") or typed_digit == "5":
                alphabet_state["buttons"][alphabet_state["selected"]].invoke()
                return "break"
            if len(key) == 1 and key in "abcdefghijklmnopqrstuvwxyz":
                alphabet_state["buttons"][ord(key)-ord("a")+1].invoke()
                return "break"
        if input_mode.get() == "database-list":
            listing = database_list_state.get("listing")
            if key in ("up", "down") or typed_digit in ("8", "2"):
                selected = listing.curselection()
                delta = -1 if key == "up" or typed_digit == "8" else 1
                index = max(0, min(listing.size()-1, (selected[0] if selected else 0)+delta))
                listing.selection_clear(0, "end")
                listing.selection_set(index)
                listing.see(index)
                return "break"
            if key in ("return", "kp_enter") or typed_digit == "5":
                database_list_state["choose"]()
                return "break"
            if typed_digit == "0" or key == "escape":
                render_alphabet_controls(alphabet_state["selected"], alphabet_state["database"])
                return "break"
        if input_mode.get() == "nes-options":
            buttons = nes_option_state["buttons"]
            if not buttons:
                return "break"
            delta = {"left": -1, "right": 1, "up": -4, "down": 4}.get(key)
            if delta is not None:
                nes_option_state["selected"] = (
                    nes_option_state["selected"] + delta) % len(buttons)
                for position, button in enumerate(buttons):
                    active = position == nes_option_state["selected"]
                    button.configure(background="#dbeafe" if active else "white",
                                     highlightbackground="#2563eb" if active else "white",
                                     highlightthickness=2 if active else 0)
                buttons[nes_option_state["selected"]].focus_set()
                return "break"
            if key in ("return", "space", "kp_enter"):
                buttons[nes_option_state["selected"]].invoke()
                return "break"
            if typed_digit and int(typed_digit) < len(buttons):
                buttons[int(typed_digit)].invoke()
                return "break"
        if input_mode.get() == "press" and (key in ("return", "space", "kp_enter") or typed_digit == "0"):
            send_menu_key(" ")
            return "break"
        if input_mode.get() == "about":
            if key in ("left", "right"):
                select_simple(simple_controls["selected"] + (-1 if key == "left" else 1))
                return "break"
            if key in ("escape", "space") or typed_digit == "0":
                simple_controls["buttons"][0].invoke()
                return "break"
            if key == "l" or typed_digit == "1":
                simple_controls["buttons"][1].invoke()
                return "break"
            if key in ("return", "kp_enter"):
                simple_controls["buttons"][simple_controls["selected"]].invoke()
                return "break"
        if input_mode.get() in ("candidate", "physical"):
            if typed_digit in ("0", "1", "2"):
                select_simple(int(typed_digit))
                simple_controls["buttons"][int(typed_digit)].invoke()
                return "break"
            if key in ("left", "up", "right", "down"):
                select_simple(0 if key in ("left", "up") else 1)
                simple_controls["buttons"][simple_controls["selected"]].invoke()
                return "break"
            if key in ("return", "space", "kp_enter"):
                select_simple(2)
                simple_controls["buttons"][2].invoke()
                return "break"
            if key in ("u", "d", "l"):
                send_key(key)
                return "break"
        if (input_mode.get() == "menu" and menu_navigation["items"]
                and is_widget_within(event.widget, menu_items)):
            root_menu = menu_navigation.get("root_menu", False)
            if root_menu:
                consumed, auto_entry = auto_shortcut.key_down(
                    typed_digit, menu_navigation.get("auto_entries", ()))
                if consumed:
                    if auto_entry is not None:
                        navigator = menu_navigation["navigator"]
                        selected = navigator.select_auto_shortcut(auto_entry[0])
                        if selected is not None:
                            paint = menu_navigation.get("paint_selection")
                            if paint:
                                paint()
                            activate = menu_navigation.get("activate_auto")
                            if activate:
                                activate(auto_entry)
                    return "break"

                navigator = menu_navigation["navigator"]
                if key in ("u", "d"):
                    send_menu_key(key)
                    return "break"
                if key in ("up", "down"):
                    navigator.move_vertical(-1 if key == "up" else 1)
                    menu_navigation["selected"] = navigator.row
                    menu_navigation["selected_auto"] = navigator.auto_index
                    paint = menu_navigation.get("paint_selection")
                    if paint:
                        paint()
                    return "break"
                if key in ("left", "right"):
                    page_action = navigator.move_horizontal(-1 if key == "left" else 1)
                    menu_navigation["selected"] = navigator.row
                    menu_navigation["selected_auto"] = navigator.auto_index
                    paint = menu_navigation.get("paint_selection")
                    if paint:
                        paint()
                    if page_action == "previous-page":
                        send_menu_key("[")
                    elif page_action == "next-page":
                        send_menu_key("]")
                    return "break"
                if key in ("prior", "page_up"):
                    send_menu_key("[")
                    return "break"
                if key in ("next", "page_down"):
                    send_menu_key("]")
                    return "break"
                if key in ("return", "space", "kp_enter"):
                    action = navigator.current_action()
                    if action and action[0] == "reader":
                        send_menu_key(action[1])
                    elif action and action[0] == "auto":
                        entry = action[1]
                        start_batch(entry[1], entry[2])
                    return "break"
                if typed_digit:
                    reader_key = resolve_menu_number(
                        menu_navigation["title"], menu_navigation["options"],
                        typed_digit, menu_navigation.get("paged", False))
                    if reader_key is not None:
                        if reader_key in ("[", "]"):
                            send_menu_key(reader_key)
                        else:
                            target_row = next(
                                (i for i, row_data in enumerate(menu_navigation["rows"])
                                 if row_data["reader_number"] == reader_key),
                                None,
                            )
                            if target_row is not None:
                                navigator.select_row(target_row)
                                menu_navigation["selected"] = target_row
                                menu_navigation["selected_auto"] = None
                                paint = menu_navigation.get("paint_selection")
                                if paint:
                                    paint()
                            send_menu_key(reader_key)
                    return "break"
                if key in ("tab", "iso_left_tab"):
                    # The operation menu is one tab stop. Skip its rows,
                    # inline Auto buttons and page controls as individual stops.
                    backwards = bool(event.state & 0x0001) or key == "iso_left_tab"
                    move_focus_from_group(menu_items, backwards)
                    return "break"
                return None

            # Submenus keep their existing reader numbering and page behavior.
            if key in ("u", "d"):
                send_menu_key(key)
                return "break"
            if menu_navigation.get("paged") and typed_digit in ("7", "8"):
                send_menu_key("[" if typed_digit == "7" else "]")
                return "break"
            if key in ("prior", "page_up"):
                send_menu_key("[")
                return "break"
            if key in ("next", "page_down"):
                send_menu_key("]")
                return "break"
            if key in ("up", "down"):
                delta = -1 if key == "up" else 1
                selected = (menu_navigation["selected"] + delta) % len(menu_navigation["items"])
                menu_navigation["selected"] = selected
                paint = menu_navigation.get("paint_selection")
                if paint:
                    paint()
                return "break"
            if key == "left":
                send_menu_key("[")
                return "break"
            if key == "right":
                send_menu_key("]")
                return "break"
            if key in ("return", "space", "kp_enter"):
                send_menu_key(menu_navigation["options"][menu_navigation["selected"]][0])
                return "break"
            if typed_digit and typed_digit in "0123456789ud":
                send_menu_key(typed_digit)
                return "break"
            return None
    # Bind the disabled console directly as well: Tk's Text class can consume
    # key events before the application-wide binding gets them.
    capture_tag = "ReaderKeyboardCapture"
    def global_key_release(event):
        key = event.keysym.lower()
        if key in ("0", "kp_0", "kp_insert") or (
                os.name == "nt" and event.keycode in (48, 96)):
            auto_shortcut.key_up("0")

    window.bind_class(capture_tag, "<KeyPress>", global_key)
    window.bind_class(capture_tag, "<KeyRelease>", global_key_release)
    window.bind_all("<FocusOut>", lambda _event: auto_shortcut.reset(), add="+")
    def install_capture(widget):
        if widget.winfo_toplevel() is not window:
            return
        tags = widget.bindtags()
        if capture_tag not in tags:
            widget.bindtags((capture_tag,) + tags)
        for child in widget.winfo_children():
            install_capture(child)
    def refresh_capture():
        install_capture(window)
        window.after(100, refresh_capture)
    refresh_capture()
    def pump():
        nonlocal parser_buffer, pending_title, pending_options, pending_paged
        displayed_chunks = []
        destination_state = "disabled" if worker and worker.is_alive() else "normal"
        output_entry.configure(state=destination_state)
        output_button.configure(state=destination_state)
        text.configure(state="normal")
        latest_transfer = None
        while True:
            try:
                latest_transfer = transfer_updates.get_nowait()
            except queue.Empty:
                break
        if isinstance(latest_transfer, tuple) and len(latest_transfer) == 3:
            transferred, current, average = latest_transfer
            transfer_speed.set(
                f"転送: {current:.1f} KiB/s (平均 {average:.1f}) / "
                f"{transferred / 1048576:.2f} MiB")
        while True:
            try:
                item = inbox.get_nowait()
                if isinstance(item, tuple) and item[0] == "ram":
                    labels = ram_labels(item[1])
                    if labels:
                        ram_state.set(labels[0])
                        ram_detail.set(labels[1])
                    if diagnostic_log.get():
                        text.insert("end", item[1])
                        displayed_chunks.append(item[1])
                    continue
                if isinstance(item, tuple) and item[0] == "status":
                    if item[1].startswith("[RECONNECT]"):
                        # The interrupted reader may have left a partial menu
                        # line in the parser buffer. Never concatenate our
                        # synthetic retry status with that stale text.
                        parser_buffer = ""
                        pending_title = ""
                        pending_options = []
                        pending_paged = False
                    parse_console(item[1])
                    continue
                if isinstance(item, tuple) and item[0] == "connection_detail":
                    if diagnostic_log.get():
                        text.insert("end", item[1])
                        displayed_chunks.append(item[1])
                        text.see("end")
                    continue
                chunk = item
                shown = chunk
                if sd_browser["cancelled"]:
                    shown = shown.replace("[SD Browser] copy failed\t", "[SD Browser] copy cancelled\t")
                    shown = shown.replace("[SD Browser] request failed\n", "")
                    shown = shown.replace("[SD Browser] request failed", "")
                if not diagnostic_log.get():
                    shown = shown.replace(
                        "[Disconnected. Check .pc-manifest.json; open files remain incomplete.]",
                        "[Connection] 転送が中断され、未完了のファイルがあります。.pc-manifest.jsonを確認してください。")
                    shown = "".join(
                        line for line in shown.splitlines(keepends=True)
                        if not line.startswith(("[Input]", "[Reader]", "[Menu]",
                                                "[SD Progress]", "[Disconnected.]")))
                # Translate presentation text; parse the original protocol below.
                shown = "".join(
                    translator.translate(line) if line.startswith(("[自動吸出し] ", "[Connection] ", "[Auto start] "))
                    else line for line in shown.splitlines(keepends=True))
                text.insert("end", shown)
                displayed_chunks.append(shown)
                parse_console(chunk)
                text.see("end")
            except queue.Empty:
                break
        if displayed_chunks:
            try:
                append_oscr_log(output.get(), "".join(displayed_chunks))
            except OSError as exc:
                if not oscr_log_error["reported"]:
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "OSCR_LOGPC.txt",
                        translator.translate("OSCR_LOGPC.txt に書き込めませんでした。") + "\n" + str(exc),
                        parent=window,
                    )
                    oscr_log_error["reported"] = True
        text.configure(state="disabled")
        translator.refresh()
        window.after(50, pump)
    def remember_geometry(event):
        if event.widget is window and window.state() == "normal":
            normal_geometry["value"] = (
                f"{window.winfo_width()}x{window.winfo_height()}"
                f"{window.winfo_x():+d}{window.winfo_y():+d}")
    def quit_app():
        ui_settings["window_geometry"] = normal_geometry["value"]
        ui_settings["window_maximized"] = window.state() == "zoomed"
        ui_settings["physical_controls_visible"] = bool(physical_visible.get())
        if sd_browser["window"] and sd_browser["window"].winfo_exists():
            ui_settings["sd_browser_geometry"] = sd_browser["window"].geometry()
        try:
            save_ui_settings(ui_settings)
        except OSError:
            pass
        disconnect()
        window.destroy()
    window.bind("<Configure>", remember_geometry, add="+")
    window.protocol("WM_DELETE_WINDOW", quit_app)
    language_picker = ttk.Combobox(info_row, textvariable=language,
                                  values=("Japanese", "English"), state="readonly", width=9)
    language_picker.pack(side="left", padx=6)
    def change_language(event=None):
        ui_settings["language"] = language.get()
        try:
            save_ui_settings(ui_settings)
        except OSError as exc:
            inbox.put(f"[Settings] {exc}\n")
        translator.refresh()
    language_picker.bind("<<ComboboxSelected>>", change_language)
    refresh()
    pump()
    window.mainloop()


def main():
    ensure_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="COM3, /dev/ttyACM0, etc.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--sd", default=str(BASE / "sd"), help="PC-side database folder; physical SD is unnecessary")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        try:
            import io
            import tempfile
            import serial
            assert receive(io.BytesIO(encode(1, 7))) == (1, 7, b"")
            with tempfile.TemporaryDirectory() as path:
                hello = Storage(path, lambda s: None).dispatch(1, b"")
                assert (len(hello) == 17 and hello[0] == 0 and hello[9] == 32
                        and int.from_bytes(hello[10:12], "little") == 512 and hello[12] == 7)
                assert ram_labels("[RAM]\t800\t300\t6260\t8192\t0\t2\n")
            (BASE / "exe-selftest.txt").write_text("PASS\n", encoding="utf-8")
            return 0
        except Exception as exc:
            # Windowed PyInstaller builds otherwise leave an unhandled-error
            # dialog and both launcher processes running.
            (BASE / "exe-selftest.txt").write_text(
                f"FAIL: {type(exc).__name__}: {exc}\n", encoding="utf-8")
            return 1
    elif args.list_ports:
        from serial.tools import list_ports
        for port in list_ports.comports():
            print(port.device, port.description)
    elif args.cli:
        args.output = args.output or str(BASE)
        if not args.port:
            parser.error("--cli requires --port")
        terminal(args)
    else:
        if not acquire_single_instance():
            return 0
        gui(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
