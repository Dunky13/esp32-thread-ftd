# Hardware

This repo is configured around one tested hardware path.

## Tested Board

Tested on:

- Waveshare [ESP32-C6-Zero](https://www.waveshare.com/esp32-c6-zero.htm)
- Waveshare product page lists it as based on `ESP32-C6FH8`

## Target Assumptions

Repo defaults assume:

- chip target: `esp32c6`
- firmware source: `esp-matter/examples/light`
- network mode: Thread enabled
- Wi-Fi disabled
- flash size: 8 MB

## Why 8 MB Matters

Build override logic forces:

- 8 MB flash size
- custom partition table
- factory partition support

Partition table used:

- [`../tools/light_partitions_8mb.csv`](../tools/light_partitions_8mb.csv)

Default build output:

- `build/light-c6-thread`

## If You Change Boards

Review at least:

1. flash size
2. partition layout
3. target chip
4. example app compatibility
5. serial port naming on host

If your board is not 8 MB flash, current defaults may be wrong.

## Related Docs

- setup: [`getting-started.md`](./getting-started.md)
- pipeline behavior: [`pipeline.md`](./pipeline.md)
- outputs: [`outputs.md`](./outputs.md)
