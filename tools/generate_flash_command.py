#!/usr/bin/env python3
"""Generate an esptool.py command for one device from the fleet summary."""

from __future__ import annotations

import argparse
import glob
import json
import pathlib
import shlex
import sys

from fleet_data import load_device_rows
from tool_paths import DEFAULT_BUILD_DIR, DEFAULT_DEVICES_CSV_PATH, DEFAULT_PARTITIONS_CSV


FLASH_METADATA_REQUIRED_KEYS = (
    "write_flash_args",
    "extra_esptool_args",
    "flash_files",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the esptool.py command for one device.",
    )
    parser.add_argument(
        "--devices-csv",
        default=str(DEFAULT_DEVICES_CSV_PATH),
        help="Fleet summary CSV produced by generate_factory_data.py.",
    )
    parser.add_argument(
        "--serial",
        help="Serial number to flash, for example LFTD-0001. Omit to select interactively.",
    )
    parser.add_argument(
        "--serial-index",
        type=int,
        help="1-based serial row index from devices CSV.",
    )
    parser.add_argument(
        "--port",
        help="Serial port, for example /dev/ttyACM0. Omit to select interactively.",
    )
    parser.add_argument(
        "--port-index",
        type=int,
        help="1-based serial port index from detected ports.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Print serial and port choices, then exit.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Fail instead of showing interactive selectors.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(DEFAULT_BUILD_DIR),
        help="ESP-IDF build directory containing flasher_args.json.",
    )
    parser.add_argument(
        "--partitions-csv",
        default=str(DEFAULT_PARTITIONS_CSV),
        help="Partition CSV used to locate the fctry partition offset.",
    )
    parser.add_argument(
        "--baud",
        default="921600",
        help="esptool baud rate.",
    )
    return parser.parse_args()


def read_flasher_args(build_dir: pathlib.Path) -> dict[str, object]:
    flasher_args_path = build_dir / "flasher_args.json"
    if not flasher_args_path.is_file():
        raise SystemExit(f"Missing flasher_args.json: {flasher_args_path}")
    with flasher_args_path.open(encoding="utf-8") as flasher_args_file:
        metadata = json.load(flasher_args_file)

    if not isinstance(metadata, dict):
        raise SystemExit(f"Invalid flasher_args.json format: {flasher_args_path}")

    missing = [key for key in FLASH_METADATA_REQUIRED_KEYS if key not in metadata]
    if missing:
        raise SystemExit(
            f"flasher_args.json missing required keys: {', '.join(missing)}"
        )

    extra_args = metadata["extra_esptool_args"]
    if not isinstance(extra_args, dict):
        raise SystemExit("flasher_args.json field 'extra_esptool_args' must be an object")
    for key in ("chip", "before", "after"):
        if not extra_args.get(key):
            raise SystemExit(f"flasher_args.json missing extra_esptool_args.{key}")

    flash_files = metadata["flash_files"]
    if not isinstance(flash_files, dict) or not flash_files:
        raise SystemExit("flasher_args.json field 'flash_files' must be a non-empty object")

    flash_args = metadata["write_flash_args"]
    if not isinstance(flash_args, list):
        raise SystemExit("flasher_args.json field 'write_flash_args' must be a list")

    return metadata


