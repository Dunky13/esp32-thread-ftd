from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import fleet_data


class FleetDataDuplicateSerialTests(unittest.TestCase):
    def test_load_manifest_rows_rejects_duplicate_serial_num(self) -> None:
        manifest = self.write_csv(
            [
                "serial_num,discriminator,passcode,vendor_id,product_id",
                "ABC,3840,20202021,0x1234,0x5678",
                "ABC,3841,20202022,0x1234,0x5678",
            ]
        )

        with self.assertRaises(SystemExit) as context:
            fleet_data.load_manifest_rows(manifest)

        self.assertEqual(
            str(context.exception),
            "Manifest has duplicate serial_num 'ABC' on rows 2 and 3",
        )

    def test_load_manifest_rows_accepts_unique_serial_num(self) -> None:
        manifest = self.write_csv(
            [
                "serial_num,discriminator,passcode,vendor_id,product_id",
                "ABC,3840,20202021,0x1234,0x5678",
                "DEF,3841,20202022,0x1234,0x5678",
            ]
        )

        rows = fleet_data.load_manifest_rows(manifest)

        self.assertEqual([row["serial_num"] for row in rows], ["ABC", "DEF"])

    def test_load_device_rows_rejects_duplicate_serial_num(self) -> None:
        devices_csv = self.write_csv(
            [
                "serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode",
                "ABC,3840,20202021,0x1234,0x5678,Vendor,Product,/tmp/a.bin,/tmp/a.csv,/tmp/a-onboard.csv,MT:ABC,12345678901",
                "ABC,3841,20202022,0x1234,0x5678,Vendor,Product,/tmp/b.bin,/tmp/b.csv,/tmp/b-onboard.csv,MT:DEF,12345678902",
            ]
        )

        with self.assertRaises(SystemExit) as context:
            fleet_data.load_device_rows(devices_csv)

        self.assertEqual(
            str(context.exception),
            "Devices CSV has duplicate serial_num 'ABC' on rows 2 and 3",
        )

    def test_load_device_rows_accepts_unique_serial_num(self) -> None:
        devices_csv = self.write_csv(
            [
                "serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode",
                "ABC,3840,20202021,0x1234,0x5678,Vendor,Product,/tmp/a.bin,/tmp/a.csv,/tmp/a-onboard.csv,MT:ABC,12345678901",
                "DEF,3841,20202022,0x1234,0x5678,Vendor,Product,/tmp/b.bin,/tmp/b.csv,/tmp/b-onboard.csv,MT:DEF,12345678902",
            ]
        )

        rows = fleet_data.load_device_rows(devices_csv)

        self.assertEqual([row["serial_num"] for row in rows], ["ABC", "DEF"])

    def write_csv(self, lines: list[str]) -> pathlib.Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = pathlib.Path(temp_dir.name) / "data.csv"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
