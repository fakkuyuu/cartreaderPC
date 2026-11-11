"""Experimental GBA stream with CRC16 and selective retransmission."""
import binascii
import struct
import time

from protocol import ProtocolError

MAGIC = b"GB2M"
HEADER = struct.Struct("<IBB")
MAX_ROUNDS = 10


def receive_window(wire, first, count, round_number, blocks, stop, cancel, block_size):
    buffer = bytearray()
    received = 0
    deadline = time.monotonic() + 0.45
    while time.monotonic() < deadline:
        if stop.is_set() or (cancel is not None and cancel.is_set()):
            raise ProtocolError("GBA 2M transfer cancelled")
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
            blocks[index] = bytes(body[HEADER.size:])
            del buffer[:length]
    return received, False


def receive_dump(wire, store, handle, length, log, stop, cancel, block_size=512, window=16, label="GBA"):
    previous_baud, previous_timeout = wire.baudrate, wire.timeout
    started = time.perf_counter()
    resends = 0
    first = round_number = received = committed = 0
    ended = False
    mask_format = "<BBI" if window > 16 else "<BBH"
    phase = "setting 2000000 baud"
    try:
        wire.baudrate = 2_000_000
        wire.timeout = 0.02
        log(f"[{label} 2M] COM port set to 2000000 baud\n")
        phase = "waiting for the reader's 2M ready marker"
        deadline = time.monotonic() + 2.5
        while not ended and time.monotonic() < deadline:
            count, ended = receive_window(wire, 0xffffffff, 1, 0xff, {}, stop, cancel, block_size)
            received += count
        if not ended:
            raise ProtocolError("reader did not confirm the switch to 2M")
        phase = "sending the 2M ready acknowledgement"
        ready = struct.pack(mask_format, 0xA7, 0xff, 0)
        ready += struct.pack("<H", binascii.crc_hqx(ready, 0xffff))
        if wire.write(ready) != len(ready):
            raise ProtocolError("GBA 2M ready acknowledgement was not sent")
        log(f"[{label} 2M] Reader confirmed at 2000000 baud\n")
        total = length // block_size
        for first in range(0, total, window):
            count = min(window, total - first)
            blocks = {}
            for round_number in range(MAX_ROUNDS):
                phase = "receiving frames"
                received = 0
                ended = False
                received, ended = receive_window(wire, first, count, round_number, blocks, stop, cancel, block_size)
                mask = sum(1 << i for i in range(count) if first + i not in blocks)
                if mask and round_number == MAX_ROUNDS - 1:
                    raise ProtocolError(f"GBA 2M retry limit at block {first}")
                if not mask:
                    phase = "writing validated blocks"
                    for index in range(first, first + count):
                        payload = struct.pack("<BI", handle, index * block_size) + blocks[index]
                        if store.dispatch(22, payload) != struct.pack("<BH", 0, block_size):
                            raise ProtocolError(f"GBA 2M file write failed at block {index}")
                        committed += block_size
                request = struct.pack(mask_format, 0xA7, round_number, mask)
                request += struct.pack("<H", binascii.crc_hqx(request, 0xffff))
                phase = f"sending reply (mask=0x{mask:04X})"
                if wire.write(request) != len(request):
                    raise ProtocolError("GBA 2M retry request was not sent")
                if not mask:
                    break
                resends += mask.bit_count()
        phase = "flushing the last reply"
        wire.flush()
        time.sleep(0.04)
    except Exception as exc:
        log(f"[{label} 2M] Failed while {phase}: {type(exc).__name__}: {exc}; "
            f"window_start={first}, round={round_number}, received={received}, "
            f"end_marker={ended}, saved={committed}\n")
        raise
    finally:
        wire.baudrate = previous_baud
        wire.timeout = previous_timeout
    log(f"[{label} 2M] Validated {length} bytes, retransmitted {resends} blocks, "
        f"{time.perf_counter() - started:.3f} s\n")
