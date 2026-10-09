"""meshfx - Meshtastic forensics proof-of-concept.

Formats follow meshtastic/firmware master @ 40a0178 (2026-10-09); see ../research/.
Needs only Python 3.10+ and `cryptography`.

  python meshfx.py header  <packet-hex>
  python meshfx.py decrypt <packet-hex> [--psk BASE64] [--channel NAME]
  python meshfx.py decrypt-pki <packet-hex> --priv HEX --pub HEX
  python meshfx.py msgs    <Messages_default.msgs>
  python meshfx.py carve   <raw-flash-or-partition.bin>
"""
import argparse, base64, hashlib, json, struct, sys

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

# src/mesh/Channels.h - the published "AQ==" key
DEFAULT_PSK = bytes.fromhex("d4f1bb3a20290759f0bcffabcf4e6901")
BROADCAST = 0xFFFFFFFF


def expand_psk(psk: bytes) -> bytes:
    """Channels::getKey(): 1-byte PSKs index the default key, short keys are zero-padded."""
    if len(psk) == 1:
        if psk[0] == 0:
            return b""  # encryption disabled
        return DEFAULT_PSK[:-1] + bytes([(DEFAULT_PSK[-1] + psk[0] - 1) & 0xFF])
    if 0 < len(psk) < 16:
        return psk.ljust(16, b"\0")
    if 16 < len(psk) < 32:
        return psk.ljust(32, b"\0")
    return psk


def channel_hash(name: str, key: bytes, aead: bool = False) -> int:
    """Channels::generateHash(): xor of name bytes ^ xor of key bytes (^0xAE for AEAD channels)."""
    h = 0
    for b in name.encode() + key:
        h ^= b
    return h ^ 0xAE if aead else h


def parse_header(pkt: bytes) -> dict:
    """16-byte cleartext header (meshtastic.org/docs/overview/mesh-algo)."""
    dest, sender, pid, flags, chash, next_hop, relay = struct.unpack_from("<IIIBBBB", pkt)
    return {
        "to": dest, "from": sender, "id": pid,
        "hop_limit": flags & 7, "want_ack": bool(flags & 8), "via_mqtt": bool(flags & 16),
        "hop_start": flags >> 5, "channel_hash": chash, "next_hop": next_hop, "relay_node": relay,
        "payload_len": len(pkt) - 16,
    }


def aes_ctr(key: bytes, counter_block: bytes, data: bytes) -> bytes:
    """CryptoEngine::encryptAESCtr - whole 16-byte block is the big-endian initial counter."""
    return Cipher(algorithms.AES(key), modes.CTR(counter_block)).encryptor().update(data)


def decrypt_channel(pkt: bytes, key: bytes) -> bytes:
    """AES-CTR channel packet. CryptoEngine::initNonce: id as u64 LE | from u32 LE | 4 zero bytes."""
    h = parse_header(pkt)
    return aes_ctr(key, struct.pack("<QII", h["id"], h["from"], 0), pkt[16:])


def decrypt_pki(pkt: bytes, recipient_priv: bytes, sender_pub: bytes) -> bytes:
    """PKI direct message: X25519 -> SHA-256 -> AES-256-CCM, 8-byte tag, then 4-byte extraNonce.

    Nonce is 13 bytes: id (low 32) | extraNonce | from | 0x00 - initNonce() writes extraNonce over
    the high half of the 64-bit packet id.
    """
    h = parse_header(pkt)
    body = pkt[16:]
    ct_and_tag, extra = body[:-4], body[-4:]
    shared = X25519PrivateKey.from_private_bytes(recipient_priv).exchange(X25519PublicKey.from_public_bytes(sender_pub))
    nonce = struct.pack("<I", h["id"]) + extra + struct.pack("<I", h["from"]) + b"\0"
    return AESCCM(hashlib.sha256(shared).digest(), tag_length=8).decrypt(nonce, ct_and_tag, None)


def decode_data(buf: bytes) -> dict:
    """Minimal decoder for the meshtastic.Data envelope; full decode needs the protobufs."""
    out, i = {}, 0
    names = {1: "portnum", 2: "payload", 3: "want_response", 4: "dest", 5: "source",
             6: "request_id", 7: "reply_id", 8: "emoji", 9: "bitfield"}

    def varint():
        nonlocal i
        v = shift = 0
        while True:
            b = buf[i]; i += 1
            v |= (b & 0x7F) << shift; shift += 7
            if b < 0x80:
                return v

    while i < len(buf):
        key = varint()
        field, wt = key >> 3, key & 7
        if wt == 0:
            val = varint()
        elif wt == 2:
            n = varint(); val = buf[i:i + n]; i += n
        elif wt == 5:
            val = struct.unpack_from("<I", buf, i)[0]; i += 4
        elif wt == 1:
            val = struct.unpack_from("<Q", buf, i)[0]; i += 8
        else:
            raise ValueError(f"bad wire type {wt}")
        out[names.get(field, field)] = val
    if out.get("portnum") == 1 and isinstance(out.get("payload"), bytes):  # TEXT_MESSAGE_APP
        out["text"] = out["payload"].decode("utf-8", "replace")
    return out


