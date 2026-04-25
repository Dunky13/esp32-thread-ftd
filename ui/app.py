from __future__ import annotations

import argparse
from email import policy
from email.parser import BytesParser
import html
import mimetypes
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .components.device_form import value
from .components.device_table import render_device_rows
from .components.flash_panel import render_port_options
from .components.label_preview import render_label_preview
from .components.workspace_picker import render_workspace_picker
from .services.labels import open_print_preview
from .services.pipeline_runner import (
    flash_device,
    generate_workspace_outputs,
    list_generated_devices,
    read_log_tail,
    write_uploaded_tarball,
)
from .services.release_bundle import current_bundle, import_release_tarball
from .services.serial_ports import list_serial_ports
from .services.workspace_store import (
    create_workspace,
    get_last_workspace_id,
    list_workspaces,
    load_workspace,
    save_workspace,
    set_last_workspace,
)


HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _parse_qs(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


def _first(mapping: dict[str, list[str]], key: str, default: str = "") -> str:
    values = mapping.get(key)
    return values[0] if values else default


def _selected_workspace_id(query: dict[str, list[str]]) -> str | None:
    return _first(query, "workspace") or get_last_workspace_id()


def _load_selected(query: dict[str, list[str]]):
    workspace_id = _selected_workspace_id(query)
    if not workspace_id:
        return None
    try:
        workspace = load_workspace(workspace_id)
    except FileNotFoundError:
        return None
    set_last_workspace(workspace.id)
    return workspace


def _shell(body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32-C6 Provisioning</title>
<style>
:root {{
  color-scheme: light;
  --ink: #17201b;
  --muted: #65716b;
  --line: #cbd6cf;
  --paper: #f5f7f1;
  --panel: #ffffff;
  --accent: #0f766e;
  --warn: #b45309;
  --ok: #166534;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  color: var(--ink);
  background: linear-gradient(180deg, #eef3ea 0, var(--paper) 280px);
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  padding: 24px clamp(18px, 5vw, 56px) 16px;
  border-bottom: 1px solid var(--line);
}}
h1 {{ margin: 0; font-size: clamp(24px, 4vw, 42px); letter-spacing: 0; }}
main {{ display: grid; gap: 18px; padding: 18px clamp(18px, 5vw, 56px) 40px; }}
section {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
form {{ display: grid; gap: 12px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
label {{ display: grid; gap: 5px; color: var(--muted); font-size: 13px; }}
input, select, button {{
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
  background: white;
}}
button {{
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  cursor: pointer;
  font-weight: 650;
}}
button.secondary {{ background: white; color: var(--ink); border-color: var(--line); }}
.actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }}
.actions > * {{ width: auto; }}
.device-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr)); gap: 12px; }}
.device-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; min-width: 0; }}
.device-card-head {{ display: flex; gap: 10px; align-items: center; justify-content: space-between; min-width: 0; }}
.pick-row {{ display: flex; grid-template-columns: none; flex-direction: row; align-items: center; gap: 8px; min-width: 0; color: var(--ink); }}
.pick-row input {{ width: auto; min-height: auto; }}
.pick-row strong {{ overflow-wrap: anywhere; }}
.device-meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 12px 0 0; }}
.device-meta div {{ min-width: 0; }}
.device-meta .wide {{ grid-column: 1 / -1; }}
.device-meta dt {{ color: var(--muted); font-size: 12px; margin-bottom: 3px; }}
.device-meta dd {{ margin: 0; min-width: 0; }}
code {{ display: inline-block; max-width: 100%; overflow-wrap: anywhere; word-break: break-word; }}
.muted {{ color: var(--muted); }}
.badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; color: var(--ok); }}
.notice {{ border-left: 4px solid var(--warn); padding: 10px 12px; background: #fff7ed; }}
pre {{ max-height: 360px; overflow: auto; padding: 12px; background: #111827; color: #d1fae5; border-radius: 8px; }}
iframe {{ width: 100%; min-height: 420px; border: 1px solid var(--line); border-radius: 8px; background: white; }}
@media (max-width: 720px) {{
  .device-meta {{ grid-template-columns: 1fr; }}
  .actions > * {{ width: 100%; }}
}}
</style>
</head>
<body>
<header><h1>ESP32-C6 Provisioning</h1><p class="muted">Local release bundle, device identity, labels, flash.</p></header>
<main>{body}</main>
</body>
</html>""".encode("utf-8")


def render_home(query: dict[str, list[str]], notice: str = "") -> bytes:
    if not notice:
        notice = _first(query, "notice")
    workspace = _load_selected(query)
    workspaces = list_workspaces()
    defaults: dict[str, Any] = {}
    devices = []
    ports = list_serial_ports()
    selected_serial = None
    selected_port = None
    bundle_text = "No release bundle imported."
    log_text = ""
    if workspace is not None:
        raw_defaults = workspace.data.get("defaults")
        defaults = raw_defaults if isinstance(raw_defaults, dict) else {}
        devices = list_generated_devices(workspace)
        selection = workspace.data.get("selection")
        if isinstance(selection, dict):
            selected_serial = str(selection.get("serial_num") or "") or None
            selected_port = str(selection.get("serial_port") or "") or None
        bundle = current_bundle(workspace)
        if bundle is not None:
            build_dir = bundle.build_dir if bundle.build_dir else "not found"
            bundle_text = f"{bundle.source_filename} / {bundle.sha256[:12]} / build: {build_dir}"
        generation = workspace.data.get("generation")
        if isinstance(generation, dict) and generation.get("log_path"):
            log_text = read_log_tail(workspace, str(generation["log_path"]))
        flash = workspace.data.get("flash")
        if isinstance(flash, dict) and flash.get("log_path"):
            log_text = read_log_tail(workspace, str(flash["log_path"]))

    workspace_id = workspace.id if workspace else ""
    notice_html = f'<section class="notice">{html.escape(notice)}</section>' if notice else ""
    body = f"""
{notice_html}
<section>
  <h2>Workspace</h2>
  <form method="post" action="/workspace">
    <div class="grid">
      <label>Open<select name="workspace_id">{render_workspace_picker(workspaces, workspace_id or None)}</select></label>
      <label>New name<input name="name" placeholder="Office Lights"></label>
    </div>
    <div class="actions"><button>Open or create</button></div>
  </form>
</section>
<section>
  <h2>Release Bundle</h2>
  <p class="muted">{html.escape(bundle_text)}</p>
  <form method="post" action="/import?workspace={html.escape(workspace_id)}" enctype="multipart/form-data">
    <label>Tarball<input type="file" name="tarball" accept=".tar,.tar.gz,.tgz,application/gzip,application/x-tar"></label>
    <div class="actions"><button {"disabled" if not workspace else ""}>Import tarball</button></div>
  </form>
</section>
<section>
  <h2>Device Identity</h2>
  <form method="post" action="/generate?workspace={html.escape(workspace_id)}">
    <div class="grid">
      <label>Vendor ID<input name="vendor_id" value="{value(defaults, "vendor_id", "0xFFF1")}"></label>
      <label>Product ID<input name="product_id" value="{value(defaults, "product_id", "0x8000")}"></label>
      <label>Vendor name<input name="vendor_name" value="{value(defaults, "vendor_name", "ESP-C6-Matter")}"></label>
      <label>Product name<input name="product_name" value="{value(defaults, "product_name", "Thread Light")}"></label>
      <label>Amount<input name="count" type="number" min="1" value="{value(defaults, "count", 8)}"></label>
      <label>Hardware version<input name="hw_ver" value="{value(defaults, "hw_ver", "1")}"></label>
      <label>Hardware version string<input name="hw_ver_str" value="{value(defaults, "hw_ver_str", "1.0")}"></label>
      <label>Manufacturing date<input name="mfg_date" type="date" value="{value(defaults, "mfg_date", datetime_today())}"></label>
      <label>DAC provider<select name="dac_provider">
        {option("example", "Example DAC", str(defaults.get("dac_provider", "example")))}
        {option("factory", "Factory DAC", str(defaults.get("dac_provider", "example")))}
      </select></label>
      <label>Serial mode<select name="serial_mode">
        {option("sequential", "Sequential", str(defaults.get("serial_mode", "sequential")))}
        {option("uuid", "UUID-derived", str(defaults.get("serial_mode", "sequential")))}
      </select></label>
      <label>Serial prefix<input name="serial_prefix" value="{value(defaults, "serial_prefix", "LGT")}"></label>
      <label>Start index<input name="start_index" type="number" min="1" value="{value(defaults, "start_index", 1)}"></label>
      <label>Serial width<input name="serial_width" type="number" min="1" value="{value(defaults, "serial_width", 4)}"></label>
    </div>
    <label><input type="checkbox" name="use_test_attestation" value="1"> Use CHIP test attestation assets</label>
    <label><input type="checkbox" name="regenerate_identities" value="1"> Regenerate identities</label>
    <div class="actions"><button {"disabled" if not workspace else ""}>Generate files</button></div>
  </form>
</section>
<section>
  <h2>Generated Devices</h2>
  <form method="post" action="/flash?workspace={html.escape(workspace_id)}">
    <div class="device-grid">{render_device_rows(devices, selected_serial)}</div>
    <div class="grid">
      <label>Serial port<select name="port">{render_port_options(ports, selected_port)}</select></label>
      <label>Options<span><input type="checkbox" name="erase" value="1"> Erase first</span><span><input type="checkbox" name="monitor" value="1"> Monitor after flash</span></label>
    </div>
    <div class="actions">
      <button {"disabled" if not workspace or not devices else ""}>Flash selected</button>
      <a href="/?workspace={html.escape(workspace_id)}"><button type="button" class="secondary">Refresh ports</button></a>
      <a href="/print?workspace={html.escape(workspace_id)}"><button type="button" class="secondary">Print labels</button></a>
    </div>
  </form>
</section>
<section>
  <h2>Label Preview</h2>
  {render_label_preview(bool(workspace and workspace.label_html_path.is_file()), workspace_id or None)}
</section>
<section>
  <h2>Latest Log</h2>
  <pre>{html.escape(log_text or "No job logs yet.")}</pre>
</section>
"""
    return _shell(body)


def datetime_today() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


def option(value: str, label: str, selected_value: str) -> str:
    selected = " selected" if value == selected_value else ""
    return f'<option value="{html.escape(value)}"{selected}>{html.escape(label)}</option>'


def start_background_job(workspace_id: str, job_kind: str, fields: dict[str, Any]) -> None:
    workspace = load_workspace(workspace_id)
    workspace.data[job_kind] = {"status": "queued"}
    save_workspace(workspace)

    def run_job() -> None:
        job_workspace = load_workspace(workspace_id)
        try:
            if job_kind == "generation":
                generate_workspace_outputs(job_workspace, fields)
            elif job_kind == "flash":
                flash_device(
                    job_workspace,
                    str(fields["serial_num"]),
                    str(fields["port"]),
                    erase=bool(fields.get("erase")),
                    monitor=bool(fields.get("monitor")),
                )
        except Exception as exc:
            failed_workspace = load_workspace(workspace_id)
            failed_workspace.data[job_kind] = {
                "status": "failed",
                "error": str(exc),
            }
            save_workspace(failed_workspace)

    threading.Thread(target=run_job, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = _parse_qs(self.path)
        try:
            if parsed.path == "/":
                self._send_html(render_home(query))
            elif parsed.path == "/labels":
                self._send_label(query)
            elif parsed.path == "/print":
                workspace = _load_selected(query)
                if workspace is None:
                    self._redirect("/", "Create or open workspace first.")
                else:
                    open_print_preview(workspace)
                    self._redirect(f"/?workspace={workspace.id}", "Print preview opened.")
            else:
                self.send_error(404)
        except Exception as exc:
            self._send_html(render_home(query, str(exc)), status=500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = _parse_qs(self.path)
        try:
            if parsed.path == "/workspace":
                fields = self._read_form()
                workspace_id = str(fields.get("workspace_id") or "")
                name = str(fields.get("name") or "").strip()
                if workspace_id:
                    workspace = load_workspace(workspace_id)
                elif name:
                    workspace = create_workspace(name)
                else:
                    raise ValueError("Choose existing workspace or enter new name.")
                set_last_workspace(workspace.id)
                self._redirect(f"/?workspace={workspace.id}", "Workspace ready.")
            elif parsed.path == "/import":
                workspace = _load_selected(query)
                if workspace is None:
                    raise ValueError("Create or open workspace first.")
                fields = self._read_form()
                file_item = fields.get("tarball")
                if not isinstance(file_item, tuple):
                    raise ValueError("Choose release tarball.")
                filename, data = file_item
                uploaded = write_uploaded_tarball(workspace, filename, data)
                bundle = import_release_tarball(workspace, uploaded)
                self._redirect(f"/?workspace={workspace.id}", f"Imported {bundle.source_filename}.")
            elif parsed.path == "/generate":
                workspace = _load_selected(query)
                if workspace is None:
                    raise ValueError("Create or open workspace first.")
                fields = self._read_form()
                start_background_job(workspace.id, "generation", fields)
                self._redirect(f"/?workspace={workspace.id}", "Generation queued.")
            elif parsed.path == "/flash":
                workspace = _load_selected(query)
                if workspace is None:
                    raise ValueError("Create or open workspace first.")
                fields = self._read_form()
                serial_num = str(fields.get("serial_num") or "")
                port = str(fields.get("port") or "")
                if not serial_num or not port:
                    raise ValueError("Select serial row and serial port.")
                start_background_job(workspace.id, "flash", fields)
                self._redirect(f"/?workspace={workspace.id}", "Flash queued.")
            else:
                self.send_error(404)
        except Exception as exc:
            self._send_html(render_home(query, str(exc)), status=500)

    def _read_form(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        if content_type.startswith("multipart/form-data"):
            message = BytesParser(policy=policy.default).parsebytes(
                b"Content-Type: "
                + content_type.encode("utf-8")
                + b"\r\nMIME-Version: 1.0\r\n\r\n"
                + raw_body
            )
            fields: dict[str, Any] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if filename:
                    fields[name] = (filename, payload)
                else:
                    charset = part.get_content_charset() or "utf-8"
                    fields[name] = payload.decode(charset, errors="replace")
            return fields
        raw = raw_body.decode("utf-8")
        parsed = urllib.parse.parse_qs(raw)
        return {key: values[0] for key, values in parsed.items()}

    def _send_html(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_label(self, query: dict[str, list[str]]) -> None:
        workspace = _load_selected(query)
        if workspace is None or not workspace.label_html_path.is_file():
            self.send_error(404)
            return
        body = workspace.label_html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.types_map.get(".html", "text/html"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, notice: str) -> None:
        separator = "&" if "?" in location else "?"
        target = f"{location}{separator}notice={urllib.parse.quote(notice)}"
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def run(host: str = HOST, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{server.server_port}/"
    print(url)
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local ESP32-C6 provisioning UI.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run(args.host, args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
