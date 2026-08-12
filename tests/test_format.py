import struct
import litf
from litf.format import (
    LITFFont, Glyph, read_litf, write_litf, validate_path, LITFError,
    _HEADER_FMT, _GLYPH_HDR_FMT,
)


def _roundtrip(font):
    data = write_litf(font)
    back = read_litf(data)
    assert back.glyph_count == font.glyph_count
    assert back.viewbox_w == font.viewbox_w
    for a, b in zip(font.glyphs, back.glyphs):
        assert a.codepoint == b.codepoint
        assert a.advance_width == b.advance_width
        assert a.path_data == b.path_data
    return back


def test_roundtrip_basic():
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph(0x41, 600, "M0 0 L100 0 L100 700 L0 700 Z"),
        Glyph(0x42, 600, "M0 0 C50 0 50 100 0 100 Z"),
    ])
    _roundtrip(f)


def test_sorted_and_deduped():
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph(0x42, 1, "M0 0 L1 1 Z"),
        Glyph(0x41, 1, "M0 0 L1 1 Z"),
        Glyph(0x41, 9, "M0 0 L1 1 Z"),  # duplicate codepoint -> dropped
    ])
    data = write_litf(f)
    back = read_litf(data)
    assert [g.codepoint for g in back.glyphs] == [0x41, 0x42]
    assert back.get(0x41).advance_width == 1  # first wins


def test_empty_glyph_via_E():
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph.empty(0x20, 278),                      # space
        Glyph(0x41, 600, "M0 0 L100 0 L100 700 Z"),
    ])
    back = _roundtrip(f)
    space = back.get(0x20)
    assert space.is_empty
    assert space.advance_width == 278
    # byte length is 1 ('E'), never 0
    assert space.byte_len() == 1


def test_empty_glyph_helper():
    g = Glyph.empty(0x200B, 0)
    assert g.is_empty
    assert g.path_data == "E"


def test_forbidden_command_rejected():
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph(0x41, 1, "M0 0 Q10 10 20 0 Z"),  # Q not allowed
    ])
    try:
        write_litf(f)
        assert False, "should have rejected Q"
    except LITFError:
        pass


def test_bad_magic_rejected():
    data = bytearray(write_litf(LITFFont(1000, 1000, 800, -200, 1000,
                                         [Glyph(0x41, 1, "M0 0 L1 1 Z")])))
    data[0] = ord("X")
    try:
        read_litf(bytes(data))
        assert False
    except LITFError:
        pass


def test_not_ascending_rejected():
    # craft two glyphs out of order manually
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph(0x42, 1, "M0 0 L1 1 Z"),
        Glyph(0x41, 1, "M0 0 L1 1 Z"),
    ])
    # write_litf sorts, so force an unsorted byte stream instead
    out = bytearray()
    out += struct.pack(_HEADER_FMT, b"LITF", 1000, 1000, 800, -200, 1000, 2, 0, 0)
    for cp in (0x42, 0x41):
        raw = "M0 0 L1 1 Z".encode("utf-8")
        out += struct.pack(_GLYPH_HDR_FMT, cp, 1, len(raw))
        out += raw
    try:
        read_litf(bytes(out))
        assert False
    except LITFError:
        pass


def test_validate_path_rules():
    # valid
    for d in ["M0 0 L1 1 Z", "M0 0 C1 1 2 2 3 3 Z", "E", "m0 0 l1 1 z"]:
        validate_path(d)
    # invalid: empty string
    try:
        validate_path("")
        assert False
    except LITFError:
        pass
    # invalid: forbidden command
    try:
        validate_path("M0 0 Q1 1 2 2 Z")
        assert False
    except LITFError:
        pass
    # invalid: non-E single letter is rejected
    try:
        validate_path("B")
        assert False
    except LITFError:
        pass


def test_binary_search_missing():
    f = LITFFont(1000, 1000, 800, -200, 1000, [
        Glyph(0x41, 1, "M0 0 L1 1 Z"),
        Glyph(0x42, 1, "M0 0 L1 1 Z"),
    ])
    data = write_litf(f)
    back = read_litf(data)
    assert back.get(0x41) is not None
    assert back.get(0x43) is None
