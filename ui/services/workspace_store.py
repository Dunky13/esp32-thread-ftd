from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


UI_ROOT = Path(__file__).resolve().parents[1]
WORKSPACES_DIR = UI_ROOT / "workspaces"
STATE_DIR = UI_ROOT / "state"
APP_STATE_PATH = STATE_DIR / "app_state.json"


@dataclass(frozen=True)
class WorkspaceSummary:
    id: str
    name: str
    updated_at: str
    generation_status: str


@dataclass
class Workspace:
    id: str
    name: str
    path: Path
    data: dict[str, object] = field(default_factory=dict)

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest" / "device_manifest.csv"

    @property
    def out_dir(self) -> Path:
        return self.path / "out"

    @property
    def devices_csv_path(self) -> Path:
        return self.out_dir / "devices.csv"

    @property
    def labels_dir(self) -> Path:
        return self.path / "labels"

    @property
    def label_html_path(self) -> Path:
        return self.labels_dir / "matter-labels.html"

    @property
    def logs_dir(self) -> Path:
        return self.path / "logs"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "workspace"


def _workspace_json(workspace_id: str) -> Path:
    return WORKSPACES_DIR / workspace_id / "workspace.json"


def _read_json(path: Path, default: dict[str, object]) -> dict[str, object]:
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected object in {path}")
    return loaded


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")


def _workspace_from_data(workspace_id: str, data: dict[str, object]) -> Workspace:
    return Workspace(
        id=workspace_id,
        name=str(data.get("name") or workspace_id),
        path=WORKSPACES_DIR / workspace_id,
        data=data,
    )


def load_workspace(workspace_id: str) -> Workspace:
    path = _workspace_json(workspace_id)
    if not path.is_file():
        raise FileNotFoundError(f"Workspace not found: {workspace_id}")
    return _workspace_from_data(workspace_id, _read_json(path, {}))


def save_workspace(workspace: Workspace) -> None:
    workspace.data["updated_at"] = now_iso()
    _write_json(workspace.path / "workspace.json", workspace.data)


def list_workspaces() -> list[WorkspaceSummary]:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[WorkspaceSummary] = []
    for workspace_json in sorted(WORKSPACES_DIR.glob("*/workspace.json")):
        data = _read_json(workspace_json, {})
        status = "not generated"
        generation = data.get("generation")
        if isinstance(generation, dict):
            status = str(generation.get("status") or status)
        summaries.append(
            WorkspaceSummary(
                id=workspace_json.parent.name,
                name=str(data.get("name") or workspace_json.parent.name),
                updated_at=str(data.get("updated_at") or ""),
                generation_status=status,
            )
        )
    return sorted(summaries, key=lambda item: item.updated_at, reverse=True)


def create_workspace(name: str) -> Workspace:
    base_slug = slugify(name)
    workspace_id = base_slug
    suffix = 2
    while _workspace_json(workspace_id).exists():
        workspace_id = f"{base_slug}-{suffix}"
        suffix += 1

    created_at = now_iso()
    path = WORKSPACES_DIR / workspace_id
    for relative in ("inputs", "bundle", "manifest", "out", "labels", "logs"):
        (path / relative).mkdir(parents=True, exist_ok=True)

    data: dict[str, object] = {
        "version": 1,
        "id": workspace_id,
        "name": name,
        "created_at": created_at,
        "updated_at": created_at,
        "defaults": {
            "vendor_id": "0xFFF1",
            "product_id": "0x8000",
            "vendor_name": "ESP-C6-Matter",
            "product_name": "Thread Light",
            "serial_mode": "sequential",
            "serial_prefix": "LGT",
            "start_index": 1,
            "serial_width": 4,
            "count": 8,
            "hw_ver": "1",
            "hw_ver_str": "1.0",
            "mfg_date": datetime.now(UTC).date().isoformat(),
            "dac_provider": "example",
        },
        "outputs": {
            "manifest": "manifest/device_manifest.csv",
            "devices_csv": "out/devices.csv",
            "label_html": "labels/matter-labels.html",
        },
        "selection": {},
    }
    workspace = Workspace(id=workspace_id, name=name, path=path, data=data)
    save_workspace(workspace)
    set_last_workspace(workspace_id)
    return workspace


def set_last_workspace(workspace_id: str) -> None:
    state = _read_json(APP_STATE_PATH, {"version": 1, "recent_workspace_ids": []})
    recent = state.get("recent_workspace_ids")
    recent_ids = [str(item) for item in recent] if isinstance(recent, list) else []
    recent_ids = [workspace_id] + [item for item in recent_ids if item != workspace_id]
    state["last_workspace_id"] = workspace_id
    state["recent_workspace_ids"] = recent_ids[:10]
    _write_json(APP_STATE_PATH, state)


def get_last_workspace_id() -> str | None:
    state = _read_json(APP_STATE_PATH, {})
    value = state.get("last_workspace_id")
    return str(value) if value else None

