#!/usr/bin/env python3
"""User-facing pipeline for esp-matter/examples/light."""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import datetime
from types import ModuleType

try:
    from .detect_env_paths import (
        choose_idf_candidate,
        collect_idf_candidates,
        load_eim_idf_path,
        version_hint_from_build_dirs,
    )
    from .fleet_data import load_device_rows, load_manifest_rows
    from . import generate_factory_data
    from .tool_paths import (
        CHIP_ROOT,
        DEFAULT_BUILD_DIR,
        DEFAULT_LABEL_HTML_PATH,
        DEFAULT_LABEL_OUTPUT_DIR,
        DEFAULT_MANIFEST_PATH,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_PARTITIONS_CSV,
        ESP_MATTER_ROOT,
        EXAMPLE_DIR,
        PROJECT_ROOT,
        TOOLS_DIR,
    )
    from .tool_python import resolve_tool_python
except ImportError:
    from detect_env_paths import (
        choose_idf_candidate,
        collect_idf_candidates,
        load_eim_idf_path,
        version_hint_from_build_dirs,
    )
    from fleet_data import load_device_rows, load_manifest_rows
    import generate_factory_data
    from tool_paths import (
        CHIP_ROOT,
        DEFAULT_BUILD_DIR,
        DEFAULT_LABEL_HTML_PATH,
        DEFAULT_LABEL_OUTPUT_DIR,
        DEFAULT_MANIFEST_PATH,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_PARTITIONS_CSV,
        ESP_MATTER_ROOT,
        EXAMPLE_DIR,
        PROJECT_ROOT,
        TOOLS_DIR,
    )
    from tool_python import resolve_tool_python


DEFAULT_TARGET = "esp32c6"
DEFAULT_THREAD_SDKCONFIG = EXAMPLE_DIR / "sdkconfig.defaults.c6_thread"
DEFAULT_BASE_SDKCONFIG = EXAMPLE_DIR / "sdkconfig.defaults"
PATCHES_DIR = PROJECT_ROOT / "patches"
_GIT_SUBMODULE_JOBS_SUPPORTED: bool | None = None
_EXAMPLE_DAC_VENDOR_IDS = {0xFFF1, 0xFFF2, 0xFFF3}
_EXAMPLE_DAC_PRODUCT_ID_MIN = 0x8000
_EXAMPLE_DAC_PRODUCT_ID_MAX = 0x801F
_EXPLICIT_ATTESTATION_FIELDS = ("dac_cert", "dac_key", "pai_cert", "cd")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and provision esp-matter/examples/light for ESP32-C6 Thread-only devices.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Validate repo paths and detect ESP-IDF.")
    doctor_parser.add_argument(
        "--build-dir",
        default=str(DEFAULT_BUILD_DIR),
        help="Build directory to inspect.",
    )

    run_parser = subparsers.add_parser("run", help="Generate manifest, build, provision, label, and optionally flash.")
    add_pipeline_arguments(run_parser)

    flash_parser = subparsers.add_parser("flash", help="Flash one generated device onto a target board.")
    add_flash_arguments(flash_parser, required_port=True)
    flash_parser.add_argument(
        "--build-dir",
        default=str(DEFAULT_BUILD_DIR),
        help="ESP-IDF build directory.",
    )
    flash_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Factory-data output directory.",
    )
    flash_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only.",
    )

    list_parser = subparsers.add_parser("list", help="List generated serials and detected serial ports.")
    list_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Factory-data output directory.",
    )
    list_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command only.",
    )
    return parser.parse_args(argv)


def add_common_identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--vendor-id",
        default="0xFFF1",
        help="Matter vendor ID for firmware config and generated device data.",
    )
    parser.add_argument(
        "--product-id",
        default="0x8000",
        help="Matter product ID for firmware config and generated device data.",
    )
    parser.add_argument(
        "--vendor-name",
        default="ESP-C6-Matter",
        help="Vendor name stored in generated device data.",
    )
    parser.add_argument(
        "--product-name",
        default="Thread Light",
        help="Product name stored in generated device data.",
    )


def add_manifest_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Manifest CSV path.",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="If set, regenerate manifest with this many unique devices.",
    )
    parser.add_argument(
        "--serial-prefix",
        default="LGT",
        help="Serial prefix when generating a manifest.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="Starting serial index when generating a manifest.",
    )
    parser.add_argument(
        "--serial-width",
        type=int,
        default=4,
        help="Serial zero-pad width when generating a manifest.",
    )
    parser.add_argument(
        "--discriminator-start",
        type=int,
        default=3840,
        help="First discriminator when generating a manifest.",
    )
    parser.add_argument(
        "--hw-ver",
        default="1",
        help="Hardware version stored in generated device data.",
    )
    parser.add_argument(
        "--hw-ver-str",
        default="1.0",
        help="Hardware version string stored in generated device data.",
    )
    parser.add_argument(
        "--mfg-date",
        help="Manufacturing date YYYY-MM-DD for generated manifest rows.",
    )


def add_flash_arguments(parser: argparse.ArgumentParser, *, required_port: bool) -> None:
    parser.add_argument(
        "--port",
        required=required_port,
        help="Serial port, for example /dev/ttyUSB0.",
    )
    parser.add_argument(
        "--serial",
        help="Serial number to flash from devices.csv.",
    )
    parser.add_argument(
        "--serial-index",
        type=int,
        default=1,
        help="1-based device index from devices.csv when --serial is omitted.",
    )
    parser.add_argument(
        "--baud",
        default="921600",
        help="Baud rate for esptool.py.",
    )
    parser.add_argument(
        "--erase",
        action="store_true",
        help="Erase flash before flashing.",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Open idf.py monitor after flashing.",
    )


