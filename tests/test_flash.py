import struct

from littlefs import LittleFS

from meshfx import flash

FLASH_SIZE = 0x400000  # 4 MB
SPIFFS_OFF, SPIFFS_SIZE = 0x300000, 0x100000


def _entry(ptype, subtype, off, size, label):
    return struct.pack("<HBBII16sI", flash.PART_MAGIC, ptype, subtype, off, size,
                       label.encode().ljust(16, b"\0"), 0)


def build_esp32_image():
    """A minimal but real 4 MB ESP32 image: partition table + a populated LittleFS v2 'spiffs'."""
    fs = LittleFS(block_size=4096, block_count=SPIFFS_SIZE // 4096)
    fs.mkdir("/prefs")
    with fs.open("/prefs/config.proto", "wb") as f:
        f.write(b"\x08\x01config-bytes")
    with fs.open("/Messages_default.msgs", "wb") as f:
        f.write(b"\x00")  # a cleared message file
    spiffs = bytes(fs.context.buffer)

    img = bytearray(b"\xff" * FLASH_SIZE)
    table = (_entry(0x01, 0x02, 0x9000, 0x5000, "nvs")
             + _entry(0x00, 0x10, 0x10000, 0x250000, "app0")
             + _entry(0x01, 0x82, SPIFFS_OFF, SPIFFS_SIZE, "spiffs"))
    img[flash.PART_TABLE_OFFSET:flash.PART_TABLE_OFFSET + len(table)] = table
    img[SPIFFS_OFF:SPIFFS_OFF + len(spiffs)] = spiffs
    return bytes(img)


def test_partition_table():
    parts = flash.parse_partition_table(build_esp32_image())
    labels = {p["label"]: p for p in parts}
    assert set(labels) == {"nvs", "app0", "spiffs"}
    assert labels["spiffs"]["offset"] == SPIFFS_OFF and labels["spiffs"]["size"] == SPIFFS_SIZE


def test_extract_files():
    files = flash.extract_files(build_esp32_image())
    assert files["/prefs/config.proto"] == b"\x08\x01config-bytes"
    assert files["/Messages_default.msgs"] == b"\x00"


def test_no_data_partition_raises():
    img = bytearray(b"\xff" * FLASH_SIZE)
    img[flash.PART_TABLE_OFFSET:flash.PART_TABLE_OFFSET + 32] = _entry(0x00, 0x10, 0x10000, 0x250000, "app0")
    try:
        flash.extract_files(bytes(img))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
