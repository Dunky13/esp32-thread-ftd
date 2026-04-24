# ESP32-C6 Full Thread Device Light

Build, provision, label, and flash a Full Thread Device (FTD) Thread-only Matter light on ESP32-C6 with one CLI.

Main script: [`tools/light_pipeline.py`](./tools/light_pipeline.py)

Docs index: [`docs/README.md`](./docs/README.md)

## What This Repo Does

This repo adds reproducible automation around upstream [`esp-matter`](./esp-matter) for one target flow:

- firmware source: `esp-matter/examples/light`
- chip target: `esp32c6`
- network mode: Thread enabled, Wi-Fi disabled
- flash layout: 8 MB via [`tools/light_partitions_8mb.csv`](./tools/light_partitions_8mb.csv)
- provisioning model: one manifest row per device with unique pairing data

Result:

1. build firmware
2. generate factory partition
3. generate onboarding codes
4. generate printable labels
5. flash device

## Tested Hardware

Tested on:

- Waveshare [ESP32-C6-Zero](https://www.waveshare.com/esp32-c6-zero.htm)
- Waveshare product page lists it as based on `ESP32-C6FH8`
- 8 MB flash layout used by this repo

## Quick Start

### 1. Install host tools

Install these first:

- Python 3: <https://www.python.org/downloads/>
- Git: <https://git-scm.com/downloads>
- ESP-IDF / EIM: <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/> and <https://docs.espressif.com/projects/idf-im-cli/en/latest/>

### 2. Clone and init submodules

```bash
git clone <your-repo-url>
cd esp32-c6-matter
git submodule update --init --recursive
```

### 3. Install upstream ESP-Matter dependencies

```bash
cd esp-matter
./install.sh
cd ..
```

### 4. Generate `eim_config.toml`

Recommended: install ESP-IDF with Espressif Installation Manager (`eim`), then save or export its config as `eim_config.toml` in repo root.

If you do not want full exported config, minimal file also works:

```toml
idf_path = "/Users/<you>/.espressif/v5.5.2/esp-idf"
```

Repo tools read `eim_config.toml` before `IDF_PATH`.

Check detection with:

```bash
python3 tools/detect_env_paths.py
```

### 5. Verify environment

```bash
python3 tools/light_pipeline.py doctor
```

### 6. Build and provision one device

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

### 7. Flash it

```bash
python3 tools/light_pipeline.py flash \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

Use `--dry-run` first if you want command preview without changing anything.

## Common Commands

Check environment:

```bash
python3 tools/light_pipeline.py doctor
```

Build 8 devices:

```bash
python3 tools/light_pipeline.py run \
  --count 8 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

Build and flash in one go:

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light" \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

List generated devices and detected serial ports:

```bash
python3 tools/light_pipeline.py list
```

## Read Next

- setup and first run: [`docs/getting-started.md`](./docs/getting-started.md)
- pipeline behavior: [`docs/pipeline.md`](./docs/pipeline.md)
- vendor ID, product ID, DAC, PAI, PAA, CD: [`docs/identity-and-attestation.md`](./docs/identity-and-attestation.md)
- commissioning after flash: [`docs/commissioning.md`](./docs/commissioning.md)
- manifest schema: [`docs/manifest.md`](./docs/manifest.md)
- CLI options: [`docs/cli.md`](./docs/cli.md)
- generated outputs: [`docs/outputs.md`](./docs/outputs.md)
- helper scripts: [`docs/internal-scripts.md`](./docs/internal-scripts.md)
- version assumptions: [`docs/version-compatibility.md`](./docs/version-compatibility.md)
- security and generated secrets: [`docs/security-and-generated-secrets.md`](./docs/security-and-generated-secrets.md)
- maintenance and clean rebuilds: [`docs/maintenance.md`](./docs/maintenance.md)
- upstream submodule and patches: [`docs/upstream-and-patches.md`](./docs/upstream-and-patches.md)
- examples: [`docs/examples.md`](./docs/examples.md)
- troubleshooting: [`docs/troubleshooting.md`](./docs/troubleshooting.md)

## Notes

- `tools/device_manifest.csv` is reused if it already exists
- `--count` does not overwrite existing manifest automatically
- `--port` on `run` triggers flashing automatically
- `--flash` is deprecated compatibility flag
- repo is configured around 8 MB flash target
