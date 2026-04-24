# Docs

This folder splits project docs by concept so each page stays short and easy to scan.

## Start Here

- project overview: [`../README.md`](../README.md)
- setup and first run: [`getting-started.md`](./getting-started.md)

## Topics

- hardware and target assumptions: [`hardware.md`](./hardware.md)
- pipeline flow and implementation behavior: [`pipeline.md`](./pipeline.md)
- Matter identity and attestation: [`identity-and-attestation.md`](./identity-and-attestation.md)
- commissioning after flash: [`commissioning.md`](./commissioning.md)
- manifest schema and row fields: [`manifest.md`](./manifest.md)
- CLI commands and options: [`cli.md`](./cli.md)
- generated files and labels: [`outputs.md`](./outputs.md)
- helper scripts: [`internal-scripts.md`](./internal-scripts.md)
- version assumptions: [`version-compatibility.md`](./version-compatibility.md)
- security and generated secrets: [`security-and-generated-secrets.md`](./security-and-generated-secrets.md)
- maintenance and clean rebuilds: [`maintenance.md`](./maintenance.md)
- CI and released build artifacts: [`ci-and-releases.md`](./ci-and-releases.md)
- upstream submodule and repo patches: [`upstream-and-patches.md`](./upstream-and-patches.md)
- sample commands and rows: [`examples.md`](./examples.md)
- troubleshooting: [`troubleshooting.md`](./troubleshooting.md)

## Suggested Reading Order

1. [`getting-started.md`](./getting-started.md)
2. [`hardware.md`](./hardware.md)
3. [`pipeline.md`](./pipeline.md)
4. [`identity-and-attestation.md`](./identity-and-attestation.md)
5. [`commissioning.md`](./commissioning.md)
6. [`manifest.md`](./manifest.md)
7. [`cli.md`](./cli.md)

## Scope

These docs describe repo-local automation in `tools/`.

Upstream SDK source and APIs still live under [`../esp-matter/`](../esp-matter).
