#!/usr/bin/env python3
"""Generate development attestation assets for custom Matter VID/PID pairs."""

from __future__ import annotations

import argparse
import csv
import pathlib
import shlex
import subprocess

import cryptography.hazmat.primitives.serialization
import cryptography.x509

if __package__ in (None, ""):
    from fleet_data import load_manifest_rows
    from generate_factory_data import (
        DEFAULT_LIGHT_DEVICE_TYPE,
        DEFAULT_PRODUCT_NAME,
        DEFAULT_VENDOR_NAME,
        format_manifest_hex_u16,
        generate_test_cd,
        render_chip_cert_missing_message,
        resolve_chip_cert_path,
    )
    from tool_paths import CHIP_ROOT, DEFAULT_CHIP_CERT, DEFAULT_MANIFEST_PATH, DEFAULT_OUTPUT_DIR
else:
    from .fleet_data import load_manifest_rows
    from .generate_factory_data import (
        DEFAULT_LIGHT_DEVICE_TYPE,
        DEFAULT_PRODUCT_NAME,
        DEFAULT_VENDOR_NAME,
        format_manifest_hex_u16,
        generate_test_cd,
        render_chip_cert_missing_message,
        resolve_chip_cert_path,
    )
    from .tool_paths import CHIP_ROOT, DEFAULT_CHIP_CERT, DEFAULT_MANIFEST_PATH, DEFAULT_OUTPUT_DIR


DEFAULT_ATTESTATION_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "attestation"
DEFAULT_ATTESTATION_MANIFEST = DEFAULT_ATTESTATION_OUTPUT_DIR / "manifest_with_attestation.csv"
DEFAULT_VALID_FROM = "2021-06-28 14:23:43"
DEFAULT_LIFETIME = "4294967295"
ATTESTATION_FIELDNAMES = ("dac_cert", "dac_key", "pai_cert", "cd")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate development PAA/PAI/DAC/CD assets for manifest rows.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Input manifest CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_ATTESTATION_OUTPUT_DIR),
        help="Directory where generated attestation assets will be written.",
    )
    parser.add_argument(
        "--manifest-out",
        default=str(DEFAULT_ATTESTATION_MANIFEST),
        help="Path to write a manifest augmented with dac_cert/dac_key/pai_cert/cd columns.",
    )
    parser.add_argument(
        "--chip-cert",
        default=str(DEFAULT_CHIP_CERT),
        help="Path to CHIP host chip-cert tool.",
    )
    parser.add_argument(
        "--vendor-name",
        default=DEFAULT_VENDOR_NAME,
        help="Vendor name used for generated certificate subjects.",
    )
    parser.add_argument(
        "--product-name",
        default=DEFAULT_PRODUCT_NAME,
        help="Product name used for generated certificate subjects.",
    )
    parser.add_argument(
        "--device-type",
        default=DEFAULT_LIGHT_DEVICE_TYPE,
        help="Matter device type used when generating test CD files.",
    )
    parser.add_argument(
        "--valid-from",
        default=DEFAULT_VALID_FROM,
        help="Certificate validity start time passed to chip-cert.",
    )
    parser.add_argument(
        "--lifetime",
        default=DEFAULT_LIFETIME,
        help="Certificate lifetime passed to chip-cert.",
    )
    return parser.parse_args()


def run_checked_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(shlex.quote(part) for part in command)
        raise SystemExit(
            f"Command failed with exit code {exc.returncode}: {rendered}"
        ) from exc


def convert_cert_pem_to_der(source_path: pathlib.Path, destination_path: pathlib.Path) -> pathlib.Path:
    certificate = cryptography.x509.load_pem_x509_certificate(source_path.read_bytes())
    destination_path.write_bytes(
        certificate.public_bytes(cryptography.hazmat.primitives.serialization.Encoding.DER)
    )
    return destination_path


def convert_key_pem_to_der(source_path: pathlib.Path, destination_path: pathlib.Path) -> pathlib.Path:
    private_key = cryptography.hazmat.primitives.serialization.load_pem_private_key(
        source_path.read_bytes(),
        password=None,
    )
    destination_path.write_bytes(
        private_key.private_bytes(
            encoding=cryptography.hazmat.primitives.serialization.Encoding.DER,
            format=cryptography.hazmat.primitives.serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=cryptography.hazmat.primitives.serialization.NoEncryption(),
        )
    )
    return destination_path


