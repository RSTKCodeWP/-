"""Standard-library OSD PNG font loading and glyph preparation.

This module ports the non-rendering part of GroundConfiguration's OSD font
pipeline.  It intentionally stops at cached RGBA and premultiplied-BGRA glyph
bytes; a GUI or video overlay is outside this project's scope.
"""

from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Sequence


BYTES_PER_PIXEL = 4
HD_FONT_WIDTH = 24
NUM_CHARS = 256
NUM_FONT_PAGES = 16

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ADAM7_PASSES = (
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
)


class FontLoadError(ValueError):
    """Raised when a PNG cannot be decoded as a valid image."""


@dataclass
class DisplayFontInfo:
    """Loaded OSD font metadata and page-major RGBA data."""

    font_width: int = 0
    font_height: int = 0
    fonts: list[bytes | None] = field(
        default_factory=lambda: [None] * NUM_FONT_PAGES
    )

    def close(self) -> None:
        """Release all loaded font pages."""
        if self.fonts is not None:
            for index in range(len(self.fonts)):
                self.fonts[index] = None


@dataclass(frozen=True)
class PngImage:
    """Decoded PNG pixels in row-major RGBA order."""

    width: int
    height: int
    rgba: bytes


@dataclass(frozen=True)
class CachedGlyph:
    """A decoded glyph ready for a platform renderer.

    ``pixels`` is row-major premultiplied BGRA, matching GDI+'s
    ``Format32bppPArgb`` memory representation.
    """

    width: int
    height: int
    pixels: bytes


def _ensure_font_cache(display_info: DisplayFontInfo) -> None:
    if display_info.fonts is None or len(display_info.fonts) < NUM_FONT_PAGES:
        display_info.fonts = [None] * NUM_FONT_PAGES


def _validate_display_info(display_info: DisplayFontInfo) -> None:
    if display_info is None:
        raise ValueError("display_info is required")
    if display_info.font_width <= 0:
        raise ValueError("FontWidth must be greater than zero.")
    if display_info.font_height <= 0:
        raise ValueError("FontHeight must be greater than zero.")


def _infer_height(file_name: str | None, image_height: int) -> int:
    name = (file_name or "").lower()
    if "_24" in name:
        return 36
    if "_36" in name:
        return 54
    if "540p" in name:
        return 27
    if "720p" in name:
        return 36
    if "1080p" in name:
        return 54
    if "1440p" in name:
        return 72
    if "2160p" in name:
        return 108
    if image_height % NUM_CHARS == 0:
        return image_height // NUM_CHARS
    return 0


def _infer_width(file_name: str | None, image_width: int) -> int:
    name = (file_name or "").lower()
    if "_24" in name:
        return 24
    if "_36" in name:
        return 36
    if "540p" in name:
        return 18
    if "720p" in name:
        return 24
    if "1080p" in name:
        return 36
    if "1440p" in name:
        return 48
    if "2160p" in name:
        return 72
    if image_width % HD_FONT_WIDTH == 0:
        return HD_FONT_WIDTH
    return image_width


def try_infer_font_size(
    file_name_without_extension: str | None,
    image_width: int,
    image_height: int,
) -> tuple[int, int] | None:
    """Infer ``(font_width, font_height)`` using the C# rule ordering."""
    height = _infer_height(file_name_without_extension, image_height)
    if height <= 0 or image_height % (height * NUM_CHARS) != 0:
        return None

    width = _infer_width(file_name_without_extension, image_width)
    if width <= 0 or image_width % width != 0:
        return None
    return width, height


def infer_font_size_from_file(file_path: str | Path) -> tuple[int, int] | None:
    """Read only the PNG dimensions and apply the filename inference rules."""
    path = Path(file_path)
    with path.open("rb") as stream:
        width, height = _read_png_dimensions(stream)
    return try_infer_font_size(path.stem, width, height)


