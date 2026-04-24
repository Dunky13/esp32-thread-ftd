# Tools Docs

This directory contains implementation scripts.

Main entrypoint:

- [`light_pipeline.py`](./light_pipeline.py)

Project docs now live under [`../docs/`](../docs/README.md).

Use docs by topic:

- first setup: [`../docs/getting-started.md`](../docs/getting-started.md)
- pipeline flow: [`../docs/pipeline.md`](../docs/pipeline.md)
- VID/PID and attestation: [`../docs/identity-and-attestation.md`](../docs/identity-and-attestation.md)
- commissioning after flash: [`../docs/commissioning.md`](../docs/commissioning.md)
- manifest schema: [`../docs/manifest.md`](../docs/manifest.md)
- CLI options: [`../docs/cli.md`](../docs/cli.md)
- outputs and labels: [`../docs/outputs.md`](../docs/outputs.md)
- helper script roles: [`../docs/internal-scripts.md`](../docs/internal-scripts.md)
- version assumptions: [`../docs/version-compatibility.md`](../docs/version-compatibility.md)
- security and generated secrets: [`../docs/security-and-generated-secrets.md`](../docs/security-and-generated-secrets.md)
- maintenance and clean rebuilds: [`../docs/maintenance.md`](../docs/maintenance.md)
- upstream submodule and repo patches: [`../docs/upstream-and-patches.md`](../docs/upstream-and-patches.md)
- examples: [`../docs/examples.md`](../docs/examples.md)
- troubleshooting: [`../docs/troubleshooting.md`](../docs/troubleshooting.md)

Helper scripts in this folder:

- `detect_env_paths.py`
- `generate_device_manifest.py`
- `generate_attestation_chain.py`
- `generate_factory_data.py`
- `generate_flash_command.py`
- `generate_label_assets.py`
- `generate_label_html.py`
- `run_workflow.py`

For direct CLI usage, each script supports `--help`, for example:

```bash
python3 tools/light_pipeline.py --help
python3 tools/generate_factory_data.py --help
```
