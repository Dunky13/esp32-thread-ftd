from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ui.services import workspace_store
from ui.services.release_bundle import import_release_tarball, is_supported_tarball


def write_tar(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tarball:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tarball.addfile(info, io.BytesIO(data))


class ReleaseBundleTests(unittest.TestCase):
    def test_tarball_extension_filter_accepts_release_formats(self) -> None:
        self.assertTrue(is_supported_tarball(Path("release.tar")))
        self.assertTrue(is_supported_tarball(Path("release.tar.gz")))
        self.assertTrue(is_supported_tarball(Path("release.tgz")))
        self.assertFalse(is_supported_tarball(Path("release.gz")))

    def test_rejects_path_traversal_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tarball = root / "bad.tar.gz"
            write_tar(tarball, {"../escape": b"nope"})
            with mock.patch.object(workspace_store, "WORKSPACES_DIR", root / "workspaces"), mock.patch.object(
                workspace_store, "STATE_DIR", root / "state"
            ), mock.patch.object(workspace_store, "APP_STATE_PATH", root / "state" / "app_state.json"):
                workspace = workspace_store.create_workspace("Office Lights")
                with self.assertRaises(ValueError):
                    import_release_tarball(workspace, tarball)

    def test_detects_flasher_args_build_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tarball = root / "release.tar.gz"
            write_tar(
                tarball,
                {
                    "release/build/light/flasher_args.json": b"{}",
                    "release/connectedhomeip/scripts/tools/generate_esp32_chip_factory_bin.py": b"",
                },
            )
            with mock.patch.object(workspace_store, "WORKSPACES_DIR", root / "workspaces"), mock.patch.object(
                workspace_store, "STATE_DIR", root / "state"
            ), mock.patch.object(workspace_store, "APP_STATE_PATH", root / "state" / "app_state.json"):
                workspace = workspace_store.create_workspace("Office Lights")
                bundle = import_release_tarball(workspace, tarball)

                self.assertIsNotNone(bundle.build_dir)
                self.assertTrue(bundle.provisioning_supported)


if __name__ == "__main__":
    unittest.main()
