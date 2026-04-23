from __future__ import annotations

import pathlib


TOOLS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
ESP_MATTER_ROOT = PROJECT_ROOT / "esp-matter"
EXAMPLE_DIR = ESP_MATTER_ROOT / "examples" / "light"
CHIP_ROOT = ESP_MATTER_ROOT / "connectedhomeip" / "connectedhomeip"

DEFAULT_MANIFEST_PATH = TOOLS_DIR / "device_manifest.csv"
DEFAULT_OUTPUT_DIR = TOOLS_DIR / "out"
DEFAULT_DEVICES_CSV_PATH = DEFAULT_OUTPUT_DIR / "devices.csv"
DEFAULT_LABEL_OUTPUT_DIR = TOOLS_DIR / "labels"
DEFAULT_LABEL_HTML_PATH = TOOLS_DIR / "matter-labels.html"
DEFAULT_PARTITIONS_CSV = TOOLS_DIR / "light_partitions_8mb.csv"

DEFAULT_BUILD_DIR = PROJECT_ROOT / "build" / "light-c6-thread"
DEFAULT_FACTORY_GENERATOR = (
    CHIP_ROOT / "scripts" / "tools" / "generate_esp32_chip_factory_bin.py"
)
DEFAULT_CHIP_CERT = CHIP_ROOT / "out" / "host" / "chip-cert"