def generate_attestation_certificate(
    *,
    chip_cert_path: pathlib.Path,
    cert_type: str,
    subject_cn: str,
    out_key_pem: pathlib.Path,
    out_cert_pem: pathlib.Path,
    valid_from: str,
    lifetime: str,
    vendor_id_hex: str | None = None,
    product_id_hex: str | None = None,
    ca_key_pem: pathlib.Path | None = None,
    ca_cert_pem: pathlib.Path | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    command = [
        str(chip_cert_path),
        "gen-att-cert",
        "--type",
        cert_type,
        "--subject-cn",
        subject_cn,
        "--valid-from",
        valid_from,
        "--lifetime",
        lifetime,
        "--out-key",
        str(out_key_pem),
        "--out",
        str(out_cert_pem),
    ]
    if vendor_id_hex is not None:
        command.extend(["--subject-vid", vendor_id_hex])
    if product_id_hex is not None:
        command.extend(["--subject-pid", product_id_hex])
    if ca_key_pem is not None and ca_cert_pem is not None:
        command.extend(["--ca-key", str(ca_key_pem), "--ca-cert", str(ca_cert_pem)])
    run_checked_command(command)
    return out_key_pem, out_cert_pem


def generate_pair_attestation_bundle(
    *,
    chip_cert_path: pathlib.Path,
    output_dir: pathlib.Path,
    vendor_id_hex: str,
    product_id_hex: str,
    vendor_name: str,
    product_name: str,
    valid_from: str,
    lifetime: str,
    device_type_hex: str,
) -> dict[str, pathlib.Path]:
    pair_dir = output_dir / f"{vendor_id_hex}_{product_id_hex}"
    pair_dir.mkdir(parents=True, exist_ok=True)

    paa_key_pem = pair_dir / "paa_key.pem"
    paa_cert_pem = pair_dir / "paa_cert.pem"
    pai_key_pem = pair_dir / "pai_key.pem"
    pai_cert_pem = pair_dir / "pai_cert.pem"

    generate_attestation_certificate(
        chip_cert_path=chip_cert_path,
        cert_type="a",
        subject_cn=f"{vendor_name} Dev PAA {vendor_id_hex}",
        out_key_pem=paa_key_pem,
        out_cert_pem=paa_cert_pem,
        valid_from=valid_from,
        lifetime=lifetime,
        vendor_id_hex=vendor_id_hex,
    )
    generate_attestation_certificate(
        chip_cert_path=chip_cert_path,
        cert_type="i",
        subject_cn=f"{vendor_name} {product_name} Dev PAI {vendor_id_hex}/{product_id_hex}",
        out_key_pem=pai_key_pem,
        out_cert_pem=pai_cert_pem,
        valid_from=valid_from,
        lifetime=lifetime,
        vendor_id_hex=vendor_id_hex,
        product_id_hex=product_id_hex,
        ca_key_pem=paa_key_pem,
        ca_cert_pem=paa_cert_pem,
    )

    bundle = {
        "paa_key_pem": paa_key_pem,
        "paa_cert_pem": paa_cert_pem,
        "paa_cert_der": convert_cert_pem_to_der(paa_cert_pem, pair_dir / "paa_cert.der"),
        "pai_key_pem": pai_key_pem,
        "pai_cert_pem": pai_cert_pem,
        "pai_key_der": convert_key_pem_to_der(pai_key_pem, pair_dir / "pai_key.der"),
        "pai_cert_der": convert_cert_pem_to_der(pai_cert_pem, pair_dir / "pai_cert.der"),
        "cd": generate_test_cd(
            chip_cert=chip_cert_path,
            chip_root=CHIP_ROOT,
            output_path=pair_dir / f"Chip-Test-CD-{vendor_id_hex}-{product_id_hex}.der",
            vendor_id_hex=vendor_id_hex,
            product_id_hex=product_id_hex,
            device_type_hex=device_type_hex,
        ),
    }
    return bundle


def generate_device_attestation_credentials(
    *,
    chip_cert_path: pathlib.Path,
    serial_num: str,
    serial_index: int,
    output_dir: pathlib.Path,
    vendor_id_hex: str,
    product_id_hex: str,
    valid_from: str,
    lifetime: str,
    pai_key_pem: pathlib.Path,
    pai_cert_pem: pathlib.Path,
    pai_cert_der: pathlib.Path,
    cd_path: pathlib.Path,
) -> dict[str, pathlib.Path]:
    device_dir = output_dir / serial_num
    device_dir.mkdir(parents=True, exist_ok=True)

    dac_key_pem = device_dir / "dac_key.pem"
    dac_cert_pem = device_dir / "dac_cert.pem"
    generate_attestation_certificate(
        chip_cert_path=chip_cert_path,
        cert_type="d",
        subject_cn=f"Matter Dev DAC {serial_num}",
        out_key_pem=dac_key_pem,
        out_cert_pem=dac_cert_pem,
        valid_from=valid_from,
        lifetime=lifetime,
        vendor_id_hex=vendor_id_hex,
        product_id_hex=product_id_hex,
        ca_key_pem=pai_key_pem,
        ca_cert_pem=pai_cert_pem,
    )

    pai_copy_path = device_dir / "pai_cert.der"
    pai_copy_path.write_bytes(pai_cert_der.read_bytes())
    cd_copy_path = device_dir / "cd.der"
    cd_copy_path.write_bytes(cd_path.read_bytes())

    return {
        "dac_cert": convert_cert_pem_to_der(dac_cert_pem, device_dir / "dac_cert.der"),
        "dac_key": convert_key_pem_to_der(dac_key_pem, device_dir / "dac_key.der"),
        "pai_cert": pai_copy_path,
        "cd": cd_copy_path,
        "dac_cert_pem": dac_cert_pem,
        "dac_key_pem": dac_key_pem,
    }


def read_manifest_fieldnames(manifest_path: pathlib.Path) -> list[str]:
    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames is None:
            raise SystemExit("Manifest has no header row")
        return list(reader.fieldnames)


def write_manifest_with_attestation_paths(
    *,
    manifest_path: pathlib.Path,
    output_path: pathlib.Path,
    rows: list[dict[str, str]],
) -> pathlib.Path:
    fieldnames = read_manifest_fieldnames(manifest_path)
    for extra_field in ATTESTATION_FIELDNAMES:
        if extra_field not in fieldnames:
            fieldnames.append(extra_field)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path


def augment_rows_with_attestation_paths(
    *,
    rows: list[dict[str, str]],
    output_dir: pathlib.Path,
    chip_cert_path: pathlib.Path,
    vendor_name: str,
    product_name: str,
    valid_from: str,
    lifetime: str,
    device_type_hex: str,
) -> list[dict[str, str]]:
    pair_bundles: dict[tuple[str, str], dict[str, pathlib.Path]] = {}
    augmented_rows: list[dict[str, str]] = []

    for index, row in enumerate(rows):
        vendor_id_hex = format_manifest_hex_u16(row["vendor_id"])
        product_id_hex = format_manifest_hex_u16(row["product_id"])
        pair = (vendor_id_hex, product_id_hex)
        if pair not in pair_bundles:
            pair_bundles[pair] = generate_pair_attestation_bundle(
                chip_cert_path=chip_cert_path,
                output_dir=output_dir / "pairs",
                vendor_id_hex=vendor_id_hex,
                product_id_hex=product_id_hex,
                vendor_name=vendor_name,
                product_name=product_name,
                valid_from=valid_from,
                lifetime=lifetime,
                device_type_hex=device_type_hex,
            )

        bundle = pair_bundles[pair]
        device_assets = generate_device_attestation_credentials(
            chip_cert_path=chip_cert_path,
            serial_num=row["serial_num"],
            serial_index=index,
            output_dir=output_dir / "devices",
            vendor_id_hex=vendor_id_hex,
            product_id_hex=product_id_hex,
            valid_from=valid_from,
            lifetime=lifetime,
            pai_key_pem=bundle["pai_key_pem"],
            pai_cert_pem=bundle["pai_cert_pem"],
            pai_cert_der=bundle["pai_cert_der"],
            cd_path=bundle["cd"],
        )

        augmented_rows.append(
            {
                **row,
                "dac_cert": str(device_assets["dac_cert"].resolve()),
                "dac_key": str(device_assets["dac_key"].resolve()),
                "pai_cert": str(device_assets["pai_cert"].resolve()),
                "cd": str(device_assets["cd"].resolve()),
            }
        )

    return augmented_rows


def main() -> int:
    args = parse_args()
    manifest_path = pathlib.Path(args.manifest).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()
    manifest_out_path = pathlib.Path(args.manifest_out).resolve()
    requested_chip_cert = pathlib.Path(args.chip_cert).expanduser().resolve()
    chip_cert_path, searched_paths = resolve_chip_cert_path(requested_chip_cert, CHIP_ROOT)

    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    if chip_cert_path is None:
        raise SystemExit(
            render_chip_cert_missing_message(
                requested_path=requested_chip_cert,
                chip_root=CHIP_ROOT,
                searched_paths=searched_paths,
            )
        )

    rows = load_manifest_rows(manifest_path)
    device_type_hex = format_manifest_hex_u16(args.device_type)
    augmented_rows = augment_rows_with_attestation_paths(
        rows=rows,
        output_dir=output_dir,
        chip_cert_path=chip_cert_path,
        vendor_name=args.vendor_name,
        product_name=args.product_name,
        valid_from=args.valid_from,
        lifetime=args.lifetime,
        device_type_hex=device_type_hex,
    )
    manifest_out = write_manifest_with_attestation_paths(
        manifest_path=manifest_path,
        output_path=manifest_out_path,
        rows=augmented_rows,
    )

    print(f"Wrote attestation assets to {output_dir}")
    print(f"Wrote manifest with attestation paths to {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
