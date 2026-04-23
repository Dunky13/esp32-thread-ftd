#!/usr/bin/env python3
"""Generate a CSV manifest for per-device Matter commissioning data."""

from __future__ import annotations

import argparse
import pathlib
import secrets
from datetime import date

from fleet_data import load_manifest_rows, write_manifest
from tool_paths import DEFAULT_MANIFEST_PATH


INVALID_PASSCODES = {
    0,
    11111111,
    22222222,
    33333333,
    44444444,
    55555555,
    66666666,
    77777777,
    88888888,
    99999999,
    12345678,
    87654321,
}

MIN_PASSCODE = 1
MAX_PASSCODE = 99999998
MAX_DISCRIMINATOR = 4095
DEFAULT_VENDOR_ID = "0xFFF1"
DEFAULT_PRODUCT_ID = "0x8000"
DEFAULT_HW_VER = "1"
DEFAULT_HW_VER_STR = "1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a CSV manifest for Matter factory-data generation.",
    )
    parser.add_argument("--count", type=int, required=True, help="Number of devices.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to write the generated CSV manifest.",
    )
    parser.add_argument(
        "--serial-prefix",
        default="LFTD",
        help="Prefix used in generated serial numbers.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="Starting numeric suffix for serial numbers.",
    )
    parser.add_argument(
        "--serial-width",
        type=int,
        default=4,
        help="Zero-padding width for the serial suffix.",
    )
    parser.add_argument(
        "--discriminator-start",
        type=int,
        default=3840,
        help="First discriminator to use. Rows increment from here.",
    )
    parser.add_argument(
        "--vendor-id",
        default=DEFAULT_VENDOR_ID,
        help="Matter vendor ID stored in every manifest row.",
    )
    parser.add_argument(
        "--product-id",
        default=DEFAULT_PRODUCT_ID,
        help="Matter product ID stored in every manifest row.",
    )
    parser.add_argument(
        "--hw-ver",
        default=DEFAULT_HW_VER,
        help="Hardware version stored in every manifest row.",
    )
    parser.add_argument(
        "--hw-ver-str",
        default=DEFAULT_HW_VER_STR,
        help="Hardware version string stored in every manifest row.",
    )
    parser.add_argument(
        "--mfg-date",
        default=date.today().isoformat(),
        help="Manufacturing date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    if args.start_index < 1:
        raise SystemExit("--start-index must be at least 1")
    if args.serial_width < 1:
        raise SystemExit("--serial-width must be at least 1")
    if args.discriminator_start < 0 or args.discriminator_start > MAX_DISCRIMINATOR:
        raise SystemExit("--discriminator-start must be between 0 and 4095")
    max_discriminator = args.discriminator_start + args.count - 1
    if max_discriminator > MAX_DISCRIMINATOR:
        raise SystemExit("Requested count overruns discriminator range 0-4095")
    if not args.serial_prefix.strip():
        raise SystemExit("--serial-prefix must not be empty")
    if any(character in args.serial_prefix for character in (",", "\n", "\r")):
        raise SystemExit("--serial-prefix must not contain commas or newlines")

    try:
        vendor_id = int(args.vendor_id, 0)
        product_id = int(args.product_id, 0)
        hw_ver = int(args.hw_ver, 0)
        date.fromisoformat(args.mfg_date)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if not 0 <= vendor_id <= 0xFFFF:
        raise SystemExit("--vendor-id must be between 0 and 0xFFFF")
    if not 0 <= product_id <= 0xFFFF:
        raise SystemExit("--product-id must be between 0 and 0xFFFF")
    if hw_ver < 0:
        raise SystemExit("--hw-ver must be non-negative")


def generate_passcode() -> str:
    while True:
        passcode = secrets.randbelow(MAX_PASSCODE) + MIN_PASSCODE
        if passcode not in INVALID_PASSCODES:
            return str(passcode)


def generate_rd_id_uid() -> str:
    return secrets.token_hex(16).upper()


def build_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    rows = []
    for offset in range(args.count):
        serial_suffix = str(args.start_index + offset).zfill(args.serial_width)
        rows.append(
            {
                "serial_num": f"{args.serial_prefix}-{serial_suffix}",
                "discriminator": str(args.discriminator_start + offset),
                "passcode": generate_passcode(),
                "vendor_id": args.vendor_id,
                "product_id": args.product_id,
                "hw_ver": args.hw_ver,
                "hw_ver_str": args.hw_ver_str,
                "mfg_date": args.mfg_date,
                "rd_id_uid": generate_rd_id_uid(),
            }
        )
    return rows


def reuse_existing_manifest(output_path: pathlib.Path, requested_count: int) -> bool:
    if not output_path.is_file():
        return False

    existing_rows = load_manifest_rows(output_path)
    message = f"Manifest exists at {output_path}; reusing {len(existing_rows)} rows"
    if len(existing_rows) != requested_count:
        message += f" (requested --count {requested_count} ignored)"
    print(message)
    return True


def main() -> int:
    args = parse_args()
    validate_args(args)
    output_path = pathlib.Path(args.output).resolve()
    if reuse_existing_manifest(output_path, args.count):
        return 0
    rows = build_rows(args)
    write_manifest(output_path, rows)
    print(f"Wrote {len(rows)} manifest rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