def add_pipeline_arguments(parser: argparse.ArgumentParser) -> None:
    add_manifest_arguments(parser)
    add_common_identity_arguments(parser)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Factory-data output directory.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(DEFAULT_BUILD_DIR),
        help="ESP-IDF build directory.",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help="ESP target passed to idf.py and factory-data generator.",
    )
    parser.add_argument(
        "--dac-provider",
        choices=("example", "factory"),
        default="example",
        help="DAC source. 'example' only supports Matter test VID/PID values (VID 0xFFF1-0xFFF3, PID 0x8000-0x801F).",
    )
    parser.add_argument(
        "--use-test-attestation",
        action="store_true",
        help="Only for --dac-provider factory. Uses CHIP test DAC/PAI/CD assets.",
    )
    parser.add_argument(
        "--label-output-dir",
        default=str(DEFAULT_LABEL_OUTPUT_DIR),
        help="Directory for per-device text labels.",
    )
    parser.add_argument(
        "--label-html",
        default=str(DEFAULT_LABEL_HTML_PATH),
        help="Printable HTML label output path.",
    )
    parser.add_argument(
        "--label-csv",
        help="Optional extra CSV export for labels.",
    )
    parser.add_argument(
        "--render-qr-svg",
        action="store_true",
        help="Also render QR SVG files. Auto-installs 'segno' when missing.",
    )
    parser.add_argument(
        "--apply-patches",
        action="store_true",
        help="Apply repo patch files under patches/ to esp-matter/ before building.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip firmware build and only provision from an existing build directory.",
    )
    parser.add_argument(
        "--skip-labels",
        action="store_true",
        help="Skip label generation.",
    )
    parser.add_argument(
        "--flash",
        action="store_true",
        help="Deprecated. Flash now happens automatically when --port is provided.",
    )
    add_flash_arguments(parser, required_port=False)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only.",
    )


def detect_idf_path() -> pathlib.Path:
    eim_idf = load_eim_idf_path()
    if eim_idf is not None:
        return eim_idf

    env_idf = os.environ.get("IDF_PATH")
    if env_idf:
        candidate = pathlib.Path(env_idf).expanduser().resolve()
        if is_idf_path(candidate):
            return candidate

    candidates = collect_idf_candidates()
    idf_path = choose_idf_candidate(candidates, version_hint_from_build_dirs())
    if idf_path is None:
        raise SystemExit(
            "ESP-IDF not found.\n"
            "Set IDF_PATH or install ESP-IDF in a standard location such as ~/esp-idf."
        )
    return idf_path


def is_idf_path(path: pathlib.Path) -> bool:
    return (path / "export.sh").is_file() and (path / "tools" / "idf.py").is_file()


def ensure_example_tree() -> None:
    if not EXAMPLE_DIR.is_dir():
        raise SystemExit(f"Light example not found: {EXAMPLE_DIR}")
    if not ESP_MATTER_ROOT.is_dir():
        raise SystemExit(f"ESP-Matter checkout not found: {ESP_MATTER_ROOT}")


def list_missing_submodules() -> list[str]:
    completed = subprocess.run(
        ["git", "submodule", "status", "--recursive"],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    missing: list[str] = []
    for line in completed.stdout.splitlines():
        if line.startswith("-"):
            missing.append(line[1:].strip())
    return missing


def submodule_update_jobs() -> int | None:
    number_of_threads = os.cpu_count()
    if number_of_threads is None:
        return None
    return max(1, min(number_of_threads - 2, 8))


def git_submodule_jobs_supported() -> bool:
    global _GIT_SUBMODULE_JOBS_SUPPORTED
    if _GIT_SUBMODULE_JOBS_SUPPORTED is not None:
        return _GIT_SUBMODULE_JOBS_SUPPORTED

    try:
        with tempfile.TemporaryDirectory(prefix="git-submodule-jobs-") as temp_dir:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=temp_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            completed = subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive", "--jobs", "1"],
                cwd=temp_dir,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except (OSError, subprocess.SubprocessError):
        _GIT_SUBMODULE_JOBS_SUPPORTED = False
        return _GIT_SUBMODULE_JOBS_SUPPORTED

    _GIT_SUBMODULE_JOBS_SUPPORTED = completed.returncode == 0
    return _GIT_SUBMODULE_JOBS_SUPPORTED


def recursive_submodule_update_command() -> list[str]:
    command = ["git", "submodule", "update", "--init", "--recursive"]
    jobs = submodule_update_jobs()
    if jobs is not None and git_submodule_jobs_supported():
        command.extend(["--jobs", str(jobs)])
    return command


def ensure_recursive_submodules() -> None:
    try:
        missing = list_missing_submodules()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Failed to inspect git submodule state.\n"
            "Run `git submodule status --recursive` from repo root to inspect manually."
        ) from exc

    if not missing:
        return

    command = recursive_submodule_update_command()
    command_text = shlex.join(command)

    print(f"    Missing git submodules detected; running `{command_text}`")
    for entry in missing[:5]:
        print(f"      - {entry}")
    if len(missing) > 5:
        print(f"      ... and {len(missing) - 5} more")

    try:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Failed to initialize recursive git submodules.\n"
            f"Command: {command_text}\n"
            f"Exit code: {exc.returncode}"
        ) from exc

    remaining = list_missing_submodules()
    if remaining:
        raise SystemExit(
            "Recursive submodule init completed, but some submodules are still missing.\n"
            "Run `git submodule status --recursive` from repo root for details."
        )


