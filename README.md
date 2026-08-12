# LightType Font (LITF)

> A lightweight, open-source vector font format built on standard SVG cubic-Bézier paths — minimal, flat, and easy to adopt.
>
> **Public name: LightType Font (LITF)**
> The full project name *Open LightType Font* is reserved for the open-source license and project pages; the file marker, extension, and magic number never carry `Open`.

---

## What it is

LITF is a **minimal, flat, SVG-native** vector font format. It does one thing well: store each glyph outline as an SVG `path` `d` string, organized in a *fixed header + sorted glyph array*. There are **no separate CMAP / HMTX / GSUB tables** — a third-party developer can write a parser in about half an hour.

## Why LITF

| Pain (TTF / OTF) | What LITF does |
| --- | --- |
| Many separate tables (CMAP, HMTX, GSUB …) — steep learning curve | One fixed header + sorted array, flat structure |
| Outline model divorced from SVG | Outline *is* the SVG `path d`, renders natively |
| 16-bit indices struggle with large CJK sets | 32-bit codepoints, native support for huge character sets |
| Extension clashes / unclear MIME | Magic `LITF` checked first, extension dependency weakened |

## Naming convention

- Full project name: **Open LightType Font** (`Open` only signals open-source)
- Public promotion name: **LightType Font**
- Abbreviation: **L**ight + **I** (internal join marker) + **T**ype + **F**ont → **LITF**
- Unified markers: extension `.litf`, magic `LITF`
- Prefer *LightType Font (LITF)* in public; "Open LightType Font" only in the license / project home

## Quick start

```bash
pip install litf
```

```python
import litf

# 1) Convert any TTF/OTF to LITF (printable ASCII subset by default: small & license-clean)
font = litf.converter.from_ttf("arial.ttf")
data = litf.write_litf(font)
open("arial.litf", "wb").write(data)

# 2) Read it back
font = litf.read_litf(open("arial.litf", "rb").read())

# 3) Fetch a glyph (binary search, O(log n))
g = font.get(ord("A"))
print(g.path_data)            # "M... C... Z"

# 4) Render: drop it straight into SVG
svg = litf.converter.to_text_svg(font, "LITF rocks")
```

### Command-line tool

```bash
litf info     demo.litf                 # dump header and glyph summary
litf validate demo.litf                 # validate against the spec
litf convert  arial.ttf arial.litf      # TTF/OTF -> LITF (ASCII subset by default)
litf convert  arial.ttf cjk.litf --codepoints 0x5F00,0x6E90,0x5B57,0x4F53
litf extract  demo.litf sheet.svg       # export glyph contact sheet
litf render   demo.litf "Hello LITF" -o out.svg   # text -> SVG
```

### Web demo (pure frontend, no backend)

Open [`web/index.html`](web/index.html) and drag any `.litf` file in:
- Pure `ArrayBuffer` parsing, zero dependencies, runs offline
- Glyph grid preview; click a glyph to inspect its SVG `path` and live render
- Text layout preview — proves "outline is SVG, renders natively"

## Binary layout

All multi-byte integers are **little-endian**; text is **UTF-8**.

### Fixed header (26 bytes)

| Type | Name | Description |
| --- | --- | --- |
| char[4] | magic | fixed ASCII `LITF` |
| uint16 | viewBox_w | global viewBox width |
| uint16 | viewBox_h | global viewBox height |
| int16 | ascent | font ascent (positive) |
| int16 | descent | font descent (negative) |
| uint16 | units_per_em | EM base unit |
| uint32 | glyph_count | total number of glyphs |
| uint32 | reserved[2] | reserved, must be zero |

### Glyph entry (repeated glyph_count times, ascending by codepoint)

| Type | Name | Description |
| --- | --- | --- |
| uint32 | codepoint | Unicode codepoint (32-bit, native CJK support) |
| int32 | advance_width | horizontal advance width |
| uint32 | path_byte_len | byte length of path_data |
| uint8[] | path_data | UTF-8 SVG path `d` string, no terminator |

### Path syntax constraints

Glyph `path` strings MAY ONLY contain these commands; all others are forbidden:

```
M m L l C c Z z
```

- `C/c` cubic Bézier — interoperable with CFF / OTF outlines for cross-format conversion
- All coordinates reference the global `viewBox` in the header; per-glyph canvas data is not repeated
- Only the necessary separating spaces are kept; no newlines or extra whitespace

## Empty-glyph convention (important)

Some codepoints are *covered but draw no outline* (e.g. space, control chars, `.notdef` slots). Since the spec forbids `path_byte_len = 0`, an empty glyph is declared with the single letter **`E`** as `path_data`:

- `path_data == "E"` → parser treats it as an empty glyph: codepoint covered, but nothing is drawn and no error is raised
- Writers emit `E` for contour-less glyphs, guaranteeing `path_byte_len == 1` with clear semantics
- This resolves the edge case "this codepoint counts as font coverage, but has no outline", avoiding misclassification as a missing glyph

## Standard parse flow (for third-party developers)

1. Read the first 4 bytes; verify magic `LITF`; reject on mismatch
2. Read the full fixed header; obtain `glyph_count`
3. Read all glyph entries sequentially
4. Entries are ordered — use **binary search** to match the target Unicode codepoint
5. Obtain `advance_width` and `path_data`
6. Render: `<path d="path_data" fill="#000"/>` using the global `viewBox`

## Write rules (converters / editors must obey)

- All multi-byte integers are little-endian
- Sort all glyph entries ascending by codepoint; drop duplicate codepoints before writing
- Forbid empty-path glyphs with `path_byte_len = 0` (use `E` for contour-less glyphs)
- Keep only necessary separating spaces in the path string; no newlines or extra whitespace
- `reserved` fields must be zeroed
- Restrict path commands strictly; forbid `A/a`, `Q/q`, `S/s`, `T/t`

## Feature summary

- Minimal structure, no separate CMAP / HMTX tables — low integration cost
- Native SVG paths — cross-platform rendering, easy debugging
- Unified magic and extension — simple, memorable naming
- 32-bit index — native support for massive character sets (CJK)

## Repository layout

```
litf/                 Python reference implementation (codec + TTF/OTF conversion + rendering)
  format.py           fixed header + sorted glyph array binary read/write and validation
  converter.py        TTF/OTF -> LITF (quad->cubic), LITF -> SVG
  cli.py              command-line tool `litf`
tests/                pytest unit tests (round-trip / sort-dedup / empty glyph / command check)
web/index.html        pure-frontend parser + renderer demo
samples/              sample fonts (demo.litf / cjk.litf ...) and SVG output
spec/                 LITF format specification V1.4
```

## License

[MIT](LICENSE) — free to use, modify, and redistribute.
