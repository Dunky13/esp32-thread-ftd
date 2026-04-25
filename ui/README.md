# Python UI Plan

This folder contains the implementation plan for a local Python UI that wraps the
existing ESP32-C6 Matter provisioning pipeline.

## Target

Build a clickable local app where a user can:

- Create or reopen a workspace.
- Drop a downloaded release tarball.
- Enter vendor/product identity and device count.
- Choose serial generation: sequential or UUID-derived.
- Generate manifest, factory data, onboarding codes, and QR label previews.
- Select a connected serial port and flash one generated device.
- Reopen later with workspace state preserved.
- Print labels through the system/browser print dialog.

## Proposed Stack

Use a local Python web UI backed by the existing repo tooling.

- UI: NiceGUI or equivalent local browser UI.
- Runtime: Python subprocess/service wrappers around `tools/light_pipeline.py`.
- State: JSON + CSV files under `ui/workspaces/<workspace-id>/`.
- Preview: read `devices.csv`, reuse QR data from pipeline outputs, render cards in UI.
- Print: generate/reuse label HTML and call browser `window.print()`.

This keeps the UI Python-owned while avoiding native desktop packaging early.

## Core Rule

Do not duplicate provisioning logic in the UI. The UI should orchestrate current
tooling first, then extract reusable Python service functions only where needed.

