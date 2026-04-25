from __future__ import annotations

from html import escape


def render_port_options(ports: list[str], selected_port: str | None) -> str:
    if not ports:
        return '<option value="">No ports detected</option>'
    options = []
    for port in ports:
        selected = " selected" if port == selected_port else ""
        options.append(f'<option value="{escape(port)}"{selected}>{escape(port)}</option>')
    return "\n".join(options)

