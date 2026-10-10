from meshfx.msgstore import BROADCAST, MSG_REC, carve_msgs, read_msgs


def rec(text, dest=BROADCAST, typ=0, boot_rel=0):
    t = text.encode()
    return MSG_REC.pack(1760000000, 0xA1B2C3D4, 0, dest, boot_rel, 1, typ, 1, len(t), t)


def test_record_size_matches_firmware_struct():
    assert MSG_REC.size == 239


def test_read_msgs_file():
    out = read_msgs(bytes([2]) + rec("meet at the bridge") + rec("ok", dest=0x11223344, typ=1, boot_rel=1))
    assert [r["text"] for r in out] == ["meet at the bridge", "ok"]
    assert out[0]["to"] == "^all" and out[0]["xeddsa_signed"]
    assert out[1]["type"] == "DM" and out[1]["to"] == "!11223344" and out[1]["timestamp_is_uptime"]


def test_cleared_file_and_truncated_file():
    assert read_msgs(b"\x00") == []
    assert read_msgs(b"") == []
    assert read_msgs(bytes([3]) + rec("only one")) == [read_msgs(bytes([1]) + rec("only one"))[0]]


def test_carve_finds_record_in_free_space():
    img = b"\xff" * 1000 + rec("deleted msg") + b"\x00" * 500
    assert [(h["offset"], h["text"]) for h in carve_msgs(img)] == [(1000, "deleted msg")]
    assert carve_msgs(b"\xff" * 4096) == []
