"""litf -- command line toolkit for the LightType Font (.litf) format.

Subcommands:
    info      Dump the fixed header and glyph summary of a .litf file.
    validate  Check a .litf file against the spec (magic, order, paths).
    convert   Convert a .ttf/.otf font into a .litf file (ASCII subset by default).
    extract   Export glyphs of a .litf file to an SVG contact sheet.
    render    Render a text string to SVG using a .litf font.
"""

from __future__ import annotations

import argparse
import sys

from .format import LITFError, LITFFont, read_litf, write_litf
from . import converter


def _cmd_info(args: argparse.Namespace) -> int:
    data = open(args.input, "rb").read()
    font = read_litf(data)
    print(f"file            : {args.input}")
    print(f"magic           : LITF (OK)")
    print(f"viewBox         : {font.viewbox_w} x {font.viewbox_h}")
    print(f"ascent          : {font.ascent}")
    print(f"descent         : {font.descent}")
    print(f"units_per_em    : {font.units_per_em}")
    print(f"glyph_count     : {font.glyph_count}")
    if args.verbose:
        print("--- glyphs (codepoint, advance, path_len) ---")
        for g in font.glyphs:
            ch = chr(g.codepoint) if 32 <= g.codepoint < 127 else "?"
            tag = "empty" if g.is_empty else f"len={g.byte_len()}"
            print(f"  U+{g.codepoint:04X} {ch!r:>4}  adv={g.advance_width:<5} {tag}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    data = open(args.input, "rb").read()
    try:
        font = read_litf(data)
    except LITFError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    for g in font.glyphs:
        try:
            from .format import validate_path
            validate_path(g.path_data)
        except LITFError as e:
            print(f"INVALID glyph U+{g.codepoint:04X}: {e}", file=sys.stderr)
            return 1
    print(f"OK: {font.glyph_count} glyphs, structurally valid.")
    return 0


def _cmd_convert(args: argparse.Namespace) -> int:
    if args.codepoints:
        cps = [int(x, 0) for x in args.codepoints.split(",")]
        font = converter.from_ttf(args.input, codepoints=cps)
    else:
        font = converter.from_ttf(args.input)
    data = write_litf(font)
    open(args.output, "wb").write(data)
    print(f"wrote {args.output}: {font.glyph_count} glyphs, {len(data)} bytes")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    data = open(args.input, "rb").read()
    font = read_litf(data)
    svg = converter.to_svg(font, cols=args.cols, cell=args.cell)
    open(args.output, "w", encoding="utf-8").write(svg)
    print(f"wrote {args.output}: {len(svg)} bytes SVG")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    data = open(args.input, "rb").read()
    font = read_litf(data)
    svg = converter.to_text_svg(font, args.text, size=args.size)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(svg)
        print(f"wrote {args.output}: {len(svg)} bytes SVG")
    else:
        sys.stdout.write(svg + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="litf", description="LightType Font (.litf) toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("info", help="dump .litf header and glyph summary")
    pi.add_argument("input")
    pi.add_argument("-v", "--verbose", action="store_true")
    pi.set_defaults(func=_cmd_info)

    pv = sub.add_parser("validate", help="validate a .litf file against the spec")
    pv.add_argument("input")
    pv.set_defaults(func=_cmd_validate)

    pc = sub.add_parser("convert", help="convert .ttf/.otf to .litf")
    pc.add_argument("input")
    pc.add_argument("output")
    pc.add_argument("--codepoints", help="comma list of codepoints (e.g. 0x41,0x42)")
    pc.set_defaults(func=_cmd_convert)

    pe = sub.add_parser("extract", help="export glyphs to an SVG contact sheet")
    pe.add_argument("input")
    pe.add_argument("output")
    pe.add_argument("--cols", type=int, default=16)
    pe.add_argument("--cell", type=int, default=64)
    pe.set_defaults(func=_cmd_extract)

    pr = sub.add_parser("render", help="render a text string to SVG")
    pr.add_argument("input")
    pr.add_argument("text")
    pr.add_argument("--size", type=int, default=64)
    pr.add_argument("-o", "--output")
    pr.set_defaults(func=_cmd_render)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LITFError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
