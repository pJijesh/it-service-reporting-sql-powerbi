"""Command line entry point: ``python -m generator``."""

from __future__ import annotations

import argparse
import sys

from .model import DEFAULT_SEED, Config
from .writer import write_all


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m generator",
        description="Write a synthetic, fictional service desk data set as CSV files.")
    parser.add_argument("--out", default="data", help="output folder (default: data)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="random seed (default: %d); the same seed gives identical files" % DEFAULT_SEED)
    parser.add_argument("--scale", type=float, default=1.0,
                        help="multiply ticket volumes, for example 0.1 for a small fast data set")
    args = parser.parse_args(argv)
    if args.scale <= 0:
        parser.error("--scale must be greater than zero")
    sums = write_all(args.out, Config(seed=args.seed, scale=args.scale))
    with open(args.out + "/tickets.csv", encoding="utf-8") as handle:
        n = sum(1 for _ in handle) - 1
    print("Wrote %d files to %s (%d tickets, seed %d)" % (len(sums), args.out, n, args.seed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
