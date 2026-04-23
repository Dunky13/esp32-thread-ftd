# AGENTS.md

Shared agent rules live in `agents/shared.md`.

Language-specific agent rules for repo-local tooling live in:

- `agents/python.md`

This repo is mostly ESP-IDF C/C++ in `esp-matter/` plus Python automation in `tools/`.

Before planning validation or final checks:

- Read `agents/shared.md`
- Detect scope you changed
- For `tools/*.py` and `tools/tests/*.py`, read `agents/python.md`
- For native-only work, use repo guidelines below plus component-appropriate build checks
- Do not run TypeScript or ESLint checks for this repo unless new TS/JS files are introduced
- Do not run Python checks for native-only changes

Scope rules:

- Prefer not editing `esp-matter/` directly. It is upstream submodule content.
- If `esp-matter/` needs changes, create a patch file in top-level repo unless user explicitly asks for direct submodule edits.
- Treat `build/` and `tools/out/` as disposable artifacts.

## Project Structure & Module Organization
`esp-matter/` is upstream SDK submodule and main codebase. Core libraries live in `esp-matter/components/`, hardware support in `esp-matter/device_hal/`, and runnable samples in `esp-matter/examples/` such as `light_switch/` and `unit_test_app/`. Repo-local automation lives in `tools/` for manifest generation, factory data, flashing, and printable labels.

## Build, Test, and Development Commands
Initialize dependencies first:

```bash
git submodule update --init --recursive
cd esp-matter && ./install.sh && . ./export.sh
```

Common workflows:

```bash
mkdir -p build/light_switch && cd esp-matter/examples/light_switch && idf.py -B ../../../build/light_switch set-target esp32c6 build
cd esp-matter/examples/light_switch && idf.py -B ../../../build/light_switch -p /dev/ttyUSB0 flash monitor
cd esp-matter && pre-commit run --all-files
mkdir -p build/unit_test_app && cd esp-matter/examples/unit_test_app && idf.py -B ../../../build/unit_test_app -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.qemu" set-target esp32c3 build
cd esp-matter/examples/unit_test_app && pytest pytest_unit_test_app.py --target esp32c3 -m qemu --embedded-services idf,qemu --qemu-extra-args="-global driver=timer.esp32c3.timg,property=wdt_disable,value=true"
python3 tools/run_workflow.py --count 8 --dry-run
```

Create target `build/` directory first if it does not exist, and keep all build output there instead of inside submodule tree. Use `--dry-run` on local tooling before erase/flash operations.

## Coding Style & Naming Conventions
Follow existing `esp-matter` conventions. C and C++ formatting is enforced by `pre-commit` with `astyle_py`; sorted lists are enforced by `keep-sorted`; spelling is checked with `codespell`. Use 4-space indentation in Python, `snake_case` for Python modules and example directories, and keep CMake target names aligned with directory names such as `light_switch`. Do not hand-edit generated files under `esp-matter/components/esp_matter/data_model/generated/`.

## Testing Guidelines
Python test runners are named `pytest_*.py` per `esp-matter/pytest.ini`. Repo-local Python tooling tests live in `tools/tests/`. Component-level C/C++ tests live under `components/*/test/`. For firmware validation, build and run `examples/unit_test_app` on hardware or QEMU. When adding pytest coverage, use explicit markers such as `@pytest.mark.qemu` and target markers like `@pytest.mark.esp32c3`.

## Commit & Pull Request Guidelines
Current history uses short imperative commit subjects, for example `Add project gitignore` and `Add esp-matter submodule`. Keep commit titles concise, scoped, and action-led. Pull requests should state affected example or component, target chip, commands run, and any required setup changes. Include serial logs, screenshots, or generated-label samples when behavior or output changes.

## Security & Configuration Tips
Keep `ESP_MATTER_PATH` and `IDF_PATH` consistent in active shell before building. Do not commit factory binaries, generated onboarding data, certificates, or device-specific outputs from `tools/out/`.