def list_repo_patch_files() -> list[pathlib.Path]:
    if not PATCHES_DIR.is_dir():
        return []
    return sorted(path for path in PATCHES_DIR.iterdir() if path.is_file() and path.suffix == ".patch")

def git_apply_check_command(patch_path: pathlib.Path, *, reverse: bool = False) -> list[str]:
    command = ["git", "apply", "--check"]
    if reverse:
        command.append("--reverse")
    command.append(str(patch_path))
    return command


def repo_patch_status(patch_path: pathlib.Path) -> str:
    forward_check = subprocess.run(
        git_apply_check_command(patch_path),
        cwd=ESP_MATTER_ROOT,
        capture_output=True,
        text=True,
    )
    if forward_check.returncode == 0:
        return "needs_apply"

    reverse_check = subprocess.run(
        git_apply_check_command(patch_path, reverse=True),
        cwd=ESP_MATTER_ROOT,
        capture_output=True,
        text=True,
    )
    if reverse_check.returncode == 0:
        return "already_applied"

    details = "\n".join(
        detail
        for detail in (
            forward_check.stdout.strip(),
            forward_check.stderr.strip(),
            reverse_check.stdout.strip(),
            reverse_check.stderr.strip(),
        )
        if detail
    )
    message = (
        f"Repo patch cannot be applied cleanly: {patch_path.name}\n"
        f"Patch path: {patch_path}\n"
        f"Run `git -C {ESP_MATTER_ROOT} status --short` and inspect local submodule edits."
    )
    if details:
        message = f"{message}\n{details}"
    raise SystemExit(message)


def ensure_repo_patches_applied(*, apply: bool = False) -> None:
    patch_files = list_repo_patch_files()
    if not patch_files:
        return

    applied: list[str] = []
    already_applied: list[str] = []
    pending_apply: list[str] = []
    for patch_path in patch_files:
        status = repo_patch_status(patch_path)
        if status == "already_applied":
            already_applied.append(patch_path.name)
            continue
        pending_apply.append(patch_path.name)
        if not apply:
            continue

        print(f"    Applying repo patch to `esp-matter/`: {patch_path.name}")
        try:
            subprocess.run(
                ["git", "apply", str(patch_path)],
                cwd=ESP_MATTER_ROOT,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                "Failed to apply repo patch.\n"
                f"Patch: {patch_path}\n"
                f"Exit code: {exc.returncode}"
            ) from exc
        applied.append(patch_path.name)

    if applied:
        print("    Applied repo patches:")
        for patch_name in applied[:5]:
            print(f"      - {patch_name}")
        if len(applied) > 5:
            print(f"      ... and {len(applied) - 5} more")
    elif pending_apply:
        print("    Repo patches available under `patches/` but not auto-applied:")
        for patch_name in pending_apply[:5]:
            print(f"      - {patch_name}")
        if len(pending_apply) > 5:
            print(f"      ... and {len(pending_apply) - 5} more")
        print("    Re-run with `--apply-patches` to mutate `esp-matter/`.")
    elif already_applied:
        print("    Repo patches already applied in `esp-matter/`.")


def write_build_override(
    *,
    build_dir: pathlib.Path,
    vendor_id: str,
    product_id: str,
    dac_provider: str,
) -> pathlib.Path:
    validate_dac_provider_config(
        dac_provider=dac_provider,
        vendor_id=vendor_id,
        product_id=product_id,
    )
    override_dir = build_dir.parent / "generated-configs"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_path = override_dir / f"{build_dir.name}.sdkconfig.defaults.generated"
    lines = [
        f"CONFIG_DEVICE_VENDOR_ID={vendor_id}",
        f"CONFIG_DEVICE_PRODUCT_ID={product_id}",
        "CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y",
        'CONFIG_ESPTOOLPY_FLASHSIZE="8MB"',
        "CONFIG_PARTITION_TABLE_CUSTOM=y",
        f'CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="{DEFAULT_PARTITIONS_CSV}"',
        f'CONFIG_PARTITION_TABLE_FILENAME="{DEFAULT_PARTITIONS_CSV}"',
        "CONFIG_PARTITION_TABLE_OFFSET=0xC000",
        'CONFIG_CHIP_FACTORY_NAMESPACE_PARTITION_LABEL="fctry"',
        "CONFIG_ENABLE_ESP32_FACTORY_DATA_PROVIDER=y",
        "CONFIG_ENABLE_ESP32_DEVICE_INSTANCE_INFO_PROVIDER=y",
        "CONFIG_ENABLE_ESP32_DEVICE_INFO_PROVIDER=y",
        "CONFIG_FACTORY_COMMISSIONABLE_DATA_PROVIDER=y",
        "CONFIG_FACTORY_DEVICE_INSTANCE_INFO_PROVIDER=y",
        "CONFIG_FACTORY_DEVICE_INFO_PROVIDER=y",
    ]
    if dac_provider == "example":
        lines.append("CONFIG_EXAMPLE_DAC_PROVIDER=y")
    else:
        lines.append("CONFIG_FACTORY_PARTITION_DAC_PROVIDER=y")
    override_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return override_path


def validate_dac_provider_config(*, dac_provider: str, vendor_id: str, product_id: str) -> None:
    if dac_provider != "example":
        return

    vendor_id_int = int(vendor_id, 0)
    product_id_int = int(product_id, 0)
    if (
        vendor_id_int in _EXAMPLE_DAC_VENDOR_IDS
        and _EXAMPLE_DAC_PRODUCT_ID_MIN <= product_id_int <= _EXAMPLE_DAC_PRODUCT_ID_MAX
    ):
        return

    raise SystemExit(
        "Example DAC provider only supports Matter test credentials for "
        "VID 0xFFF1-0xFFF3 and PID 0x8000-0x801F.\n"
        f"Got VID {vendor_id} and PID {product_id}.\n"
        "Use custom DAC/PAI/CD assets with --dac-provider factory if you need custom VID/PID."
    )


