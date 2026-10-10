"""meshfx command line. Every command only reads its inputs."""
import argparse
import json
import os
import sys

from meshfx import flash, msgstore


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


if __name__ == "__main__":
    sys.exit(main())