def _read_png_dimensions(stream: BinaryIO) -> tuple[int, int]:
    signature = stream.read(8)
    if signature != PNG_SIGNATURE:
        raise FontLoadError("invalid PNG signature")
    length_data = stream.read(4)
    chunk_type = stream.read(4)
    if len(length_data) != 4 or len(chunk_type) != 4:
        raise FontLoadError("truncated PNG header")
    length = struct.unpack(">I", length_data)[0]
    if chunk_type != b"IHDR" or length != 13:
        raise FontLoadError("PNG does not start with IHDR")
    payload = stream.read(length)
    if len(payload) != length:
        raise FontLoadError("truncated PNG IHDR")
    width, height = struct.unpack(">II", payload[:8])
    if width <= 0 or height <= 0:
        raise FontLoadError("PNG dimensions must be positive")
    return width, height


def _read_png(path: str | Path) -> PngImage:
    """Decode common PNG color types without third-party dependencies."""
    data = Path(path).read_bytes()
    if len(data) < 8 or data[:8] != PNG_SIGNATURE:
        raise FontLoadError("invalid PNG signature")

    position = 8
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    idat = bytearray()
    palette: bytes | None = None
    transparency: bytes | None = None
    seen_iend = False

    while position < len(data):
        if position + 12 > len(data):
            raise FontLoadError("truncated PNG chunk")
        length = struct.unpack(">I", data[position : position + 4])[0]
        position += 4
        chunk_type = data[position : position + 4]
        position += 4
        end = position + length
        if end + 4 > len(data):
            raise FontLoadError("truncated PNG chunk data")
        payload = data[position:end]
        position = end
        received_crc = struct.unpack(">I", data[position : position + 4])[0]
        position += 4
        calculated_crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
        if received_crc != calculated_crc:
            raise FontLoadError("PNG chunk CRC mismatch")

        if chunk_type == b"IHDR":
            if ihdr is not None or length != 13:
                raise FontLoadError("invalid PNG IHDR")
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"PLTE":
            palette = bytes(payload)
        elif chunk_type == b"tRNS":
            transparency = bytes(payload)
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"IEND":
            if length != 0:
                raise FontLoadError("invalid PNG IEND")
            seen_iend = True
            break

    if ihdr is None or not seen_iend:
        raise FontLoadError("PNG is missing IHDR or IEND")

    width, height, bit_depth, color_type, compression, filter_method, interlace = ihdr
    if width <= 0 or height <= 0:
        raise FontLoadError("PNG dimensions must be positive")
    if compression != 0 or filter_method != 0 or interlace not in (0, 1):
        raise FontLoadError("unsupported PNG compression, filter, or interlace")

    allowed_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if color_type not in allowed_depths or bit_depth not in allowed_depths[color_type]:
        raise FontLoadError("unsupported PNG color type or bit depth")
    if color_type == 3 and (palette is None or len(palette) == 0 or len(palette) % 3):
        raise FontLoadError("indexed PNG is missing a valid palette")
    if transparency is not None and color_type not in (0, 2, 3):
        raise FontLoadError("invalid PNG transparency chunk")

    try:
        decompressed = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise FontLoadError("PNG image data could not be decompressed") from exc

    rgba = _decode_scanlines(
        decompressed,
        width,
        height,
        bit_depth,
        color_type,
        interlace,
        palette,
        transparency,
    )
    return PngImage(width, height, bytes(rgba))


def _channels(color_type: int) -> int:
    return {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]


def _pass_size(length: int, start: int, step: int) -> int:
    return 0 if length <= start else (length - start + step - 1) // step


