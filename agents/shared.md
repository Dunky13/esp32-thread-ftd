# Shared Agent Rules

Apply these rules before validation and before final response.

- Keep scope tight. Change only files required for task.
- Treat `esp-matter/` as upstream submodule. Prefer top-level patch files over direct edits unless user explicitly asks otherwise.
- Ignore generated artifacts in `build/` and `tools/out/`. Do not treat them as source.
- Match validation to changed scope. Small doc-only changes do not need firmware builds.
- If an env or dependency blocker prevents validation, say exactly what is missing and which command failed.
- Prefer focused commands over repo-wide builds when working in `tools/`.
- Do not invent TypeScript workflows for this repo.
- When build logs contain warnings from upstream `esp-matter/` or ESP-IDF, do not claim them fixed unless changed in this repo.