def validate_test_attestation_pair(*, vendor_id: str, product_id: str) -> None:
    generate_factory_data.ensure_test_attestation_pair_supported(
        chip_root=CHIP_ROOT,
        vendor_id_hex=generate_factory_data.format_manifest_hex_u16(vendor_id),
        product_id_hex=generate_factory_data.format_manifest_hex_u16(product_id),
    )


def validate_test_attestation_manifest(manifest_path: pathlib.Path) -> None:
    rows = load_manifest_rows(manifest_path)
    checked_pairs: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        if all(row.get(field, "") for field in _EXPLICIT_ATTESTATION_FIELDS):
            continue
        pair = (row["vendor_id"], row["product_id"])
        if pair in checked_pairs:
            continue
        checked_pairs.add(pair)
        try:
            validate_test_attestation_pair(
                vendor_id=row["vendor_id"],
                product_id=row["product_id"],
            )
        except SystemExit as exc:
            raise SystemExit(f"Manifest row {index}: {exc}") from None


def cleanup_stale_build_dir(build_dir: pathlib.Path) -> None:
    if not build_dir.is_dir():
        return

    if (build_dir / "CMakeCache.txt").is_file():
        return

    entries = list(build_dir.iterdir())
    removable_names = {
        "sdkconfig.defaults.generated",
        "CMakeFiles",
        "log",
    }
    if not entries or any(entry.name not in removable_names for entry in entries):
        return

    for entry in entries:
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def build_dir_looks_like_cmake_build(build_dir: pathlib.Path) -> bool:
    return (build_dir / "CMakeCache.txt").is_file()


def read_cmake_cache_value(build_dir: pathlib.Path, key: str) -> str | None:
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.is_file():
        return None

    prefix = f"{key}:"
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        _, _, value = line.partition("=")
        return value.strip() or None
    return None


def configured_build_target(build_dir: pathlib.Path) -> str | None:
    return read_cmake_cache_value(build_dir, "IDF_TARGET")


def build_dir_conflicts_with_set_target(build_dir: pathlib.Path) -> bool:
    if not build_dir.is_dir():
        return False
    if build_dir_looks_like_cmake_build(build_dir):
        return False
    return any(build_dir.iterdir())


def timestamped_build_dir(build_dir: pathlib.Path) -> pathlib.Path:
    suffix = datetime.now().strftime("%Y%m%d%H%M")
    candidate = build_dir.with_name(f"{build_dir.name}-{suffix}")
    counter = 1
    while candidate.exists():
        candidate = build_dir.with_name(f"{build_dir.name}-{suffix}-{counter}")
        counter += 1
    return candidate


def clear_build_dir(build_dir: pathlib.Path) -> None:
    if not build_dir.is_dir():
        return
    shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)


def choose_build_dir_action(build_dir: pathlib.Path, *, dry_run: bool) -> str:
    if dry_run or not sys.stdin.isatty():
        return "new"

    prompt = (
        f"Build dir exists but is not an ESP-IDF build dir:\n"
        f"  {build_dir}\n"
        "Choose action: [c]lear dir or use [n]ew timestamped dir? "
    )
    while True:
        try:
            choice = input(prompt).strip().lower()
        except EOFError:
            return "new"
        if choice in {"c", "clear"}:
            return "clear"
        if choice in {"n", "new"}:
            return "new"
        print("Enter 'c' to clear or 'n' to use a new dir.")


