# CI And Releases

This repo ships two GitHub workflows:

- `python-tools-ci.yml`
  Runs repo-local Python tests and entrypoint smoke checks for `tools/`.
- `light-firmware-build.yml`
  Builds base `esp-matter/examples/light` firmware for `esp32c6`, uploads a CI artifact, and publishes the same bundle on version tags like `v1.2.3`.

## What The Firmware Build Produces

The firmware workflow builds:

- `build/light-c6-thread/`
- `flasher_args.json` and the firmware binaries referenced by it
- `provisioning-support/connectedhomeip/`
- a release tarball: `light-c6-thread-build.tar.gz`

This is a base firmware build, not a per-device commissioned release bundle.

It does **not** include:

- per-device factory partitions
- onboarding codes
- device-specific labels
- generated DAC/PAI/CD material

Those are intentionally generated later from `tools/`.

## How To Use Released Core Build

1. Download `light-c6-thread-build.tar.gz` from GitHub Actions artifacts or the GitHub Release page.
2. Extract it under repo root so you get:

- `build/light-c6-thread/`
- `provisioning-support/connectedhomeip/`

3. Generate device-specific data:

```bash
python3 tools/light_pipeline.py run \
  --count 8 \
  --skip-build \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

4. Flash one generated device:

```bash
python3 tools/light_pipeline.py flash \
  --build-dir build/light-c6-thread \
  --output-dir tools/out \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

## Why Split Build From Provisioning

This split keeps CI artifacts reusable:

- firmware build only needs source + toolchain
- per-device provisioning stays local and reproducible
- users do not need to rebuild the full firmware for every manufactured device
- `run --skip-build` can provision from the extracted bundle without initializing git submodules first

## Notes

- `run --skip-build` can reuse `provisioning-support/connectedhomeip` from the release bundle when `esp-matter/` is not checked out.
- direct flashing still works from the extracted build tree because it uses generated `esptool.py` commands.
- `--erase` and serial monitor still require the full `esp-matter/examples/light` checkout.
- factory-mode custom attestation may still need a working `chip-cert` binary if you generate your own DAC/PAI/CD assets.
- repo patches under `patches/` stay non-mutating by default; use `--apply-patches` if you explicitly need them applied before build.
- `tools/device_manifest.csv` reuse remains default when present. Delete it or change `--manifest` path if you want a fresh manifest.
