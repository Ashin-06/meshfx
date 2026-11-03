"""meshfx command line. Every command only reads its inputs."""
import argparse
import json
import os
import sys
from pathlib import Path

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
    sv = sub.add_parser("serve", help="analysis API (settings: MESHFX_* environment variables)")
    sv.add_argument("--host", help="default MESHFX_HOST or 127.0.0.1; any other address needs API keys")
    sv.add_argument("--port", type=int, help="default MESHFX_PORT or 8101")
    sub.add_parser("migrate", help="apply database migrations to MESHFX_DATABASE_URL")
    a = p.parse_args(argv)
    if a.cmd in ("serve", "migrate"):
        return _service(a)

    if a.cmd in ("msgs", "carve"):
        data = Path(a.file if a.cmd == "msgs" else a.image).read_bytes()
        _lines(msgstore.read_msgs(data) if a.cmd == "msgs" else msgstore.carve_msgs(data))
    elif a.cmd == "parts":
        _lines(flash.parse_partition_table(Path(a.image).read_bytes()))
    elif a.cmd == "extract":
        files = flash.extract_files(Path(a.image).read_bytes())
        for path, data in sorted(files.items()):
            print(f"{len(data):8d}  {path}")
            if a.out:
                root = os.path.realpath(a.out)
                dest = os.path.realpath(os.path.join(root, path.lstrip("/\\")))
                if os.path.commonpath([root, dest]) != root:  # names come from the seized image
                    sys.exit(f"refusing to write {path!r}: it resolves outside {a.out}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
    elif a.cmd == "decode":
        data = Path(a.file).read_bytes()
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


def _service(a) -> int:
    import os

    from meshfx import db, ops

    if a.cmd == "serve":
        for flag, var in (("host", "MESHFX_HOST"), ("port", "MESHFX_PORT")):
            if getattr(a, flag) is not None:
                os.environ[var] = str(getattr(a, flag))
    try:
        settings = ops.load_settings()  # fail here, before uvicorn, with a readable message
    except ops.ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 1
    if a.cmd == "migrate":
        print(*(db.migrate(db.engine(settings.database_url)) or ["up to date"]), sep="\n")
        return 0
    import uvicorn

    ops.setup_logging(settings.log_level)
    try:
        uvicorn.run("meshfx.api:app", host=settings.host, port=settings.port, log_config=None, access_log=False)
    except ops.ConfigError as e:  # checks the API module makes when it loads
        print(f"configuration error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
