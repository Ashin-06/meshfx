"""Read an ESP32 flash dump: parse the partition table, pull files out of the LittleFS data partition.

Non-destructive: operates on a bytes image, never writes to it. nRF52 radios use LittleFS v1
(128-byte blocks) which the bundled littlefs-python (v2) cannot mount - see README known gaps.
"""
import struct

from littlefs import LittleFS

PART_TABLE_OFFSET = 0x8000  # fixed on ESP32
PART_MAGIC = 0x50AA
PART_MD5_MAGIC = 0xEBEB
_ENTRY = struct.Struct("<HBBII16sI")  # magic, type, subtype, offset, size, label, flags
TYPE_DATA = 0x01
SUBTYPE_SPIFFS = 0x82  # Meshtastic labels the LittleFS data partition "spiffs"


def parse_partition_table(img: bytes, offset: int = PART_TABLE_OFFSET) -> list[dict]:
    """Return partition entries from the table at `offset` (ESP32 layout)."""
    parts = []
    for i in range(0, 0xC00, _ENTRY.size):
        chunk = img[offset + i:offset + i + _ENTRY.size]
        if len(chunk) < _ENTRY.size:
            break
        magic, ptype, subtype, poff, size, label, flags = _ENTRY.unpack(chunk)
        if magic == PART_MD5_MAGIC:
            continue
        if magic != PART_MAGIC:
            break  # table ends at first non-entry
        parts.append({
            "label": label.split(b"\0", 1)[0].decode("ascii", "replace"),
            "type": ptype, "subtype": subtype, "offset": poff, "size": size, "flags": flags,
        })
    return parts


def _data_partition(img: bytes) -> dict | None:
    for p in parse_partition_table(img):
        if p["type"] == TYPE_DATA and p["subtype"] == SUBTYPE_SPIFFS:
            return p
    return None


def mount_fs(partition: bytes, block_size: int = 4096):
    """Mount a LittleFS v2 image read-only. Raises if it is not a valid v2 filesystem."""
    if len(partition) % block_size:
        partition = partition + b"\xff" * (block_size - len(partition) % block_size)
    fs = LittleFS(block_size=block_size, block_count=len(partition) // block_size, mount=False)
    fs.context.buffer = bytearray(partition)
    fs.mount()  # raises on bad magic / corruption
    return fs


def list_files(fs) -> list[str]:
    out = []
    for root, _dirs, files in fs.walk("/"):
        for f in files:
            out.append((root.rstrip("/") + "/" + f).replace("//", "/"))
    return out


def read_file(fs, path: str) -> bytes:
    with fs.open(path, "rb") as f:
        return f.read()


def extract_files(img: bytes) -> dict[str, bytes]:
    """From a whole ESP32 flash dump, return {path: contents} for every file in the data partition."""
    part = _data_partition(img)
    if part is None:
        raise ValueError("no LittleFS data partition (type=data subtype=spiffs) in table")
    end = part["offset"] + part["size"]
    fs = mount_fs(img[part["offset"]:end])
    return {p: read_file(fs, p) for p in list_files(fs)}
