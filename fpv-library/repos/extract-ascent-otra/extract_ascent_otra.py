#!/usr/bin/env python3
"""
Extract partitions from Artosyn / Walksnail OTRA firmware update images.
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import lz4.block
from PySquashfsImage import SquashFsImage
from PySquashfsImage import compressor as squashfs_compressor
from PySquashfsImage.extract import extract_dir as extract_squashfs_dir
from ubireader import settings as ubi_settings
from ubireader.ubi import ubi
from ubireader.ubi_io import ubi_file
from ubireader.ubifs import ubifs
from ubireader.ubifs.output import extract_files as extract_ubifs_files
from ubireader.utils import guess_leb_size, guess_peb_size, guess_start_offset


PART_REC_SIZE = 0x34
CHUNK_REC_SIZE = 0x20
ERASED_BYTE = 0xFF
UBI_MAGIC = b"UBI#"


@dataclass(frozen=True)
class Partition:
    name: str
    start: int
    size: int
    flag: int


@dataclass(frozen=True)
class Chunk:
    file_off: int
    flash_off: int
    comp_size: int
    raw_size: int


class SquashfsLZ4Compressor(squashfs_compressor.Compressor):
    name = "lz4"

    def uncompress(self, src: bytes, size: int, outsize: int) -> bytes:
        return lz4.block.decompress(src, uncompressed_size=outsize)


squashfs_compressor.compressors[squashfs_compressor.Compression.LZ4] = SquashfsLZ4Compressor


def hx(value: int) -> str:
    return f"0x{value:08x}"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._+-]+", "_", name).strip("_") or "partition"


def find_otra_base(buf: bytes) -> int:
    off = buf.find(b"OTRA")
    if off < 0:
        raise RuntimeError("OTRA header not found")
    return off


def parse_partitions_at(buf: bytes, off: int, min_records: int = 1) -> list[Partition]:
    parts: list[Partition] = []
    index = 0
    last_start = -1

    while off + (index + 1) * PART_REC_SIZE <= len(buf):
        rec = off + index * PART_REC_SIZE
        raw_name = buf[rec : rec + 32]
        name = raw_name.split(b"\0", 1)[0]
        if not name:
            break
        if any(c < 0x20 or c > 0x7E for c in name):
            break

        name_s = name.decode("ascii", errors="strict")
        start, size = struct.unpack_from("<QQ", buf, rec + 32)
        flag = struct.unpack_from("<I", buf, rec + 48)[0]

        if size <= 0 or size > 0x40000000:
            break
        if start < last_start:
            break
        if start % 0x1000 != 0 or size % 0x1000 != 0:
            break

        parts.append(Partition(name_s, start, size, flag))
        last_start = start
        index += 1

    if len(parts) < min_records:
        raise RuntimeError("partition table candidate is too short")
    return parts


def find_partition_table(buf: bytes, search_from: int = 0) -> int:
    pos = search_from
    while True:
        pos = buf.find(b"bl31\0", pos)
        if pos < 0:
            raise RuntimeError("partition table not found")
        try:
            parts = parse_partitions_at(buf, pos, min_records=3)
        except Exception:
            pos += 1
            continue

        names = [part.name for part in parts[:8]]
        if "uboot0" in names and "kernel" in names:
            return pos
        pos += 1


def parse_chunks(buf: bytes, chunk_table_off: int, otra_base: int) -> list[Chunk]:
    first_data_rel = struct.unpack_from("<Q", buf, chunk_table_off)[0]
    first_data_abs = otra_base + first_data_rel
    if not (chunk_table_off < first_data_abs <= len(buf)):
        raise RuntimeError("invalid chunk table")

    chunks: list[Chunk] = []
    off = chunk_table_off
    while off + CHUNK_REC_SIZE <= first_data_abs:
        file_off, flash_off, comp_size, raw_size = struct.unpack_from("<QQQQ", buf, off)
        abs_file_off = otra_base + file_off

        if not (0 <= abs_file_off < len(buf)):
            break
        if comp_size <= 0 or raw_size <= 0:
            break
        if abs_file_off + comp_size > len(buf):
            break

        chunks.append(Chunk(file_off, flash_off, comp_size, raw_size))
        off += CHUNK_REC_SIZE

    if not chunks:
        raise RuntimeError("no chunk records found")
    return chunks


class LZO1XError(RuntimeError):
    pass


class LZO1XDecoder:
    @staticmethod
    def decompress(src: bytes, expected_size: int | None = None) -> bytes:
        ip = 0
        n = len(src)
        out = bytearray()

        def get_byte() -> int:
            nonlocal ip
            if ip >= n:
                raise LZO1XError("LZO input overrun")
            value = src[ip]
            ip += 1
            return value

        def copy_literal(length: int) -> None:
            nonlocal ip
            if length < 0:
                raise LZO1XError("negative literal length")
            if ip + length > n:
                raise LZO1XError("LZO literal input overrun")
            out.extend(src[ip : ip + length])
            ip += length

        def copy_match(match_pos: int, length: int) -> None:
            if length < 0:
                raise LZO1XError("negative match length")
            if match_pos < 0 or match_pos >= len(out):
                raise LZO1XError(
                    f"LZO look-behind overrun: match_pos={match_pos}, out={len(out)}, length={length}"
                )
            for _ in range(length):
                out.append(out[match_pos])
                match_pos += 1

        t = get_byte()

        if t > 17:
            t -= 17
            copy_literal(t)
            t = get_byte()

        while True:
            if t < 16:
                if t == 0:
                    while True:
                        value = get_byte()
                        if value != 0:
                            t += 15 + value
                            break
                        t += 255

                copy_literal(t + 3)
                t = get_byte()

                if t < 16:
                    match_pos = len(out) - 0x801 - (t >> 2) - (get_byte() << 2)
                    copy_match(match_pos, 3)
                    t = src[ip - 2] & 3
                    if t:
                        copy_literal(t)
                        t = get_byte()
                    else:
                        t = get_byte()
                    continue

            if t >= 64:
                match_pos = len(out) - 1 - ((t >> 2) & 7) - (get_byte() << 3)
                length = (t >> 5) + 1
                copy_match(match_pos, length)

            elif t >= 32:
                t &= 31
                if t == 0:
                    while True:
                        value = get_byte()
                        if value != 0:
                            t += 31 + value
                            break
                        t += 255

                value = get_byte() | (get_byte() << 8)
                match_pos = len(out) - 1 - (value >> 2)
                copy_match(match_pos, t + 2)

            elif t >= 16:
                match_pos = len(out) - ((t & 8) << 11)
                t &= 7
                if t == 0:
                    while True:
                        value = get_byte()
                        if value != 0:
                            t += 7 + value
                            break
                        t += 255

                value = get_byte() | (get_byte() << 8)
                match_pos -= value >> 2

                if match_pos == len(out):
                    break

                match_pos -= 0x4000
                copy_match(match_pos, t + 2)

            else:
                match_pos = len(out) - 1 - (t >> 2) - (get_byte() << 2)
                copy_match(match_pos, 2)

            t = src[ip - 2] & 3
            if t:
                copy_literal(t)
                t = get_byte()
            else:
                t = get_byte()

        if expected_size is not None and len(out) != expected_size:
            raise LZO1XError(f"LZO raw size mismatch: got {len(out)}, expected {expected_size}")

        return bytes(out)


def rebuild_partition(buf: bytes, part: Partition, chunks: list[Chunk], otra_base: int) -> tuple[bytes, list[Chunk]]:
    selected = [chunk for chunk in chunks if part.start <= chunk.flash_off < part.start + part.size]
    out = bytearray([ERASED_BYTE]) * part.size

    for chunk in selected:
        abs_off = otra_base + chunk.file_off
        comp = buf[abs_off : abs_off + chunk.comp_size]
        raw = LZO1XDecoder.decompress(comp, chunk.raw_size)

        dst = chunk.flash_off - part.start
        end = dst + len(raw)
        if end > part.size:
            raise RuntimeError(
                f"chunk overflow: {part.name} flash={hx(chunk.flash_off)} "
                f"raw={hx(len(raw))} partition_size={hx(part.size)}"
            )
        out[dst:end] = raw

    return bytes(out), selected


def detect_image_type(path: Path) -> str:
    data = path.read_bytes()[:0x1000]
    if data.startswith(UBI_MAGIC):
        return "ubi"
    if data.startswith(b"\x31\x18\x10\x06"):
        return "ubifs"
    if data.startswith(b"hsqs"):
        return "squashfs"
    if data.startswith(b"\x45\x3d\xcd\x28"):
        return "cramfs"
    if data.startswith(b"\x1f\x8b"):
        return "gzip"
    if data.startswith(b"\x27\x05\x19\x56"):
        return "uimage"
    if data.startswith(b"\x7fELF"):
        return "elf"
    if data.startswith(b"\xd0\x0d\xfe\xed"):
        return "dtb"
    return "raw"


def volume_output_name(path: Path) -> str:
    stem = path.stem
    marker = "_vol-"
    if marker in stem:
        stem = stem.split(marker, 1)[1]
    return safe_name(stem)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def configure_ubi_reader() -> None:
    ubi_settings.logging_on = False
    ubi_settings.logging_on_verbose = False
    ubi_settings.warn_only_block_read_errors = False
    ubi_settings.ignore_block_header_errors = False
    ubi_settings.uboot_fix = False
    ubi_settings.use_dummy_devices = True
    ubi_settings.use_dummy_socket_file = True


def guess_required_size(path: Path, guesser, label: str) -> int:
    try:
        value = guesser(str(path))
    except SystemExit as exc:
        raise RuntimeError(f"could not determine {label} for {path}") from exc
    if value is None:
        raise RuntimeError(f"could not determine {label} for {path}")
    return value


def extract_ubi_volume_images(ubi_path: Path, out_dir: Path) -> list[Path]:
    configure_ubi_reader()
    block_size = guess_required_size(ubi_path, guess_peb_size, "PEB size")
    start_offset = guess_required_size(ubi_path, guess_start_offset, "UBI start offset")

    volume_root = out_dir / ubi_path.name
    reset_dir(volume_root)
    written: list[Path] = []

    try:
        ufile = ubi_file(str(ubi_path), block_size, start_offset)
        try:
            ubi_obj = ubi(ufile)
            for image in ubi_obj.images:
                for volume_name, volume in image.volumes.items():
                    name = safe_name(str(volume_name))
                    volume_path = volume_root / f"img-{image.image_seq}_vol-{name}.ubifs"
                    with volume_path.open("wb") as f:
                        for block in volume.reader(ubi_obj):
                            f.write(block)
                    written.append(volume_path)
        finally:
            ufile.close()
    except SystemExit as exc:
        raise RuntimeError(f"failed to parse UBI image {ubi_path}") from exc

    return written


def unpack_squashfs(image_path: Path, out_dir: Path) -> bool:
    try:
        reset_dir(out_dir)
        with SquashFsImage.from_file(str(image_path)) as image:
            extract_squashfs_dir(image.root, str(out_dir), force=True, quiet=True)
    except Exception as exc:
        print(f"[warn] SquashFS extraction failed for {image_path.name}: {exc}")
        return False

    print(f"[extract] SquashFS -> {out_dir}")
    return True


def unpack_ubifs(image_path: Path, out_dir: Path) -> bool:
    configure_ubi_reader()
    try:
        reset_dir(out_dir)
        block_size = guess_required_size(image_path, guess_leb_size, "LEB size")
        start_offset = guess_required_size(image_path, guess_start_offset, "UBIFS start offset")
        ufile = ubi_file(str(image_path), block_size, start_offset)
        try:
            ubifs_obj = ubifs(ufile)
            extract_ubifs_files(ubifs_obj, str(out_dir), False)
        finally:
            ufile.close()
    except (Exception, SystemExit) as exc:
        print(f"[warn] UBIFS extraction failed for {image_path.name}: {exc}")
        return False

    print(f"[extract] UBIFS -> {out_dir}")
    return True


def unpack_ubi(ubi_path: Path, out_dir: Path) -> None:
    images_out = out_dir.with_name(out_dir.name + "_images")
    try:
        volume_images = extract_ubi_volume_images(ubi_path, images_out)
    except RuntimeError as exc:
        print(f"[warn] UBI volume image extraction failed for {ubi_path.name}: {exc}")
        return

    print(f"[extract] UBI volumes -> {images_out / ubi_path.name}")
    for image in volume_images:
        kind = detect_image_type(image)
        print(f"[info] volume image: {image} ({kind})")
        volume_dir = out_dir / volume_output_name(image)

        if kind == "squashfs":
            unpack_squashfs(image, volume_dir)
        elif kind == "ubifs":
            unpack_ubifs(image, volume_dir)
        else:
            print(f"[skip] unsupported volume filesystem: {kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract OTRA firmware partitions.")
    parser.add_argument("image", type=Path, help="firmware image")
    parser.add_argument("-o", "--out", type=Path, default=Path("extracted_otra"), help="output directory")
    parser.add_argument("--no-unpack", action="store_true", help="do not unpack UBI or filesystem volumes")
    parser.add_argument("--no-ubi-unpack", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--write-all-bin", action="store_true", help="also write .bin copies for UBI partitions")
    args = parser.parse_args()

    buf = args.image.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)

    otra_base = find_otra_base(buf)
    part_table = find_partition_table(buf, search_from=otra_base)
    parts = parse_partitions_at(buf, part_table)
    chunk_table = part_table + len(parts) * PART_REC_SIZE
    chunks = parse_chunks(buf, chunk_table, otra_base)

    print(f"OTRA_BASE        = {hx(otra_base)}")
    print(f"PART_TABLE       = {hx(part_table)}")
    print(f"CHUNK_TABLE      = {hx(chunk_table)}")
    print(f"PARTITIONS       = {len(parts)}")
    print(f"CHUNKS           = {len(chunks)}")
    print()

    rebuilt = 0
    should_unpack = not (args.no_unpack or args.no_ubi_unpack)

    for part in parts:
        image, used = rebuild_partition(buf, part, chunks, otra_base)
        if not used:
            print(f"[skip] {part.name:<10} no chunk in update image")
            continue

        name = safe_name(part.name)
        is_ubi = image.startswith(UBI_MAGIC)
        ext = ".ubi" if is_ubi else ".bin"
        out_path = args.out / f"{name}{ext}"
        out_path.write_bytes(image)
        rebuilt += 1

        print(
            f"[ok]   {part.name:<10} mtd_start={hx(part.start)} size={hx(part.size)} "
            f"chunks={len(used):>2} -> {out_path}"
        )

        if is_ubi:
            if args.write_all_bin:
                (args.out / f"{name}.bin").write_bytes(image)
            if should_unpack:
                unpack_ubi(out_path, args.out / f"{name}_files")

    print()
    print(f"done: rebuilt {rebuilt} partition image(s) under {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        raise SystemExit(130)
