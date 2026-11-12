"""Experimental GBA stream with CRC16 and selective retransmission."""
import binascii
import struct
import time

from protocol import ProtocolError

MAGIC = b"GB2M"
HEADER = struct.Struct("<IBB")
MAX_ROUNDS = 10
N64_HANDOFF_MAGIC = b"N64D"
N64_HANDOFF_ACK = b"N64A"


def complete_n64_handoff(wire, stop, cancel):
    """Confirm the reader consumed the final zero-mask before leaving 2 Mbps."""
    deadline = time.monotonic() + 2.5
    marker = bytearray()
    while len(marker) < 6 and time.monotonic() < deadline:
        if stop.is_set() or (cancel is not None and cancel.is_set()):
            raise ProtocolError("N64 2M handoff cancelled")
        chunk = wire.read(6 - len(marker))
        if chunk:
            marker.extend(chunk)
    if len(marker) != 6:
        raise ProtocolError("reader did not send the final N64 2M handoff marker")
    observed = marker.hex(" ")
    if marker[:4] != N64_HANDOFF_MAGIC:
        raise ProtocolError(f"invalid final N64 2M handoff marker: bytes={observed}")
    expected = binascii.crc_hqx(marker[:4], 0xffff)
    if int.from_bytes(marker[4:], "little") != expected:
        raise ProtocolError(f"final N64 2M handoff marker CRC mismatch: bytes={observed}")
    acknowledgement = N64_HANDOFF_ACK + struct.pack(
        "<H", binascii.crc_hqx(N64_HANDOFF_ACK, 0xffff))
    if wire.write(acknowledgement) != len(acknowledgement):
        raise ProtocolError("final N64 2M handoff acknowledgement was not sent")
    wire.flush()


def receive_window(wire, first, count, round_number, blocks, stop, cancel, block_size, label="GBA"):
    buffer = bytearray()
    received = 0
    deadline = time.monotonic() + 0.45
    while time.monotonic() < deadline:
        if stop.is_set() or (cancel is not None and cancel.is_set()):
            raise ProtocolError(f"{label} 2M transfer cancelled")
        chunk = wire.read(wire.in_waiting or 1)
        if not chunk:
            continue
        received += len(chunk)
        buffer.extend(chunk)
        deadline = time.monotonic() + 0.45
        while True:
            start = buffer.find(MAGIC)
            if start < 0:
                del buffer[:-3]
                break
            if start:
                del buffer[:start]
            if len(buffer) < 12:
                break
            index, frame_round, end = HEADER.unpack_from(buffer, 4)
            if (frame_round != round_number or end not in (0, 1)
                    or not first <= index < first + count or (end and index != first)):
                del buffer[0]
                continue
            length = 12 if end else 12 + block_size
            if len(buffer) < length:
                break
            body = buffer[4:length - 2]
            checksum = int.from_bytes(buffer[length - 2:length], "little")
            if binascii.crc_hqx(body, 0xffff) != checksum:
                del buffer[0]
                continue
            if end:
                return received, True
            # CRC16 alone cannot authenticate the framing: if one payload
            # byte vanishes, the low CRC byte may move into the payload and
            # the high CRC byte plus the next frame's 'G' can accidentally
            # pass CRC16 (observed on a real 32 MiB GBA dump). Do not commit
            # a block until the *whole* next frame marker and its header are
            # present at the exact byte boundary.
            next_at = length
            if len(buffer) < next_at + len(MAGIC):
                break
            if buffer[next_at:next_at + len(MAGIC)] != MAGIC:
                # The candidate frame swallowed or skipped a byte. Discard
                # the candidate and resynchronize, then request retransmit.
                del buffer[0]
                continue
            if len(buffer) < next_at + 12:
                break
            next_index, next_round, next_end = HEADER.unpack_from(buffer, next_at + 4)
            if (next_round != round_number or next_end not in (0, 1)
                    or not first <= next_index < first + count
                    or (next_end and next_index != first)):
                del buffer[0]
                continue
            if next_end:
                # The last data frame must lead into a *valid* end marker.
                # A bad or absent end marker cannot certify its boundary.
                next_body = buffer[next_at + 4:next_at + 10]
                next_crc = int.from_bytes(buffer[next_at + 10:next_at + 12], "little")
                if binascii.crc_hqx(next_body, 0xffff) != next_crc:
                    del buffer[0]
                    continue
            blocks[index] = bytes(body[HEADER.size:])
            del buffer[:length]
    return received, False


