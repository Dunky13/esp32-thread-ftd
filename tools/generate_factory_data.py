#!/usr/bin/env python3
"""Generate per-device factory partitions and onboarding data for the light example."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import zipfile

from fleet_data import load_manifest_rows, read_onboarding_codes, write_devices_summary
from tool_python import resolve_tool_python
from tool_paths import (
    CHIP_ROOT,
    DEFAULT_CHIP_CERT,
    DEFAULT_FACTORY_GENERATOR,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_DIR,
)


DEFAULT_VENDOR_NAME = "ESP-C6-Matter"
DEFAULT_PRODUCT_NAME = "Light FTD"
DEFAULT_DISCOVERY_MODE = "2"
DEFAULT_COMMISSIONING_FLOW = "0"
DEFAULT_LIGHT_DEVICE_TYPE = "0x010D"
TEST_CERTIFICATION_ID = "ZIG0000000000000000"
SETUPPAYLOAD_REQUIREMENTS = (
    CHIP_ROOT / "scripts" / "setup" / "requirements.setuppayload.txt"
)
SETUPPAYLOAD_IMPORT_CHECK = "import bitarray, click, construct, stdnum"
TEST_PAI_CERT_PATTERN = re.compile(
    r"Chip-Test-PAI-([0-9A-F]{4})-([0-9A-F]{4})-Cert\.der$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate per-device Matter factory data and onboarding codes.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="CSV manifest describing one device per row.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where per-device outputs will be written.",
    )
    parser.add_argument(
        "--vendor-name",
        default=DEFAULT_VENDOR_NAME,
        help="Matter VendorName stored in factory data.",
    )
    parser.add_argument(
        "--product-name",
        default=DEFAULT_PRODUCT_NAME,
        help="Matter ProductName stored in factory data.",
    )
    parser.add_argument(
        "--target",
        default="esp32c6",
        help="Target chip passed to the factory bin generator.",
    )
    parser.add_argument(
        "--discovery-mode",
        default=DEFAULT_DISCOVERY_MODE,
        help="Discovery mode bitmap. 2 means BLE.",
    )
    parser.add_argument(
        "--commissioning-flow",
        default=DEFAULT_COMMISSIONING_FLOW,
        help="Commissioning flow. 0 means Standard.",
    )
    parser.add_argument(
        "--generator",
        default=str(DEFAULT_FACTORY_GENERATOR),
        help="Path to generate_esp32_chip_factory_bin.py.",
    )
    parser.add_argument(
        "--chip-cert",
        default=str(DEFAULT_CHIP_CERT),
        help="Path to CHIP host chip-cert tool used to generate test CDs when needed.",
    )
    parser.add_argument(
        "--use-test-attestation",
        action="store_true",
        help="Populate DAC/PAI/CD using CHIP test credentials for development commissioning.",
    )
    parser.add_argument(
        "--no-auto-install-deps",
        action="store_true",
        help=(
            "Fail instead of auto-installing missing CHIP setup-payload Python "
            "dependencies into the active tool Python env."
        ),
    )
    return parser.parse_args()


def parse_manifest_int(value: str) -> int:
    return int(value, 0)


def format_manifest_hex_u16(value: str) -> str:
    return f"{parse_manifest_int(value):04X}"


def discover_supported_test_attestation_pairs(
    chip_root: pathlib.Path,
) -> list[tuple[str, str]]:
    attestation_dir = chip_root / "credentials" / "test" / "attestation"
    supported_pairs: set[tuple[str, str]] = set()

    for pai_cert in attestation_dir.glob("Chip-Test-PAI-*-Cert.der"):
        match = TEST_PAI_CERT_PATTERN.fullmatch(pai_cert.name)
        if match is None:
            continue
        vendor_id_hex, product_id_hex = match.groups()
        dac_certs = sorted(
            attestation_dir.glob(
                f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-[0-9A-F][0-9A-F][0-9A-F][0-9A-F]-Cert.der"
            )
        )
        if dac_certs or (attestation_dir / f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-Cert.der").is_file():
            supported_pairs.add((vendor_id_hex, product_id_hex))

    return sorted(supported_pairs)


def render_missing_test_attestation_message(
    *,
    chip_root: pathlib.Path,
    vendor_id_hex: str,
    product_id_hex: str,
) -> str:
    supported_pairs = discover_supported_test_attestation_pairs(chip_root)
    lines = [
        "CHIP test attestation bundle missing exact PAI/DAC assets for requested VID/PID.",
        f"Requested pair: 0x{vendor_id_hex}/0x{product_id_hex}",
    ]
    if supported_pairs:
        lines.append(
            "Supported pairs in connectedhomeip test bundle: "
            + ", ".join(f"0x{vendor_id}/0x{product_id}" for vendor_id, product_id in supported_pairs)
        )
    lines.extend(
        [
            "Fix:",
            "  - use one supported test VID/PID pair, or",
            "  - provide explicit dac_cert/dac_key/pai_cert/cd paths in manifest, or",
            "  - stop using --use-test-attestation.",
        ]
    )
    return "\n".join(lines)


def ensure_test_attestation_pair_supported(
    *,
    chip_root: pathlib.Path,
    vendor_id_hex: str,
    product_id_hex: str,
) -> None:
    attestation_dir = chip_root / "credentials" / "test" / "attestation"
    pai_cert = attestation_dir / f"Chip-Test-PAI-{vendor_id_hex}-{product_id_hex}-Cert.der"
    dac_certs = sorted(
        attestation_dir.glob(
            f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-[0-9A-F][0-9A-F][0-9A-F][0-9A-F]-Cert.der"
        )
    )
    dac_cert = attestation_dir / f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-Cert.der"
    if pai_cert.is_file() and (dac_certs or dac_cert.is_file()):
        return
    raise SystemExit(
        render_missing_test_attestation_message(
            chip_root=chip_root,
            vendor_id_hex=vendor_id_hex,
            product_id_hex=product_id_hex,
        )
    )


def resolve_manifest_path(path_value: str, base_dir: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise SystemExit(f"Attestation file not found: {path}")
    return path


def iter_chip_cert_candidates(
    requested_path: pathlib.Path,
    chip_root: pathlib.Path,
):
    yield requested_path

    which_path = shutil.which("chip-cert")
    if which_path:
        yield pathlib.Path(which_path)

    yield chip_root / "out" / "host" / "chip-cert"
    yield chip_root / "out" / "host" / "chip-cert.exe"
    yield chip_root / "src" / "tools" / "chip-cert" / "out" / "chip-cert"
    yield chip_root / "src" / "tools" / "chip-cert" / "out" / "chip-cert.exe"

    out_dir = chip_root / "out"
    if out_dir.is_dir():
        for pattern in ("*chip-cert*/chip-cert", "*chip-cert*/chip-cert.exe"):
            for candidate in sorted(out_dir.glob(pattern)):
                yield candidate


def resolve_chip_cert_path(
    requested_path: pathlib.Path,
    chip_root: pathlib.Path,
) -> tuple[pathlib.Path | None, list[pathlib.Path]]:
    searched_paths: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()

    for candidate in iter_chip_cert_candidates(requested_path, chip_root):
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        searched_paths.append(resolved)
        if resolved.is_file():
            return resolved, searched_paths

    return None, searched_paths


def render_chip_cert_missing_message(
    *,
    requested_path: pathlib.Path,
    chip_root: pathlib.Path,
    searched_paths: list[pathlib.Path],
) -> str:
    lines = [
        f"chip-cert tool not found. Requested path: {requested_path}",
        "Searched paths:",
    ]
    lines.extend(f"  - {path}" for path in searched_paths)
    lines.extend(
        [
            "Build it once from connectedhomeip:",
            f"  cd {chip_root}",
            "  source scripts/activate.sh",
            "  gn gen out/host",
            "  ninja -C out/host chip-cert",
        ]
    )
    return "\n".join(lines)


def generate_test_cd(
    chip_cert: pathlib.Path,
    chip_root: pathlib.Path,
    output_path: pathlib.Path,
    vendor_id_hex: str,
    product_id_hex: str,
    device_type_hex: str,
) -> pathlib.Path:
    signing_dir = (
        chip_root
        / "credentials"
        / "test"
        / "certification-declaration"
    )
    signing_cert = signing_dir / "Chip-Test-CD-Signing-Cert.pem"
    signing_key = signing_dir / "Chip-Test-CD-Signing-Key.pem"
    if output_path.is_file():
        return output_path
    chip_cert_path, searched_paths = resolve_chip_cert_path(chip_cert, chip_root)
    if chip_cert_path is None:
        raise SystemExit(
            render_chip_cert_missing_message(
                requested_path=chip_cert,
                chip_root=chip_root,
                searched_paths=searched_paths,
            )
        )
    if not signing_cert.is_file() or not signing_key.is_file():
        raise SystemExit("Missing CHIP test CD signing materials")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_checked_command(
        [
            str(chip_cert_path),
            "gen-cd",
            "-C",
            str(signing_cert),
            "-K",
            str(signing_key),
            "--out",
            str(output_path),
            "-f",
            "1",
            "-V",
            vendor_id_hex,
            "-p",
            product_id_hex,
            "-d",
            device_type_hex,
            "-c",
            TEST_CERTIFICATION_ID,
            "-l",
            "0",
            "-i",
            "0",
            "-n",
            "0001",
            "-t",
            "0",
        ]
    )
    return output_path


def run_checked_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> None:
    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(shlex.quote(part) for part in command)
        raise SystemExit(
            f"Command failed with exit code {exc.returncode}: {rendered}"
        ) from exc


def probe_setup_payload_python_dependencies(
    python_executable: str,
):
    return subprocess.run(
        [
            python_executable,
            "-c",
            SETUPPAYLOAD_IMPORT_CHECK,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def install_setup_payload_python_dependencies(
    python_executable: str,
    requirements_path: pathlib.Path,
) -> None:
    print(
        "Missing CHIP setup-payload deps in tool Python env. "
        f"Installing from {requirements_path} ..."
    )
    subprocess.run(
        [
            python_executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
        ],
        check=True,
    )


def verify_setup_payload_python_dependencies(
    python_executable: str,
    requirements_path: pathlib.Path,
    *,
    auto_install: bool,
) -> None:
    probe = probe_setup_payload_python_dependencies(python_executable)
    if probe.returncode == 0:
        return

    install_command = (
        f"{shlex.quote(python_executable)} -m pip install -r "
        f"{shlex.quote(str(requirements_path))}"
    )
    if auto_install:
        try:
            install_setup_payload_python_dependencies(
                python_executable=python_executable,
                requirements_path=requirements_path,
            )
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                "\n".join(
                    [
                        "Failed to auto-install CHIP setup-payload deps.",
                        f"Python env: {python_executable}",
                        f"Requirements: {requirements_path}",
                        f"Install command: {install_command}",
                        f"pip exit code: {exc.returncode}",
                    ]
                )
            ) from exc
        probe = probe_setup_payload_python_dependencies(python_executable)
        if probe.returncode == 0:
            return

    combined_output = "\n".join(
        part.strip()
        for part in (probe.stdout, probe.stderr)
        if part and part.strip()
    )
    missing_match = re.search(
        r"ModuleNotFoundError: No module named '([^']+)'",
        combined_output,
    )
    missing_module = missing_match.group(1) if missing_match else "unknown"
    message_lines = [
        "Factory generator Python env missing CHIP setup-payload deps.",
        f"Python env: {python_executable}",
        f"Requirements: {requirements_path}",
        f"Missing module: {missing_module}",
        f"Install with: {install_command}",
    ]
    if combined_output:
        message_lines.extend(
            [
                "Original import check output:",
                combined_output,
            ]
        )
    raise SystemExit("\n".join(message_lines))


def resolve_attestation_paths(
    *,
    row: dict[str, str],
    row_index: int,
    manifest_dir: pathlib.Path,
    chip_root: pathlib.Path,
    chip_cert: pathlib.Path,
    device_output_dir: pathlib.Path,
    use_test_attestation: bool,
) -> dict[str, pathlib.Path]:
    explicit_keys = ("dac_cert", "dac_key", "pai_cert", "cd")
    if any(row.get(key, "") for key in explicit_keys):
        required = [key for key in explicit_keys if not row.get(key, "")]
        if required:
            raise SystemExit(
                f"Row {row_index + 2} missing attestation fields: {', '.join(required)}"
            )
        return {
            "dac_cert": resolve_manifest_path(row["dac_cert"], manifest_dir),
            "dac_key": resolve_manifest_path(row["dac_key"], manifest_dir),
            "pai_cert": resolve_manifest_path(row["pai_cert"], manifest_dir),
            "cd": resolve_manifest_path(row["cd"], manifest_dir),
        }

    if not use_test_attestation:
        return {}

    attestation_dir = (
        chip_root / "credentials" / "test" / "attestation"
    )
    cd_dir = (
        chip_root / "credentials" / "test" / "certification-declaration"
    )
    vendor_id_hex = format_manifest_hex_u16(row["vendor_id"])
    product_id_hex = format_manifest_hex_u16(row["product_id"])
    device_type_hex = format_manifest_hex_u16(row.get("device_type") or DEFAULT_LIGHT_DEVICE_TYPE)

    ensure_test_attestation_pair_supported(
        chip_root=chip_root,
        vendor_id_hex=vendor_id_hex,
        product_id_hex=product_id_hex,
    )

    pai_cert = attestation_dir / f"Chip-Test-PAI-{vendor_id_hex}-{product_id_hex}-Cert.der"

    dac_certs = sorted(
        attestation_dir.glob(f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-[0-9][0-9][0-9][0-9]-Cert.der")
    )
    if dac_certs:
        dac_cert = dac_certs[row_index % len(dac_certs)]
    else:
        dac_cert = attestation_dir / f"Chip-Test-DAC-{vendor_id_hex}-{product_id_hex}-Cert.der"

    dac_key = dac_cert.with_name(dac_cert.name.replace("-Cert.der", "-Key.der"))
    if not dac_key.is_file():
        raise SystemExit(f"Missing matching DAC key: {dac_key}")

    cd = cd_dir / f"Chip-Test-CD-{vendor_id_hex}-{product_id_hex}.der"
    if not cd.is_file():
        cd = generate_test_cd(
            chip_cert=chip_cert,
            chip_root=chip_root,
            output_path=device_output_dir / f"Chip-Test-CD-{vendor_id_hex}-{product_id_hex}.der",
            vendor_id_hex=vendor_id_hex,
            product_id_hex=product_id_hex,
            device_type_hex=device_type_hex,
        )

    return {
        "dac_cert": dac_cert,
        "dac_key": dac_key,
        "pai_cert": pai_cert,
        "cd": cd,
    }


def build_command(
    generator: pathlib.Path,
    row: dict[str, str],
    output_dir: pathlib.Path,
    vendor_name: str,
    product_name: str,
    target: str,
    discovery_mode: str,
    commissioning_flow: str,
    attestation_paths: dict[str, pathlib.Path],
) -> list[str]:
    command = [
        resolve_tool_python(),
        str(generator),
        "--output_dir",
        str(output_dir),
        "--target",
        target,
        "--vendor-name",
        vendor_name,
        "--product-name",
        product_name,
        "--serial-num",
        row["serial_num"],
        "--discriminator",
        row["discriminator"],
        "--passcode",
        row["passcode"],
        "--vendor-id",
        row["vendor_id"],
        "--product-id",
        row["product_id"],
        "--commissioning-flow",
        commissioning_flow,
        "--discovery-mode",
        discovery_mode,
    ]

    optional_fields = {
        "hw_ver": "--hw-ver",
        "hw_ver_str": "--hw-ver-str",
        "mfg_date": "--mfg-date",
        "rd_id_uid": "--rd-id-uid",
        "device_type": "--device-type",
        "product_label": "--product-label",
        "product_url": "--product-url",
        "part_number": "--part-number",
        "product_finish": "--product-finish",
        "product_color": "--product-color",
    }

    for manifest_key, flag in optional_fields.items():
        value = row.get(manifest_key, "")
        if value:
            command.extend([flag, value])

    if attestation_paths:
        command.extend(["--dac-cert", str(attestation_paths["dac_cert"])])
        command.extend(["--dac-key", str(attestation_paths["dac_key"])])
        command.extend(["--pai-cert", str(attestation_paths["pai_cert"])])
        command.extend(["--cd", str(attestation_paths["cd"])])

    return command


def version_key(path: pathlib.Path) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", path.name))


def has_esp_secure_cert_tools_dir(path: pathlib.Path) -> bool:
    return (path / "esp_secure_cert" / "tlv_format.py").is_file()


def zip_has_esp_secure_cert_tools(zip_path: pathlib.Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            return "tools/esp_secure_cert/tlv_format.py" in archive.namelist()
    except (FileNotFoundError, OSError, zipfile.BadZipFile):
        return False


def collect_generator_pythonpath_entries(shim_root: pathlib.Path) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()

    def add(entry: str) -> None:
        if entry and entry not in seen:
            entries.append(entry)
            seen.add(entry)

    if shim_root.is_dir():
        add(str(shim_root))

    idf_path = os.environ.get("IDF_PATH")
    if idf_path:
        idf_tools_dir = (
            pathlib.Path(idf_path).expanduser().resolve()
            / "components"
            / "esp_secure_cert_mgr"
            / "tools"
        )
        if has_esp_secure_cert_tools_dir(idf_tools_dir):
            add(str(idf_tools_dir))

    component_cache_root = (
        pathlib.Path.home()
        / ".espressif"
        / "tools"
        / "components"
        / "espressif"
        / "esp_secure_cert_mgr"
    )
    if component_cache_root.is_dir():
        version_dirs = sorted(
            (path for path in component_cache_root.iterdir() if path.is_dir()),
            key=version_key,
            reverse=True,
        )
        for version_dir in version_dirs:
            unpacked_tools_dir = version_dir / "tools"
            if has_esp_secure_cert_tools_dir(unpacked_tools_dir):
                add(str(unpacked_tools_dir))

            for zip_path in sorted(version_dir.glob("*.zip"), reverse=True):
                if zip_has_esp_secure_cert_tools(zip_path):
                    add(f"{zip_path}/tools")

    return entries


def build_generator_pythonpath(
    existing_pythonpath: str,
    shim_root: pathlib.Path,
) -> str:
    entries = collect_generator_pythonpath_entries(shim_root)
    if existing_pythonpath:
        entries.append(existing_pythonpath)
    return os.pathsep.join(entries)


def main() -> int:
    args = parse_args()
    manifest_path = pathlib.Path(args.manifest).resolve()
    generator_path = pathlib.Path(args.generator).resolve()
    chip_cert_path = pathlib.Path(args.chip_cert).expanduser().resolve()
    output_root = pathlib.Path(args.output_dir).resolve()
    shim_root = pathlib.Path(__file__).resolve().parent / "_factory_generator_shim"
    tool_python = resolve_tool_python()

    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    if not generator_path.is_file():
        raise SystemExit(f"Generator not found: {generator_path}")
    if not SETUPPAYLOAD_REQUIREMENTS.is_file():
        raise SystemExit(
            f"Missing CHIP setup-payload requirements file: {SETUPPAYLOAD_REQUIREMENTS}"
        )
    verify_setup_payload_python_dependencies(
        python_executable=tool_python,
        requirements_path=SETUPPAYLOAD_REQUIREMENTS,
        auto_install=not args.no_auto_install_deps,
    )
    rows = load_manifest_rows(manifest_path)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        serial_num = row["serial_num"]
        device_output_dir = output_root / serial_num
        device_output_dir.mkdir(parents=True, exist_ok=True)

        attestation_paths = resolve_attestation_paths(
            row=row,
            row_index=row_index,
            manifest_dir=manifest_path.parent,
            chip_root=CHIP_ROOT,
            chip_cert=chip_cert_path,
            device_output_dir=device_output_dir,
            use_test_attestation=args.use_test_attestation,
        )
        command = build_command(
            generator=generator_path,
            row=row,
            output_dir=device_output_dir,
            vendor_name=args.vendor_name,
            product_name=args.product_name,
            target=args.target,
            discovery_mode=args.discovery_mode,
            commissioning_flow=args.commissioning_flow,
            attestation_paths=attestation_paths,
        )
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = build_generator_pythonpath(
            existing_pythonpath=existing_pythonpath,
            shim_root=shim_root,
        )
        run_checked_command(command, env=environment)

        onboarding_path = device_output_dir / "onboarding_codes.csv"
        factory_bin_path = device_output_dir / "factory_partition.bin"
        factory_csv_path = device_output_dir / "nvs_partition.csv"
        if not factory_bin_path.is_file():
            raise SystemExit(f"Factory bin not found after generation: {factory_bin_path}")
        if not factory_csv_path.is_file():
            raise SystemExit(f"Factory CSV not found after generation: {factory_csv_path}")
        qrcode, manualcode = read_onboarding_codes(onboarding_path)
        summary_rows.append(
            {
                "serial_num": serial_num,
                "discriminator": row["discriminator"],
                "passcode": row["passcode"],
                "vendor_id": row["vendor_id"],
                "product_id": row["product_id"],
                "vendor_name": args.vendor_name,
                "product_name": args.product_name,
                "factory_bin": str(factory_bin_path.resolve()),
                "factory_csv": str(factory_csv_path.resolve()),
                "onboarding_csv": str(onboarding_path.resolve()),
                "qrcode": qrcode,
                "manualcode": manualcode,
            }
        )

    summary_path = write_devices_summary(output_root, summary_rows)
    print(f"Wrote per-device outputs to {output_root}")
    print(f"Wrote fleet summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
