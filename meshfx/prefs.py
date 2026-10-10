"""Decode the protobuf and binary files Meshtastic stores under /prefs and /backups.

File -> message type map is from firmware src/mesh/NodeDB.h. All functions read only.
"""
import struct

from google.protobuf.json_format import MessageToDict

from meshfx.proto.meshtastic import (
    device_ui_pb2,
    deviceonly_pb2,
    localonly_pb2,
    portnums_pb2,
)

# basename -> protobuf message class (NodeDB.h constants)
PROTO_FILES = {
    "device.proto": deviceonly_pb2.DeviceState,
    "db.proto": deviceonly_pb2.DeviceState,          # legacy: DeviceState incl. node DB (<=2.5)
    "nodes.proto": deviceonly_pb2.NodeDatabase,
    "config.proto": localonly_pb2.LocalConfig,
    "event-config.proto": localonly_pb2.LocalConfig,
    "module.proto": localonly_pb2.LocalModuleConfig,
    "channels.proto": deviceonly_pb2.ChannelFile,
    "event-channels.proto": deviceonly_pb2.ChannelFile,
    "uiconfig.proto": device_ui_pb2.DeviceUIConfig,
    "backup.proto": deviceonly_pb2.BackupPreferences,
    "event-backup.proto": deviceonly_pb2.BackupPreferences,
}

MENC_MAGIC = 0x4D454E43  # "MENC", stored little-endian (lockdown builds)


def is_encrypted(data: bytes) -> bool:
    """True if the file is a lockdown-build encrypted proto (starts with the MENC magic)."""
    return len(data) >= 4 and struct.unpack("<I", data[:4])[0] == MENC_MAGIC


def decode_proto(basename: str, data: bytes) -> dict:
    """Decode a known /prefs or /backups protobuf file to a dict.

    Raises KeyError for an unknown basename. nodes.proto falls back to the legacy schema if the
    2.8 NodeDatabase does not parse (older firmware wrote NodeDatabase_Legacy here).
    """
    if is_encrypted(data):
        return {"_encrypted": True, "note": "lockdown MENC file; key not on device"}
    msg = PROTO_FILES[basename]()
    try:
        msg.ParseFromString(data)
    except Exception:
        if basename == "nodes.proto":
            msg = deviceonly_pb2.NodeDatabase_Legacy()
            msg.ParseFromString(data)
        else:
            raise
    return MessageToDict(msg, preserving_proto_field_name=True)


_TH_HDR = struct.Struct("<IBB")       # magic "THST", version, count
_PORTNUM = {v.number: v.name for v in portnums_pb2.PortNum.DESCRIPTOR.values}


def decode_transmit_history(data: bytes) -> dict:
    """Parse /prefs/transmit_history.dat (firmware TransmitHistory): last broadcast time per portnum."""
    magic, version, count = _TH_HDR.unpack_from(data, 0)
    if magic != 0x54485354:  # "THST"
        raise ValueError("not a transmit_history.dat (bad magic)")
    # Entry is packed {key:u16, epochSeconds:u32, flags:u8}=7B (v2) or {key:u16, epoch:u32}=6B (v1)
    entries, off = [], _TH_HDR.size
    for _ in range(count):
        key, epoch = struct.unpack_from("<HI", data, off)
        if version >= 2:
            flags = data[off + 6]
            off += 7
        else:
            flags = 0
            off += 6
        entries.append({
            "portnum": _PORTNUM.get(key, key),
            "epoch_seconds": epoch,
            "boot_relative": bool(flags & 0x01),
        })
    return {"version": version, "entries": entries}
