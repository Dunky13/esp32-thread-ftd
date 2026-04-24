# Commissioning

This page covers what happens after firmware is flashed.

## What You Need

Flashing device is not same as commissioning it.

To commission Matter-over-Thread device, you still need:

- powered flashed device
- Thread border router on same network
- commissioner app or tool
- onboarding code from generated outputs

Typical commissioner choices:

- Apple Home
- Google Home
- Home Assistant Matter integration
- `chip-tool`

## Where Pairing Data Comes From

After successful provisioning run, pairing data is available in:

- `tools/out/devices.csv`
- `tools/out/<serial>/onboarding_codes.csv`
- label outputs under `tools/labels/`
- printable sheet `tools/matter-labels.html`

Relevant values:

- `qrcode`
- `manualcode`
- `discriminator`
- `passcode`

## Recommended Flow

1. run pipeline and generate one device
2. flash selected device
3. open `tools/out/devices.csv`
4. pick correct row by `serial_num`
5. use `qrcode` or `manualcode` in commissioner

## Using QR Code

Best path:

- scan generated QR code from label output
- or use QR text from `devices.csv` with tool that accepts raw Matter payload

If you generated SVG labels, you can scan those too.

## Using Manual Code

Use manual code when:

- scanner is unavailable
- commissioner supports numeric entry
- you want to cross-check generated output against printed label

Manual code comes from:

- `tools/out/devices.csv`
- `tools/out/<serial>/onboarding_codes.csv`

## Thread Requirements

This repo builds Thread-only firmware by default.

That means:

- device expects Thread commissioning path
- no Wi-Fi onboarding path is documented here
- you need working Thread border router in environment

If Thread network is absent or unhealthy, commissioning may fail even when flash succeeded.

## What Success Looks Like

Expected signs:

- commissioner accepts QR or manual code
- device joins Thread network
- Matter commissioner sees node come online
- selected ecosystem creates new light device entry

## Common Failure Shapes

QR or manual code rejected:

- wrong device row selected
- stale printed label from previous run
- wrong manifest reused

Commissioner cannot find device:

- Thread border router missing
- device not booted correctly
- wrong firmware build

Commissioning starts then fails attestation:

- VID/PID mismatch
- wrong DAC mode
- bad explicit attestation files

## Good Practice

- generate one device first, not eight
- flash one board
- commission it
- only then scale to larger batch

## Related Docs

- outputs: [`outputs.md`](./outputs.md)
- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- examples: [`examples.md`](./examples.md)
- troubleshooting: [`troubleshooting.md`](./troubleshooting.md)
