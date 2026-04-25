from __future__ import annotations

import webbrowser
from pathlib import Path

from .workspace_store import Workspace


def open_print_preview(workspace: Workspace) -> Path:
    label_html = workspace.label_html_path
    if not label_html.is_file():
        raise FileNotFoundError(f"Label HTML not found: {label_html}")
    webbrowser.open(label_html.resolve().as_uri())
    return label_html

