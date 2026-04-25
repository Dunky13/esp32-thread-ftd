from __future__ import annotations

from html import escape

from ui.services.pipeline_runner import DeviceRow


def render_device_rows(devices: list[DeviceRow], selected_serial: str | None) -> str:
    if not devices:
        return '<tr><td colspan="6" class="muted">No generated devices yet.</td></tr>'
    rows = []
    for device in devices:
        checked = " checked" if device.serial_num == selected_serial else ""
        rows.append(
            "<tr>"
            f'<td><input type="radio" name="serial_num" value="{escape(device.serial_num)}"{checked}></td>'
            f"<td>{escape(device.serial_num)}</td>"
            f"<td>{escape(device.vendor_id)} / {escape(device.product_id)}</td>"
            f"<td><code>{escape(device.manualcode)}</code></td>"
            f"<td><code>{escape(device.qrcode)}</code></td>"
            f'<td><span class="badge">{escape(device.flash_status)}</span></td>'
            "</tr>"
        )
    return "\n".join(rows)

