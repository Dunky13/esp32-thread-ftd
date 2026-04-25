# UI Implementation Plan

## Product Shape

Local app starts from repo root:

```bash
python3 -m ui.app
```

It opens a browser window or prints a localhost URL. User flow:

1. Pick workspace or create new one.
2. Drop release tarball.
3. Fill device identity fields.
4. Generate files.
5. Preview generated devices and QR labels.
6. Select serial row + connected device port.
7. Flash one device.
8. Print labels if needed.

## Non-Goals For First Cut

- No cloud storage.
- No remote flashing.
- No direct edits inside `esp-matter/`.
- No rewrite of factory-data, attestation, QR, or flash logic.
- No automatic deletion of generated credentials.

## Phase 1: Service Boundary

Create a repo-local UI package under `ui/`:

```text
ui/
  app.py
  services/
    workspace_store.py
    release_bundle.py
    pipeline_runner.py
    serial_ports.py
    labels.py
  components/
    workspace_picker.py
    device_form.py
    device_table.py
    label_preview.py
    flash_panel.py
  workspaces/        # ignored runtime state
  state/             # ignored app preferences
```

First implementation can call existing CLIs. Later refactor shared logic out of
`tools/light_pipeline.py` only when UI needs structured progress or richer errors.

Required service APIs:

- `list_workspaces() -> list[WorkspaceSummary]`
- `create_workspace(name: str) -> Workspace`
- `import_release_tarball(workspace, tarball_path) -> ReleaseBundle`
- `generate_workspace_outputs(workspace, request) -> JobResult`
- `list_generated_devices(workspace) -> list[DeviceRow]`
- `list_serial_ports() -> list[str]`
- `flash_device(workspace, serial_num, port, erase=False, monitor=False) -> JobResult`
- `open_print_preview(workspace) -> Path`

## Phase 2: Workspace State

Persist state under `ui/workspaces/<slug>/`:

```text
workspace.json
inputs/
  release.tar.gz
  release.sha256
bundle/
  extracted release files
manifest/
  device_manifest.csv
out/
  devices.csv
  per-device factory bins
labels/
  matter-labels.html
logs/
  generate-<timestamp>.log
  flash-<timestamp>.log
```

`workspace.json` stores UI metadata only:

- name
- created/updated timestamps
- imported bundle checksum
- vendor/product defaults
- last serial mode and count
- last selected serial
- last selected serial port
- generation status
- output paths

Credentials and generated Matter data remain in CSV/bin files, not duplicated in
JSON.

## Phase 3: Tarball Import

Drag/drop accepts `.tar`, `.tar.gz`, `.tgz`.

Validation:

- Reject path traversal members.
- Compute SHA-256.
- Extract into `bundle/<sha256-prefix>/`.
- Detect prebuilt build dir by finding `flasher_args.json`.
- Detect provisioning support by finding `connectedhomeip/scripts/tools/generate_esp32_chip_factory_bin.py`.
- Detect optional metadata file if release later adds one.

If bundle contains firmware build artifacts, UI runs generation with `--skip-build`
and `--build-dir <bundle-build-dir>`. If not, UI can offer full build path using
repo-local `esp-matter/`.

## Phase 4: Device Input Form

Fields:

- Vendor ID: default `0xFFF1`.
- Product ID: default `0x8000`.
- Vendor name.
- Product name.
- Amount.
- Hardware version.
- Hardware version string.
- Manufacturing date.
- DAC provider: example, factory with generated dev attestation, or factory with test assets.
- Serial mode: sequential or UUID-derived.

Sequential serial examples:

- Prefix `LGT`, start `1`, width `4` -> `LGT-0001`, `LGT-0002`.
- Prefix `OFFICE`, start `42`, width `3` -> `OFFICE-042`.

UUID-derived serial examples:

- `C6-3F9A81D2`
- `C6-8B6C-4C1E`

First cut should support existing sequential generator directly. UUID mode needs
a small addition to manifest generation so serials are deterministic per workspace
unless user explicitly regenerates.

## Phase 5: Generate Files

Generation maps to current pipeline:

```bash
python3 tools/light_pipeline.py run \
  --manifest ui/workspaces/<slug>/manifest/device_manifest.csv \
  --output-dir ui/workspaces/<slug>/out \
  --label-output-dir ui/workspaces/<slug>/labels \
  --label-html ui/workspaces/<slug>/labels/matter-labels.html \
  --count <amount> \
  --vendor-id <vid> \
  --product-id <pid> \
  --vendor-name <name> \
  --product-name <name> \
  --serial-prefix <prefix> \
  --start-index <n> \
  --serial-width <n> \
  --skip-build \
  --build-dir <bundle-build-dir>
```

Important behavior to preserve:

- Existing manifest is reused unless user chooses "Regenerate identities".
- Existing labels are skipped when fingerprint matches.
- Full build is optional; release tarball should allow generation + flashing without
  rebuilding firmware.
- UI must surface stdout/stderr logs, not hide pipeline failures.

## Phase 6: QR Preview

Read `out/devices.csv` after generation.

Preview grid:

- Serial number.
- Vendor/Product IDs.
- Manual code.
- QR code rendered from `qrcode` payload.
- Factory binary status.
- Flash status badge.

Implementation options:

- Use Python QR renderer for in-app preview.
- Reuse generated HTML label file inside iframe/webview.
- Prefer reusing `tools/generate_label_html.py` output for print parity.

Print action:

- Open generated `labels/matter-labels.html`.
- Trigger browser/system print dialog.
- No silent printer selection in first cut.

## Phase 7: Flash UX

Serial port selector uses existing detection from `tools/generate_flash_command.py`.

Flash form:

- Device row selector.
- Serial port selector with refresh button.
- Erase checkbox, default off.
- Monitor checkbox, default off in UI first cut to avoid blocking browser job.
- Flash button.

Flash maps to current command:

```bash
python3 tools/light_pipeline.py flash \
  --output-dir ui/workspaces/<slug>/out \
  --build-dir <bundle-build-dir> \
  --serial <serial_num> \
  --port <port> \
  --no-monitor
```

If monitor is enabled, run it in a separate terminal or provide explicit "Open
monitor" after flash. Do not block UI worker indefinitely.

## Phase 8: Job Runner

Use background jobs for generation and flashing.

Job state:

- queued
- running
- success
- failed
- cancelled

Each job writes:

- command line
- start/end timestamps
- exit code
- stdout/stderr log file

UI shows streaming log tail if framework supports it; otherwise poll log file.

## Phase 9: Validation And Tests

Doc-only phase needs no firmware build.

When code starts:

- Unit-test workspace store with temp dirs.
- Unit-test tarball extraction path traversal rejection.
- Unit-test command construction.
- Unit-test serial generation modes.
- Unit-test parsing `devices.csv` into preview rows.
- Smoke-test `python3 -m ui.app --help` if CLI exists.

For Python tooling changes, run:

```bash
python3 -m unittest tools.tests.test_robustness
```

If UI package has its own tests:

```bash
python3 -m unittest discover -s ui/tests
```

## Phase 10: Packaging Later

After local app works:

- Add `requirements-ui.txt`.
- Add `python3 -m ui.app --host 127.0.0.1 --port 0`.
- Add optional PyInstaller/native wrapper only after UI behavior is stable.
- Keep release tarball format documented so UI can validate it without guesses.

