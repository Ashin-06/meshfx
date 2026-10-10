import json
import sqlite3

from meshfx import apps


def _android_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE packet (uuid TEXT, port_num INT, contact_key TEXT, received_time INT, "
              "read INT, data TEXT, message_text TEXT, snr REAL, rssi INT)")
    c.execute("CREATE TABLE nodes (num INT, long_name TEXT, short_name TEXT, last_heard INT, "
              "latitude REAL, longitude REAL, public_key BLOB, via_mqtt INT, hops_away INT)")
    c.execute("INSERT INTO packet VALUES (?,?,?,?,?,?,?,?,?)",
              ("u1", 1, "0^all", 1760000000, 1,
               json.dumps({"from": 0xA1B2C3D4, "to": 0xFFFFFFFF, "channel": 0}),
               "meet at the bridge", 5.5, -90))
    c.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?)",
              (0xA1B2C3D4, "Alice", "AL", 1760000000, 37.1, -122.2, b"\xaa" * 32, 0, 0))
    c.commit()
    c.close()


def _ios_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE ZNODEINFOENTITY (Z_PK INTEGER PRIMARY KEY, ZNUM INT, ZLASTHEARD INT)")
    c.execute("CREATE TABLE ZMESSAGEENTITY (Z_PK INTEGER PRIMARY KEY, ZMESSAGETIMESTAMP INT, "
              "ZMESSAGEPAYLOAD TEXT, ZCHANNEL INT, ZPORTNUM INT, ZFROMUSER INT, ZTOUSER INT)")
    c.execute("INSERT INTO ZNODEINFOENTITY VALUES (1, ?, 1760000000)", (0xA1B2C3D4,))
    c.execute("INSERT INTO ZNODEINFOENTITY VALUES (2, ?, 1760000050)", (0x11223344,))
    c.execute("INSERT INTO ZMESSAGEENTITY VALUES (1, 1760000000, 'hi there', 0, 1, 1, 2)")
    c.commit()
    c.close()


def test_android(tmp_path):
    db = tmp_path / "meshtastic_database_abc"
    _android_db(str(db))
    rows = apps.read(str(db))
    msg = next(r for r in rows if r["kind"] == "message")
    node = next(r for r in rows if r["kind"] == "node")
    assert msg["text"] == "meet at the bridge"
    assert msg["from"] == "!a1b2c3d4" and msg["to"] == "!ffffffff"
    assert node["long_name"] == "Alice" and node["public_key"] == "aa" * 32


def test_ios(tmp_path):
    db = tmp_path / "default.store"
    _ios_db(str(db))
    rows = apps.read(str(db))
    msg = next(r for r in rows if r["kind"] == "message")
    assert msg["text"] == "hi there"
    assert msg["from"] == "!a1b2c3d4" and msg["to"] == "!11223344"
    assert any(r["kind"] == "node" and r["num"] == "!a1b2c3d4" for r in rows)


def test_read_only_cannot_write(tmp_path):
    db = tmp_path / "meshtastic_database_abc"
    _android_db(str(db))
    conn = apps.open_ro(str(db))
    try:
        conn.execute("DELETE FROM packet")
        assert False, "read-only connection must reject writes"
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
