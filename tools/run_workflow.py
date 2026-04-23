#!/usr/bin/env python3
"""Compatibility wrapper for the new light pipeline CLI."""

from __future__ import annotations

import sys

from light_pipeline import main as light_pipeline_main


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["run", *argv]
    return light_pipeline_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
