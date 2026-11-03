"""Read Meshtastic companion-app databases (Android Room / iOS Core Data), strictly read-only.

Opens SQLite with mode=ro&immutable=1 so the original evidence file is never written (not even
a journal). Copy the file with its -wal/-shm sidecars before running this. Output rows share one
schema (kind="message"|"node") so apps and radio data merge into a single timeline later.
"""
import json
import sqlite3


def open_ro(path: str) -> sqlite3.Connection:
    """Open a SQLite DB read-only and immutable (no writes, no journal creation)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.execute("PRAGMA trusted_schema = OFF")  # a seized database's views and triggers can't call functions
    return conn


def _q(name: str) -> str:
    """A column name from the evidence file's own schema, quoted as an SQL identifier."""
    return '"' + name.replace('"', '""') + '"'


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')")]  # nosec B608 - fixed table names only


def detect(conn) -> str | None:
    t = _tables(conn)
    if "packet" in t and "nodes" in t:
        return "android"
    if "ZMESSAGEENTITY" in t or "ZNODEINFOENTITY" in t:
        return "ios"
    return None


def _nodenum(v):
    if v is None:
        return None
    if isinstance(v, int):
        return f"!{v & 0xFFFFFFFF:08x}"
    return str(v)


def _dicts(conn, table):
    """Yield each row of a table as a {column: value} dict, tolerant of schema version."""
    cur = conn.execute(f"SELECT * FROM {table}")  # nosec B608 - fixed table names only
    cols = [c[0] for c in cur.description]
    for r in cur:
        yield dict(zip(cols, r))


def read_android(conn) -> list[dict]:
    rows = []
    for d in _dicts(conn, "packet"):
        frm = to = chan = None
        if d.get("data"):
            try:
                j = json.loads(d["data"])
                frm, to, chan = j.get("from"), j.get("to"), j.get("channel")
            except (ValueError, TypeError):
                pass
        rows.append({
            "source": "android-app", "kind": "message",
            "time": d.get("received_time"),
            "from": _nodenum(frm), "to": _nodenum(to),
            "channel": chan if chan is not None else d.get("contact_key"),
            "text": d.get("message_text"),
            "portnum": d.get("port_num"),
            "snr": d.get("snr"), "rssi": d.get("rssi"), "read": d.get("read"),
        })
    for d in _dicts(conn, "nodes"):
        pk = d.get("public_key")
        rows.append({
            "source": "android-app", "kind": "node",
            "num": _nodenum(d.get("num")),
            "long_name": d.get("long_name"), "short_name": d.get("short_name"),
            "last_heard": d.get("last_heard"),
            "lat": d.get("latitude"), "lon": d.get("longitude"),
            "public_key": pk.hex() if isinstance(pk, (bytes, bytearray)) else None,
            "via_mqtt": d.get("via_mqtt"), "hops_away": d.get("hops_away"),
        })
    return rows


def read_ios(conn) -> list[dict]:
    t, rows = _tables(conn), []
    # Core Data stores relationships as Z_PK refs; map message fromUser/toUser to node num.
    pk_to_num = {}
    if "ZNODEINFOENTITY" in t:
        ncols = _cols(conn, "ZNODEINFOENTITY")
        numcol = next((c for c in ncols if c.endswith("NUM")), None)
        if numcol:
            for pk, num in conn.execute(f"SELECT Z_PK, {_q(numcol)} FROM ZNODEINFOENTITY"):  # nosec B608 - quoted identifier
                pk_to_num[pk] = num
    if "ZMESSAGEENTITY" in t:
        mcols = _cols(conn, "ZMESSAGEENTITY")

        def col(suffix):
            return next((c for c in mcols if c.endswith(suffix)), None)

        sel = {k: col(s) for k, s in {
            "time": "MESSAGETIMESTAMP", "text": "MESSAGEPAYLOAD", "channel": "CHANNEL",
            "portnum": "PORTNUM", "frm": "FROMUSER", "to": "TOUSER",
        }.items() if col(s)}
        names = ",".join(_q(c) for c in sel.values())
        for r in conn.execute(f"SELECT {names} FROM ZMESSAGEENTITY"):  # nosec B608 - quoted identifiers
            d = dict(zip(sel.keys(), r))
            rows.append({
                "source": "ios-app", "kind": "message",
                "time": d.get("time"), "text": d.get("text"),
                "channel": d.get("channel"), "portnum": d.get("portnum"),
                "from": _nodenum(pk_to_num.get(d.get("frm"))),
                "to": _nodenum(pk_to_num.get(d.get("to"))),
            })
    if "ZNODEINFOENTITY" in t:
        ncols = _cols(conn, "ZNODEINFOENTITY")
        want = [c for c in ncols if c.endswith(("NUM", "LASTHEARD"))]
        if want:
            sel = ",".join(_q(c) for c in want)
            for r in conn.execute(f"SELECT {sel} FROM ZNODEINFOENTITY"):  # nosec B608 - quoted identifiers
                d = dict(zip(want, r))
                num = next((v for k, v in d.items() if k.endswith("NUM")), None)
                rows.append({
                    "source": "ios-app", "kind": "node",
                    "num": _nodenum(num),
                    "last_heard": next((v for k, v in d.items() if k.endswith("LASTHEARD")), None),
                })
    return rows


def read(path: str) -> list[dict]:
    """Auto-detect and read an Android or iOS companion-app database."""
    conn = open_ro(path)
    try:
        kind = detect(conn)
        if kind == "android":
            return read_android(conn)
        if kind == "ios":
            return read_ios(conn)
        raise ValueError("unrecognised database (neither Android 'packet/nodes' nor iOS 'Z*ENTITY')")
    finally:
        conn.close()
