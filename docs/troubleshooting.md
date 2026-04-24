# Troubleshooting

This page lists common failures and what they usually mean.

## ESP-IDF Not Found

Run:

```bash
python3 tools/light_pipeline.py doctor
python3 tools/detect_env_paths.py --activate-shell
```

Confirm `IDF_PATH` points to real ESP-IDF tree containing:

- `export.sh`
- `tools/idf.py`

## Example DAC Mode Rejected My IDs

Expected if your IDs are outside allowed example range.

`example` mode only supports:

- VID `0xFFF1` to `0xFFF3`
- PID `0x8000` to `0x801F`

Switch to factory mode:

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --dac-provider factory \
  --vendor-id 0x1234 \
  --product-id 0x5678
```

## `--use-test-attestation` Failed

That means CHIP test bundle does not contain exact PAI/DAC assets for requested VID/PID pair.

Options:

- choose supported test pair
- stop using `--use-test-attestation`
- provide explicit `dac_cert`, `dac_key`, `pai_cert`, and `cd` in manifest

## Missing Python Package During Factory Data Generation

`generate_factory_data.py` may need extra CHIP setup-payload Python dependencies.

Default behavior:

- auto-install missing deps into active tool Python env

Fail-fast behavior:

```bash
python3 tools/generate_factory_data.py --no-auto-install-deps
```

## Manifest Not Found

If you run `light_pipeline.py run` without `--count` and no manifest exists, pipeline exits.

Fix:

- pass `--count` to generate manifest
- or create `tools/device_manifest.csv` yourself

## Need Serial Port List

Run:

```bash
python3 tools/light_pipeline.py list
```

## Need Exact Flash Command

Run:

```bash
python3 tools/generate_flash_command.py --help
python3 tools/generate_flash_command.py --port /dev/ttyUSB0 --serial-index 1
```

## Build Or Flash Side Effects

Use `--dry-run` first when you want to inspect commands before:

- erase
- flash
- monitor

## Related Docs

- CLI options: [`cli.md`](./cli.md)
- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