def _unfilter_row(
    encoded: bytes,
    previous: bytes,
    filter_type: int,
    bytes_per_pixel: int,
) -> bytes:
    result = bytearray(encoded)
    for index in range(len(result)):
        left = result[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if previous else 0
        upper_left = previous[index - bytes_per_pixel] if previous and index >= bytes_per_pixel else 0
        if filter_type == 0:
            value = result[index]
        elif filter_type == 1:
            value = result[index] + left
        elif filter_type == 2:
            value = result[index] + up
        elif filter_type == 3:
            value = result[index] + ((left + up) // 2)
        elif filter_type == 4:
            predictor = left + up - upper_left
            pa = abs(predictor - left)
            pb = abs(predictor - up)
            pc = abs(predictor - upper_left)
            nearest = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
            value = result[index] + nearest
        else:
            raise FontLoadError(f"unsupported PNG row filter: {filter_type}")
        result[index] = value & 0xFF
    return bytes(result)


def _sample(row: bytes, index: int, bit_depth: int) -> int:
    if bit_depth == 8:
        return row[index]
    if bit_depth == 16:
        return (row[index * 2] << 8) | row[index * 2 + 1]
    bit_position = index * bit_depth
    byte_value = row[bit_position // 8]
    shift = 8 - bit_depth - (bit_position % 8)
    return (byte_value >> shift) & ((1 << bit_depth) - 1)


def _scale_sample(value: int, bit_depth: int) -> int:
    if bit_depth == 8:
        return value
    maximum = (1 << bit_depth) - 1
    return (value * 255 + maximum // 2) // maximum


def _pixel_to_rgba(
    row: bytes,
    pixel_index: int,
    bit_depth: int,
    color_type: int,
    palette: bytes | None,
    transparency: bytes | None,
) -> tuple[int, int, int, int]:
    channels = _channels(color_type)
    sample_base = pixel_index * channels
    if color_type == 0:
        gray = _sample(row, sample_base, bit_depth)
        alpha = 255
        if transparency is not None and len(transparency) >= 2:
            transparent_gray = struct.unpack(">H", transparency[:2])[0]
            if bit_depth < 16:
                transparent_gray &= (1 << bit_depth) - 1
            alpha = 0 if gray == transparent_gray else 255
        gray8 = _scale_sample(gray, bit_depth)
        return gray8, gray8, gray8, alpha

    if color_type == 2:
        red = _sample(row, sample_base, bit_depth)
        green = _sample(row, sample_base + 1, bit_depth)
        blue = _sample(row, sample_base + 2, bit_depth)
        alpha = 255
        if transparency is not None and len(transparency) >= 6:
            transparent = struct.unpack(">HHH", transparency[:6])
            if bit_depth < 16:
                transparent = tuple(value & ((1 << bit_depth) - 1) for value in transparent)
            alpha = 0 if (red, green, blue) == transparent else 255
        return (
            _scale_sample(red, bit_depth),
            _scale_sample(green, bit_depth),
            _scale_sample(blue, bit_depth),
            alpha,
        )

    if color_type == 3:
        palette_index = _sample(row, pixel_index, bit_depth)
        assert palette is not None
        palette_offset = palette_index * 3
        if palette_offset + 3 > len(palette):
            raise FontLoadError("PNG palette index is out of range")
        alpha = transparency[palette_index] if transparency and palette_index < len(transparency) else 255
        return (
            palette[palette_offset],
            palette[palette_offset + 1],
            palette[palette_offset + 2],
            alpha,
        )

    if color_type == 4:
        gray = _sample(row, sample_base, bit_depth)
        alpha = _sample(row, sample_base + 1, bit_depth)
        gray8 = _scale_sample(gray, bit_depth)
        return gray8, gray8, gray8, _scale_sample(alpha, bit_depth)

    red = _sample(row, sample_base, bit_depth)
    green = _sample(row, sample_base + 1, bit_depth)
    blue = _sample(row, sample_base + 2, bit_depth)
    alpha = _sample(row, sample_base + 3, bit_depth)
    return (
        _scale_sample(red, bit_depth),
        _scale_sample(green, bit_depth),
        _scale_sample(blue, bit_depth),
        _scale_sample(alpha, bit_depth),
    )


def _decode_pass(
    decompressed: bytes,
    offset: int,
    pass_width: int,
    pass_height: int,
    bit_depth: int,
    color_type: int,
    palette: bytes | None,
    transparency: bytes | None,
) -> tuple[bytearray, int]:
    bits_per_pixel = _channels(color_type) * bit_depth
    row_bytes = (pass_width * bits_per_pixel + 7) // 8
    filter_bytes_per_pixel = max(1, (bits_per_pixel + 7) // 8)
    previous = b""
    rows = bytearray()
    for _ in range(pass_height):
        if offset >= len(decompressed):
            raise FontLoadError("PNG scanline data is truncated")
        filter_type = decompressed[offset]
        offset += 1
        end = offset + row_bytes
        if end > len(decompressed):
            raise FontLoadError("PNG scanline data is truncated")
        row = _unfilter_row(
            decompressed[offset:end], previous, filter_type, filter_bytes_per_pixel
        )
        offset = end
        previous = row
        for pixel_index in range(pass_width):
            rows.extend(
                _pixel_to_rgba(
                    row, pixel_index, bit_depth, color_type, palette, transparency
                )
            )
    return rows, offset


def _decode_scanlines(
    decompressed: bytes,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
    palette: bytes | None,
    transparency: bytes | None,
) -> bytearray:
    output = bytearray(width * height * BYTES_PER_PIXEL)
    offset = 0
    if interlace == 0:
        rows, offset = _decode_pass(
            decompressed,
            offset,
            width,
            height,
            bit_depth,
            color_type,
            palette,
            transparency,
        )
        output[:] = rows
        if offset != len(decompressed):
            raise FontLoadError("PNG contains unexpected trailing scanline data")
        return output

    for start_x, start_y, step_x, step_y in _ADAM7_PASSES:
        pass_width = _pass_size(width, start_x, step_x)
        pass_height = _pass_size(height, start_y, step_y)
        if pass_width == 0 or pass_height == 0:
            continue
        rows, offset = _decode_pass(
            decompressed,
            offset,
            pass_width,
            pass_height,
            bit_depth,
            color_type,
            palette,
            transparency,
        )
        cursor = 0
        for pass_y in range(pass_height):
            target_y = start_y + pass_y * step_y
            for pass_x in range(pass_width):
                target_x = start_x + pass_x * step_x
                target = (target_y * width + target_x) * BYTES_PER_PIXEL
                output[target : target + 4] = rows[cursor : cursor + 4]
                cursor += 4
    if offset != len(decompressed):
        raise FontLoadError("PNG contains unexpected trailing scanline data")
    return output


def _split_font_pages(
    display_info: DisplayFontInfo,
    rgba_image_data: bytes,
    image_width: int,
    horizontal_pages: int,
    vertical_pages: int,
) -> None:
    display_info.close()
    char_width_bytes = display_info.font_width * BYTES_PER_PIXEL
    char_size_bytes = display_info.font_width * display_info.font_height * BYTES_PER_PIXEL
    page_size_bytes = char_size_bytes * NUM_CHARS
    source_char_rows_bytes = image_width * display_info.font_height * BYTES_PER_PIXEL
    source_page_rows_bytes = source_char_rows_bytes * NUM_CHARS

    for vertical_page in range(vertical_pages):
        for horizontal_page in range(horizontal_pages):
            page = vertical_page * horizontal_pages + horizontal_page
            page_data = bytearray(page_size_bytes)
            display_info.fonts[page] = bytes(page_data)
            for char_index in range(NUM_CHARS):
                for row in range(display_info.font_height):
                    destination_offset = char_index * char_size_bytes + row * char_width_bytes
                    source_offset = (
                        vertical_page * source_page_rows_bytes
                        + char_index * source_char_rows_bytes
                        + image_width * row * BYTES_PER_PIXEL
                        + horizontal_page * char_width_bytes
                    )
                    page_data[destination_offset : destination_offset + char_width_bytes] = (
                        rgba_image_data[source_offset : source_offset + char_width_bytes]
                    )
            display_info.fonts[page] = bytes(page_data)


def try_open_font_file(file_path: str | Path, display_info: DisplayFontInfo) -> bool:
    """Load and split one PNG, returning ``False`` on an invalid file."""
    path = Path(file_path)
    if not path.is_file():
        return False
    try:
        image = _read_png(path)
        page_height = display_info.font_height * NUM_CHARS
        if image.height % page_height != 0:
            return False
        if image.width % display_info.font_width != 0:
            return False
        horizontal_pages = image.width // display_info.font_width
        vertical_pages = image.height // page_height
        num_pages = horizontal_pages * vertical_pages
        if horizontal_pages <= 0 or vertical_pages <= 0 or num_pages > NUM_FONT_PAGES:
            return False
        _split_font_pages(
            display_info,
            image.rgba,
            image.width,
            horizontal_pages,
            vertical_pages,
        )
        return True
    except (OSError, FontLoadError, ValueError, struct.error, zlib.error):
        display_info.close()
        return False


def close_font(display_info: DisplayFontInfo | None) -> None:
    """Clear all font pages, matching ``FontLoader.CloseFont``."""
    if display_info is not None:
        display_info.close()


def get_font_path_with_extension(
    font_path: str,
    extension: str,
    is_hd: bool,
    font_variant: str | None,
) -> str:
    """Build the C# loader's variant/HD filename."""
    if font_path is None:
        raise ValueError("font_path is required")
    if extension is None:
        raise ValueError("extension is required")
    variant_suffix = "" if not font_variant else "_" + font_variant
    hd_suffix = "_hd" if is_hd else ""
    return font_path + variant_suffix + hd_suffix + extension


def _normalize_variant(font_variant: str | None) -> str:
    return (font_variant or "")[:4].lower()


def _fallback_variant(font_variant: str) -> str:
    if font_variant == "btfl":
        return "bf"
    if font_variant == "ultr":
        return "ultra"
    return ""


def load_font_from_file(display_info: DisplayFontInfo, file_path: str | Path | None) -> bool:
    """Load a user-selected PNG into ``display_info``.

    The C# method logs and returns for an empty or invalid path rather than
    raising a file-not-found exception, so this Python API returns ``False``.
    """
    _validate_display_info(display_info)
    _ensure_font_cache(display_info)
    if file_path is None or not str(file_path).strip():
        return False
    return try_open_font_file(file_path, display_info)


def load_font(
    display_info: DisplayFontInfo,
    font_variant: str | None,
    *,
    sdcard_font_path: str = "/storage/sdcard0/font",
    fallback_font_path: str = "/blackbox/font",
    entware_font_path: str = "/opt/fonts/font",
) -> None:
    """Try the same device/fallback font search order as the C# loader."""
    _validate_display_info(display_info)
    _ensure_font_cache(display_info)
    normalized = _normalize_variant(font_variant)
    fallback = _fallback_variant(normalized)

    candidates: list[tuple[str, str]] = []
    for base in (sdcard_font_path, fallback_font_path):
        candidates.append((base, normalized))
        if fallback:
            candidates.append((base, fallback))
    candidates.append((entware_font_path, normalized))
    if not _try_any_font(candidates, display_info):
        generic = (
            (sdcard_font_path, ""),
            (fallback_font_path, ""),
            (entware_font_path, ""),
        )
        if not _try_any_font(generic, display_info):
            raise FileNotFoundError("No valid font PNG could be loaded.")


def _try_any_font(candidates: Sequence[tuple[str, str]], display_info: DisplayFontInfo) -> bool:
    for base_path, variant in candidates:
        if not base_path:
            continue
        path = get_font_path_with_extension(
            base_path,
            ".png",
            display_info.font_width == HD_FONT_WIDTH,
            variant,
        )
        if try_open_font_file(path, display_info):
            return True
    return False


def premultiply(value: int, alpha: int) -> int:
    """Apply the integer premultiplication formula used by C#."""
    return (value * alpha + 127) // 255


def copy_rgba_to_premultiplied_bgra(
    source: bytes | bytearray,
    source_offset: int,
    width: int,
    height: int,
    source_stride: int,
    destination: bytearray,
    destination_stride: int,
) -> None:
    """Convert an RGBA rectangle to a cleared premultiplied-BGRA buffer."""
    if source is None:
        raise ValueError("source is required")
    if destination is None:
        raise ValueError("destination is required")
    if width < 0 or height < 0:
        raise ValueError("width and height must not be negative")
    if source_offset < 0 or source_stride < width * 4 or destination_stride < width * 4:
        raise ValueError("invalid source or destination stride")
    required_source = source_offset + (0 if height == 0 else (height - 1) * source_stride + width * 4)
    required_destination = 0 if height == 0 else (height - 1) * destination_stride + width * 4
    if required_source > len(source):
        raise ValueError("source buffer is too small")
    if required_destination > len(destination):
        raise ValueError("destination buffer is too small")

    destination[:] = b"\x00" * len(destination)
    for row in range(height):
        source_row = source_offset + row * source_stride
        destination_row = row * destination_stride
        for column in range(width):
            source_pixel = source_row + column * 4
            destination_pixel = destination_row + column * 4
            red, green, blue, alpha = source[source_pixel : source_pixel + 4]
            destination[destination_pixel : destination_pixel + 4] = bytes(
                (premultiply(blue, alpha), premultiply(green, alpha), premultiply(red, alpha), alpha)
            )


class OsdGlyphCache:
    """Lazily convert loaded RGBA glyphs into premultiplied BGRA bytes."""

    def __init__(self, font_info: DisplayFontInfo):
        if font_info is None:
            raise ValueError("font_info is required")
        self._font_info = font_info
        self._glyphs: dict[int, CachedGlyph] = {}
        self._disposed = False

    def get_glyph(self, page: int, char_index: int) -> CachedGlyph | None:
        if self._disposed:
            raise RuntimeError("OsdGlyphCache has been disposed")
        if self._font_info.font_width <= 0 or self._font_info.font_height <= 0:
            return None
        if self._font_info.fonts is None:
            return None
        if page < 0 or page >= len(self._font_info.fonts):
            return None
        if char_index < 0 or char_index >= NUM_CHARS:
            return None
        page_data = self._font_info.fonts[page]
        if page_data is None:
            return None
        width = self._font_info.font_width
        height = self._font_info.font_height
        glyph_size = width * height * BYTES_PER_PIXEL
        source_offset = char_index * glyph_size
        if source_offset < 0 or source_offset + glyph_size > len(page_data):
            return None
        key = (page << 8) | char_index
        cached = self._glyphs.get(key)
        if cached is not None:
            return cached
        destination = bytearray(glyph_size)
        copy_rgba_to_premultiplied_bgra(
            page_data,
            source_offset,
            width,
            height,
            width * BYTES_PER_PIXEL,
            destination,
            width * BYTES_PER_PIXEL,
        )
        cached = CachedGlyph(width, height, bytes(destination))
        self._glyphs[key] = cached
        return cached

    def GetGlyph(self, page: int, char_index: int) -> CachedGlyph | None:
        """C#-style alias for callers ported mechanically from the source."""
        return self.get_glyph(page, char_index)

    def dispose(self) -> None:
        self._glyphs.clear()
        self._disposed = True

    def Dispose(self) -> None:
        """C#-style alias for callers ported mechanically from the source."""
        self.dispose()

    def __enter__(self) -> "OsdGlyphCache":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.dispose()


# Compatibility aliases that mirror the source class names without adding a
# GUI dependency.
GdiOsdGlyphCache = OsdGlyphCache


class OsdPixelConverter:
    """C#-style facade for the portable pixel conversion function."""

    CopyRgbaToPremultipliedBgra = staticmethod(copy_rgba_to_premultiplied_bgra)


class FontLoader:
    """C#-shaped facade for the portable font-loading functions."""

    BytesPerPixel = BYTES_PER_PIXEL
    HdFontWidth = HD_FONT_WIDTH
    NumChars = NUM_CHARS
    NumFontPages = NUM_FONT_PAGES
    FallbackFontPath = "/blackbox/font"
    EntwareFontPath = "/opt/fonts/font"
    SdcardFontPath = "/storage/sdcard0/font"

    @staticmethod
    def LoadFontFromFile(display_info: DisplayFontInfo, file_path: str | Path | None) -> None:
        load_font_from_file(display_info, file_path)

    @classmethod
    def LoadFont(cls, display_info: DisplayFontInfo, font_variant: str | None) -> None:
        load_font(
            display_info,
            font_variant,
            sdcard_font_path=cls.SdcardFontPath,
            fallback_font_path=cls.FallbackFontPath,
            entware_font_path=cls.EntwareFontPath,
        )

    @staticmethod
    def CloseFont(display_info: DisplayFontInfo | None) -> None:
        close_font(display_info)

    @staticmethod
    def GetFontPathWithExtension(
        font_path: str,
        extension: str,
        is_hd: bool,
        font_variant: str | None,
    ) -> str:
        return get_font_path_with_extension(font_path, extension, is_hd, font_variant)


__all__ = [
    "BYTES_PER_PIXEL",
    "HD_FONT_WIDTH",
    "NUM_CHARS",
    "NUM_FONT_PAGES",
    "CachedGlyph",
    "DisplayFontInfo",
    "FontLoadError",
    "FontLoader",
    "GdiOsdGlyphCache",
    "OsdGlyphCache",
    "OsdPixelConverter",
    "PngImage",
    "close_font",
    "copy_rgba_to_premultiplied_bgra",
    "get_font_path_with_extension",
    "infer_font_size_from_file",
    "load_font",
    "load_font_from_file",
    "premultiply",
    "try_infer_font_size",
    "try_open_font_file",
]