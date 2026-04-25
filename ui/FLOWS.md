# UI Flows

## Screen 1: Workspace Picker

Purpose: choose persistent context before touching generated credentials.

Controls:

- New workspace.
- Open workspace.
- Rename workspace.
- Archive workspace.
- Show last updated time and generated-device count.

Primary action:

- Open selected workspace.

Guardrails:

- Archive only; no permanent delete in first cut.
- Show warning if workspace contains generated `device_manifest.csv`.

## Screen 2: Release Import

Purpose: import downloaded build/provisioning bundle.

Controls:

- Drag/drop tarball.
- Browse file.
- Re-import bundle.
- Validate bundle.

Status:

- SHA-256.
- Detected build dir.
- Detected `flasher_args.json`.
- Detected provisioning support.
- Detected release metadata, if present.

Errors:

- Unsafe tar path.
- Missing firmware build files.
- Missing provisioning generator.
- Unsupported archive type.

## Screen 3: Device Setup

Purpose: define generated device identities.

Controls:

- Vendor ID.
- Product ID.
- Vendor name.
- Product name.
- Count.
- Serial mode: sequential or UUID.
- Sequential prefix/start/width.
- UUID prefix/format.
- Manufacturing date.
- DAC provider.

Preview:

- First 5 serial examples before generation.
- Warning when existing manifest will be reused.
- Explicit "Regenerate identities" action if user wants replacement.

## Screen 4: Generate

Purpose: run current pipeline and make files.

Controls:

- Generate files.
- Cancel job.
- Open output folder.
- Open generated label HTML.

Status:

- Current step.
- Command being run.
- Streaming log tail.
- Final paths: manifest, devices CSV, label HTML, output dir.

Failure behavior:

- Keep partial logs.
- Do not delete prior successful outputs.
- Keep previous preview visible, marked stale if inputs changed.

## Screen 5: Preview

Purpose: show what will be flashed.

Per-device card:

- Serial.
- Vendor/Product IDs.
- QR code.
- Manual code.
- Factory binary exists/missing.
- Last flash status.

Actions:

- Select for flashing.
- Open full label sheet.
- Print labels.

Print:

- Use generated HTML.
- Use system/browser print prompt.
- No silent print in first cut.

## Screen 6: Flash

Purpose: one-click flash selected generated file.

Controls:

- Device serial selector.
- Connected port selector.
- Refresh ports.
- Erase before flash checkbox, default off.
- Monitor after flash checkbox, default off.
- Flash button.

Status:

- Port detected/missing.
- Flash command preview.
- Flash log.
- Success/failure badge per serial.

Guardrails:

- Disable flash if factory bin is missing.
- Disable flash if build dir lacks `flasher_args.json`.
- Require explicit erase confirmation when erase is enabled.
- Avoid default monitor because it blocks long-running UI job.

