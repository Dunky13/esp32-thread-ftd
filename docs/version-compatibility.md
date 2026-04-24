# Version Compatibility

This page records version assumptions visible in repo config and docs.

## Known Repo Hints

From `eim_config.toml`:

- ESP-IDF path points at `v5.5.2`
- configured Python override is `python313`

These values are environment hints, not hard guarantees that every other version works.

## What To Treat As Known-Good

Most concrete version assumptions in this repo are:

- ESP-IDF: `v5.5.2`
- target chip: `esp32c6`
- flash size: 8 MB
- upstream SDK source from checked-out `esp-matter` submodule revision

## Compatibility Boundaries

If you change ESP-IDF version, watch for:

- build system changes
- toolchain path changes
- Python env layout changes
- differences in generated flash metadata

If you change Python version, watch for:

- dependency install behavior
- CHIP setup-payload dependency compatibility
- cryptography package behavior

## Host Assumptions

Docs and scripts are written mainly with:

- macOS
- Linux

in mind.

Serial device examples also assume Unix-like names such as:

- `/dev/ttyUSB0`
- `/dev/ttyACM0`

## Upstream Compatibility

Repo-local tooling depends on:

- checked-out `esp-matter/`
- checked-out nested `connectedhomeip`
- whatever patch files under `patches/` expect

If you update submodules, also review:

- [`upstream-and-patches.md`](./upstream-and-patches.md)
- [`troubleshooting.md`](./troubleshooting.md)

## Recommendation

If you need reproducible results:

1. keep current submodule revisions
2. keep ESP-IDF at repo-tested version hint
3. keep same board and flash size
4. keep same DAC mode during repeated runs

## Related Docs

- getting started: [`getting-started.md`](./getting-started.md)
- hardware: [`hardware.md`](./hardware.md)
- upstream and patches: [`upstream-and-patches.md`](./upstream-and-patches.md)