def resolve_build_dir(build_dir: pathlib.Path, *, dry_run: bool) -> pathlib.Path:
    cleanup_stale_build_dir(build_dir)
    if not build_dir_conflicts_with_set_target(build_dir):
        return build_dir

    action = choose_build_dir_action(build_dir, dry_run=dry_run)
    if action == "clear":
        clear_build_dir(build_dir)
        print(f"    Cleared build dir: {build_dir}")
        return build_dir

    new_build_dir = timestamped_build_dir(build_dir)
    print(f"    Using new build dir: {new_build_dir}")
    return new_build_dir


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def load_idf_tools_module(idf_path: pathlib.Path) -> ModuleType:
    module_path = idf_path / "tools" / "idf_tools.py"
    if not module_path.is_file():
        raise SystemExit(f"ESP-IDF tools module not found: {module_path}")

    tools_path = str(module_path.parent)
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)

    spec = importlib.util.spec_from_file_location("light_pipeline_idf_tools", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load ESP-IDF tools module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def detect_idf_python(idf_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    idf_tools = load_idf_tools_module(idf_path)
    idf_tools.g.idf_path = str(idf_path)
    idf_tools.g.idf_tools_path = os.environ.get("IDF_TOOLS_PATH") or os.path.expanduser(
        idf_tools.IDF_TOOLS_PATH_DEFAULT
    )
    idf_python_env_path, _, virtualenv_python, _ = idf_tools.get_python_env_path()
    python_path = pathlib.Path(virtualenv_python).expanduser()
    if not python_path.is_file():
        raise SystemExit(
            "ESP-IDF Python virtual environment not found.\n"
            f"Expected: {python_path}\n"
            "Run esp-matter/install.sh or `python $IDF_PATH/tools/idf_tools.py install-python-env`."
        )
    return pathlib.Path(idf_python_env_path).expanduser(), python_path


def prepare_idf_command(
    command: list[str],
    *,
    idf_path: pathlib.Path,
    idf_python: pathlib.Path,
) -> list[str]:
    if command and command[0] == "idf.py":
        return [str(idf_python), str(idf_path / "tools" / "idf.py"), *command[1:]]
    return command


def apply_idf_exports(base_env: dict[str, str], export_text: str) -> dict[str, str]:
    env = base_env.copy()
    for line in export_text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not key or any(character.isspace() for character in key):
            continue
        if key == "PATH":
            value = value.replace("$PATH", env.get("PATH", ""))
        env[key] = value
    return env


def build_idf_environment(idf_path: pathlib.Path, idf_python_env_path: pathlib.Path, idf_python: pathlib.Path) -> dict[str, str]:
    env = os.environ.copy()
    env["ESP_MATTER_PATH"] = str(ESP_MATTER_ROOT)
    env["IDF_PATH"] = str(idf_path)
    env["IDF_PYTHON_ENV_PATH"] = str(idf_python_env_path)

    export_command = [
        str(idf_python),
        str(idf_path / "tools" / "idf_tools.py"),
        "export",
        "--format",
        "key-value",
    ]
    completed = subprocess.run(
        export_command,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return apply_idf_exports(env, completed.stdout)


def prepend_env_path(env: dict[str, str], *paths: pathlib.Path) -> dict[str, str]:
    current_path = env.get("PATH", "")
    path_parts = [str(path) for path in paths]
    if current_path:
        path_parts.append(current_path)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def build_matter_environment(base_env: dict[str, str]) -> dict[str, str]:
    env = base_env.copy()
    env["ESP_MATTER_PATH"] = str(ESP_MATTER_ROOT)
    env["ZAP_INSTALL_PATH"] = str(CHIP_ROOT / ".environment" / "cipd" / "packages" / "zap")
    env["_PW_ACTUAL_ENVIRONMENT_ROOT"] = str(CHIP_ROOT / ".environment")
    return prepend_env_path(
        env,
        CHIP_ROOT / ".environment" / "cipd" / "packages" / "pigweed",
        CHIP_ROOT / "out" / "host",
    )


def command_exists(command: str, env: dict[str, str]) -> bool:
    return shutil.which(command, path=env.get("PATH")) is not None


def command_requires_matter_bootstrap(command: list[str]) -> bool:
    if not command or command[0] != "idf.py":
        return False
    return any(part in {"set-target", "build", "reconfigure"} for part in command[1:])


def ensure_matter_bootstrap(
    env: dict[str, str],
    *,
    dry_run: bool = False,
    apply_repo_patches: bool = False,
) -> dict[str, str]:
    ensure_recursive_submodules()
    ensure_repo_patches_applied(apply=apply_repo_patches)
    prepared_env = build_matter_environment(env)
    if command_exists("gn", prepared_env):
        return prepared_env

    bootstrap_script = CHIP_ROOT / "scripts" / "bootstrap.sh"
    if not bootstrap_script.is_file():
        raise SystemExit(f"Matter bootstrap script not found: {bootstrap_script}")

    print("    Matter tooling missing `gn`; running bootstrap.sh -p all,esp32")
    try:
        subprocess.run(
            ["bash", str(bootstrap_script), "-p", "all,esp32"],
            cwd=CHIP_ROOT,
            check=True,
            env=prepared_env,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Failed to bootstrap Matter build environment.\n"
            f"Command: bash {bootstrap_script} -p all,esp32\n"
            f"Exit code: {exc.returncode}"
        ) from exc

    prepared_env = build_matter_environment(env)
    if not command_exists("gn", prepared_env):
        raise SystemExit(
            "Matter bootstrap completed, but `gn` is still missing from PATH.\n"
            f"Expected under: {CHIP_ROOT / '.environment' / 'cipd' / 'packages' / 'pigweed'}"
        )
    return prepared_env


def run_command(
    command: list[str],
    *,
    cwd: pathlib.Path,
    dry_run: bool,
    capture_output: bool = False,
    print_captured_output: bool = True,
    require_idf: bool = False,
    apply_repo_patches: bool = False,
) -> str:
    rendered = quote_command(command)
    print(f"    $ {rendered}")
    if dry_run:
        return ""

    try:
        if require_idf:
            idf_path = detect_idf_path()
            idf_python_env_path, idf_python = detect_idf_python(idf_path)
            env = build_idf_environment(idf_path, idf_python_env_path, idf_python)
            if command_requires_matter_bootstrap(command):
                env = ensure_matter_bootstrap(
                    env,
                    dry_run=dry_run,
                    apply_repo_patches=apply_repo_patches,
                )
            else:
                env = build_matter_environment(env)
            command = prepare_idf_command(command, idf_path=idf_path, idf_python=idf_python)
            completed = subprocess.run(
                command,
                cwd=cwd,
                check=True,
                text=True,
                capture_output=capture_output,
                env=env,
            )
        else:
            completed = subprocess.run(
                command,
                cwd=cwd,
                check=True,
                text=True,
                capture_output=capture_output,
            )
    except subprocess.CalledProcessError as exc:
        details = []
        if exc.stdout:
            details.append(exc.stdout.strip())
        if exc.stderr:
            details.append(exc.stderr.strip())
        message = f"Command failed with exit code {exc.returncode}: {rendered}"
        if details:
            message = f"{message}\n" + "\n".join(detail for detail in details if detail)
        raise SystemExit(message) from exc

    if capture_output:
        stdout = completed.stdout.strip()
        if stdout and print_captured_output:
            print(stdout)
        return stdout
    return ""


def step_banner(index: int, total: int, title: str) -> None:
    print(f"[{index}/{total}] {title}")


def resolve_terminal_output_rows(
    *,
    devices_csv: pathlib.Path,
    serial: str | None,
    serial_index: int | None,
) -> list[dict[str, str]]:
    rows = load_device_rows(devices_csv)
    if serial is not None or serial_index is not None:
        if serial is not None:
            for row in rows:
                if row["serial_num"] == serial:
                    return [row]
            raise SystemExit(f"Serial not found in devices CSV: {serial}")
        if serial_index is not None:
            if not 1 <= serial_index <= len(rows):
                raise SystemExit(f"--serial-index must be between 1 and {len(rows)}")
            return [rows[serial_index - 1]]
    return rows


def resolve_svg_output_paths(
    *,
    devices_csv: pathlib.Path,
    label_output_dir: pathlib.Path,
    serial: str | None,
    serial_index: int | None,
) -> list[pathlib.Path]:
    rows = resolve_terminal_output_rows(
        devices_csv=devices_csv,
        serial=serial,
        serial_index=serial_index,
    )
    return [label_output_dir / f"{row['serial_num']}.svg" for row in rows]


def load_segno_module() -> ModuleType | None:
    try:
        import segno  # type: ignore
    except Exception:
        return None
    return segno


def print_qr_svgs_to_terminal(
    *,
    devices_csv: pathlib.Path,
    label_output_dir: pathlib.Path,
    serial: str | None,
    serial_index: int | None,
) -> None:
    svg_paths = resolve_svg_output_paths(
        devices_csv=devices_csv,
        label_output_dir=label_output_dir,
        serial=serial,
        serial_index=serial_index,
    )
    existing_paths = [path for path in svg_paths if path.is_file()]
    if not existing_paths:
        return

    for path in existing_paths:
        print(f"QR SVG ({path.name}):")
        print(path.read_text(encoding="utf-8"))


def print_qr_codes_to_terminal(
    *,
    devices_csv: pathlib.Path,
    serial: str | None,
    serial_index: int | None,
) -> None:
    segno_module = load_segno_module()
    if segno_module is None:
        return

    rows = resolve_terminal_output_rows(
        devices_csv=devices_csv,
        serial=serial,
        serial_index=serial_index,
    )
    for row in rows:
        qr = segno_module.make(row["qrcode"])
        rendered = io.StringIO()
        qr.terminal(out=rendered)
        print(f"QR Terminal ({row['serial_num']}):")
        print(rendered.getvalue().rstrip())


def build_manifest_command(args: argparse.Namespace, manifest_path: pathlib.Path) -> list[str]:
    command = [
        sys.executable,
        str(TOOLS_DIR / "generate_device_manifest.py"),
        "--count",
        str(args.count),
        "--output",
        str(manifest_path),
        "--serial-prefix",
        args.serial_prefix,
        "--start-index",
        str(args.start_index),
        "--serial-width",
        str(args.serial_width),
        "--discriminator-start",
        str(args.discriminator_start),
        "--vendor-id",
        args.vendor_id,
        "--product-id",
        args.product_id,
        "--hw-ver",
        args.hw_ver,
        "--hw-ver-str",
        args.hw_ver_str,
    ]
    if args.mfg_date:
        command.extend(["--mfg-date", args.mfg_date])
    return command


def build_idf_command(build_dir: pathlib.Path, override_path: pathlib.Path, target: str) -> list[str]:
    sdkconfig_defaults = ";".join(
        [
            str(DEFAULT_BASE_SDKCONFIG),
            str(DEFAULT_THREAD_SDKCONFIG),
            str(override_path),
        ]
    )
    command = [
        "idf.py",
        "-B",
        str(build_dir),
        "-D",
        f"SDKCONFIG_DEFAULTS={sdkconfig_defaults}",
    ]
    if configured_build_target(build_dir) == target:
        command.extend(["reconfigure", "build"])
    else:
        command.extend(["set-target", target, "build"])
    return command


def build_factory_data_command(args: argparse.Namespace, manifest_path: pathlib.Path, output_dir: pathlib.Path) -> list[str]:
    command = [
        resolve_tool_python(),
        str(TOOLS_DIR / "generate_factory_data.py"),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(output_dir),
        "--vendor-name",
        args.vendor_name,
        "--product-name",
        args.product_name,
        "--target",
        args.target,
    ]
    if args.use_test_attestation:
        command.append("--use-test-attestation")
    return command


def generated_attestation_output_dir(output_dir: pathlib.Path) -> pathlib.Path:
    return output_dir / "attestation"


def generated_attestation_manifest_path(output_dir: pathlib.Path) -> pathlib.Path:
    return generated_attestation_output_dir(output_dir) / "manifest_with_attestation.csv"


def should_generate_attestation_assets(args: argparse.Namespace) -> bool:
    return args.dac_provider == "factory" and not args.use_test_attestation


def build_attestation_generation_command(
    args: argparse.Namespace,
    manifest_path: pathlib.Path,
    output_dir: pathlib.Path,
) -> list[str]:
    attestation_output_dir = generated_attestation_output_dir(output_dir)
    command = [
        sys.executable,
        str(TOOLS_DIR / "generate_attestation_chain.py"),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(attestation_output_dir),
        "--manifest-out",
        str(generated_attestation_manifest_path(output_dir)),
        "--vendor-name",
        args.vendor_name,
        "--product-name",
        args.product_name,
    ]
    return command


def build_label_commands(args: argparse.Namespace, output_dir: pathlib.Path) -> list[list[str]]:
    devices_csv = output_dir / "devices.csv"
    asset_command = [
        sys.executable,
        str(TOOLS_DIR / "generate_label_assets.py"),
        "--devices-csv",
        str(devices_csv),
        "--output-dir",
        str(pathlib.Path(args.label_output_dir).resolve()),
    ]
    if args.label_csv:
        asset_command.extend(["--label-csv", str(pathlib.Path(args.label_csv).resolve())])
    if args.render_qr_svg:
        asset_command.append("--render-qr-svg")

    html_command = [
        sys.executable,
        str(TOOLS_DIR / "generate_label_html.py"),
        "--devices-csv",
        str(devices_csv),
        "--output",
        str(pathlib.Path(args.label_html).resolve()),
    ]
    return [asset_command, html_command]


def build_flash_generation_command(
    *,
    output_dir: pathlib.Path,
    build_dir: pathlib.Path,
    port: str,
    baud: str,
    serial: str | None,
    serial_index: int | None,
) -> list[str]:
    command = [
        resolve_tool_python(),
        str(TOOLS_DIR / "generate_flash_command.py"),
        "--devices-csv",
        str(output_dir / "devices.csv"),
        "--port",
        port,
        "--build-dir",
        str(build_dir),
        "--baud",
        baud,
        "--partitions-csv",
        str(DEFAULT_PARTITIONS_CSV),
        "--no-prompt",
    ]
    if serial:
        command.extend(["--serial", serial])
    else:
        command.extend(["--serial-index", str(serial_index or 1)])
    return command


def build_monitor_command(build_dir: pathlib.Path, port: str) -> list[str]:
    return [
        "idf.py",
        "-B",
        str(build_dir),
        "-p",
        port,
        "monitor",
    ]


def build_erase_command(build_dir: pathlib.Path, port: str) -> list[str]:
    return [
        "idf.py",
        "-B",
        str(build_dir),
        "-p",
        port,
        "erase-flash",
    ]


def validate_run_args(args: argparse.Namespace, manifest_path: pathlib.Path) -> None:
    vendor_id = getattr(args, "vendor_id", None)
    product_id = getattr(args, "product_id", None)
    if vendor_id is not None and product_id is not None:
        validate_dac_provider_config(
            dac_provider=args.dac_provider,
            vendor_id=vendor_id,
            product_id=product_id,
        )
    if args.use_test_attestation and args.dac_provider != "factory":
        raise SystemExit("--use-test-attestation requires --dac-provider factory")
    if args.use_test_attestation:
        if args.count is not None:
            validate_test_attestation_pair(
                vendor_id=args.vendor_id,
                product_id=args.product_id,
            )
        elif manifest_path.is_file():
            validate_test_attestation_manifest(manifest_path)
    if args.count is None and not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}. Pass --count to generate one.")
    if (args.flash or args.monitor) and not args.port:
        raise SystemExit("--port required with --flash or --monitor")


def should_open_post_flash_monitor(*, should_flash: bool, auto_open: bool, explicit_monitor: bool) -> bool:
    if not should_flash:
        return False
    return explicit_monitor


def run_pipeline(args: argparse.Namespace) -> int:
    ensure_example_tree()

    manifest_path = pathlib.Path(args.manifest).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()
    build_dir = pathlib.Path(args.build_dir).resolve()
    validate_run_args(args, manifest_path)
    should_flash = bool(args.port)
    should_monitor = should_open_post_flash_monitor(
        should_flash=should_flash,
        auto_open=False,
        explicit_monitor=args.monitor,
    )
    factory_manifest_path = manifest_path

    steps: list[tuple[str, Callable[[], object]]] = []
    monitor_action: Callable[[], object] | None = None
    if args.count is not None:
        steps.append(("Generate manifest with unique passcodes and discriminators", lambda: run_command(
            build_manifest_command(args, manifest_path),
            cwd=PROJECT_ROOT,
            dry_run=args.dry_run,
        )))
    if should_generate_attestation_assets(args):
        factory_manifest_path = generated_attestation_manifest_path(output_dir)
        steps.append(("Generate development attestation assets", lambda: run_command(
            build_attestation_generation_command(args, manifest_path, output_dir),
            cwd=PROJECT_ROOT,
            dry_run=args.dry_run,
        )))
    if not args.skip_build:
        build_dir = resolve_build_dir(build_dir, dry_run=args.dry_run)
        override_path = write_build_override(
            build_dir=build_dir,
            vendor_id=args.vendor_id,
            product_id=args.product_id,
            dac_provider=args.dac_provider,
        )
        steps.append(("Build Thread-only firmware", lambda: run_command(
            build_idf_command(build_dir, override_path, args.target),
            cwd=EXAMPLE_DIR,
            dry_run=args.dry_run,
            require_idf=True,
            apply_repo_patches=getattr(args, "apply_patches", False),
        )))
    steps.append(("Generate factory data and onboarding codes", lambda: run_command(
        build_factory_data_command(args, factory_manifest_path, output_dir),
        cwd=PROJECT_ROOT,
        dry_run=args.dry_run,
        require_idf=True,
    )))
    if not args.skip_labels:
        label_commands = build_label_commands(args, output_dir)
        steps.append(("Generate labels", lambda: [run_command(
            command,
            cwd=PROJECT_ROOT,
            dry_run=args.dry_run,
        ) for command in label_commands]))
    if should_flash:
        if args.erase:
            steps.append(("Erase flash", lambda: run_command(
                build_erase_command(build_dir, args.port),
                cwd=EXAMPLE_DIR,
                dry_run=args.dry_run,
                require_idf=True,
            )))

        def flash_device() -> None:
            flash_command_text = run_command(
                build_flash_generation_command(
                    output_dir=output_dir,
                    build_dir=build_dir,
                    port=args.port,
                    baud=args.baud,
                    serial=args.serial,
                    serial_index=args.serial_index,
                ),
                cwd=PROJECT_ROOT,
                dry_run=args.dry_run,
                capture_output=True,
                print_captured_output=False,
                require_idf=True,
            )
            if flash_command_text:
                run_command(
                    shlex.split(flash_command_text),
                    cwd=EXAMPLE_DIR,
                    dry_run=args.dry_run,
                    require_idf=True,
                )

        steps.append(("Flash selected device", flash_device))
        if should_monitor:
            monitor_action = lambda: run_command(
                build_monitor_command(build_dir, args.port),
                cwd=EXAMPLE_DIR,
                dry_run=args.dry_run,
                require_idf=True,
            )

    total_steps = len(steps) + (1 if monitor_action is not None else 0)
    for index, (title, action) in enumerate(steps, start=1):
        step_banner(index, total_steps, title)
        action()

    print(f"Manifest: {manifest_path}")
    print(f"Build dir: {build_dir}")
    print(f"Factory output: {output_dir}")
    print(f"Devices CSV: {output_dir / 'devices.csv'}")
    if not args.skip_labels:
        print(f"Label assets: {pathlib.Path(args.label_output_dir).resolve()}")
        print(f"Label HTML: {pathlib.Path(args.label_html).resolve()}")
        if args.render_qr_svg:
            print_qr_codes_to_terminal(
                devices_csv=output_dir / "devices.csv",
                serial=args.serial,
                serial_index=args.serial_index,
            )
            print_qr_svgs_to_terminal(
                devices_csv=output_dir / "devices.csv",
                label_output_dir=pathlib.Path(args.label_output_dir).resolve(),
                serial=args.serial,
                serial_index=args.serial_index,
            )
    if monitor_action is not None:
        step_banner(total_steps, total_steps, "Open serial monitor")
        monitor_action()
    return 0


def flash_only(args: argparse.Namespace) -> int:
    ensure_example_tree()
    output_dir = pathlib.Path(args.output_dir).resolve()
    build_dir = pathlib.Path(args.build_dir).resolve()

    should_monitor = should_open_post_flash_monitor(
        should_flash=True,
        auto_open=False,
        explicit_monitor=args.monitor,
    )

    steps = []
    monitor_action: Callable[[], object] | None = None
    if args.erase:
        steps.append(("Erase flash", lambda: run_command(
            build_erase_command(build_dir, args.port),
            cwd=EXAMPLE_DIR,
            dry_run=args.dry_run,
            require_idf=True,
        )))

    def flash_device() -> None:
        flash_command_text = run_command(
            build_flash_generation_command(
                output_dir=output_dir,
                build_dir=build_dir,
                port=args.port,
                baud=args.baud,
                serial=args.serial,
                serial_index=args.serial_index,
            ),
            cwd=PROJECT_ROOT,
            dry_run=args.dry_run,
            capture_output=True,
            print_captured_output=False,
            require_idf=True,
        )
        if flash_command_text:
            run_command(
                shlex.split(flash_command_text),
                cwd=EXAMPLE_DIR,
                dry_run=args.dry_run,
                require_idf=True,
            )

    steps.append(("Flash selected device", flash_device))
    if should_monitor:
        monitor_action = lambda: run_command(
            build_monitor_command(build_dir, args.port),
            cwd=EXAMPLE_DIR,
            dry_run=args.dry_run,
            require_idf=True,
        )

    total_steps = len(steps) + (1 if monitor_action is not None else 0)
    for index, (title, action) in enumerate(steps, start=1):
        step_banner(index, total_steps, title)
        action()
    if monitor_action is not None:
        step_banner(total_steps, total_steps, "Open serial monitor")
        monitor_action()
    return 0


def list_targets(args: argparse.Namespace) -> int:
    output_dir = pathlib.Path(args.output_dir).resolve()
    command = [
        resolve_tool_python(),
        str(TOOLS_DIR / "generate_flash_command.py"),
        "--devices-csv",
        str(output_dir / "devices.csv"),
        "--list-only",
    ]
    run_command(
        command,
        cwd=PROJECT_ROOT,
        dry_run=args.dry_run,
    )
    return 0


def doctor(args: argparse.Namespace) -> int:
    ensure_example_tree()
    build_dir = pathlib.Path(args.build_dir).resolve()
    idf_path = detect_idf_path()
    idf_python_env_path, idf_python = detect_idf_python(idf_path)
    missing_submodules = list_missing_submodules()

    print("1. Repo root")
    print(f"   {PROJECT_ROOT}")
    print("2. ESP-Matter root")
    print(f"   {ESP_MATTER_ROOT}")
    print("3. Light example")
    print(f"   {EXAMPLE_DIR}")
    print("4. ESP-IDF")
    print(f"   {idf_path}")
    print("5. Build dir")
    print(f"   {build_dir}")
    print("6. Thread defaults")
    print(f"   {DEFAULT_THREAD_SDKCONFIG}")
    print("7. IDF Python env")
    print(f"   {idf_python_env_path}")
    print("8. IDF Python")
    print(f"   {idf_python}")
    print("9. Recursive submodules")
    if missing_submodules:
        print(f"   missing: {len(missing_submodules)}")
        for entry in missing_submodules[:5]:
            print(f"   - {entry}")
        if len(missing_submodules) > 5:
            print(f"   ... and {len(missing_submodules) - 5} more")
    else:
        print("   OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "doctor":
        return doctor(args)
    if args.command == "run":
        return run_pipeline(args)
    if args.command == "flash":
        return flash_only(args)
    if args.command == "list":
        return list_targets(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
