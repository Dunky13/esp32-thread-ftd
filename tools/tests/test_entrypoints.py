from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


class EntryPointSmokeTests(unittest.TestCase):
    def run_cli(self, *args: str) -> None:
        completed = subprocess.run(
            [sys.executable, *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stderr or completed.stdout,
        )

    def test_direct_script_help_entrypoints(self) -> None:
        self.run_cli("tools/run_workflow.py", "--help")
        self.run_cli("tools/generate_label_assets.py", "--help")
        self.run_cli("tools/generate_label_html.py", "--help")
        self.run_cli("tools/light_pipeline.py", "--help")

    def test_module_help_entrypoints(self) -> None:
        self.run_cli("-m", "tools.run_workflow", "--help")
        self.run_cli("-m", "tools.generate_label_assets", "--help")
        self.run_cli("-m", "tools.generate_label_html", "--help")
        self.run_cli("-m", "tools.light_pipeline", "--help")


if __name__ == "__main__":
    unittest.main()
