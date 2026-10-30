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

BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
PROFILE_FILE = BASE / "baud_profiles.json"
UI_SETTINGS_FILE = BASE / "ui_settings.json"
TRANSFER_SETTINGS_FILE = BASE / "transfer_settings.json"
ALLOWED_BAUDS = (250000, 285714, 333333, 400000, 500000, 666667, 1000000, 2000000)
_SINGLE_INSTANCE_HANDLE = None


def load_transfer_block():
    try:
        data = json.loads(TRANSFER_SETTINGS_FILE.read_text(encoding="utf-8"))
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


def save_profile(identity, baud, passed=None):
    try:
        profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        if not isinstance(profiles, dict):
            profiles = {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        profiles = {}
    previous = profiles.get(identity, {})
    if passed is None and isinstance(previous, dict):
        passed = previous.get("passed", [])
    passed = sorted({int(value) for value in (passed or []) if int(value) in ALLOWED_BAUDS})
    profiles[identity] = {
        "safe": min(int(baud), 500000), "dump": int(baud), "passed": passed}
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
            None, "CartReaderPC は既に起動しています。", "Cart Reader", 0x30)
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
            raise ValueError(f"SD database folder not found: {source}")
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
    store = None
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
                                    cancel_event, progress, host_state, transfer_block)
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
                        save_profile(identity, selected)
                        log(f"[Baud] saved {selected} for {identity}\n")
                    elif passed:
                        selected = int(passed.group(1))
                        checkpoint_profile(identity, selected)
                        log(f"[Baud] checkpoint saved {selected} for {identity}\n")
                if last_seq is not None and seq != ((last_seq + 1) & 0xffff):
                    raise ValueError("unexpected sequence/reset; reconnect reader")
                last_seq = seq
                response = store.dispatch(op, payload)
                if response[0] and op == 22:
                    raise OSError("streamed host file write failed; transfer stopped")
                if pending_baud and op == 13 and b"[Benchmark] stable baud=" in payload:
                    log(f"[Baud] {pending_baud[0]} passed\n")
                    pending_baud = None
                # Console output is intentionally one-way. A lost ACK must not
                # freeze the reader between benchmark status lines.
                if op in (13, 19, 20, 22, 23):
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
                        pending_baud = None
                        if host_state is not None:
                            host_state["runtime_baud"] = requested
                        log(f"[Baud] runtime switched to {requested}\n")
                    else:
                        # Reader needs up to 2.5 seconds to time out at the rejected
                        # speed, then 300 ms to restore the previous speed.
                        pending_baud = (requested, previous, time.monotonic() + 2.6, switched)
                if response[0] and op in (1, 3, 5):
                    raise OSError("fatal host file error; transfer stopped")
        finally:
            wire.close()
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
    try:
        serve(args.port, args.output, args.sd, keys, lambda s: print(s, end="", flush=True), stop)
    except KeyboardInterrupt:
        stop.set()


