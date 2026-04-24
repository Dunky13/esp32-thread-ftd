# Outputs

This page explains generated files and where they land.

## Build Output

Default build dir:

- `build/light-c6-thread`

Important build artifacts include:

- `flasher_args.json`
- app binaries
- bootloader binaries
- partition binaries

## Provisioning Output

Default output dir:

- `tools/out`

Per-device directory:

- `tools/out/<serial>/factory_partition.bin`
- `tools/out/<serial>/nvs_partition.csv`
- `tools/out/<serial>/onboarding_codes.csv`

## Devices Summary

Summary CSV:

- `tools/out/devices.csv`

It contains:

- `serial_num`
- `discriminator`
- `passcode`
- `vendor_id`
- `product_id`
- `vendor_name`
- `product_name`
- `factory_bin`
- `factory_csv`
- `onboarding_csv`
- `qrcode`
- `manualcode`

Pipeline uses this file later for:

- device selection
- label generation
- flash command generation

## Label Output

Text labels:

- `tools/labels/*.txt`

Printable HTML:

- `tools/matter-labels.html`

Optional SVG QR labels:

- generated when `--render-qr-svg` is used

## Attestation Output

Factory mode without explicit manifest attestation files may generate:

- `tools/out/attestation/pairs/<VID>_<PID>/`
- `tools/out/attestation/devices/<serial>/`
- `tools/out/attestation/manifest_with_attestation.csv`

Per-device generated attestation files can include:

- `dac_cert.der`
- `dac_key.der`
- `pai_cert.der`
- `cd.der`

## What To Keep Out Of Git

Do not commit:

- generated onboarding data
- factory binaries
- attestation private material
- device-specific outputs in `tools/out/`

## Related Docs

- manifest fields: [`manifest.md`](./manifest.md)
- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- helper scripts: [`internal-scripts.md`](./internal-scripts.md)
