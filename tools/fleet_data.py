from __future__ import annotations

import csv
import pathlib
from collections.abc import Iterable, Sequence


MANIFEST_REQUIRED_COLUMNS = (
    "serial_num",
    "discriminator",
    "passcode",
    "vendor_id",
    "product_id",
)

MANIFEST_FIELDNAMES = [
    "serial_num",
    "discriminator",
    "passcode",
    "vendor_id",
    "product_id",
    "hw_ver",
    "hw_ver_str",
    "mfg_date",
    "rd_id_uid",
]

DEVICE_SUMMARY_FIELDNAMES = [
    "serial_num",
    "discriminator",
    "passcode",
    "vendor_id",
    "product_id",
    "vendor_name",
    "product_name",
    "factory_bin",
    "factory_csv",
    "onboarding_csv",
    "qrcode",
    "manualcode",
]

DEVICE_REQUIRED_COLUMNS = tuple(DEVICE_SUMMARY_FIELDNAMES)

ONBOARDING_REQUIRED_COLUMNS = (
    "qrcode",
    "manualcode",
)

LABEL_FIELDNAMES = [
    "serial_num",
    "label_title",
    "label_subtitle",
    "qrcode",
    "manualcode",
    "vendor_id",
    "product_id",
    "passcode",
    "discriminator",
]


def write_csv_rows(
    output_path: pathlib.Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, str]],
) -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path


def write_manifest(output_path: pathlib.Path, rows: list[dict[str, str]]) -> pathlib.Path:
    return write_csv_rows(output_path, MANIFEST_FIELDNAMES, rows)


def ensure_required_columns(
    columns: Sequence[str],
    required_columns: Sequence[str],
    *,
    source_name: str,
) -> None:
    missing = [column for column in required_columns if column not in columns]
    if missing:
        raise SystemExit(f"{source_name} missing required columns: {', '.join(missing)}")


def ensure_manifest_columns(columns: list[str]) -> None:
    ensure_required_columns(
        columns,
        MANIFEST_REQUIRED_COLUMNS,
        source_name="Manifest",
    )


def ensure_unique_serial_num(
    serial_num: str,
    *,
    row_index: int,
    source_name: str,
    seen_rows: dict[str, int],
) -> None:
    first_row = seen_rows.get(serial_num)
    if first_row is not None:
        raise SystemExit(
            f"{source_name} has duplicate serial_num '{serial_num}' on rows "
            f"{first_row} and {row_index}"
        )
    seen_rows[serial_num] = row_index


def load_manifest_rows(manifest_path: pathlib.Path) -> list[dict[str, str]]:
    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames is None:
            raise SystemExit("Manifest has no header row")
        ensure_manifest_columns(reader.fieldnames)

        rows = []
        seen_serial_rows: dict[str, int] = {}
        for index, row in enumerate(reader, start=2):
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            if not any(cleaned.values()):
                continue

            missing = [
                column for column in MANIFEST_REQUIRED_COLUMNS if not cleaned.get(column)
            ]
            if missing:
                raise SystemExit(
                    f"Manifest row {index} missing required values: {', '.join(missing)}"
                )
            ensure_unique_serial_num(
                cleaned["serial_num"],
                row_index=index,
                source_name="Manifest",
                seen_rows=seen_serial_rows,
            )
            rows.append(cleaned)

    if not rows:
        raise SystemExit("Manifest has no device rows")
    return rows


def load_device_rows(devices_csv: pathlib.Path) -> list[dict[str, str]]:
    with devices_csv.open(newline="", encoding="utf-8") as devices_file:
        reader = csv.DictReader(devices_file)
        if reader.fieldnames is None:
            raise SystemExit("Devices CSV has no header row")
        ensure_required_columns(
            reader.fieldnames,
            DEVICE_REQUIRED_COLUMNS,
            source_name="Devices CSV",
        )

        rows = []
        seen_serial_rows: dict[str, int] = {}
        for index, row in enumerate(reader, start=2):
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            if not any(cleaned.values()):
                continue

            missing = [column for column in DEVICE_REQUIRED_COLUMNS if not cleaned.get(column)]
            if missing:
                raise SystemExit(
                    f"Devices CSV row {index} missing required values: {', '.join(missing)}"
                )
            ensure_unique_serial_num(
                cleaned["serial_num"],
                row_index=index,
                source_name="Devices CSV",
                seen_rows=seen_serial_rows,
            )
            rows.append(cleaned)

    if not rows:
        raise SystemExit(f"No device rows found in {devices_csv}")
    return rows


def filter_rows_by_serial(
    rows: list[dict[str, str]],
    serials: Iterable[str] | None,
    source_name: str = "devices CSV",
) -> list[dict[str, str]]:
    if not serials:
        return rows

    wanted = list(serials)
    filtered = [row for row in rows if row["serial_num"] in wanted]
    missing = [serial for serial in wanted if not any(row["serial_num"] == serial for row in filtered)]
    if missing:
        raise SystemExit(f"Serials not found in {source_name}: {', '.join(missing)}")
    return filtered


def build_label_rows(
    rows: list[dict[str, str]],
    *,
    include_passcode: bool = True,
) -> list[dict[str, str]]:
    label_rows = []
    for row in rows:
        label_row = {
            "serial_num": row["serial_num"],
            "label_title": row["product_name"],
            "label_subtitle": row["vendor_name"],
            "qrcode": row["qrcode"],
            "manualcode": row["manualcode"],
            "vendor_id": row["vendor_id"],
            "product_id": row["product_id"],
            "discriminator": row["discriminator"],
        }
        if include_passcode:
            label_row["passcode"] = row["passcode"]
        label_rows.append(label_row)
    return label_rows


def write_devices_summary(
    output_dir: pathlib.Path,
    rows: list[dict[str, str]],
) -> pathlib.Path:
    return write_csv_rows(output_dir / "devices.csv", DEVICE_SUMMARY_FIELDNAMES, rows)


def read_onboarding_codes(path: pathlib.Path) -> tuple[str, str]:
    with path.open(newline="", encoding="utf-8") as onboarding_file:
        reader = csv.DictReader(onboarding_file)
        if reader.fieldnames is None:
            raise SystemExit(f"Onboarding CSV has no header row: {path}")
        ensure_required_columns(
            reader.fieldnames,
            ONBOARDING_REQUIRED_COLUMNS,
            source_name="Onboarding CSV",
        )
        rows = list(reader)

    if not rows:
        raise SystemExit(f"No onboarding rows found in {path}")

    row = rows[0]
    missing = [column for column in ONBOARDING_REQUIRED_COLUMNS if not (row.get(column) or "").strip()]
    if missing:
        raise SystemExit(
            f"Onboarding CSV row 2 missing required values: {', '.join(missing)}"
        )

    return row["qrcode"].strip(), row["manualcode"].strip()
