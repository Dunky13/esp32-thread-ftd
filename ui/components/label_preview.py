from __future__ import annotations

from html import escape


def render_label_preview(label_html_exists: bool, workspace_id: str | None) -> str:
    if not label_html_exists or workspace_id is None:
        return '<p class="muted">Generate files to preview printable labels.</p>'
    return (
        f'<iframe title="Label preview" src="/labels?workspace={escape(workspace_id)}"></iframe>'
    )

