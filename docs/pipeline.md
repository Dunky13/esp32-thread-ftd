# Pipeline

This page explains what `tools/light_pipeline.py` does.

## Main Entrypoint

User-facing CLI:

- `python3 tools/light_pipeline.py`

Compatibility wrapper:

- `python3 tools/run_workflow.py`
- forwards to `light_pipeline.py run`

## High-Level Flow

`light_pipeline.py run` executes this sequence:

1. validate CLI args
2. verify repo structure
3. detect ESP-IDF
4. initialize missing recursive submodules
5. optionally apply patch files from top-level `patches/` into `esp-matter/` when `--apply-patches` is passed
6. bootstrap Matter tooling if `gn` is missing
7. generate manifest if `--count` was passed
8. optionally generate development attestation assets
9. build firmware unless `--skip-build`
10. generate factory data and onboarding codes
11. generate labels unless `--skip-labels`
12. optionally erase flash
13. optionally flash selected device
14. optionally open serial monitor

## Important Runtime Behavior

- If `tools/device_manifest.csv` already exists, manifest generation reuses it
- `--count` does not overwrite existing manifest automatically
- Patch files are reported by default, not auto-applied
- Use `--apply-patches` if you want pipeline to mutate `esp-matter/`
- Passing `--port` to `run` means flashing happens automatically
- `--flash` still exists, but only as deprecated compatibility flag
- `flash` subcommand is better if you want flash-only behavior

## Environment Handling

The pipeline builds ESP-IDF and Matter environment variables internally.

That means normal use does not require manual `source "$IDF_PATH/export.sh"` first.

If `gn` is missing, pipeline runs Matter bootstrap automatically.

If nested submodules are missing, pipeline initializes them automatically.

## Build Output Path

Default build dir:

- `build/light-c6-thread`

The build logic writes generated sdkconfig overrides that include:

- target VID/PID
- 8 MB flash size
- custom partition table
- factory-backed providers

## Flash Path

When flashing, pipeline:

1. resolves device row from `tools/out/devices.csv`
2. resolves firmware flashing metadata from build output
3. generates exact `esptool.py` command
4. optionally erases flash first
5. flashes selected device

## Labels

Unless `--skip-labels` is passed, pipeline also creates:

- per-device text labels
- printable HTML labels
- optional QR SVGs if `--render-qr-svg` is used

## Related Docs

- CLI options: [`cli.md`](./cli.md)
- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- upstream and patches: [`upstream-and-patches.md`](./upstream-and-patches.md)
- outputs: [`outputs.md`](./outputs.md)
