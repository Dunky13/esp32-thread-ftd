from __future__ import annotations

import os
import pathlib


TOOLS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
ESP_MATTER_ROOT = PROJECT_ROOT / "esp-matter"
EXAMPLE_DIR = ESP_MATTER_ROOT / "examples" / "light"
CHIP_ROOT = ESP_MATTER_ROOT / "connectedhomeip" / "connectedhomeip"
PROVISIONING_SUPPORT_ROOT = PROJECT_ROOT / "provisioning-support"
PROVISIONING_CHIP_ROOT = PROVISIONING_SUPPORT_ROOT / "connectedhomeip"

DEFAULT_MANIFEST_PATH = TOOLS_DIR / "device_manifest.csv"
DEFAULT_OUTPUT_DIR = TOOLS_DIR / "out"
DEFAULT_DEVICES_CSV_PATH = DEFAULT_OUTPUT_DIR / "devices.csv"
DEFAULT_LABEL_OUTPUT_DIR = TOOLS_DIR / "labels"
DEFAULT_LABEL_HTML_PATH = TOOLS_DIR / "matter-labels.html"
DEFAULT_PARTITIONS_CSV = TOOLS_DIR / "light_partitions_8mb.csv"

DEFAULT_BUILD_DIR = PROJECT_ROOT / "build" / "light-c6-thread"


def _iter_chip_root_candidates() -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    override = os.environ.get("ESP_MATTER_CHIP_ROOT")
    if override:
        candidates.append(pathlib.Path(override).expanduser().resolve())
    candidates.extend([CHIP_ROOT, PROVISIONING_CHIP_ROOT])
    return candidates


def resolve_chip_root(*, require: bool = False) -> pathlib.Path:
    for candidate in _iter_chip_root_candidates():
        if candidate.is_dir():
            return candidate
    if require:
        checked = "\n".join(f"  - {candidate}" for candidate in _iter_chip_root_candidates())
        raise SystemExit(
            "Matter provisioning assets not found.\n"
            "Checked:\n"
            f"{checked}\n"
            "Initialize submodules or extract a release bundle that includes "
            "`provisioning-support/connectedhomeip`."
        )
    return CHIP_ROOT


def resolve_factory_generator_path(*, chip_root: pathlib.Path | None = None) -> pathlib.Path:
    active_chip_root = chip_root if chip_root is not None else resolve_chip_root()
    return active_chip_root / "scripts" / "tools" / "generate_esp32_chip_factory_bin.py"


def resolve_setuppayload_requirements_path(*, chip_root: pathlib.Path | None = None) -> pathlib.Path:
    active_chip_root = chip_root if chip_root is not None else resolve_chip_root()
    return active_chip_root / "scripts" / "setup" / "requirements.setuppayload.txt"


def resolve_default_chip_cert_path(*, chip_root: pathlib.Path | None = None) -> pathlib.Path:
    active_chip_root = chip_root if chip_root is not None else resolve_chip_root()
    return active_chip_root / "out" / "host" / "chip-cert"


DEFAULT_FACTORY_GENERATOR = resolve_factory_generator_path()
DEFAULT_CHIP_CERT = resolve_default_chip_cert_path()
