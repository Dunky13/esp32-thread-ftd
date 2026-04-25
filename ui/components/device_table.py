from __future__ import annotations

from html import escape

from ui.services.pipeline_runner import DeviceRow


def render_device_rows(devices: list[DeviceRow], selected_serial: str | None) -> str:
    if not devices:
        return '<p class="muted">No generated devices yet.</p>'
    rows = []
    for device in devices:
        checked = " checked" if device.serial_num == selected_serial else ""
        rows.append(
            '<article class="device-card">'
            '<div class="device-card-head">'
            f'<label class="pick-row"><input type="radio" name="serial_num" value="{escape(device.serial_num)}"{checked}> '
            f'<strong>{escape(device.serial_num)}</strong></label>'
            f'<span class="badge">{escape(device.flash_status)}</span>'
            "</div>"
            '<dl class="device-meta">'
            f"<div><dt>VID / PID</dt><dd>{escape(device.vendor_id)} / {escape(device.product_id)}</dd></div>"
            f"<div><dt>Manual code</dt><dd><code>{escape(device.manualcode)}</code></dd></div>"
            f'<div class="wide"><dt>QR payload</dt><dd><code>{escape(device.qrcode)}</code></dd></div>'
            "</dl>"
            "</article>"
        )
    return "\n".join(rows)