def parse_factory_offset(partitions_csv: pathlib.Path) -> str:
    with partitions_csv.open(encoding="utf-8") as partitions_file:
        for line_number, raw_line in enumerate(partitions_file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 4:
                raise SystemExit(
                    f"Malformed partitions CSV line {line_number}: {line}"
                )
            if parts[0] == "fctry":
                offset = parts[3]
                if not offset:
                    raise SystemExit("fctry partition offset is empty in partitions.csv")
                return offset
    raise SystemExit(f"Partition 'fctry' not found in {partitions_csv}")


def detect_serial_ports() -> list[str]:
    def port_rank(port: str) -> tuple[int, str]:
        normalized = port.lower()
        primary_tokens = ("usb", "acm", "serial", "uart")
        if any(token in normalized for token in primary_tokens):
            return (0, normalized)
        if "debug-console" in normalized:
            return (1, normalized)
        return (2, normalized)

    try:
        from serial.tools import list_ports  # type: ignore

        ports = sorted((port.device for port in list_ports.comports()), key=port_rank)
        if ports:
            return ports
    except Exception:
        pass

    patterns_by_platform = {
        "darwin": ["/dev/cu.usb*", "/dev/tty.usb*", "/dev/cu.*", "/dev/tty.*"],
        "linux": ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/ttyS*"],
        "win32": [],
    }
    patterns = patterns_by_platform.get(sys.platform, ["/dev/tty*"])
    ports = sorted({path for pattern in patterns for path in glob.glob(pattern)}, key=port_rank)
    return ports


def prompt_choice(title: str, values: list[str]) -> str:
    print(title)
    for index, value in enumerate(values, start=1):
        print(f"  {index}. {value}")

    while True:
        try:
            selection = input("Select number: ").strip()
        except EOFError as exc:
            raise SystemExit("Interactive selection unavailable. Pass --no-prompt or explicit flags.") from exc
        except KeyboardInterrupt as exc:
            raise SystemExit("Selection cancelled.") from exc
        if selection.isdigit():
            number = int(selection)
            if 1 <= number <= len(values):
                return values[number - 1]
        print(f"Enter a number between 1 and {len(values)}.")


def resolve_serial(
    rows: list[dict[str, str]],
    serial: str | None,
    serial_index: int | None,
    no_prompt: bool,
) -> dict[str, str]:
    serials = [row["serial_num"] for row in rows]
    if serial is not None:
        for row in rows:
            if row["serial_num"] == serial:
                return row
        raise SystemExit(f"Serial not found in devices CSV: {serial}")
    if serial_index is not None:
        if not 1 <= serial_index <= len(rows):
            raise SystemExit(f"--serial-index must be between 1 and {len(rows)}")
        return rows[serial_index - 1]
    if no_prompt:
        raise SystemExit("Serial not provided. Use --serial, --serial-index, or allow prompting.")

    selected_serial = prompt_choice("Available serials:", serials)
    for row in rows:
        if row["serial_num"] == selected_serial:
            return row
    raise SystemExit(f"Serial not found in devices CSV: {selected_serial}")


def resolve_port(port: str | None, port_index: int | None, no_prompt: bool) -> str:
    ports = detect_serial_ports()
    if port is not None:
        return port
    if port_index is not None:
        if not ports:
            raise SystemExit("No serial ports detected.")
        if not 1 <= port_index <= len(ports):
            raise SystemExit(f"--port-index must be between 1 and {len(ports)}")
        return ports[port_index - 1]
    if no_prompt:
        raise SystemExit("Port not provided. Use --port, --port-index, or allow prompting.")
    if not ports:
        raise SystemExit("No serial ports detected.")
    return prompt_choice("Available serial ports:", ports)


def print_choices(rows: list[dict[str, str]]) -> None:
    print("Available serials:")
    for index, row in enumerate(rows, start=1):
        print(f"  {index}. {row['serial_num']}")

    ports = detect_serial_ports()
    print("Available serial ports:")
    if ports:
        for index, port in enumerate(ports, start=1):
            print(f"  {index}. {port}")
    else:
        print("  none detected")


def build_flash_command(
    build_dir: pathlib.Path,
    flash_metadata: dict[str, object],
    port: str,
    baud: str,
    factory_offset: str,
    factory_bin: pathlib.Path,
) -> list[str]:
    flash_args = flash_metadata["write_flash_args"]
    extra_args = flash_metadata["extra_esptool_args"]
    flash_files = flash_metadata["flash_files"]
    if not isinstance(flash_args, list) or not isinstance(extra_args, dict) or not isinstance(flash_files, dict):
        raise SystemExit("Invalid flasher metadata structure")

    command = [
        "esptool.py",
        "--chip",
        extra_args["chip"],
        "--port",
        port,
        "--baud",
        baud,
        "--before",
        extra_args["before"],
        "--after",
        extra_args["after"],
        "write_flash",
        *flash_args,
    ]

    for offset, relative_path in flash_files.items():
        if not isinstance(offset, str) or not isinstance(relative_path, str):
            raise SystemExit("Invalid flasher_args.json flash_files entry")
        command.extend([offset, str((build_dir / relative_path).resolve())])

    command.extend([factory_offset, str(factory_bin.resolve())])
    return command


def validate_build_files(build_dir: pathlib.Path, flash_metadata: dict[str, object]) -> None:
    flash_files = flash_metadata["flash_files"]
    if not isinstance(flash_files, dict):
        raise SystemExit("Invalid flasher metadata structure")
    missing = []
    for relative_path in flash_files.values():
        if not isinstance(relative_path, str):
            raise SystemExit("Invalid flasher_args.json flash_files entry")
        file_path = build_dir / relative_path
        if not file_path.is_file():
            missing.append(str(file_path))
    if missing:
        raise SystemExit(
            "Build artifacts missing:\n" + "\n".join(missing)
        )


def main() -> int:
    args = parse_args()
    devices_csv = pathlib.Path(args.devices_csv).resolve()
    build_dir = pathlib.Path(args.build_dir).resolve()
    partitions_csv = pathlib.Path(args.partitions_csv).resolve()

    if not devices_csv.is_file():
        raise SystemExit(f"Devices CSV not found: {devices_csv}")
    if not partitions_csv.is_file():
        raise SystemExit(f"Partitions CSV not found: {partitions_csv}")

    rows = load_device_rows(devices_csv)
    if args.list_only:
        print_choices(rows)
        return 0

    device = resolve_serial(rows, args.serial, args.serial_index, args.no_prompt)
    port = resolve_port(args.port, args.port_index, args.no_prompt)
    factory_bin = pathlib.Path(device["factory_bin"]).resolve()
    if not factory_bin.is_file():
        raise SystemExit(f"Factory bin not found: {factory_bin}")

    flash_metadata = read_flasher_args(build_dir)
    validate_build_files(build_dir, flash_metadata)
    factory_offset = parse_factory_offset(partitions_csv)
    command = build_flash_command(
        build_dir=build_dir,
        flash_metadata=flash_metadata,
        port=port,
        baud=args.baud,
        factory_offset=factory_offset,
        factory_bin=factory_bin,
    )

    print(" ".join(shlex.quote(part) for part in command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
