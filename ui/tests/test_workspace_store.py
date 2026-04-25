from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ui.services import workspace_store


class WorkspaceStoreTests(unittest.TestCase):
    def test_create_workspace_persists_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(workspace_store, "WORKSPACES_DIR", root / "workspaces"), mock.patch.object(
                workspace_store, "STATE_DIR", root / "state"
            ), mock.patch.object(workspace_store, "APP_STATE_PATH", root / "state" / "app_state.json"):
                workspace = workspace_store.create_workspace("Office Lights")

                self.assertEqual(workspace.id, "office-lights")
                self.assertTrue((workspace.path / "workspace.json").is_file())
                self.assertEqual(workspace_store.get_last_workspace_id(), "office-lights")
                self.assertEqual(workspace_store.list_workspaces()[0].name, "Office Lights")


if __name__ == "__main__":
    unittest.main()

