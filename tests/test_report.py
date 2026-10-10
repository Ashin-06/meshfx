from meshfx import report


def test_attribution_levels():
    assert report.attribution({"kind": "message", "xeddsa_signed": True}).startswith("A")
    assert report.attribution({"kind": "message", "pki_encrypted": True}).startswith("B")
    assert report.attribution({"kind": "message"}).startswith("C")
    assert report.attribution({"kind": "node"}) == ""


def test_timeline_sort_and_attribution():
    radio = [{"kind": "message", "timestamp": 200, "from": "!aa", "text": "second", "xeddsa_signed": False}]
    app = [{"kind": "message", "time": 100, "from": "!bb", "text": "first", "xeddsa_signed": True},
           {"kind": "node", "num": "!cc", "last_heard": 150}]
    tl = report.build_timeline(radio, app)
    assert [e["text"] for e in tl if e["kind"] == "message"] == ["first", "second"]
    assert tl[0]["attribution"].startswith("A")
    # no-timestamp events sort last
    tl2 = report.build_timeline([{"kind": "channel", "name": "x"}], app)
    assert tl2[-1]["kind"] == "channel"


def test_android_ms_vs_radio_seconds_ordering():
    # Android received_time is epoch MILLISECONDS; radio timestamps are SECONDS.
    # The radio message (10:00:10) must sort after the app message (10:00:00), not before.
    app = [{"kind": "message", "source": "android-app", "time": 1760000000_000, "text": "app 10:00:00"}]
    radio = [{"kind": "message", "source": "radio-flash", "timestamp": 1760000010, "text": "radio 10:00:10"}]
    tl = report.build_timeline(app, radio)
    assert [e["text"] for e in tl] == ["app 10:00:00", "radio 10:00:10"]
    assert tl[0]["ts"] == 1760000000 and tl[1]["ts"] == 1760000010  # both in seconds


def test_renderers():
    tl = report.build_timeline([{"kind": "message", "time": 100, "from": "!bb", "to": "^all",
                                 "text": "hi <b>", "channel": 0}])
    assert '"attribution"' in report.to_json(tl)
    csv_out = report.to_csv(tl)
    assert "ts,source,kind" in csv_out.splitlines()[0] and "hi <b>" in csv_out
    htm = report.to_html(tl)
    assert "hi &lt;b&gt;" in htm  # text is HTML-escaped
    assert "<table>" in htm


def test_from_flash_integration(tmp_path):
    # reuse the ESP32 image builder, but put real content in the files
    import sys
    sys.path.insert(0, "tests")
    from littlefs import LittleFS
    from test_flash import FLASH_SIZE, SPIFFS_OFF, SPIFFS_SIZE, _entry

    from meshfx import flash as flashmod
    from meshfx.msgstore import BROADCAST, MSG_REC
    from meshfx.proto.meshtastic import deviceonly_pb2

    fs = LittleFS(block_size=4096, block_count=SPIFFS_SIZE // 4096)
    fs.mkdir("/prefs")
    db = deviceonly_pb2.NodeDatabase()
    n = db.nodes.add(); n.num = 0xA1B2C3D4; n.long_name = "Alice"; n.last_heard = 1760000000
    with fs.open("/prefs/nodes.proto", "wb") as f:
        f.write(db.SerializeToString())
    t = b"hello from radio"
    rec = MSG_REC.pack(1760000500, 0xA1B2C3D4, 0, BROADCAST, 0, 1, 0, 1, len(t), t)
    with fs.open("/Messages_default.msgs", "wb") as f:
        f.write(bytes([1]) + rec)
    spiffs = bytes(fs.context.buffer)

    img = bytearray(b"\xff" * FLASH_SIZE)
    table = _entry(0x01, 0x82, SPIFFS_OFF, SPIFFS_SIZE, "spiffs")
    img[flashmod.PART_TABLE_OFFSET:flashmod.PART_TABLE_OFFSET + len(table)] = table
    img[SPIFFS_OFF:SPIFFS_OFF + len(spiffs)] = spiffs

    tl = report.build_timeline(report.from_flash(bytes(img)))
    kinds = {e["kind"] for e in tl}
    assert "node" in kinds and "message" in kinds
    msg = next(e for e in tl if e["kind"] == "message")
    assert msg["text"] == "hello from radio" and msg["xeddsa_signed"]
