"""LITF (LightType Font) binary format reference implementation.

File layout (all multi-byte integers little-endian):

    +--------------------+------------------------------------------+
    | Fixed header (26B) | Ordered glyph entries (ascending codepoint)
    +--------------------+------------------------------------------+

Header fields:
    char[4]  magic         b"LITF"
    uint16   viewBox_w     global viewBox width
    uint16   viewBox_h     global viewBox height
    int16    ascent        font ascent (positive)
    int16    descent       font descent (negative)
    uint16   units_per_em  EM base unit
    uint32   glyph_count   number of glyph entries
    uint32   reserved[2]   must be zero

Per-glyph entry:
    uint32   codepoint     Unicode codepoint
    int32    advance_width horizontal advance width
    uint32   path_byte_len byte length of path_data
    uint8[]  path_data     UTF-8 SVG path "d" string (no terminator)

Path strings MAY ONLY contain the commands: M m L l C c Z z.
All glyph entries MUST be sorted ascending by codepoint, no duplicates.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import List

MAGIC = b"LITF"

# magic(4) + vbw(2) + vbh(2) + ascent(2) + descent(2) + upem(2) + count(4) + reserved(8)
_HEADER_FMT = "<4sHHhhHIII"
HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 26

_GLYPH_HDR_FMT = "<I i I"  # codepoint, advance_width, path_byte_len  -> 12 bytes
_GLYPH_HDR_SIZE = struct.calcsize(_GLYPH_HDR_FMT)

# Allowed SVG path commands per the LITF spec (section 3).
ALLOWED_COMMANDS = set("MmLlCcZz")

# The single canonical sentinel for an "empty glyph" (a covered codepoint that
# draws nothing, e.g. space / control chars / .notdef slots). Per spec, the
# empty-glyph marker is EXACTLY the letter "E"; parsers accept only this.
EMPTY_GLYPH_SENTINEL = "E"

# Tokenizer: any single ASCII letter is treated as a command token; numbers
# (incl. scientific notation) are captured whole. Unknown command letters are
# NOT silently dropped -- validators reject them explicitly.
_TOKEN_RE = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


class LITFError(Exception):
    """Raised on malformed LITF data or invalid write operations."""


@dataclass
class Glyph:
    codepoint: int
    advance_width: int
    path_data: str

    def byte_len(self) -> int:
        return len(self.path_data.encode("utf-8"))

    @property
    def is_empty(self) -> bool:
        """True when path_data is exactly the empty-glyph sentinel "E"."""
        return self.path_data.strip() == EMPTY_GLYPH_SENTINEL

    @classmethod
    def empty(cls, codepoint: int, advance_width: int) -> "Glyph":
        """Build an empty glyph: a covered codepoint that draws nothing."""
        return cls(codepoint, advance_width, EMPTY_GLYPH_SENTINEL)


@dataclass
class LITFFont:
    viewbox_w: int
    viewbox_h: int
    ascent: int
    descent: int
    units_per_em: int
    glyphs: List[Glyph] = field(default_factory=list)

    @property
    def glyph_count(self) -> int:
        return len(self.glyphs)

    def get(self, codepoint: int) -> Glyph | None:
        """Binary search for a glyph by codepoint (entries are sorted)."""
        lo, hi = 0, len(self.glyphs) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            cp = self.glyphs[mid].codepoint
            if cp == codepoint:
                return self.glyphs[mid]
            if cp < codepoint:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def to_bytes(self) -> bytes:
        return write_litf(self)


def validate_path(d: str) -> None:
    """Validate that a path string contains only allowed commands.

    A single non-drawing letter (e.g. "E") is accepted as an *empty-glyph*
    marker. Any other content must use only the commands M m L l C c Z z,
    with correct coordinate arity. Raises LITFError otherwise.
    """
    if not d or not d.strip():
        raise LITFError("empty path_data is not allowed")

    stripped = d.strip()
    # Empty-glyph sentinel: exactly the single letter "E".
    if stripped == EMPTY_GLYPH_SENTINEL:
        return

    tokens = _TOKEN_RE.findall(d)
    if not tokens:
        raise LITFError("path_data has no parseable tokens")

    i = 0
    expected_per_cmd = {"M": 2, "m": 2, "L": 2, "l": 2, "C": 6, "c": 6, "Z": 0, "z": 0}
    while i < len(tokens):
        tok = tokens[i]
        # A single letter is a command; anything else must be a number.
        if len(tok) == 1 and tok.isalpha():
            if tok not in ALLOWED_COMMANDS:
                raise LITFError(
                    f"forbidden path command '{tok}' (only M m L l C c Z z allowed)"
                )
            arity = expected_per_cmd[tok]
            i += 1
            if arity == 0:
                continue
            nums: List[float] = []
            while i < len(tokens) and not (len(tokens[i]) == 1 and tokens[i].isalpha()):
                nums.append(float(tokens[i]))
                i += 1
            if len(nums) == 0 or len(nums) % arity != 0:
                raise LITFError(
                    f"command '{tok}' expects multiples of {arity} numbers, got {len(nums)}"
                )
        else:
            raise LITFError(f"unexpected token '{tok}' (expected a path command letter)")


def _normalize_glyphs(glyphs: List[Glyph]) -> List[Glyph]:
    """Sort ascending by codepoint and drop duplicates (keep first)."""
    seen = set()
    ordered: List[Glyph] = []
    for g in sorted(glyphs, key=lambda x: x.codepoint):
        if g.codepoint in seen:
            continue
        seen.add(g.codepoint)
        ordered.append(g)
    return ordered


def write_litf(font: LITFFont) -> bytes:
    """Serialize an LITFFont to bytes. Performs all spec write checks."""
    if font.units_per_em <= 0:
        raise LITFError("units_per_em must be positive")
    if font.viewbox_w <= 0 or font.viewbox_h <= 0:
        raise LITFError("viewBox dimensions must be positive")

    ordered = _normalize_glyphs(font.glyphs)
    if not ordered:
        raise LITFError("a LITF font must contain at least one glyph")

    out = bytearray()
    out += struct.pack(
        _HEADER_FMT,
        MAGIC,
        font.viewbox_w & 0xFFFF,
        font.viewbox_h & 0xFFFF,
        font.ascent,
        font.descent,
        font.units_per_em & 0xFFFF,
        len(ordered),
        0,  # reserved[0]
        0,  # reserved[1]
    )

    for g in ordered:
        validate_path(g.path_data)
        raw = g.path_data.encode("utf-8")
        out += struct.pack(_GLYPH_HDR_FMT, g.codepoint & 0xFFFFFFFF, g.advance_width, len(raw))
        out += raw

    return bytes(out)


def read_litf(data: bytes) -> LITFFont:
    """Parse LITF bytes into an LITFFont. Raises LITFError on bad data."""
    if len(data) < HEADER_SIZE:
        raise LITFError(f"file too small: {len(data)} bytes (< {HEADER_SIZE} header)")

    (magic, vbw, vbh, ascent, descent, upem, count, r0, r1) = struct.unpack(
        _HEADER_FMT, data[:HEADER_SIZE]
    )
    if magic != MAGIC:
        raise LITFError(f"bad magic: {magic!r} (expected {MAGIC!r})")

    glyphs: List[Glyph] = []
    off = HEADER_SIZE
    prev_cp = -1
    for _ in range(count):
        if off + _GLYPH_HDR_SIZE > len(data):
            raise LITFError("truncated glyph header table")
        cp, adv, plen = struct.unpack_from(_GLYPH_HDR_FMT, data, off)
        off += _GLYPH_HDR_SIZE
        if off + plen > len(data):
            raise LITFError(f"glyph {cp:#x}: path_data extends past EOF")
        raw = data[off:off + plen]
        off += plen
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise LITFError(f"glyph {cp:#x}: path_data is not valid UTF-8 ({e})")
        if cp <= prev_cp:
            raise LITFError(f"glyph codepoints not strictly ascending at {cp:#x}")
        prev_cp = cp
        glyphs.append(Glyph(cp, adv, path))

    if off != len(data):
        raise LITFError(f"trailing bytes after last glyph: {len(data) - off}")

    return LITFFont(vbw, vbh, ascent, descent, upem, glyphs)
