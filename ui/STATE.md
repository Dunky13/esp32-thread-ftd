# Workspace State Model

## Files

```text
ui/state/app_state.json
ui/workspaces/<workspace-id>/workspace.json
ui/workspaces/<workspace-id>/manifest/device_manifest.csv
ui/workspaces/<workspace-id>/out/devices.csv
ui/workspaces/<workspace-id>/labels/matter-labels.html
```

`ui/state/app_state.json`:

```json
{
  "version": 1,
  "last_workspace_id": "office-lights",
  "recent_workspace_ids": ["office-lights"]
}
```

`workspace.json`:

```json
{
  "version": 1,
  "id": "office-lights",
  "name": "Office Lights",
  "created_at": "2026-04-25T12:00:00Z",
  "updated_at": "2026-04-25T12:20:00Z",
  "bundle": {
    "source_filename": "light-c6-thread.tar.gz",
    "sha256": "example",
    "extract_dir": "bundle/example",
    "build_dir": "bundle/example/build/light-c6-thread"
  },
  "defaults": {
    "vendor_id": "0xFFF1",
    "product_id": "0x8000",
    "vendor_name": "ESP-C6-Matter",
    "product_name": "Thread Light",
    "serial_mode": "sequential",
    "serial_prefix": "LGT",
    "start_index": 1,
    "serial_width": 4,
    "count": 8
  },
  "outputs": {
    "manifest": "manifest/device_manifest.csv",
    "devices_csv": "out/devices.csv",
    "label_html": "labels/matter-labels.html"
  },
  "selection": {
    "serial_num": "LGT-0001",
    "serial_port": "/dev/cu.usbmodem101"
  }
}
```

## Rules

- JSON stores UI choices and paths only.
- Manifest CSV owns serials, passcodes, discriminators, and RD IDs.
- `devices.csv` owns generated QR payloads, manual codes, and factory binary paths.
- Regeneration must be explicit if `device_manifest.csv` already exists.
- Workspace delete should move to trash/archive first, not immediate permanent delete.

