"""Known-answer checks for meshfx. Run: python test_meshfx.py"""
import struct

import meshfx as m


def test_aes_ctr_rfc3686():
    # Same RFC 3686 vector the firmware uses in test/test_crypto/test_main.cpp::test_AES_CTR
    key = bytes.fromhex("AE6852F8121067CC4BF7A5765577F39E")
    ctr = bytes.fromhex("00000030000000000000000000000001")
    assert m.aes_ctr(key, ctr, b"Single block msg").hex().upper() == "E4095D4FB7A7B3792D6175A3261311B8"


def test_pki_firmware_vector():
    # test/test_crypto/test_main.cpp::test_PKC - a real radio packet including its 16-byte header
    pkt = bytes.fromhex("8c646d7a2909000062d6b2136b00000040df24abfcc30a17a3d9046726099e796a1c036a792b")
    priv = bytes.fromhex("a00330633e63522f8a4d81ec6d9d1e6617f6c8ffd3a4c698229537d44e522277")
    pub = bytes.fromhex("db18fc50eea47f00251cb784819a3cf5fc361882597f589f0d7ff820e8064457")
    plain = m.decrypt_pki(pkt, priv, pub)
    assert plain.hex() == "08011204746573744800"
    assert m.decode_data(plain)["text"] == "test"
    assert m.parse_header(pkt)["from"] == 0x0929


def test_default_key_and_hash():
    assert m.expand_psk(b"\x01") == m.DEFAULT_PSK
    assert m.expand_psk(b"\x02")[-1] == 0x02
    assert m.expand_psk(b"\x00") == b""
    # LongFast on the default key is the well-known channel hash 8
    assert m.channel_hash("LongFast", m.DEFAULT_PSK) == 8


def test_channel_roundtrip():
    # CTR is symmetric, so encrypting with our nonce and decrypting must round-trip
    hdr = struct.pack("<IIIBBBB", m.BROADCAST, 0xA1B2C3D4, 0x12345678, 0x63, 8, 0, 0)
    body = bytes.fromhex("08011205") + b"hello"
    enc = m.aes_ctr(m.DEFAULT_PSK, struct.pack("<QII", 0x12345678, 0xA1B2C3D4, 0), body)
    assert m.decode_data(m.decrypt_channel(hdr + enc, m.DEFAULT_PSK))["text"] == "hello"
    h = m.parse_header(hdr)
    assert (h["hop_limit"], h["hop_start"], h["want_ack"]) == (3, 3, False)


def _rec(text, sender=0xA1B2C3D4, dest=m.BROADCAST, typ=0):
    t = text.encode()
    return m.MSG_REC.pack(1760000000, sender, 0, dest, 0, 1, typ, 1, len(t), t)


def test_msgs_file_and_carve():
    recs = [_rec("meet at the bridge"), _rec("ok", dest=0x11223344, typ=1)]
    f = bytes([len(recs)]) + b"".join(recs)
    out = m.read_msgs(f)
    assert [r["text"] for r in out] == ["meet at the bridge", "ok"]
    assert out[1]["type"] == "DM" and out[1]["to"] == "!11223344" and out[0]["xeddsa_signed"]
    # a "deleted" record sitting in free space between junk must still be found
    img = b"\xff" * 1000 + _rec("deleted msg") + b"\x00" * 500
    hits = m.carve_msgs(img)
    assert [(h["offset"], h["text"]) for h in hits] == [(1000, "deleted msg")]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
