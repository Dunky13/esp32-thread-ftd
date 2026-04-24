# Internal Scripts

Most users only need `tools/light_pipeline.py`.

This page explains lower-level helper scripts.

## `detect_env_paths.py`

Purpose:

- inspect ESP-IDF and ESP-Matter path detection
- print shell exports if needed

Use:

```bash
python3 tools/detect_env_paths.py --help
```

## `generate_device_manifest.py`

Purpose:

- generate `device_manifest.csv` directly
- create unique serials, passcodes, discriminators, and rotating IDs

Use:

```bash
python3 tools/generate_device_manifest.py --help
```

## `generate_attestation_chain.py`

Purpose:

- generate development PAA/PAI/DAC/CD assets
- write manifest augmented with `dac_cert`, `dac_key`, `pai_cert`, `cd`

Use:

```bash
python3 tools/generate_attestation_chain.py --help
```

## `generate_factory_data.py`

Purpose:

- generate per-device factory partition
- generate onboarding codes
- write `tools/out/devices.csv`

Use:

```bash
python3 tools/generate_factory_data.py --help
```

## `generate_flash_command.py`

Purpose:

- compute exact `esptool.py` command for one generated device

Use:

```bash
python3 tools/generate_flash_command.py --help
```

## `generate_label_assets.py`

Purpose:

- generate per-device text label files from `devices.csv`

Use:

```bash
python3 tools/generate_label_assets.py --help
```

## `generate_label_html.py`

Purpose:

- generate printable HTML label sheet

Use:

```bash
python3 tools/generate_label_html.py --help
```

## `run_workflow.py`

Purpose:

- compatibility wrapper for older workflow usage
- forwards to `light_pipeline.py run`

## Related Docs

- pipeline flow: [`pipeline.md`](./pipeline.md)
- CLI options: [`cli.md`](./cli.md)
