#!/usr/bin/env python3
"""Generate label text/SVG assets from fleet summary data."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import shlex
from typing import Any

if __package__ in (None, ""):
    from fleet_data import (
        LABEL_FIELDNAMES,
        build_label_rows,
        filter_rows_by_serial,
        load_device_rows,
        write_csv_rows,
    )
    from tool_paths import DEFAULT_DEVICES_CSV_PATH, DEFAULT_LABEL_OUTPUT_DIR
else:
    from .fleet_data import (
        LABEL_FIELDNAMES,
        build_label_rows,
        filter_rows_by_serial,
        load_device_rows,
        write_csv_rows,
    )
    from .tool_paths import DEFAULT_DEVICES_CSV_PATH, DEFAULT_LABEL_OUTPUT_DIR


SEGNO_PIP_SPEC = "segno==1.6.6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate label text/SVG assets from Matter fleet summary data.",
    )
    parser.add_argument(
        "--devices-csv",
        default=str(DEFAULT_DEVICES_CSV_PATH),
        help="Fleet summary CSV produced by generate_factory_data.py.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_LABEL_OUTPUT_DIR),
        help="Directory where label assets will be written.",
    )
    parser.add_argument(
        "--label-csv",
        help="Optional CSV export path. Omit to keep devices.csv as only canonical dataset.",
    )
    parser.add_argument(
        "--serial",
        action="append",
        help="Limit output to one or more serial numbers. Repeat flag to include multiple devices.",
    )
    parser.add_argument(
        "--render-qr-svg",
        action="store_true",
        help="Also render QR codes as SVG files. Auto-installs 'segno' when missing.",
    )
    return parser.parse_args()


def write_text_label(output_dir: pathlib.Path, label_row: dict[str, str]) -> pathlib.Path:
    output_path = output_dir / f"{label_row['serial_num']}.txt"
    content = "\n".join(
        [
            f"Product: {label_row['label_title']}",
            f"Vendor: {label_row['label_subtitle']}",
            f"Serial: {label_row['serial_num']}",
            f"Manual Code: {label_row['manualcode']}",
            f"QR Payload: {label_row['qrcode']}",
            f"VID: {label_row['vendor_id']}",
            f"PID: {label_row['product_id']}",
            f"Discriminator: {label_row['discriminator']}",
            f"Passcode: {label_row['passcode']}",
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def load_segno_module() -> Any | None:
    try:
        import segno  # type: ignore
    except Exception:
        return None
    return segno


def install_segno_dependency(python_executable: str) -> None:
    print(
        "Missing QR SVG dep in tool Python env. "
        f"Installing '{SEGNO_PIP_SPEC}' ..."
    )
    subprocess.run(
        [
            python_executable,
            "-m",
            "pip",
            "install",
            SEGNO_PIP_SPEC,
        ],
        check=True,
    )


def verify_segno_dependency(python_executable: str) -> Any:
    segno_module = load_segno_module()
    if segno_module is not None:
        return segno_module

    install_command = f"{shlex.quote(python_executable)} -m pip install {SEGNO_PIP_SPEC}"
    try:
        install_segno_dependency(python_executable)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "\n".join(
                [
                    "Failed to auto-install QR SVG dependency.",
                    f"Python env: {python_executable}",
                    f"Install command: {install_command}",
                    f"pip exit code: {exc.returncode}",
                ]
            )
        ) from exc

    segno_module = load_segno_module()
    if segno_module is not None:
        return segno_module

    raise SystemExit(
        "\n".join(
            [
                "QR SVG dependency still unavailable after auto-install.",
                f"Python env: {python_executable}",
                f"Install command: {install_command}",
            ]
        )
    )


def render_qr_svg(
    output_dir: pathlib.Path,
    label_row: dict[str, str],
    segno_module: Any,
) -> pathlib.Path:

    output_path = output_dir / f"{label_row['serial_num']}.svg"
    qr = segno_module.make(label_row["qrcode"])
    qr.save(output_path, kind="svg", scale=8, border=2)
    return output_path


def main() -> int:
    args = parse_args()
    devices_csv = pathlib.Path(args.devices_csv).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()

    if not devices_csv.is_file():
        raise SystemExit(f"Devices CSV not found: {devices_csv}")

    rows = load_device_rows(devices_csv)
    selected_rows = filter_rows_by_serial(rows, args.serial)
    label_rows = build_label_rows(selected_rows, include_passcode=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    label_csv_path = None
    if args.label_csv:
        label_csv_path = write_csv_rows(
            pathlib.Path(args.label_csv).resolve(),
            LABEL_FIELDNAMES,
            label_rows,
        )

    for label_row in label_rows:
        write_text_label(output_dir, label_row)

    if args.render_qr_svg:
        segno_module = verify_segno_dependency(sys.executable)
        for label_row in label_rows:
            render_qr_svg(output_dir, label_row, segno_module)

    print(f"Wrote {len(label_rows)} per-device text labels to {output_dir}")
    if label_csv_path is not None:
        print(f"Wrote label CSV to {label_csv_path}")
    if args.render_qr_svg:
        print("Wrote QR SVG files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