def gui(args):
    import tkinter as tk
    from tkinter import ttk, filedialog
    from tkinter.scrolledtext import ScrolledText
    from serial.tools import list_ports
    window = tk.Tk()
    ui_settings = load_ui_settings()
    window.title("Cart Reader 15.5 — 未接続")
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
    output = tk.StringVar(value=str(Path(args.output).resolve()))
    folder = ttk.Frame(window, padding=8)
    folder.pack(fill="x")
    ttk.Label(folder, text="保存先").pack(side="left")
    ttk.Entry(folder, textvariable=output).pack(side="left", fill="x", expand=True, padx=8)
    def choose():
        selected = filedialog.askdirectory()
        if selected:
            output.set(selected)
    ttk.Button(folder, text="選択", command=choose).pack(side="left")
    info_row = ttk.Frame(window, padding=(8, 3, 8, 5))
    info_row.pack(fill="x")
    ttk.Label(info_row, text="本体ボタン、下のメニュー、数字キーのどれでも操作できます。").pack(
        side="left", anchor="nw")
    menu_panel = ttk.LabelFrame(window, text="操作メニュー", padding=8)
    menu_panel.pack(fill="x", padx=8, pady=(0, 8))
    text = ScrolledText(window, wrap="word", font=("Consolas", 10), state="disabled")
    inbox, keys = queue.Queue(), queue.Queue()
    transfer_updates = queue.Queue()
    stop = threading.Event()
    detach_ack = threading.Event()
    copy_cancel = threading.Event()
    worker = None
    host_state = {}
    menu_title = tk.StringVar(value="接続すると、ここに選択肢が表示されます")
    ttk.Label(menu_panel, textvariable=menu_title).pack(anchor="w")
    menu_items = ttk.Frame(menu_panel)
    menu_items.pack(fill="x", pady=(5, 0))
    parser_buffer = ""
    pending_title = ""
    pending_options = []
    pending_paged = False
    normal_baud = tk.StringVar(value="通信速度（通常）：未接続")
    dump_baud = tk.StringVar(value="通信速度（吸い出し）：未接続")
    transfer_speed = tk.StringVar(value="転送: 待機")
    storage_mode = tk.StringVar(value="保存先: PC")
    storage_current = {"mode": "PC", "pending": None}
    connection_state = tk.StringVar(value="未接続")
    led_state = tk.StringVar(value="本体LED: 状態未取得")
    connection_widgets = {"button": None}
    storage_widgets = {"PC": None, "SD": None}
    connection_colors = {
        "未接続": ("#e5e7eb", "#111827"),
        "接続中…": ("#fde68a", "#78350f"),
        "接続済み": ("#86efac", "#14532d"),
        "再接続待ち": ("#fdba74", "#7c2d12"),
        "接続エラー": ("#fca5a5", "#7f1d1d"),
    }
    def set_connection_state(value):
        connection_state.set(value)
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
    menu_navigation = {"items": [], "options": [], "selected": 0}
    sd_browser = {"window": None, "tree": None, "path": "/", "pending": [],
                  "busy": False, "progress": None, "progress_text": None,
                  "status": None, "resort": None, "action": None,
                  "scan_active": False, "scan_queue": [],
                  "scan_current": None, "scan_entries": [],
                  "cancelled": False}

    def browser_command(action, path):
        if not (worker and worker.is_alive() and input_ready.get()) or sd_browser["busy"]:
            return False
        encoded = path.encode("utf-8")
        if not encoded or len(encoded) > 250 or b"\n" in encoded:
            return False
        input_ready.set(False)
        sd_browser["busy"] = True
        sd_browser["action"] = action
        if action == "C":
            copy_cancel.clear()
        # Queue the complete command atomically.  Putting K, action and path
        # one byte at a time lets the reader poll between bytes and interpret
        # the remainder as menu input.
        keys.put(b"K" + action.encode("ascii") + encoded + b"\n")
        return True

    def browser_start_next():
        if sd_browser["busy"] or not input_ready.get():
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

    def send_key(value):
        if worker and worker.is_alive() and input_ready.get():
            input_ready.set(False)
            keys.put(ord(value))

    def send_bytes(values):
        if worker and worker.is_alive() and input_ready.get():
            input_ready.set(False)
            keys.put(bytes(values))

    def clear_operation(message="処理中..."):
        input_mode.set("busy")
        menu_title.set(message)
        menu_navigation["items"] = []
        menu_navigation["options"] = []
        for child in menu_items.winfo_children():
            child.destroy()

    def send_menu_key(value, message="処理中..."):
        if worker and worker.is_alive() and input_ready.get():
            clear_operation(message)
            send_key(value)

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
    physical_controls = (
        ("左ボタン：次へ／変更 (d)", "d"),
        ("右ボタン：決定 (Space)", " "),
        ("左ボタン2回押し：前へ／戻る (u)", "u"),
    )
    for label, value in physical_controls:
        ttk.Button(physical_panel, text=label,
                   command=lambda key=value: send_key(key)).pack(
                       side="left", expand=True, fill="x", padx=2)

    def render_menu(title, options, paged):
        input_mode.set("menu")
        menu_title.set(title or "選択してください")
        for child in menu_items.winfo_children():
            child.destroy()
        rendered = []
        def select_row(index):
            if not rendered:
                return
            menu_navigation["selected"] = index % len(rendered)
            for position, widget in enumerate(rendered):
                active = position == menu_navigation["selected"]
                widget.configure(background="#dbeafe" if active else "white",
                                 highlightbackground="#2563eb" if active else "white",
                                 highlightthickness=2 if active else 0)
        for position, (number, label) in enumerate(options):
            item = tk.Label(menu_items, text=f"{number}  {label}", anchor="w",
                            padx=10, pady=5, relief="solid", borderwidth=1,
                            background="white", cursor="hand2")
            item.pack(fill="x", pady=2)
            rendered.append(item)
            item.bind("<Enter>", lambda event, i=position: select_row(i))
            item.bind("<Button-1>", lambda event, n=number: send_menu_key(n))
        menu_navigation["items"] = rendered
        menu_navigation["options"] = list(options)
        menu_navigation["selected"] = 0
        if rendered:
            select_row(0)
            window.focus_set()
        if paged:
            nav = ttk.Frame(menu_items)
            nav.pack(fill="x", pady=(5, 0))
            ttk.Button(nav, text="◀ 前のページ (PageUp)", command=lambda: send_key("[")).pack(side="left")
            ttk.Button(nav, text="次のページ (PageDown) ▶", command=lambda: send_key("]")).pack(side="right")

    def render_press_button():
        input_mode.set("press")
        menu_title.set("Press Button...")
        for child in menu_items.winfo_children():
            child.destroy()
        item = tk.Label(menu_items, text="Press Button", anchor="center",
                        padx=10, pady=8, relief="solid", borderwidth=1,
                        background="white", cursor="hand2")
        item.pack(fill="x", pady=2)
        item.bind("<Enter>", lambda event: item.configure(background="#dbeafe", highlightbackground="#2563eb", highlightthickness=2))
        item.bind("<Leave>", lambda event: item.configure(background="white", highlightthickness=0))
        item.bind("<Button-1>", lambda event: send_menu_key(" "))

    def render_candidate_controls():
        input_mode.set("candidate")
        menu_title.set("カセット候補を選択")
        for child in menu_items.winfo_children():
            child.destroy()
        controls = (
            ("◀ 前の候補 (u)", "u"),
            ("次の候補 (d) ▶", "d"),
            ("この候補を選択 (Space)", " "),
        )
        for label, value in controls:
            ttk.Button(menu_items, text=label,
                       command=lambda key=value: (
                           send_menu_key(key) if key == " " else send_key(key))).pack(
                           side="left", expand=True, fill="x", padx=2)

    def render_physical_fallback():
        input_mode.set("physical")
        menu_title.set("本体画面の操作待ち")
        for child in menu_items.winfo_children():
            child.destroy()
        controls = (
            ("前へ／戻る", "u"),
            ("次へ／変更", "d"),
            ("決定", " "),
        )
        for label, value in controls:
            ttk.Button(menu_items, text=label,
                       command=lambda key=value: send_key(key)).pack(
                           side="left", expand=True, fill="x", padx=2)

    alphabet_state = {"selected": 0, "database": ""}

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

    def render_database_candidates(letter):
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
        controls = ttk.Frame(menu_items)
        controls.pack(fill="x", pady=(5, 0))
        ttk.Button(controls, text="文字一覧へ戻る",
                   command=lambda: render_alphabet_controls(
                       alphabet_state["selected"], alphabet_state["database"])).pack(side="left")
        ttk.Button(controls, text="選択したゲームを決定",
                   command=choose_record).pack(side="right")
        if matches:
            listing.selection_set(0)
            listing.focus_set()
        else:
            listing.insert("end", "該当するゲームがありません")

    def render_alphabet_controls(selected_index=0, database_name=""):
        input_mode.set("alphabet")
        alphabet_state["selected"] = selected_index
        alphabet_state["database"] = database_name
        menu_title.set("ゲーム名の先頭文字を選択")
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
        for column in range(7):
            grid.grid_columnconfigure(column, weight=1)

    def parse_console(chunk):
        nonlocal parser_buffer, pending_title, pending_options, pending_paged
        parser_buffer += chunk.replace("\r", "")
        while "\n" in parser_buffer:
            line, parser_buffer = parser_buffer.split("\n", 1)
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
            if line.startswith("[Connected:"):
                set_connection_state("接続済み")
                set_storage_state("PC", storage_current["pending"])
            if version_match:
                window.title(
                    f"Cart Reader {version_match.group(2)} — {version_match.group(1)} / PC・本体SD")
            if runtime_match:
                value = int(runtime_match.group(1))
                if value > 500000:
                    dump_baud.set(f"通信速度（吸い出し）：{value:,} baud")
                else:
                    normal_baud.set(f"通信速度（通常）：{value:,} baud")
            elif switched_match:
                dump_baud.set(f"通信速度（吸い出し）：速度ベンチ中 {int(switched_match.group(1)):,} baud")
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
            elif stable_match:
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
                set_storage_state(storage_match.group(1), None)
            if led_match:
                set_led_state(led_match.group(1))
            if led_activity_match:
                set_led_activity(led_activity_match.group(1) == "blinking")
            if msx_title_match:
                host_state["msx_title"] = msx_title_match.group(1).strip()
            if line.startswith("[RECONNECT]"):
                set_connection_state("接続エラー")
            elif line.startswith("[Reconnect] waiting"):
                set_connection_state("再接続待ち")
            elif line.startswith("[Disconnected"):
                set_connection_state("未接続")
            if line.startswith(("[Disconnected", "[RECONNECT]")):
                set_led_activity(False)
                set_led_state("unknown")
                window.title("Cart Reader 15.5 — 未接続")
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
                if sd_browser["tree"]:
                    sd_browser["tree"].delete(*sd_browser["tree"].get_children())
                if sd_browser["status"]:
                    sd_browser["status"].set("再接続後にSDを読み込みます")
            if line == "[Reader] input ready":
                input_ready.set(True)
                if input_mode.get() not in ("candidate", "physical", "alphabet", "database-list",
                                             "nes-mapper", "nes-options"):
                    input_mode.set("menu")
                if storage_current["pending"] and input_mode.get() == "menu":
                    requested = storage_current["pending"]
                    storage_current["pending"] = None
                    code = "J" if requested == "PC" else "I"
                    storage_mode.set(f"保存先: {storage_current['mode']}（{requested}へ切替中）")
                    window.after(20, lambda key=code: send_key(key))
                browser_start_next()
            elif line == "[Reader] press button ready":
                input_ready.set(True)
                render_press_button()
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
                    sd_browser["tree"].insert("", "end", values=(name, "フォルダ" if kind == "D" else "ファイル", "" if kind == "D" else size), tags=(kind,))
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
                sd_browser["cancelled"] = False
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
            save_profile(port_identity(port.get()), selected, benchmark["passed"])
            inbox.put(f"[Benchmark] stable baud={selected}\n")
            benchmark["index"] = None
            benchmark["waiting"] = False
            return
        if not benchmark["waiting"]:
            keys.put(ord("A") + index)
            benchmark["waiting"] = True
            inbox.put(f"[Benchmark] independent test {index + 1}/{len(benchmark_rates)}\n")

    def run(selected_port, selected_output):
        last_error = None
        waiting_announced = False
        def service_log(message):
            nonlocal last_error, waiting_announced
            if "[Connected:" in message:
                last_error = None
                waiting_announced = False
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
                    last_error = None
                    waiting_announced = False
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
                if message != last_error:
                    inbox.put(f"\n[RECONNECT] {message}\n")
                    last_error = message
            if not stop.wait(1.0):
                if not waiting_announced:
                    inbox.put(f"[Reconnect] waiting for {selected_port}...\n")
                    waiting_announced = True
    def connect():
        nonlocal worker
        if worker and worker.is_alive():
            return
        set_connection_state("接続中…")
        safe_rate, dump_rate = load_profile(port_identity(port.get()))
        normal_baud.set(f"通信速度（通常）：{safe_rate:,} baud")
        dump_baud.set(f"通信速度（吸い出し）：{dump_rate:,} baud")
        stop.clear()
        while not keys.empty():
            keys.get_nowait()
        worker = threading.Thread(target=run, args=(port.get(), output.get()), daemon=True)
        worker.start()
    def disconnect():
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
        inbox.put("[Benchmark] requested\n")
        if benchmark["index"] is not None:
            return
        reset_profile_candidates(port_identity(port.get()))
        benchmark["index"] = 0
        benchmark["waiting"] = False
        benchmark["passed"] = []
        if input_ready.get():
            queue_benchmark_rate()
    ttk.Button(row, text="速度ベンチ", command=request_benchmark).pack(side="left", padx=8)
    def open_sd_browser():
        if sd_browser["window"] and sd_browser["window"].winfo_exists():
            sd_browser["window"].lift()
            return
        dialog = tk.Toplevel(window)
        dialog.title("本体SDブラウザ — 読み取り専用")
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
        requested = "PC" if code == "J" else "SD"
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
        key = event.keysym.lower()
        keypad = {f"kp_{n}": str(n) for n in range(10)}
        keypad.update({
            "kp_insert": "0", "kp_end": "1", "kp_down": "2",
            "kp_next": "3", "kp_left": "4", "kp_begin": "5",
            "kp_right": "6", "kp_home": "7", "kp_up": "8",
            "kp_prior": "9",
        })
        fullwidth_digits = "０１２３４５６７８９"
        # On Windows/Tk the numeric keypad sometimes reports an empty char and
        # a locale-dependent keysym. Virtual-key codes 96..105 are stable.
        if os.name == "nt" and 96 <= event.keycode <= 105:
            typed_digit = str(event.keycode - 96)
        elif os.name == "nt" and 48 <= event.keycode <= 57:
            typed_digit = str(event.keycode - 48)
        elif event.char in "0123456789":
            typed_digit = event.char
        elif event.char in fullwidth_digits:
            typed_digit = str(fullwidth_digits.index(event.char))
        elif key in "0123456789":
            # Japanese IME and some focused Tk widgets report an empty char
            # while keeping the top-row digit in keysym.
            typed_digit = key
        else:
            typed_digit = keypad.get(key, "")
        if input_mode.get() == "nes-mapper":
            # The mapper combobox receives digits, Backspace and Enter itself.
            return None
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
        if input_mode.get() == "press" and key in ("return", "space", "kp_enter"):
            send_menu_key(" ")
            return "break"
        if input_mode.get() in ("candidate", "physical"):
            if key in ("return", "space", "kp_enter"):
                send_key(" ")
                return "break"
            if key in ("u", "d", "l"):
                send_key(key)
                return "break"
        if input_mode.get() == "menu" and menu_navigation["items"]:
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
                for position, item in enumerate(menu_navigation["items"]):
                    active = position == selected
                    item.configure(background="#dbeafe" if active else "white",
                                   highlightbackground="#2563eb" if active else "white",
                                   highlightthickness=2 if active else 0)
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
        value = typed_digit or (key if key in "ud" else event.char.lower())
        if input_mode.get() == "menu" and value in "0123456789ud":
            send_menu_key(value)
            return "break"
    # Bind the disabled console directly as well: Tk's Text class can consume
    # key events before the application-wide binding gets them.
    text.bind("<KeyPress>", global_key, add="+")
    window.bind_all("<KeyPress>", global_key, add="+")
    def pump():
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
                if isinstance(item, tuple) and item[0] == "status":
                    parse_console(item[1])
                    continue
                chunk = item
                text.insert("end", chunk)
                parse_console(chunk)
                text.see("end")
            except queue.Empty:
                break
        text.configure(state="disabled")
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
    refresh()
    pump()
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="COM3, /dev/ttyACM0, etc.")
    parser.add_argument("--output", default=str(BASE))
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
                assert (len(hello) == 12 and hello[0] == 0 and hello[9] == 32
                        and int.from_bytes(hello[10:12], "little") == 512)
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