def receive_dump(wire, store, handle, length, log, stop, cancel, block_size=512, window=16, label="GBA", *, expected_block=None, fallback_before_payload=False, completion_handshake=False):
    if expected_block is not None and len(expected_block) != block_size:
        raise ValueError("benchmark pattern must match the frame size")
    previous_baud, previous_timeout = wire.baudrate, wire.timeout
    started = time.perf_counter()
    resends = 0
    first = round_number = received = committed = 0
    ended = False
    stars = -1
    mask_format = "<BBI" if window > 16 else "<BBH"
    phase = "setting 2000000 baud"
    try:
        wire.baudrate = 2_000_000
        wire.timeout = 0.02
        log(f"[{label} 2M] COM port set to 2000000 baud\n")
        phase = "waiting for the reader's 2M ready marker"
        deadline = time.monotonic() + 2.5
        while not ended and time.monotonic() < deadline:
            count, ended = receive_window(wire, 0xffffffff, 1, 0xff, {}, stop, cancel, block_size, label)
            received += count
        if not ended:
            if fallback_before_payload:
                log(f"[{label} 2M] no ready marker; no ROM payload sent, returning to normal transfer\n")
                return None
            raise ProtocolError("reader did not confirm the switch to 2M")
        phase = "sending the 2M ready acknowledgement"
        ready = struct.pack(mask_format, 0xA7, 0xff, 0)
        ready += struct.pack("<H", binascii.crc_hqx(ready, 0xffff))
        if wire.write(ready) != len(ready):
            raise ProtocolError(f"{label} 2M ready acknowledgement was not sent")
        log(f"[{label} 2M] Reader confirmed at 2000000 baud\n")
        if expected_block is None:
            log("[")
            stars = 0
        total = length // block_size
        for first in range(0, total, window):
            count = min(window, total - first)
            blocks = {}
            for round_number in range(MAX_ROUNDS):
                phase = "receiving frames"
                received = 0
                ended = False
                received, ended = receive_window(wire, first, count, round_number, blocks, stop, cancel, block_size, label)
                mask = sum(1 << i for i in range(count) if first + i not in blocks)
                if mask and round_number == MAX_ROUNDS - 1:
                    raise ProtocolError(f"{label} 2M retry limit at block {first}")
                if not mask:
                    phase = "writing validated blocks"
                    for index in range(first, first + count):
                        block = blocks[index]
                        if expected_block is not None and block != expected_block:
                            raise ProtocolError(f"2M benchmark data mismatch at block {index}")
                        payload = struct.pack("<BI", handle, index * block_size) + block
                        if store.dispatch(22, payload) != struct.pack("<BH", 0, block_size):
                            raise ProtocolError(f"{label} 2M file write failed at block {index}")
                        committed += block_size
                request = struct.pack(mask_format, 0xA7, round_number, mask)
                request += struct.pack("<H", binascii.crc_hqx(request, 0xffff))
                phase = f"sending reply (mask=0x{mask:04X})"
                if wire.write(request) != len(request):
                    raise ProtocolError(f"{label} 2M retry request was not sent")
                if not mask:
                    if expected_block is None:
                        completed_stars = committed * 19 // length
                        if completed_stars > stars:
                            log("*" * (completed_stars - stars))
                            stars = completed_stars
                    break
                resends += mask.bit_count()
        if completion_handshake:
            phase = "waiting for final N64 2M handoff marker"
            complete_n64_handoff(wire, stop, cancel)
            log("[N64 2M] Reader handoff marker received; acknowledgement sent\n")
        phase = "flushing the last reply"
        wire.flush()
        time.sleep(0.04)
    except Exception as exc:
        if stars >= 0:
            log("\n")
        log(f"[{label} 2M] Failed while {phase}: {type(exc).__name__}: {exc}; "
            f"window_start={first}, round={round_number}, received={received}, "
            f"end_marker={ended}, saved={committed}\n")
        raise
    finally:
        wire.baudrate = previous_baud
        wire.timeout = previous_timeout
    elapsed = time.perf_counter() - started
    if expected_block is None:
        log("]\n")
    log(f"[{label} 2M] Validated {length} bytes, retransmitted {resends} blocks, "
        f"{elapsed:.3f} s\n")
    return elapsed, resends
