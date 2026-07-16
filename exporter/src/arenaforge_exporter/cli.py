from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .core import Anchor, ExportPaths, ExporterError, default_script_dir, load_saved_anchors, run_export


def parse_anchor(value: str) -> Anchor:
    if "=" not in value:
        raise argparse.ArgumentTypeError("anchors must use NAME=QTY")
    name, qty = value.rsplit("=", 1)
    try:
        quantity = int(qty)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid quantity: {qty}") from exc
    return Anchor(0, quantity, name.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=f"ArenaForge MTGA Exporter {__version__}")
    parser.add_argument("--output-dir", default=str(default_script_dir()))
    parser.add_argument("--raw-dir", default=None, help="Optional MTGA Downloads\\Raw folder override")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--anchor", action="append", type=parse_anchor, help='Anchor as "Card Name=Quantity"')
    args = parser.parse_args()

    paths = ExportPaths(Path(args.output_dir))
    anchors = args.anchor or []
    if not anchors:
        try:
            anchors = load_saved_anchors(paths)
        except Exception:
            anchors = []
    if not anchors:
        print('Provide at least one --anchor "Card Name=Quantity" or run the GUI.')
        return 2

    try:
        result = run_export(
            anchors=anchors,
            output_dir=args.output_dir,
            manual_raw_path=args.raw_dir,
            refresh_cache=args.refresh_cache,
            log=print,
            progress=lambda label, index, total: print(f"[{index}/{total}] {label}"),
        )
    except ExporterError as exc:
        print(f"Export failed: {exc}")
        input("Press Enter to exit...")
        return 1

    print("Export complete!")
    print(f"JSON: {result.output_json}")
    print(f"TXT:  {result.output_txt}")
    print(f"CSV:  {result.output_csv}")
    input("Press Enter to exit...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
