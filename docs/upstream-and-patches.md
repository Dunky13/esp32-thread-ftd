# Upstream And Patches

This repo depends on upstream submodule content plus repo-local automation.

## Upstream Layout

Main upstream dependency:

- `esp-matter/`

Nested dependency inside it:

- `connectedhomeip`

Repo-local automation lives in:

- `tools/`

## Why Patches Exist

Top-level `patches/` lets this repo carry local adjustments without hiding drift in upstream submodule content.

Patch files are separate because:

- `esp-matter/` is upstream-owned
- repo-local automation may depend on small custom changes
- patch review is easier than hidden edits

## Current Behavior

Pipeline always checks patch status.

By default it does not mutate `esp-matter/`.

If patch files are pending, pipeline reports them and tells you to rerun with:

```bash
python3 tools/light_pipeline.py run --apply-patches ...
```

Use `--apply-patches` only when you intentionally want local patch state applied into submodule working tree.

## What To Watch

If you update `esp-matter/` submodule revision:

- existing patches may no longer apply cleanly
- build behavior may change
- tooling assumptions may drift

If patch apply fails, inspect:

- patch file contents
- current `esp-matter/` revision
- local submodule working tree changes

## Good Workflow

1. keep submodules initialized
2. inspect pending patches
3. apply patches only when intended
4. verify `git -C esp-matter status --short`
5. rebuild from clean state if upstream revision changed

## Related Docs

- pipeline behavior: [`pipeline.md`](./pipeline.md)
- version assumptions: [`version-compatibility.md`](./version-compatibility.md)
- maintenance: [`maintenance.md`](./maintenance.md)
