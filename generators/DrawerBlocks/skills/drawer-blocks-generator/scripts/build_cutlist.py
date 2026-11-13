"""Write the cut list of a block of drawers as a CSV file.

Usage: python build_cutlist.py --width 760 --height 350 --depth 540 --box-clearance 4 --drawers 2 --drawer-clearance 5 --thick 18
       --thin 6 --slide-thickness 12 --slide-length 500 --slide-height 35 --slide-clearance 0.5 --out "list.csv"

All lengths in mm. The rules are d02_rules.py (an exact copy of core/drawer_rules.py). The last line printed is OK, or FAILED: <why>
(exit code 1) when the request is impossible; nothing is written then. Exit code 2: bad command line.
"""
import argparse
import sys
from pathlib import Path

from d02_rules import DrawerError, pieces_to_csv, plan_drawer_block

LENGTHS = ("width", "height", "depth", "box_clearance", "drawer_clearance", "thick", "thin", "slide_thickness", "slide_length",
           "slide_height", "slide_clearance")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drawers", type=int, required=True)
    for name in LENGTHS:
        ap.add_argument("--" + name.replace("_", "-"), type=float, required=True, dest=name)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    try:
        pieces = plan_drawer_block(drawers=args.drawers, **{k: getattr(args, k) for k in LENGTHS})
    except DrawerError as e:
        print("FAILED: %s" % e)
        return 1
    out = Path(args.out)
    out.write_text(pieces_to_csv(pieces), encoding="utf-8", newline="\n")
    print("wrote %s (%d pieces)" % (out.name, sum(p.qty for p in pieces)))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