# --- on-device message history: src/MessageStore.cpp StoredMessageRecord (packed, LE) ---
MSG_REC = struct.Struct("<IIBIBBBBH220s")  # 239 bytes
ACK = ["NONE", "ACKED", "NACKED", "TIMEOUT", "RELAYED"]


def _record(raw: bytes, offset=None) -> dict:
    ts, sender, ch, dest, boot_rel, ack, typ, signed, tlen, text = MSG_REC.unpack(raw)
    r = {
        "timestamp": ts, "timestamp_is_uptime": bool(boot_rel), "from": f"!{sender:08x}",
        "to": "^all" if dest == BROADCAST else f"!{dest:08x}", "channel_index": ch,
        "type": "DM" if typ == 1 else "BROADCAST", "ack": ACK[ack] if ack < len(ACK) else ack,
        "xeddsa_signed": bool(signed), "text": text.split(b"\0", 1)[0].decode("utf-8", "replace"),
    }
    if offset is not None:
        r["offset"] = offset
    return r


def read_msgs(data: bytes) -> list[dict]:
    """Parse a /Messages_<label>.msgs file: 1-byte count, then count fixed-size records."""
    count = data[0]
    if len(data) != 1 + count * MSG_REC.size:
        print(f"warning: {len(data)} bytes does not match {count} x {MSG_REC.size}-byte records; "
              "older firmware layout?", file=sys.stderr)
    return [_record(data[1 + k * MSG_REC.size: 1 + (k + 1) * MSG_REC.size])
            for k in range(count) if 1 + (k + 1) * MSG_REC.size <= len(data)]


def carve_msgs(img: bytes) -> list[dict]:
    """Find StoredMessageRecords anywhere in a raw image, including freed LittleFS blocks.

    ponytail: byte-by-byte scan with cheap early exits; fine for 8-16 MB dumps. Records split
    across LittleFS blocks (always on nRF52's 128-byte blocks) are missed - needs an lfs-aware pass.
    """
    hits, n, size = [], len(img), MSG_REC.size
    for o in range(n - size + 1):
        if img[o + 13] > 1 or img[o + 14] > 4 or img[o + 15] > 1 or img[o + 16] > 1:
            continue
        tlen = img[o + 17] | img[o + 18] << 8
        if not 0 < tlen < 220:
            continue
        text = img[o + 19: o + 19 + tlen]
        if 0 in text or any(img[o + 19 + tlen: o + size]):
            continue
        try:
            text.decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits.append(_record(img[o: o + size], offset=o))
    return hits


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("header").add_argument("packet")
    d = sub.add_parser("decrypt")
    d.add_argument("packet")
    d.add_argument("--psk", default="AQ==", help="channel PSK, base64 (default: public AQ== key)")
    d.add_argument("--channel", default="LongFast", help="channel name, used only to check the hash")
    k = sub.add_parser("decrypt-pki")
    k.add_argument("packet")
    k.add_argument("--priv", required=True, help="recipient X25519 private key, hex")
    k.add_argument("--pub", required=True, help="sender X25519 public key, hex")
    sub.add_parser("msgs").add_argument("file")
    sub.add_parser("carve").add_argument("image")
    a = p.parse_args(argv)

    if a.cmd in ("header", "decrypt", "decrypt-pki"):
        pkt = bytes.fromhex(a.packet)
        out = {"header": parse_header(pkt)}
        if a.cmd == "decrypt":
            key = expand_psk(base64.b64decode(a.psk))
            out["hash_matches"] = channel_hash(a.channel, key) == out["header"]["channel_hash"]
            out["data"] = decode_data(decrypt_channel(pkt, key) if key else pkt[16:])
        elif a.cmd == "decrypt-pki":
            out["data"] = decode_data(decrypt_pki(pkt, bytes.fromhex(a.priv), bytes.fromhex(a.pub)))
        print(json.dumps(out, indent=2, default=lambda b: b.hex()))
    else:
        data = open(a.file if a.cmd == "msgs" else a.image, "rb").read()
        for r in (read_msgs(data) if a.cmd == "msgs" else carve_msgs(data)):
            print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
