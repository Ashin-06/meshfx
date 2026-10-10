"""Merge radio-flash and companion-app artifacts into one timeline, with sender attribution.

Attribution levels follow research/05: a message's "from" is only trustworthy with a verified
signature or a PKI tag. Everything else is self-asserted and forgeable by any channel-key holder.
"""
import csv
import html
import io
import json
import os

from meshfx import apps, flash, msgstore, prefs


def attribution(event: dict) -> str:
    """Confidence that `from` is genuine, for a message event (research/05, levels A-D)."""
    if event.get("kind") != "message":
        return ""
    if event.get("xeddsa_signed"):
        return "A: signature verified"
    if event.get("pki_encrypted"):
        return "B: pairwise PKI"
    return "C: channel key only (sender self-asserted, forgeable)"


def _ts(event: dict):
    for k in ("time", "timestamp", "last_heard", "epoch_seconds"):
        v = event.get(k)
        if isinstance(v, int) and v > 0:
            return v
    return None


def from_flash(image: bytes) -> list[dict]:
    """All timeline events recoverable from one ESP32 flash dump."""
    events, files = [], flash.extract_files(image)
    for path, data in files.items():
        base = os.path.basename(path)
        if base.endswith(".msgs"):
            events += [{**m, "kind": "message", "source": "radio-flash"} for m in msgstore.read_msgs(data)]
        elif base in prefs.PROTO_FILES:
            try:
                decoded = prefs.decode_proto(base, data)
            except Exception as e:  # keep going; note the unparsable file
                events.append({"source": "radio-flash", "kind": "parse_error", "file": path, "error": str(e)})
                continue
            events += _events_from_proto(base, decoded)
    return events


def _events_from_proto(base: str, decoded: dict) -> list[dict]:
    out = []
    if decoded.get("_encrypted"):
        return [{"source": "radio-flash", "kind": "encrypted_file", "file": base}]
    nodes = decoded.get("nodes") if base in ("nodes.proto", "db.proto") else None
    for n in nodes or []:
        out.append({
            "source": "radio-flash", "kind": "node",
            "num": f"!{n['num']:08x}" if isinstance(n.get("num"), int) else n.get("num"),
            "long_name": n.get("long_name"), "short_name": n.get("short_name"),
            "last_heard": n.get("last_heard"),
            "public_key": n.get("public_key"),
        })
    if base == "channels.proto":
        for c in decoded.get("channels", []):
            s = c.get("settings", {})
            if s.get("name") or s.get("psk"):
                out.append({"source": "radio-flash", "kind": "channel",
                            "name": s.get("name"), "has_key": bool(s.get("psk"))})
    return out


def build_timeline(*event_lists) -> list[dict]:
    """Flatten, attribute, and sort events. Events with no timestamp sort to the end."""
    events = [e for lst in event_lists for e in lst]
    for e in events:
        if e.get("kind") == "message":
            e["attribution"] = attribution(e)
        e["ts"] = _ts(e)
    events.sort(key=lambda e: (e["ts"] is None, e["ts"] or 0))
    return events


def collect(flash_path: str | None = None, app_paths: list[str] | None = None) -> list[dict]:
    lists = []
    if flash_path:
        lists.append(from_flash(open(flash_path, "rb").read()))
    for ap in app_paths or []:
        lists.append(apps.read(ap))
    return build_timeline(*lists)


def to_json(events: list[dict]) -> str:
    return json.dumps(events, indent=2, ensure_ascii=False, default=str)


def to_csv(events: list[dict]) -> str:
    cols = ["ts", "source", "kind", "from", "to", "channel", "text", "attribution",
            "num", "long_name", "short_name", "name"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for e in events:
        w.writerow(e)
    return buf.getvalue()


def to_html(events: list[dict], title: str = "MeshFX timeline") -> str:
    rows = []
    for e in events:
        cells = [e.get("ts") or "", e.get("source", ""), e.get("kind", ""),
                 e.get("from") or e.get("num") or "", e.get("to") or "",
                 e.get("text") or e.get("long_name") or e.get("name") or "",
                 e.get("attribution", "")]
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in cells) + "</tr>")
    head = "".join(f"<th>{h}</th>" for h in ["ts", "source", "kind", "from/num", "to", "text/name", "attribution"])
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            "<style>body{font:14px system-ui;margin:1rem}table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}"
            "th{background:#f0f0f0}tr:nth-child(even){background:#fafafa}</style>"
            f"<h1>{html.escape(title)}</h1><p>{len(events)} events. "
            "Attribution C means the sender name is self-asserted and forgeable.</p>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
