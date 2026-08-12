"""LightType Font (LITF) -- reference implementation.

Public API:
    read_litf(data) -> LITFFont
    write_litf(font) -> bytes
    LITFFont, Glyph, LITFError
    converter.from_ttf / from_otf / to_svg / to_text_svg
"""

from .format import (
    LITFError,
    LITFFont,
    Glyph,
    MAGIC,
    read_litf,
    write_litf,
    validate_path,
)
from . import converter

__version__ = "1.4.0"
__all__ = [
    "LITFFont",
    "Glyph",
    "LITFError",
    "MAGIC",
    "read_litf",
    "write_litf",
    "validate_path",
    "converter",
    "__version__",
]
