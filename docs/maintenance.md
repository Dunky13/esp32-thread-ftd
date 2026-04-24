# Maintenance

This page covers clean rebuilds, reruns, and routine repo care.

## Build Cache

Default build dir:

- `build/light-c6-thread`

If build state looks stale or inconsistent, remove build dir and rebuild.

Typical reasons:

- changed ESP-IDF version
- changed target assumptions
- changed patch state in `esp-matter/`
- old `flasher_args.json` no longer matches current build

## Output Cache

Generated output lives under:

- `tools/out`
- `tools/labels`
- `tools/matter-labels.html`

If you want clean repro run, remove old generated outputs before rerunning.

Typical reasons:

- old onboarding codes causing confusion
- labels from prior batch still visible
- switching VID/PID or product naming

## Manifest Reuse

Important behavior:

- if `tools/device_manifest.csv` already exists, generator reuses it
- `--count` does not overwrite it automatically

If you want fresh device identities, remove or rename existing manifest first.

## Suggested Clean Rebuild Workflow

1. remove old `build/light-c6-thread`
2. remove old `tools/out`
3. remove old labels if needed
4. remove or rename `tools/device_manifest.csv`
5. rerun `light_pipeline.py run --count ...`

## Patch State

If you use `--apply-patches`, remember `esp-matter/` may now contain local changes.

Before updating submodule or rebuilding after upstream changes, inspect:

- `patches/`
- `git -C esp-matter status --short`

## Routine Checks

Useful commands:

```bash
python3 tools/light_pipeline.py doctor
python3 tools/light_pipeline.py list
```

## Related Docs

- pipeline behavior: [`pipeline.md`](./pipeline.md)
- outputs: [`outputs.md`](./outputs.md)
- upstream and patches: [`upstream-and-patches.md`](./upstream-and-patches.md)
