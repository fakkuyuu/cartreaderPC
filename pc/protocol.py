"""CRPC v1: bounded frames, CRC16-CCITT-FALSE, no mutation retries."""
import binascii
import struct
import time

MAGIC = b"CRPC"
MAX_PAYLOAD = 1029
HEADER = struct.Struct("<BBHH")


class ProtocolError(Exception):
    pass


def encode(op, seq, payload=b""):
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("oversized frame")
    body = HEADER.pack(1, op, seq, len(payload)) + payload
    return MAGIC + body + struct.pack("<H", binascii.crc_hqx(body, 0xffff))


def exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        if not chunk:
            raise TimeoutError("USB timeout/disconnect; reset reader to start a new session")
        result.extend(chunk)
    return bytes(result)


def receive(stream, synchronize=False, sync_timeout=20):
    if synchronize:
        deadline = time.monotonic() + sync_timeout
        window = bytearray()
        discarded = 0
        while bytes(window) != MAGIC:
            chunk = stream.read(1)
            if not chunk:
                if time.monotonic() >= deadline:
                    raise TimeoutError("No CRPC frame. Press RESET on the reader and reconnect.")
                continue
            window.extend(chunk)
            if len(window) > len(MAGIC):
                del window[0]
                discarded += 1
            if discarded > 1024:
                raise ProtocolError("too much non-CRPC serial data; wrong firmware or baud rate")
    elif exact(stream, 4) != MAGIC:
        raise ProtocolError("frame magic mismatch")
    header = exact(stream, HEADER.size)
    version, op, seq, size = HEADER.unpack(header)
    if version != 1 or size > MAX_PAYLOAD:
        raise ProtocolError("unsupported version or oversized frame")
    payload = exact(stream, size)
    checksum, = struct.unpack("<H", exact(stream, 2))
    if binascii.crc_hqx(header + payload, 0xffff) != checksum:
        raise ProtocolError("CRC mismatch; transfer stopped")
    return op, seq, payload
