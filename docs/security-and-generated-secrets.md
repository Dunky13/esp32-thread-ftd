# Security And Generated Secrets

This page explains what generated data is sensitive and what should stay out of git.

## Sensitive Outputs

Treat these as sensitive:

- `tools/out/`
- generated onboarding codes
- generated factory partition binaries
- generated attestation private keys
- generated QR labels that embed commissioning data

## Why They Matter

These files can contain:

- setup passcodes
- onboarding payloads
- device identity material
- factory partition contents
- device-specific certificate/key material

Leaking them makes test devices easier to impersonate or commission unexpectedly.

## Files To Avoid Committing

Do not commit:

- `tools/out/**`
- generated `dac_key` files
- generated `factory_partition.bin`
- generated `onboarding_codes.csv`
- screenshots or PDFs containing live QR codes unless intended

## Development Vs Production

This repo is clearly development-oriented.

Examples:

- default VID/PID values are test values
- `example` DAC mode uses Matter test credential ranges
- `factory` mode can generate development attestation assets automatically

That is fine for debugging and lab work.

It is not same thing as production credential issuance or product certification process.

## Patch Safety

If you use `--apply-patches`, repo may mutate `esp-matter/`.

Review patch files before applying them, especially if they affect:

- credential handling
- factory provider paths
- build-time identity behavior

## Sharing Outputs

If you need to share logs or examples:

- prefer redacted `devices.csv`
- remove passcodes
- remove QR payloads
- remove key file paths if they reveal local layout you do not want shared

## Good Hygiene

- use `--dry-run` before destructive steps
- clean old `tools/out/` when switching projects or customers
- do not email raw onboarding bundles around
- do not keep generated secrets longer than needed

## Related Docs

- outputs: [`outputs.md`](./outputs.md)
- identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- maintenance: [`maintenance.md`](./maintenance.md)
