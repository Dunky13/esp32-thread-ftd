# CLI

This page summarizes `light_pipeline.py` commands and options.

## Top-Level Commands

- `doctor`
- `run`
- `flash`
- `list`

## `doctor`

```bash
python3 tools/light_pipeline.py doctor [--build-dir BUILD_DIR]
```

Purpose:

- validate repo paths
- detect ESP-IDF

Option:

- `--build-dir`
  - build directory to inspect
  - default: `build/light-c6-thread`

## `run`

```bash
python3 tools/light_pipeline.py run [options]
```

### Manifest Options

- `--manifest`
  - manifest CSV path
  - default: `tools/device_manifest.csv`
- `--count`
  - generate manifest with this many devices
- `--serial-prefix`
  - default: `LGT`
- `--start-index`
  - default: `1`
- `--serial-width`
  - default: `4`
- `--discriminator-start`
  - default: `3840`
- `--hw-ver`
  - default: `1`
- `--hw-ver-str`
  - default: `1.0`
- `--mfg-date`
  - manufacturing date in `YYYY-MM-DD`

### Identity Options

- `--vendor-id`
  - default: `0xFFF1`
- `--product-id`
  - default: `0x8000`
- `--vendor-name`
  - default: `ESP-C6-Matter`
- `--product-name`
  - default: `Thread Light`

### Build And Output Options

- `--output-dir`
  - default: `tools/out`
- `--build-dir`
  - default: `build/light-c6-thread`
- `--target`
  - default: `esp32c6`
- `--skip-build`
- `--skip-labels`
- `--dry-run`

### Attestation Options

- `--dac-provider {example,factory}`
  - default: `example`
- `--use-test-attestation`

### Label Options

- `--label-output-dir`
  - default: `tools/labels`
- `--label-html`
  - default: `tools/matter-labels.html`
- `--label-csv`
- `--render-qr-svg`

### Patch Option

- `--apply-patches`
  - apply repo patch files under `patches/` to `esp-matter/` before build
  - omitted by default, so patches are only reported

### Flash Options Accepted By `run`

- `--port`
- `--serial`
- `--serial-index`
  - default: `1`
- `--baud`
  - default: `921600`
- `--erase`
- `--monitor`
- `--flash`
  - deprecated compatibility flag

## `flash`

```bash
python3 tools/light_pipeline.py flash --port PORT [options]
```

Purpose:

- flash one generated device using existing build + provisioning outputs

Options:

- `--port`
- `--serial`
- `--serial-index`
- `--baud`
- `--erase`
- `--monitor`
- `--build-dir`
- `--output-dir`
- `--dry-run`

## `list`

```bash
python3 tools/light_pipeline.py list [--output-dir OUTPUT_DIR] [--dry-run]
```

Purpose:

- list generated device serials
- list detected serial ports

## Useful Examples

Check environment:

```bash
python3 tools/light_pipeline.py doctor
```

Build one test device:

```bash
python3 tools/light_pipeline.py run --count 1
```

Build with custom identity:

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --dac-provider factory \
  --vendor-id 0x1234 \
  --product-id 0x5678
```

Flash first generated row:

```bash
python3 tools/light_pipeline.py flash --port /dev/ttyUSB0 --serial-index 1
```

## Related Docs

- pipeline behavior: [`pipeline.md`](./pipeline.md)
- manifest fields: [`manifest.md`](./manifest.md)
- commissioning flow: [`commissioning.md`](./commissioning.md)
- troubleshooting: [`troubleshooting.md`](./troubleshooting.md)
