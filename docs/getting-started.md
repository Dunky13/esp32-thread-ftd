# Getting Started

This page covers first setup and first successful device run.

## Prerequisites

You need:

- `git`
- `python3`
- ESP-IDF installed locally
- serial port access for flashing

Recommended host OS:

- macOS
- Linux

Official install pages:

- Python 3: <https://www.python.org/downloads/>
- Git: <https://git-scm.com/downloads>
- ESP-IDF / EIM: <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/> and <https://docs.espressif.com/projects/idf-im-cli/en/latest/>

## 1. Clone repo

```bash
git clone <your-repo-url>
cd esp32-c6-matter
git submodule update --init --recursive
```

## 2. Install upstream ESP-Matter dependencies

```bash
cd esp-matter
./install.sh
cd ..
```

## 3. Generate `eim_config.toml`

Recommended flow:

1. install ESP-IDF with Espressif Installation Manager (`eim`)
2. at end of EIM wizard, save or export config file
3. copy that file to repo root as `eim_config.toml`

Minimal repo-local config also works if you only want path detection:

```toml
idf_path = "/Users/<you>/.espressif/v5.5.2/esp-idf"
```

Repo tooling checks `eim_config.toml` before `IDF_PATH`.

## 4. Check environment detection

```bash
python3 tools/detect_env_paths.py
python3 tools/light_pipeline.py doctor
```

If you want shell exports:

```bash
python3 tools/detect_env_paths.py
python3 tools/detect_env_paths.py --activate-shell
```

ESP-IDF detection order:

1. `eim_config.toml`
2. `IDF_PATH`
3. common install locations such as `~/esp-idf`, `~/esp/esp-idf`, and `~/.espressif/.../esp-idf`

## 5. Build and provision one device

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

This does:

1. generate or reuse manifest
2. build firmware
3. generate factory data
4. generate onboarding data
5. generate labels

## 6. Flash one device

```bash
python3 tools/light_pipeline.py flash \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

## 7. One-command build and flash

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

## Safe Preview

Use `--dry-run` before erase or flash operations:

```bash
python3 tools/light_pipeline.py run --count 1 --dry-run
python3 tools/light_pipeline.py flash --port /dev/ttyUSB0 --serial-index 1 --dry-run
```

## Read Next

- hardware assumptions: [`hardware.md`](./hardware.md)
- pipeline behavior: [`pipeline.md`](./pipeline.md)
- CLI options: [`cli.md`](./cli.md)
