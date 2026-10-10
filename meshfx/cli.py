"""meshfx command line. Every command only reads its inputs."""
import argparse
import json
import sys

from meshfx import msgstore


def _lines(rows):
    for r in rows:
        print(json.dumps(r, ensure_ascii=False, default=str))


def main(argv=None):
    p = argparse.ArgumentParser(prog="meshfx", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("msgs", help="parse a /Messages_*.msgs file").add_argument("file")
    sub.add_parser("carve", help="find message records anywhere in a raw image").add_argument("image")
    a = p.parse_args(argv)

    data = open(a.file if a.cmd == "msgs" else a.image, "rb").read()
    _lines(msgstore.read_msgs(data) if a.cmd == "msgs" else msgstore.carve_msgs(data))


if __name__ == "__main__":
    sys.exit(main())
