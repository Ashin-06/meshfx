"""meshfx command line. Every command only reads its inputs."""
import argparse
import json
import os
import sys

from meshfx import apps, flash, msgstore, prefs, report


def _lines(rows):
    for r in rows:
        print(json.dumps(r, ensure_ascii=False, default=str))


def main(argv=None):
    p = argparse.ArgumentParser(prog="meshfx", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("msgs", help="parse a /Messages_*.msgs file").add_argument("file")
    sub.add_parser("carve", help="find message records anywhere in a raw image").add_argument("image")
    pt = sub.add_parser("parts", help="print the ESP32 partition table of a flash dump")
    pt.add_argument("image")
    ex = sub.add_parser("extract", help="extract the LittleFS data partition of an ESP32 flash dump")
    ex.add_argument("image")
    ex.add_argument("-o", "--out", help="write files to this directory (default: just list them)")
    dc = sub.add_parser("decode", help="decode a stored /prefs or /backups file (.proto or transmit_history.dat)")
    dc.add_argument("file")
    ap = sub.add_parser("app", help="read an Android/iOS companion-app database (read-only)")
    ap.add_argument("db")
    tl = sub.add_parser("timeline", help="merge a flash dump and/or app DBs into one timeline")
    tl.add_argument("--flash", help="ESP32 flash dump")
    tl.add_argument("--app", action="append", default=[], help="companion-app DB (repeatable)")
    tl.add_argument("--format", choices=["json", "csv", "html"], default="json")
    a = p.parse_args(argv)

    if a.cmd in ("msgs", "carve"):
        data = open(a.file if a.cmd == "msgs" else a.image, "rb").read()
        _lines(msgstore.read_msgs(data) if a.cmd == "msgs" else msgstore.carve_msgs(data))
    elif a.cmd == "parts":
        _lines(flash.parse_partition_table(open(a.image, "rb").read()))
    elif a.cmd == "extract":
        files = flash.extract_files(open(a.image, "rb").read())
        for path, data in sorted(files.items()):
            print(f"{len(data):8d}  {path}")
            if a.out:
                dest = os.path.join(a.out, path.lstrip("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
    elif a.cmd == "decode":
        data = open(a.file, "rb").read()
        base = os.path.basename(a.file)
        if base == "transmit_history.dat":
            out = prefs.decode_transmit_history(data)
        elif base in prefs.PROTO_FILES:
            out = prefs.decode_proto(base, data)
        else:
            sys.exit(f"don't know how to decode {base}; known: {', '.join(prefs.PROTO_FILES)}, "
                     "transmit_history.dat")
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "app":
        _lines(apps.read(a.db))
    elif a.cmd == "timeline":
        if not a.flash and not a.app:
            p.error("timeline needs --flash and/or --app")
        events = report.collect(a.flash, a.app)
        renderer = {"json": report.to_json, "csv": report.to_csv, "html": report.to_html}[a.format]
        print(renderer(events))


if __name__ == "__main__":
    sys.exit(main())
