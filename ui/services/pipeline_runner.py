from __future__ import annotations

import csv
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.fleet_data import load_device_rows, write_manifest
from tools.generate_device_manifest import generate_passcode, generate_rd_id_uid

from .release_bundle import current_bundle
from .workspace_store import Workspace, save_workspace


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class JobResult:
    command: list[str]
    exit_code: int
    log_path: Path
    status: str


@dataclass(frozen=True)
class DeviceRow:
    serial_num: str
    vendor_id: str
    product_id: str
    manualcode: str
    qrcode: str
    factory_bin: str
    flash_status: str


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_log(log_path: Path, command: list[str], completed: subprocess.CompletedProcess[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + shlex.join(command) + "\n\n")
        log.write(f"exit_code={completed.returncode}\n\n")
        if completed.stdout:
            log.write("## stdout\n")
            log.write(completed.stdout)
            log.write("\n")
        if completed.stderr:
            log.write("## stderr\n")
            log.write(completed.stderr)
            log.write("\n")


def _run_job(workspace: Workspace, name: str, command: list[str]) -> JobResult:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = workspace.logs_dir / f"{name}-{timestamp()}.log"
    _write_log(log_path, command, completed)
    status = "success" if completed.returncode == 0 else "failed"
    return JobResult(
        command=command,
        exit_code=completed.returncode,
        log_path=log_path,
        status=status,
    )


def _bundle_build_dir(workspace: Workspace) -> Path | None:
    bundle = current_bundle(workspace)
    return bundle.build_dir if bundle else None


def _string(data: dict[str, Any], key: str, fallback: str) -> str:
    value = data.get(key, fallback)
    return str(value if value is not None else fallback)


def _int(data: dict[str, Any], key: str, fallback: int) -> int:
    value = data.get(key, fallback)
    return int(value if value is not None else fallback)


def _write_uuid_manifest(workspace: Workspace, request: dict[str, Any]) -> None:
    count = _int(request, "count", 8)
    prefix = _string(request, "serial_prefix", "C6")
    vendor_id = _string(request, "vendor_id", "0xFFF1")
    product_id = _string(request, "product_id", "0x8000")
    hw_ver = _string(request, "hw_ver", "1")
    hw_ver_str = _string(request, "hw_ver_str", "1.0")
    mfg_date = _string(request, "mfg_date", datetime.now(UTC).date().isoformat())
    discriminator_start = _int(request, "discriminator_start", 3840)

    rows: list[dict[str, str]] = []
    for index in range(count):
        serial_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"{workspace.id}:{index}:{prefix}")
        serial = f"{prefix}-{serial_uuid.hex[:8].upper()}"
        rows.append(
            {
                "serial_num": serial,
                "discriminator": str(discriminator_start + index),
                "passcode": generate_passcode(),
                "vendor_id": vendor_id,
                "product_id": product_id,
                "hw_ver": hw_ver,
                "hw_ver_str": hw_ver_str,
                "mfg_date": mfg_date,
                "rd_id_uid": generate_rd_id_uid(),
            }
        )
    write_manifest(workspace.manifest_path, rows)


