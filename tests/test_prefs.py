import struct

from meshfx import prefs
from meshfx.proto.meshtastic import deviceonly_pb2, localonly_pb2


def test_decode_config_roundtrip():
    cfg = localonly_pb2.LocalConfig()
    cfg.lora.region = 1  # US
    cfg.security.private_key = b"\x11" * 32
    cfg.network.wifi_ssid = "mesh-lab"
    cfg.network.wifi_psk = "secret-pw"
    out = prefs.decode_proto("config.proto", cfg.SerializeToString())
    assert out["network"]["wifi_ssid"] == "mesh-lab"
    assert out["network"]["wifi_psk"] == "secret-pw"
    assert out["lora"]["region"] in ("US", 1)


def test_decode_nodes_and_channels():
    db = deviceonly_pb2.NodeDatabase()
    n = db.nodes.add()
    n.num = 0xA1B2C3D4
    n.long_name = "Alice"
    n.last_heard = 1760000000
    out = prefs.decode_proto("nodes.proto", db.SerializeToString())
    assert out["nodes"][0]["long_name"] == "Alice"

    cf = deviceonly_pb2.ChannelFile()
    c = cf.channels.add()
    c.settings.name = "LabNet"
    c.settings.psk = bytes(range(32))
    out = prefs.decode_proto("channels.proto", cf.SerializeToString())
    assert out["channels"][0]["settings"]["name"] == "LabNet"


def test_detect_encrypted_file():
    menc = struct.pack("<I", prefs.MENC_MAGIC) + b"\x00" * 20
    assert prefs.is_encrypted(menc)
    assert prefs.decode_proto("config.proto", menc)["_encrypted"] is True
    assert not prefs.is_encrypted(b"\x08\x01plain")


def test_transmit_history():
    # v2: magic THST, version 2, 2 entries {key u16, epoch u32, flags u8}
    body = struct.pack("<IBB", 0x54485354, 2, 2)
    body += struct.pack("<HIB", 3, 1760000000, 0)   # POSITION_APP
    body += struct.pack("<HIB", 4, 1760000100, 1)   # NODEINFO_APP, boot-relative
    out = prefs.decode_transmit_history(body)
    assert out["version"] == 2
    assert out["entries"][0]["portnum"] == "POSITION_APP"
    assert out["entries"][1]["portnum"] == "NODEINFO_APP" and out["entries"][1]["boot_relative"]
