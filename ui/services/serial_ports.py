from __future__ import annotations


def list_serial_ports() -> list[str]:
    try:
        from tools.generate_flash_command import detect_serial_ports

        return detect_serial_ports()
    except Exception:
        return []

