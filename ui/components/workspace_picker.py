from __future__ import annotations

from html import escape

from ui.services.workspace_store import WorkspaceSummary


def render_workspace_picker(workspaces: list[WorkspaceSummary], selected_id: str | None) -> str:
    options = ['<option value="">Create new workspace...</option>']
    for workspace in workspaces:
        selected = " selected" if workspace.id == selected_id else ""
        options.append(
            f'<option value="{escape(workspace.id)}"{selected}>'
            f'{escape(workspace.name)} - {escape(workspace.generation_status)}</option>'
        )
    return "\n".join(options)

