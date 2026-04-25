from __future__ import annotations

import hashlib
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path

from .workspace_store import Workspace, save_workspace


@dataclass(frozen=True)
class ReleaseBundle:
    source_filename: str
    sha256: str
    extract_dir: Path
    build_dir: Path | None
    provisioning_supported: bool


def is_supported_tarball(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith((".tar", ".tar.gz", ".tgz"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_tar_members(tarball: tarfile.TarFile) -> None:
    for member in tarball.getmembers():
        name = member.name
        target = Path(name)
        if target.is_absolute() or ".." in target.parts:
            raise ValueError(f"Unsafe tar member path: {name}")
        if member.islnk() or member.issym():
            link = Path(member.linkname)
            if link.is_absolute() or ".." in link.parts:
                raise ValueError(f"Unsafe tar link target: {member.linkname}")


def _find_first(root: Path, filename: str) -> Path | None:
    for path in root.rglob(filename):
        if path.is_file():
            return path
    return None


def import_release_tarball(workspace: Workspace, tarball_path: str | Path) -> ReleaseBundle:
    source = Path(tarball_path).expanduser().resolve()
    if not is_supported_tarball(source):
        raise ValueError("Release bundle must be .tar, .tar.gz, or .tgz")
    if not source.is_file():
        raise FileNotFoundError(f"Release tarball not found: {source}")

    checksum = _sha256(source)
    inputs_dir = workspace.path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    copied_tarball = inputs_dir / "release.tar.gz"
    if source != copied_tarball.resolve():
        shutil.copy2(source, copied_tarball)
    (inputs_dir / "release.sha256").write_text(f"{checksum}  {source.name}\n", encoding="utf-8")

    extract_dir = workspace.path / "bundle" / checksum[:12]
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with tarfile.open(copied_tarball) as tarball:
        _validate_tar_members(tarball)
        tarball.extractall(extract_dir)

    flasher_args = _find_first(extract_dir, "flasher_args.json")
    build_dir = flasher_args.parent if flasher_args else None
    provisioning_script = _find_first(
        extract_dir,
        "generate_esp32_chip_factory_bin.py",
    )

    bundle = ReleaseBundle(
        source_filename=source.name,
        sha256=checksum,
        extract_dir=extract_dir,
        build_dir=build_dir,
        provisioning_supported=provisioning_script is not None,
    )
    workspace.data["bundle"] = {
        "source_filename": bundle.source_filename,
        "sha256": bundle.sha256,
        "extract_dir": str(bundle.extract_dir.relative_to(workspace.path)),
        "build_dir": str(bundle.build_dir.relative_to(workspace.path)) if bundle.build_dir else None,
        "provisioning_supported": bundle.provisioning_supported,
    }
    save_workspace(workspace)
    return bundle


def current_bundle(workspace: Workspace) -> ReleaseBundle | None:
    data = workspace.data.get("bundle")
    if not isinstance(data, dict):
        return None
    extract_dir = data.get("extract_dir")
    if not extract_dir:
        return None
    build_dir = data.get("build_dir")
    return ReleaseBundle(
        source_filename=str(data.get("source_filename") or ""),
        sha256=str(data.get("sha256") or ""),
        extract_dir=workspace.path / str(extract_dir),
        build_dir=(workspace.path / str(build_dir)) if build_dir else None,
        provisioning_supported=bool(data.get("provisioning_supported")),
    )
