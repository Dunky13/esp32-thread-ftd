# Light Pipeline

User-facing entrypoint: `tools/light_pipeline.py`

The pipeline shells into ESP-IDF automatically after it finds `IDF_PATH`. No manual `source export.sh` step needed.
If Matter tooling such as `gn` is missing, the pipeline also runs CHIP bootstrap automatically before the firmware build step.
If nested git submodules under `esp-matter/connectedhomeip` are missing, the pipeline also runs `git submodule update --init --recursive` from repo root before the build step.
If repo patch files exist under top-level `patches/`, the pipeline reports them but does not apply them. `esp-matter/` stays untouched by `light_pipeline.py` execution.

Target flow:

- `esp-matter/examples/light`
- `esp32c6`
- Wi-Fi disabled
- Thread enabled
- custom vendor/product IDs
- unique passcodes, discriminators, rotating IDs per generated device

## Steps

1. Check environment:

```bash
python3 tools/light_pipeline.py doctor
```

2. Run full pipeline:

```bash
python3 tools/light_pipeline.py run \
  --count 8 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

What step 2 does:

1. regenerates manifest with unique pairing data
2. auto-generates development DAC/PAI/CD assets when `--dac-provider factory` is used without `--use-test-attestation`
3. builds `examples/light` for ESP32-C6 with Thread on and Wi-Fi off
4. enables factory-backed commissioning/device info
5. generates per-device factory partitions
6. generates `tools/out/devices.csv`
7. generates text labels and printable HTML labels

3. Flash one generated device:

```bash
python3 tools/light_pipeline.py flash \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

Or do build + provision + flash in one run:

```bash
python3 tools/light_pipeline.py run \
  --count 8 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light" \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

When `run` gets `--port`, it flashes automatically. `--flash` remains accepted but no longer needed.

## Notes

- Default DAC mode is `example`. It only works with Matter test VID/PID ranges `0xFFF1-0xFFF3` and `0x8000-0x801F`.
- If you want custom VID/PID values, use `--dac-provider factory`. The pipeline now generates a development PAA/PAI/DAC chain plus test CD automatically and feeds a sidecar manifest into provisioning.
- Generated development attestation assets land under `tools/out/attestation/`.
- If you already have your own DAC/PAI/CD files, you can still run `tools/generate_factory_data.py` directly with a manifest that includes `dac_cert,dac_key,pai_cert,cd`.
- `--use-test-attestation` is only for factory mode when your VID/PID matches exact CHIP test credentials shipped in `connectedhomeip`.
- Build output goes to `build/light-c6-thread`.
- Generated provisioning output goes to `tools/out/`.
- `generate_factory_data.py` auto-installs missing CHIP setup-payload Python deps into active tool Python env. Use `--no-auto-install-deps` to force fail-fast behavior.
- `--render-qr-svg` auto-installs `segno` into active tool Python env when missing, renders SVG QR labels, and prints terminal QR + SVG output before opening serial monitor.
- `tools/run_workflow.py` still works. It now forwards to `light_pipeline.py`.

## Internal Scripts

These still exist, but are internal building blocks now:

- `generate_device_manifest.py`
- `generate_attestation_chain.py`
- `generate_factory_data.py`
- `generate_flash_command.py`
- `generate_label_assets.py`
- `generate_label_html.py`
