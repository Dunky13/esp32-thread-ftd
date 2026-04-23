#!/usr/bin/env python3
"""Detect likely ESP-IDF and ESP-Matter paths for this repo."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shlex
from dataclasses import dataclass

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


SCRIPT_PATH = pathlib.Path(__file__).resolve()
TOOLS_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = TOOLS_DIR.parent
ESP_MATTER_ROOT = PROJECT_ROOT / "esp-matter"
EXAMPLE_DIR = ESP_MATTER_ROOT / "examples" / "light"
EIM_CONFIG_PATH = PROJECT_ROOT / "eim_config.toml"


@dataclass(frozen=True)
class DetectionResult:
    esp_matter_path: pathlib.Path
    idf_path: pathlib.Path | None
    idf_candidates: list[pathlib.Path]
    version_hint: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect likely IDF_PATH and ESP_MATTER_PATH values.",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Print shell export commands only.",
    )
    parser.add_argument(
        "--clean-shell",
        action="store_true",
        help="Print commands to leave current Python env, then export ESP_MATTER_PATH and IDF_PATH.",
    )
    parser.add_argument(
        "--activate-shell",
        action="store_true",
        help="Print clean-shell commands plus `source \"$IDF_PATH/export.sh\"`.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Also print all detected ESP-IDF candidates.",
    )
    return parser.parse_args()


def is_esp_idf_dir(path: pathlib.Path) -> bool:
    return (path / "export.sh").is_file() and (path / "tools" / "idf.py").is_file()


def is_esp_matter_dir(path: pathlib.Path) -> bool:
    return (path / "examples" / "light").is_dir() and (path / "connectedhomeip").is_dir()


def parse_version(text: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", text)
    return tuple(int(number) for number in numbers)


def version_hint_from_build_dirs() -> str | None:
    patterns = (
        EXAMPLE_DIR / "build-*",
    )
    matches: list[str] = []
    for pattern in patterns:
        for path in pattern.parent.glob(pattern.name):
            match = re.search(r"v(\d+)(?:[-_]|$)", path.name)
            if match:
                raw = match.group(1)
                if len(raw) >= 3:
                    matches.append(".".join(raw))
                elif len(raw) == 2:
                    matches.append(f"{raw[0]}.{raw[1]}")
                else:
                    matches.append(raw)
    if not matches:
        return None
    matches.sort(key=parse_version, reverse=True)
    return matches[0]


def load_eim_idf_path(config_path: pathlib.Path | None = None) -> pathlib.Path | None:
    if config_path is None:
        config_path = EIM_CONFIG_PATH
    if tomllib is None or not config_path.is_file():
        return None

    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    raw_idf_path = config.get("idf_path")
    if not isinstance(raw_idf_path, str) or not raw_idf_path.strip():
        return None

    candidate = pathlib.Path(raw_idf_path).expanduser()
    if not candidate.is_absolute():
        candidate = (config_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if is_esp_idf_dir(candidate):
        return candidate
    return None


def collect_idf_candidates() -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()

    eim_idf_path = load_eim_idf_path()
    if eim_idf_path is not None:
        candidates.append(eim_idf_path)
        seen.add(eim_idf_path)

    env_idf = os.environ.get("IDF_PATH")
    if env_idf:
        path = pathlib.Path(env_idf).expanduser().resolve()
        if is_esp_idf_dir(path):
            candidates.append(path)
            seen.add(path)

    possible_paths = [
        pathlib.Path.home() / "esp-idf",
        pathlib.Path.home() / "esp" / "esp-idf",
        PROJECT_ROOT.parent / "esp-idf",
    ]
    possible_paths.extend((pathlib.Path.home() / ".espressif").glob("*/esp-idf"))

    for candidate in possible_paths:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            continue
        if resolved in seen or not is_esp_idf_dir(resolved):
            continue
        candidates.append(resolved)
        seen.add(resolved)

    return candidates


def choose_idf_candidate(
    candidates: list[pathlib.Path],
    hint: str | None,
) -> pathlib.Path | None:
    if not candidates:
        return None

    eim_idf_path = load_eim_idf_path()
    if eim_idf_path is not None and eim_idf_path in candidates:
        return eim_idf_path

    env_idf = os.environ.get("IDF_PATH")
    if env_idf:
        env_path = pathlib.Path(env_idf).expanduser().resolve()
        if env_path in candidates:
            return env_path

    if hint:
        hinted = [candidate for candidate in candidates if hint in str(candidate)]
        if hinted:
            hinted.sort(key=lambda path: parse_version(str(path)), reverse=True)
            return hinted[0]

    preferred = sorted(candidates, key=lambda path: parse_version(str(path)), reverse=True)
    return preferred[0]


def detect_paths() -> DetectionResult:
    esp_matter_path = ESP_MATTER_ROOT
    if not is_esp_matter_dir(esp_matter_path):
        raise SystemExit(f"Current repo does not look like ESP-Matter: {esp_matter_path}")

    hint = version_hint_from_build_dirs()
    idf_candidates = collect_idf_candidates()
    idf_path = choose_idf_candidate(idf_candidates, hint)

    return DetectionResult(
        esp_matter_path=esp_matter_path,
        idf_path=idf_path,
        idf_candidates=idf_candidates,
        version_hint=hint,
    )


def render_shell(result: DetectionResult, *, clean: bool, activate: bool) -> str:
    lines: list[str] = []
    if clean:
        lines.extend(
            [
                "deactivate >/dev/null 2>&1 || true",
                "pyenv deactivate >/dev/null 2>&1 || true",
                "pyenv shell --unset >/dev/null 2>&1 || true",
                "unset VIRTUAL_ENV",
                "unset PYENV_VERSION",
                "unset CONDA_PREFIX",
                "hash -r >/dev/null 2>&1 || true",
            ]
        )
    lines.append(f"export ESP_MATTER_PATH={shlex.quote(str(result.esp_matter_path))}")
    if result.idf_path is not None:
        lines.append(f"export IDF_PATH={shlex.quote(str(result.idf_path))}")
        if activate:
            lines.append('source "$IDF_PATH/export.sh"')
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = detect_paths()

    if args.shell or args.clean_shell or args.activate_shell:
        print(render_shell(result, clean=args.clean_shell or args.activate_shell, activate=args.activate_shell))
        return 0

    print(f"ESP_MATTER_PATH: {result.esp_matter_path}")
    if result.idf_path is not None:
        print(f"IDF_PATH: {result.idf_path}")
    else:
        print("IDF_PATH: not found")

    if result.version_hint is not None:
        print(f"Version hint: {result.version_hint}")

    print("\nExports:")
    print(render_shell(result, clean=False, activate=False))

    if result.idf_path is not None:
        print("\nClean exports:")
        print(render_shell(result, clean=True, activate=False))

        print("\nActivate:")
        print(render_shell(result, clean=True, activate=True))

    if args.all and result.idf_candidates:
        print("\nESP-IDF candidates:")
        for candidate in result.idf_candidates:
            marker = " *" if candidate == result.idf_path else " -"
            print(f"{marker} {candidate}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
