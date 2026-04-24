# Identity And Attestation

This page explains `vendor_id`, `product_id`, DAC mode, and attestation files.

## Vendor ID And Product ID

`--vendor-id` and `--product-id` are Matter identifiers for the device.

In this repo they affect:

- firmware build overrides
- manifest rows
- factory data generation
- onboarding metadata
- attestation selection or generation
- certification declaration generation in factory mode

Defaults in `light_pipeline.py`:

- `--vendor-id 0xFFF1`
- `--product-id 0x8000`

Those defaults are development/test values.

## Why These IDs Matter

The same VID/PID pair must stay aligned across:

- firmware config
- provisioning data
- attestation assets
- certification declaration

If those parts disagree, commissioning can fail or produce invalid identity data.

## Terms

`DAC`

- Device Attestation Certificate
- usually per-device

`PAI`

- Product Attestation Intermediate
- signs DACs

`PAA`

- Product Attestation Authority
- root above PAI

`CD`

- Certification Declaration
- signed metadata used during commissioning

## DAC Provider Modes

### `--dac-provider example`

Use this for easiest development path.

Restrictions enforced by code:

- VID must be `0xFFF1`, `0xFFF2`, or `0xFFF3`
- PID must be between `0x8000` and `0x801F`

If you pass other values, pipeline exits and tells you to use factory mode.

### `--dac-provider factory`

Use this when:

- you want custom VID/PID values
- you want explicit attestation files
- you want factory-partition-backed attestation flow

Factory mode has two paths:

1. `--use-test-attestation`
   - uses CHIP test credentials shipped in `connectedhomeip`
   - requested VID/PID must match exact supported test bundle assets
2. no `--use-test-attestation`
   - pipeline generates development PAA/PAI/DAC/CD assets automatically
   - generated manifest with file paths is then used for provisioning

## Explicit Attestation Files In Manifest

Manifest rows may include:

- `dac_cert`
- `dac_key`
- `pai_cert`
- `cd`

If those values are present, provisioning uses them directly.

If they are absent and factory mode is active, repo can generate development assets automatically.

## Generated Attestation Output

Development attestation generation writes under:

- `tools/out/attestation/pairs/`
- `tools/out/attestation/devices/`
- `tools/out/attestation/manifest_with_attestation.csv`

Per device, generated outputs include:

- `dac_cert.der`
- `dac_key.der`
- `pai_cert.der`
- `cd.der`

## Practical Guidance

Use `example` mode when:

- you only need quick development flow
- your VID/PID fits allowed test range

Use `factory` mode when:

- you need custom VID/PID values
- you want to supply your own attestation files
- you want generated development DAC assets for non-example IDs

## Related Docs

- manifest fields: [`manifest.md`](./manifest.md)
- CLI options: [`cli.md`](./cli.md)
- outputs: [`outputs.md`](./outputs.md)
- troubleshooting: [`troubleshooting.md`](./troubleshooting.md)
