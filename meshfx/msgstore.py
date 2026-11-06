"""On-device message history: /Messages_<label>.msgs (firmware src/MessageStore.cpp).

File = 1-byte count, then `count` packed little-endian StoredMessageRecord structs (239 bytes).
"""
import struct
import sys

BROADCAST = 0xFFFFFFFF
# timestamp, sender, channelIndex, dest, isBootRelative, ackStatus, type, xeddsaSigned, textLength, text
MSG_REC = struct.Struct("<IIBIBBBBH220s")
ACK = ["NONE", "ACKED", "NACKED", "TIMEOUT", "RELAYED"]


def _record(raw: bytes, offset=None) -> dict:
    ts, sender, ch, dest, boot_rel, ack, typ, signed, _tlen, text = MSG_REC.unpack(raw)
    r = {
        "timestamp": ts,
        "timestamp_is_uptime": bool(boot_rel),
        "from": f"!{sender:08x}",
        "to": "^all" if dest == BROADCAST else f"!{dest:08x}",
        "channel_index": ch,
        "type": "DM" if typ == 1 else "BROADCAST",
        "ack": ACK[ack] if ack < len(ACK) else ack,
        "xeddsa_signed": bool(signed),
        "text": text.split(b"\0", 1)[0].decode("utf-8", "replace"),
    }
    if offset is not None:
        r["offset"] = offset
    return r


def read_msgs(data: bytes) -> list[dict]:
    """Parse a .msgs file. Trailing bytes or a short file are reported, never fatal."""
    if not data:
        return []
    count = data[0]
    if len(data) != 1 + count * MSG_REC.size:
        print(f"warning: {len(data)} bytes does not match {count} x {MSG_REC.size}-byte records; "
              "older firmware layout?", file=sys.stderr)
    out = []
    for k in range(count):
        start = 1 + k * MSG_REC.size
        if start + MSG_REC.size > len(data):
            break
        out.append(_record(data[start:start + MSG_REC.size]))
    return out


def carve_msgs(img: bytes) -> list[dict]:
    """Find StoredMessageRecords anywhere in a raw image, including freed filesystem blocks.

    Byte-by-byte scan with cheap early exits; fine for 8-16 MB dumps. Records split
    across filesystem blocks are missed - needs a filesystem-aware pass.
    """
    hits, size = [], MSG_REC.size
    for o in range(len(img) - size + 1):
        if img[o + 13] > 1 or img[o + 14] > 4 or img[o + 15] > 1 or img[o + 16] > 1:
            continue
        tlen = img[o + 17] | img[o + 18] << 8
        if not 0 < tlen < 220:
            continue
        text = img[o + 19:o + 19 + tlen]
        if 0 in text or any(img[o + 19 + tlen:o + size]):
            continue
        try:
            text.decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits.append(_record(img[o:o + size], offset=o))
    return hits
