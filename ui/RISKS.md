# Risks And Decisions

## Framework Decision

Preferred first cut: local Python web UI.

Reason:

- Drag/drop tarball is simple.
- Browser print prompt is natural.
- Long jobs can stream logs.
- No native desktop packaging needed yet.
- App can still control local serial devices through Python backend.

Avoid starting with Tkinter unless dependency-free distribution becomes more
important than drag/drop and rich preview.

## Manifest Reuse

Existing repo behavior reuses manifests. UI must make this visible.

Bad behavior:

- User changes VID/PID/count and UI silently keeps old manifest.

Required behavior:

- Show "Existing manifest will be reused".
- Show existing row count and VID/PID sample.
- Require explicit "Regenerate identities" before replacing manifest.

## UUID Serials

Current manifest generator supports sequential serials. UUID-derived serials need
a small generator extension.

Rule:

- UUID serials must be stable once generated.
- Regenerate only on explicit user action.
- Store generated rows in manifest CSV, not only `workspace.json`.

## Blocking Monitor

CLI defaults monitor on after flash in some paths. UI should default monitor off.

Reason:

- `idf.py monitor` is blocking.
- Browser job would appear stuck.

Plan:

- Flash with `--no-monitor`.
- Add separate "Open monitor" action later.

## Tarball Format Drift

UI cannot guess every bundle shape forever.

Plan:

- Detect current required files.
- Add release metadata file in future CI packaging.
- Treat metadata as preferred source when present.

## Secret Handling

Generated passcodes, factory bins, DAC keys, and onboarding payloads are sensitive.

Rules:

- Keep `ui/workspaces/` git-ignored.
- Do not log full passcodes unless existing tools already emit them.
- Do not copy generated secrets into app-global state.
- Archive before delete.