def generate_workspace_outputs(workspace: Workspace, request: dict[str, Any]) -> JobResult:
    workspace.data["generation"] = {"status": "running"}
    save_workspace(workspace)

    regenerate = bool(request.get("regenerate_identities"))
    serial_mode = _string(request, "serial_mode", "sequential")
    if regenerate and workspace.manifest_path.exists():
        workspace.manifest_path.unlink()
    if serial_mode == "uuid" and not workspace.manifest_path.exists():
        _write_uuid_manifest(workspace, request)

    build_dir = _bundle_build_dir(workspace)
    if build_dir is None:
        build_dir = PROJECT_ROOT / "build" / "light-c6-thread"

    command = [
        sys.executable,
        "tools/light_pipeline.py",
        "run",
        "--manifest",
        str(workspace.manifest_path),
        "--output-dir",
        str(workspace.out_dir),
        "--label-output-dir",
        str(workspace.labels_dir),
        "--label-html",
        str(workspace.label_html_path),
        "--count",
        str(_int(request, "count", 8)),
        "--vendor-id",
        _string(request, "vendor_id", "0xFFF1"),
        "--product-id",
        _string(request, "product_id", "0x8000"),
        "--vendor-name",
        _string(request, "vendor_name", "ESP-C6-Matter"),
        "--product-name",
        _string(request, "product_name", "Thread Light"),
        "--serial-prefix",
        _string(request, "serial_prefix", "LGT"),
        "--start-index",
        str(_int(request, "start_index", 1)),
        "--serial-width",
        str(_int(request, "serial_width", 4)),
        "--hw-ver",
        _string(request, "hw_ver", "1"),
        "--hw-ver-str",
        _string(request, "hw_ver_str", "1.0"),
        "--mfg-date",
        _string(request, "mfg_date", datetime.now(UTC).date().isoformat()),
        "--dac-provider",
        _string(request, "dac_provider", "example"),
        "--skip-build",
        "--build-dir",
        str(build_dir),
        "--no-monitor",
    ]
    if request.get("use_test_attestation"):
        command.append("--use-test-attestation")

    result = _run_job(workspace, "generate", command)
    workspace.data["defaults"] = {
        key: request[key]
        for key in (
            "vendor_id",
            "product_id",
            "vendor_name",
            "product_name",
            "serial_mode",
            "serial_prefix",
            "start_index",
            "serial_width",
            "count",
            "hw_ver",
            "hw_ver_str",
            "mfg_date",
            "dac_provider",
        )
        if key in request
    }
    workspace.data["generation"] = {
        "status": result.status,
        "exit_code": result.exit_code,
        "log_path": str(result.log_path.relative_to(workspace.path)),
    }
    save_workspace(workspace)
    return result


def list_generated_devices(workspace: Workspace) -> list[DeviceRow]:
    if not workspace.devices_csv_path.is_file():
        return []
    rows = load_device_rows(workspace.devices_csv_path)
    devices: list[DeviceRow] = []
    for row in rows:
        factory_bin = row["factory_bin"]
        factory_path = Path(factory_bin)
        if not factory_path.is_absolute():
            factory_path = PROJECT_ROOT / factory_path
        devices.append(
            DeviceRow(
                serial_num=row["serial_num"],
                vendor_id=row["vendor_id"],
                product_id=row["product_id"],
                manualcode=row["manualcode"],
                qrcode=row["qrcode"],
                factory_bin=factory_bin,
                flash_status="ready" if factory_path.exists() else "missing factory bin",
            )
        )
    return devices


def flash_device(
    workspace: Workspace,
    serial_num: str,
    port: str,
    *,
    erase: bool = False,
    monitor: bool = False,
) -> JobResult:
    workspace.data["flash"] = {"status": "running"}
    save_workspace(workspace)

    build_dir = _bundle_build_dir(workspace) or PROJECT_ROOT / "build" / "light-c6-thread"
    command = [
        sys.executable,
        "tools/light_pipeline.py",
        "flash",
        "--output-dir",
        str(workspace.out_dir),
        "--build-dir",
        str(build_dir),
        "--serial",
        serial_num,
        "--port",
        port,
    ]
    if erase:
        command.append("--erase")
    command.append("--monitor" if monitor else "--no-monitor")
    result = _run_job(workspace, "flash", command)
    workspace.data["selection"] = {
        "serial_num": serial_num,
        "serial_port": port,
    }
    workspace.data["flash"] = {
        "status": result.status,
        "exit_code": result.exit_code,
        "log_path": str(result.log_path.relative_to(workspace.path)),
    }
    save_workspace(workspace)
    return result


def read_log_tail(workspace: Workspace, relative_log_path: str, max_lines: int = 80) -> str:
    path = workspace.path / relative_log_path
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as file:
        lines = file.readlines()
    return "".join(lines[-max_lines:])


def write_uploaded_tarball(workspace: Workspace, filename: str, data: bytes) -> Path:
    safe_name = Path(filename).name or "release.tar.gz"
    target = workspace.path / "inputs" / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target
