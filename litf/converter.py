"""Conversions between LITF and other font formats.

* from_ttf / from_otf: use fontTools to read an existing font, convert
  outlines to cubic-only SVG path strings, map the cmap + hmtx tables, and
  emit an LITFFont.
* to_svg: render an LITFFont (whole font, single glyph, or text string)
  back to SVG -- demonstrating the format's native SVG compatibility.

Required third-party dependency: fontTools (``pip install fonttools``).
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .format import Glyph, LITFFont, EMPTY_GLYPH_SENTINEL

__all__ = ["from_ttf", "from_otf", "to_svg", "to_text_svg"]


class _QuadToCubicPen:
    """A fontTools pen that records a glyph outline as a cubic-only SVG path.

    TrueType outlines use quadratic Beziers (qCurveTo). We elevate each
    quadratic segment to a cubic so the result matches the LITF command set
    (M m L l C c Z z) and stays interoperable with CFF/OTF.
    """

    def __init__(self) -> None:
        self.parts: List[str] = []
        self._cx = 0.0
        self._cy = 0.0
        self._start = (0.0, 0.0)

    def moveTo(self, pt):
        x, y = float(pt[0]), float(pt[1])
        self._cx, self._cy = x, y
        self._start = (x, y)
        self.parts.append(f"M{x:g} {y:g}")

    def lineTo(self, pt):
        x, y = float(pt[0]), float(pt[1])
        self._cx, self._cy = x, y
        self.parts.append(f"L{x:g} {y:g}")

    def curveTo(self, *points):
        # Already cubic (OTF / CFF). points = (c1, c2, ..., end)
        coords = " ".join(f"{p[0]:g} {p[1]:g}" for p in points)
        self._cx, self._cy = float(points[-1][0]), float(points[-1][1])
        self.parts.append(f"C{coords}")

    def qCurveTo(self, *points):
        # TrueType quadratic. Last point is on-curve; preceding are off-curve.
        cps = [tuple(map(float, p)) for p in points]
        end = cps[-1]
        offcurves = cps[:-1]
        start = (self._cx, self._cy)

        # Expand implicit on-curve points between consecutive off-curves.
        segs: List[tuple] = []  # (control, end)
        if len(offcurves) == 1:
            segs.append((offcurves[0], end))
        else:
            full = offcurves + [end]
            for i in range(len(offcurves)):
                c = full[i]
                if i + 1 < len(full) - 1:
                    nxt = full[i + 1]
                    onc = ((c[0] + nxt[0]) / 2.0, (c[1] + nxt[1]) / 2.0)
                    segs.append((c, onc))
                else:
                    segs.append((c, end))

        for control, seg_end in segs:
            # Degree-elevation: quadratic(start, control, end) -> cubic.
            c1x = start[0] + (2.0 / 3.0) * (control[0] - start[0])
            c1y = start[1] + (2.0 / 3.0) * (control[1] - start[1])
            c2x = seg_end[0] + (2.0 / 3.0) * (control[0] - seg_end[0])
            c2y = seg_end[1] + (2.0 / 3.0) * (control[1] - seg_end[1])
            self.parts.append(
                f"C{c1x:g} {c1y:g} {c2x:g} {c2y:g} {seg_end[0]:g} {seg_end[1]:g}"
            )
            start = seg_end
        self._cx, self._cy = float(end[0]), float(end[1])

    def closePath(self):
        self.parts.append("Z")
        self._cx, self._cy = self._start

    def endPath(self):
        pass

    def get_path(self) -> str:
        return "".join(self.parts)


def _font_to_litf(font, codepoints: Optional[Iterable[int]] = None) -> LITFFont:
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import RecordingPen  # noqa: F401 (kept for parity)

    if not isinstance(font, TTFont):
        raise TypeError("expected a fontTools TTFont instance")

    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()  # {codepoint: glyphName}
    if codepoints is not None:
        wanted = set(codepoints)
        cmap = {cp: name for cp, name in cmap.items() if cp in wanted}

    upem = int(font["head"].unitsPerEm)
    ascent = int(font["hhea"].ascent)
    descent = int(font["hhea"].descent)
    hmtx = font["hmtx"]

    glyph_order = font.getGlyphOrder()
    metrics = hmtx.metrics  # name -> (advance, lsb); robust direct dict access
    glyphs: List[Glyph] = []
    for cp, gname in sorted(cmap.items()):
        # cmap may yield glyph IDs (ints) instead of names; resolve by index.
        if isinstance(gname, int):
            gname = glyph_order[gname]
        pen = _QuadToCubicPen()
        glyph_set[gname].draw(pen)
        d = pen.get_path()
        adv = int(metrics.get(gname, (upem, 0))[0])
        if not d:
            # No contours == covered but draws nothing (e.g. space). Declare
            # as an empty glyph (sentinel "E") so codepoint coverage stays explicit.
            glyphs.append(Glyph.empty(cp, adv))
            continue
        glyphs.append(Glyph(cp, adv, d))

    return LITFFont(upem, upem, ascent, descent, upem, glyphs)


def from_ttf(path: str, codepoints: Optional[Iterable[int]] = None) -> LITFFont:
    """Convert a .ttf / .otf file to an LITFFont (ASCII subset by default)."""
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    try:
        if codepoints is None:
            # Default: printable ASCII so samples stay small and license-clean.
            codepoints = range(0x20, 0x7F)
        return _font_to_litf(font, codepoints)
    finally:
        font.close()


def from_otf(path: str, codepoints: Optional[Iterable[int]] = None) -> LITFFont:
    """Alias of from_ttf (fontTools handles both via TTFont)."""
    return from_ttf(path, codepoints)


def to_svg(font: LITFFont, codepoints: Optional[Iterable[int]] = None,
           cols: int = 16, cell: int = 64, background: str = "#ffffff") -> str:
    """Render all (or selected) glyphs of a font into a single contact-sheet SVG."""
    glyphs = font.glyphs
    if codepoints is not None:
        want = set(codepoints)
        glyphs = [g for g in glyphs if g.codepoint in want]

    rows = max(1, (len(glyphs) + cols - 1) // cols)
    width = cols * cell
    height = rows * cell
    vbw, vbh = font.viewbox_w, font.viewbox_h
    ascent, descent = font.ascent, font.descent
    # Design box height in font units (the part that actually carries ink).
    box_h = max(1, ascent - descent)
    scale = (cell * 0.9) / box_h
    # SVG-y of font baseline (y=0): top margin + ascent worth of pixels.
    baseline_y = cell * 0.05 + scale * ascent

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}">']
    out.append(f'<rect width="{width}" height="{height}" fill="{background}"/>')

    for idx, g in enumerate(glyphs):
        r, c = divmod(idx, cols)
        ox = c * cell
        oy = r * cell
        if g.is_empty:
            continue  # covered but draws nothing
        # Flip Y (font coords are y-up) and fit the design box into the cell.
        tx = ox + cell * 0.05
        ty = oy + baseline_y
        transform = f"translate({tx:.2f} {ty:.2f}) scale({scale:.6f} -{scale:.6f})"
        out.append(f'<g transform="{transform}"><path d="{g.path_data}" fill="#111"/></g>')

    out.append("</svg>")
    return "\n".join(out)


def to_text_svg(font: LITFFont, text: str, size: int = 64,
               color: str = "#111", background: str = "#ffffff") -> str:
    """Render a text string by laying out glyphs using their advance_width.

    ``size`` is the font size in px, i.e. the EM square height. The baseline is
    positioned so ascenders sit at the top and descenders at the bottom — no
    clipping. ``advance_width`` is in font units and scaled by ``size/upem``.
    """
    vbw, vbh = font.viewbox_w, font.viewbox_h
    ascent, descent = font.ascent, font.descent
    scale = size / vbh
    baseline_y = scale * ascent
    height = scale * (ascent - descent)
    pen_x = 0.0
    groups: List[str] = []
    for ch in text:
        cp = ord(ch)
        g = font.get(cp)
        if g is None:
            # Missing glyph: advance by 0.5em and skip.
            pen_x += 0.5 * vbw * scale
            continue
        transform = f"translate({pen_x:.2f} {baseline_y:.2f}) scale({scale:.6f} -{scale:.6f})"
        if not g.is_empty:
            groups.append(f'<g transform="{transform}"><path d="{g.path_data}" fill="{color}"/></g>')
        pen_x += g.advance_width * scale

    width = max(1.0, pen_x)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.2f} {height:.2f}">']
    out.append(f'<rect width="{width:.2f}" height="{height:.2f}" fill="{background}"/>')
    out.extend(groups)
    out.append("</svg>")
    return "\n".join(out)
