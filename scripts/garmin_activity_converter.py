#!/usr/bin/env python3
"""Patch a FIT activity with Garmin creator metadata and rewrite checksums."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GARMIN_MANUFACTURER = 1
EDGE_1030_PLUS_PRODUCT = 3570
EDGE_1030_PLUS_NAME = "Edge 1030 Plus"

FILE_ID_MESG = 0
DEVICE_INFO_MESG = 23
FILE_ID_MANUFACTURER = 1
FILE_ID_PRODUCT = 2
DEVICE_INFO_DEVICE_INDEX = 0
DEVICE_INFO_MANUFACTURER = 2
DEVICE_INFO_PRODUCT = 4

CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
]


class FitConvertError(Exception):
    pass


def crc16(data: bytes | bytearray, start: int = 0, end: int | None = None, seed: int = 0) -> int:
    crc = seed
    if end is None:
        end = len(data)
    for index in range(start, end):
        value = data[index]
        tmp = CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ CRC_TABLE[value & 0xF]
        tmp = CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ CRC_TABLE[(value >> 4) & 0xF]
    return crc


def read_u16(data: bytes, offset: int, little_endian: bool) -> int:
    if little_endian:
        return data[offset] | (data[offset + 1] << 8)
    return (data[offset] << 8) | data[offset + 1]


def write_u16(data: bytearray, offset: int, value: int, little_endian: bool) -> None:
    if little_endian:
        data[offset] = value & 0xFF
        data[offset + 1] = (value >> 8) & 0xFF
    else:
        data[offset] = (value >> 8) & 0xFF
        data[offset + 1] = value & 0xFF


def read_u32(data: bytes, offset: int, little_endian: bool) -> int:
    if little_endian:
        return (
            data[offset]
            | (data[offset + 1] << 8)
            | (data[offset + 2] << 16)
            | (data[offset + 3] << 24)
        )
    return (
        (data[offset] << 24)
        | (data[offset + 1] << 16)
        | (data[offset + 2] << 8)
        | data[offset + 3]
    )


def parse_header(data: bytes) -> tuple[int, int]:
    if len(data) < 14:
        raise FitConvertError("File is too small to be a FIT activity.")
    header_size = data[0]
    if header_size not in (12, 14):
        raise FitConvertError("Unsupported FIT header size.")
    if data[8:12] != b".FIT":
        raise FitConvertError("This is not a FIT file.")
    data_size = read_u32(data, 4, True)
    data_end = header_size + data_size
    if data_end + 2 > len(data):
        raise FitConvertError("The FIT file is truncated.")
    return header_size, data_end


def output_name(path: Path, product_name: str) -> Path:
    stem = path.stem
    if "_Garmin_" in stem:
        stem = stem.split("_Garmin_")[0]
    slug = product_name.replace(" ", "_")
    return path.with_name(f"{stem}_Garmin_{slug}.fit")


def patch_data_message(
    data: bytearray,
    start: int,
    definition: dict,
    manufacturer: int,
    product: int,
    patches: list[str],
    device_info_seen: list[int],
) -> None:
    cursor = start
    device_index = None
    offsets: dict[int, tuple[int, dict]] = {}
    for field in definition["fields"]:
        offsets[field["num"]] = (cursor, field)
        if (
            definition["global"] == DEVICE_INFO_MESG
            and field["num"] == DEVICE_INFO_DEVICE_INDEX
            and field["size"] >= 1
        ):
            device_index = data[cursor]
        cursor += field["size"]

    def apply(field_num: int, value: int, label: str) -> None:
        located = offsets.get(field_num)
        if not located:
            return
        offset, field = located
        if field["size"] < 2:
            return
        write_u16(data, offset, value, definition["little_endian"])
        patches.append(label)

    if definition["global"] == FILE_ID_MESG:
        apply(FILE_ID_MANUFACTURER, manufacturer, "file_id.manufacturer")
        apply(FILE_ID_PRODUCT, product, "file_id.product")

    if definition["global"] == DEVICE_INFO_MESG:
        device_info_seen[0] += 1
        is_creator = device_index == 0 or (device_index is None and device_info_seen[0] == 1)
        if is_creator:
            apply(DEVICE_INFO_MANUFACTURER, manufacturer, "device_info.manufacturer")
            apply(DEVICE_INFO_PRODUCT, product, "device_info.product")


def patch_records(
    data: bytearray,
    header_size: int,
    data_end: int,
    manufacturer: int,
    product: int,
) -> tuple[list[str], list[str]]:
    patches: list[str] = []
    warnings: list[str] = []
    locals_: dict[int, dict] = {}
    device_info_seen = [0]
    cursor = header_size

    while cursor < data_end:
        header = data[cursor]
        cursor += 1

        if header & 0x80:
            definition = locals_.get((header >> 5) & 0x03)
            if definition is None:
                raise FitConvertError("Compressed timestamp record appeared before its definition.")
            patch_data_message(data, cursor, definition, manufacturer, product, patches, device_info_seen)
            cursor += sum(field["size"] for field in definition["fields"]) + definition["developer_size"]
            continue

        if header & 0x40:
            local_type = header & 0x0F
            has_developer = bool(header & 0x20)
            cursor += 1
            architecture = data[cursor]
            cursor += 1
            little_endian = architecture == 0
            global_num = read_u16(data, cursor, little_endian)
            cursor += 2
            field_count = data[cursor]
            cursor += 1
            fields = []
            for _ in range(field_count):
                fields.append({"num": data[cursor], "size": data[cursor + 1], "base_type": data[cursor + 2]})
                cursor += 3
            developer_size = 0
            if has_developer:
                developer_count = data[cursor]
                cursor += 1
                for _ in range(developer_count):
                    developer_size += data[cursor + 1]
                    cursor += 3
            locals_[local_type] = {
                "global": global_num,
                "little_endian": little_endian,
                "fields": fields,
                "developer_size": developer_size,
            }
            continue

        definition = locals_.get(header & 0x0F)
        if definition is None:
            raise FitConvertError("Data record appeared before its definition.")
        patch_data_message(data, cursor, definition, manufacturer, product, patches, device_info_seen)
        cursor += sum(field["size"] for field in definition["fields"]) + definition["developer_size"]

    if cursor != data_end:
        warnings.append("Record walk did not land exactly on the data end.")
    if not any(patch.startswith("file_id.") for patch in patches):
        warnings.append("No file_id manufacturer/product fields were found to patch.")
    return list(dict.fromkeys(patches)), warnings


def convert_fit(
    source: Path,
    destination: Path,
    manufacturer: int = GARMIN_MANUFACTURER,
    product: int = EDGE_1030_PLUS_PRODUCT,
    product_name: str = EDGE_1030_PLUS_NAME,
) -> dict:
    raw = bytearray(source.read_bytes())
    header_size, data_end = parse_header(raw)
    patches, warnings = patch_records(raw, header_size, data_end, manufacturer, product)
    write_u16(raw, len(raw) - 2, crc16(raw, 0, len(raw) - 2), True)
    destination.write_bytes(raw)
    warnings.append(
        "Output is a structurally valid FIT file with Garmin metadata, not an original Garmin recording. "
        "Garmin decides Training Readiness, Training Effect, Exercise Load and VO2 max after upload."
    )
    return {
        "input": str(source),
        "output": str(destination),
        "manufacturer": manufacturer,
        "product": product,
        "product_name": product_name,
        "patches": patches,
        "warnings": warnings,
        "bytes": len(raw),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Patch a FIT activity with Garmin creator metadata (default Edge 1030 Plus)."
    )
    parser.add_argument("input", type=Path, help="Source .fit file")
    parser.add_argument("-o", "--output", type=Path, help="Destination .fit file")
    parser.add_argument("--manufacturer", type=int, default=GARMIN_MANUFACTURER)
    parser.add_argument("--product", type=int, default=EDGE_1030_PLUS_PRODUCT)
    parser.add_argument("--product-name", default=EDGE_1030_PLUS_NAME)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    args = parser.parse_args(argv)

    source = args.input.expanduser().resolve()
    if not source.is_file():
        parser.error(f"Input file not found: {source}")
    destination = (
        args.output.expanduser().resolve()
        if args.output
        else output_name(source, args.product_name)
    )
    if destination == source:
        parser.error("Refusing to overwrite the source file. Pass -o with a different path.")

    try:
        report = convert_fit(source, destination, args.manufacturer, args.product, args.product_name)
    except FitConvertError as error:
        print(error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Wrote {destination}")
        print(f"Identity: Garmin manufacturer {args.manufacturer}, {args.product_name} product {args.product}")
        print("Patched: " + (", ".join(report["patches"]) or "nothing"))
        for warning in report["warnings"]:
            print(f"Note: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
