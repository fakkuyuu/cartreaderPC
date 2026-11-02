"""PC87 sampled SRAM telemetry. GPL-3.0-or-later.

Gap means SP minus the heap break, including neither free heap holes nor a
promise about unsampled call/interrupt peaks. Negative readings are retained.
"""
import re
import struct

STAGES = ("メニュー", "通信処理", "SD一覧を開く", "SD一覧取得",
          "SDコピーを開く", "SD読込後", "PC書込後", "転送",
          "キャッシュ確保", "指令受信後", "ボタン待ち", "入力待ち")


def decode_ram(payload):
    if len(payload) != 10:
        raise ValueError("invalid RAM telemetry length")
    gap, minimum, fixed, total, stage, minimum_stage = struct.unpack("<hhHHBB", payload)
    if (total != 8192 or fixed > total or minimum > gap or
            not -total <= minimum <= gap <= total or
            stage >= len(STAGES) or minimum_stage >= len(STAGES)):
        raise ValueError("invalid RAM telemetry values")
    return gap, minimum, fixed, total, stage, minimum_stage


def ram_labels(line):
    match = re.fullmatch(r"\[RAM\]\t(-?\d+)\t(-?\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\s*", line)
    if not match:
        return None
    try:
        values = tuple(map(int, match.groups()))
        gap, minimum, fixed, total, stage, minimum_stage = decode_ram(struct.pack("<hhHHBB", *values))
    except (ValueError, struct.error):
        return None
    return (f"RAM空き：{gap:,} B　観測最小：{minimum:,} B",
            f"常駐RAM：{fixed:,} / {total:,} B　最小記録：{STAGES[minimum_stage]}")
