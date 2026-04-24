# Manifest

This page explains `tools/device_manifest.csv`.

## What Manifest Is

Manifest is CSV input describing one device per row.

Pipeline uses it to generate:

- factory partition data
- onboarding codes
- labels
- optional attestation file mapping

Default manifest path:

- `tools/device_manifest.csv`

## Required Columns

Minimum required columns:

- `serial_num`
- `discriminator`
- `passcode`
- `vendor_id`
- `product_id`

## Default Generated Columns

`generate_device_manifest.py` creates:

- `serial_num`
- `discriminator`
- `passcode`
- `vendor_id`
- `product_id`
- `hw_ver`
- `hw_ver_str`
- `mfg_date`
- `rd_id_uid`

## Optional Extra Columns

Provisioning also passes through these fields if present:

- `device_type`
- `product_label`
- `product_url`
- `part_number`
- `product_finish`
- `product_color`
- `dac_cert`
- `dac_key`
- `pai_cert`
- `cd`

## Field Notes

`serial_num`

- device serial string
- also used for per-device output directory naming

`discriminator`

- Matter pairing discriminator
- default generation starts at `3840`

`passcode`

- Matter setup passcode
- generated randomly
- known invalid values are excluded by generator

`vendor_id`, `product_id`

- Matter identifiers used by both build and provisioning logic

`hw_ver`, `hw_ver_str`, `mfg_date`

- device metadata passed into factory generator

`rd_id_uid`

- rotating device identifier input
- generated as 16-byte hex string

`dac_cert`, `dac_key`, `pai_cert`, `cd`

- optional explicit attestation file paths
- used mainly with factory DAC mode

## Generation Behavior

If you run:

```bash
python3 tools/light_pipeline.py run --count 8
```

pipeline calls manifest generator first.

Important behavior:

- if manifest file already exists, generator reuses it
- `--count` does not overwrite existing manifest automatically

## Direct Manifest Generation

Use helper directly:

```bash
python3 tools/generate_device_manifest.py --help
```

Typical example:

```bash
python3 tools/generate_device_manifest.py \
  --count 8 \
  --output tools/device_manifest.csv \
  --serial-prefix LGT \
  --start-index 1 \
  --serial-width 4 \
  --discriminator-start 3840 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000
```

## Related Docs

- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- outputs: [`outputs.md`](./outputs.md)
- CLI options: [`cli.md`](./cli.md)
