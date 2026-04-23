from __future__ import annotations

import csv
import pathlib
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from unittest.mock import patch
import os


TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import detect_env_paths
import fleet_data
import generate_attestation_chain
import generate_device_manifest
import generate_factory_data
import generate_flash_command
import generate_label_assets
import generate_label_html
import light_pipeline
import tool_paths


class FleetDataTests(unittest.TestCase):
    def test_load_device_rows_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = pathlib.Path(temp_dir) / "devices.csv"
            csv_path.write_text("serial_num,vendor_id\nABC,0x1234\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                fleet_data.load_device_rows(csv_path)

        self.assertIn("Devices CSV missing required columns", str(context.exception))

    def test_read_onboarding_codes_rejects_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = pathlib.Path(temp_dir) / "onboarding.csv"
            csv_path.write_text("qrcode,manualcode\nMT:ABC,\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                fleet_data.read_onboarding_codes(csv_path)

        self.assertIn("Onboarding CSV row 2 missing required values", str(context.exception))


class DetectEnvPathsTests(unittest.TestCase):
    def test_render_shell_quotes_paths_with_spaces(self) -> None:
        result = detect_env_paths.DetectionResult(
            esp_matter_path=pathlib.Path("/tmp/My Repo/esp-matter"),
            idf_path=pathlib.Path("/tmp/ESP IDF/v5.4"),
            idf_candidates=[],
            version_hint=None,
        )

        rendered = detect_env_paths.render_shell(result, clean=False, activate=False)

        self.assertIn("export ESP_MATTER_PATH='/tmp/My Repo/esp-matter'", rendered)
        self.assertIn("export IDF_PATH='/tmp/ESP IDF/v5.4'", rendered)

    def test_load_eim_idf_path_reads_repo_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            idf_path = temp_root / "esp-idf"
            (idf_path / "tools").mkdir(parents=True)
            (idf_path / "export.sh").write_text("", encoding="utf-8")
            (idf_path / "tools" / "idf.py").write_text("", encoding="utf-8")
            config_path = temp_root / "eim_config.toml"
            config_path.write_text(f'idf_path = "{idf_path}"\n', encoding="utf-8")

            loaded_path = detect_env_paths.load_eim_idf_path(config_path)

        self.assertEqual(loaded_path, idf_path.resolve())

    def test_choose_idf_candidate_prefers_eim_config_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            eim_idf_path = temp_root / "idf-from-eim"
            env_idf_path = temp_root / "idf-from-env"
            for path in (eim_idf_path, env_idf_path):
                (path / "tools").mkdir(parents=True)
                (path / "export.sh").write_text("", encoding="utf-8")
                (path / "tools" / "idf.py").write_text("", encoding="utf-8")
            config_path = temp_root / "eim_config.toml"
            config_path.write_text(f'idf_path = "{eim_idf_path}"\n', encoding="utf-8")

            with patch.object(detect_env_paths, "EIM_CONFIG_PATH", config_path):
                with patch.dict(os.environ, {"IDF_PATH": str(env_idf_path)}, clear=False):
                    chosen = detect_env_paths.choose_idf_candidate(
                        [eim_idf_path, env_idf_path],
                        hint=None,
                    )

        self.assertEqual(chosen, eim_idf_path)


class GenerateFactoryDataTests(unittest.TestCase):
    def test_generate_test_cd_uses_chip_root_credentials_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chip_root = pathlib.Path(temp_dir) / "connectedhomeip"
            signing_dir = chip_root / "credentials" / "test" / "certification-declaration"
            signing_dir.mkdir(parents=True)
            (signing_dir / "Chip-Test-CD-Signing-Cert.pem").write_text("cert", encoding="utf-8")
            (signing_dir / "Chip-Test-CD-Signing-Key.pem").write_text("key", encoding="utf-8")

            chip_cert = pathlib.Path(temp_dir) / "chip-cert"
            chip_cert.write_text("", encoding="utf-8")
            output_path = pathlib.Path(temp_dir) / "device" / "Chip-Test-CD.der"

            with patch.object(generate_factory_data, "run_checked_command") as mocked_run:
                generate_factory_data.generate_test_cd(
                    chip_cert=chip_cert,
                    chip_root=chip_root,
                    output_path=output_path,
                    vendor_id_hex="FFF1",
                    product_id_hex="8000",
                    device_type_hex="010D",
                )

            command = mocked_run.call_args.args[0]
            self.assertIn(str(signing_dir / "Chip-Test-CD-Signing-Cert.pem"), command)
            self.assertIn(str(signing_dir / "Chip-Test-CD-Signing-Key.pem"), command)

    def test_generate_test_cd_finds_chip_cert_in_host_target_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chip_root = pathlib.Path(temp_dir) / "connectedhomeip"
            signing_dir = chip_root / "credentials" / "test" / "certification-declaration"
            signing_dir.mkdir(parents=True)
            (signing_dir / "Chip-Test-CD-Signing-Cert.pem").write_text("cert", encoding="utf-8")
            (signing_dir / "Chip-Test-CD-Signing-Key.pem").write_text("key", encoding="utf-8")

            chip_cert = chip_root / "out" / "darwin-arm64-chip-cert" / "chip-cert"
            chip_cert.parent.mkdir(parents=True)
            chip_cert.write_text("", encoding="utf-8")
            output_path = pathlib.Path(temp_dir) / "device" / "Chip-Test-CD.der"

            with patch.object(generate_factory_data, "run_checked_command") as mocked_run:
                generate_factory_data.generate_test_cd(
                    chip_cert=chip_root / "out" / "host" / "chip-cert",
                    chip_root=chip_root,
                    output_path=output_path,
                    vendor_id_hex="FFF1",
                    product_id_hex="8000",
                    device_type_hex="010D",
                )

            command = mocked_run.call_args.args[0]
            self.assertEqual(pathlib.Path(command[0]), chip_cert.resolve())

    def test_resolve_attestation_paths_skips_chip_cert_when_test_cd_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chip_root = pathlib.Path(temp_dir) / "connectedhomeip"
            attestation_dir = chip_root / "credentials" / "test" / "attestation"
            cd_dir = chip_root / "credentials" / "test" / "certification-declaration"
            attestation_dir.mkdir(parents=True)
            cd_dir.mkdir(parents=True)

            pai_cert = attestation_dir / "Chip-Test-PAI-FFF1-8000-Cert.der"
            dac_cert = attestation_dir / "Chip-Test-DAC-FFF1-8000-Cert.der"
            dac_key = attestation_dir / "Chip-Test-DAC-FFF1-8000-Key.der"
            cd = cd_dir / "Chip-Test-CD-FFF1-8000.der"
            for path in (pai_cert, dac_cert, dac_key, cd):
                path.write_text("", encoding="utf-8")

            resolved = generate_factory_data.resolve_attestation_paths(
                row={"vendor_id": "0xFFF1", "product_id": "0x8000"},
                row_index=0,
                manifest_dir=pathlib.Path(temp_dir),
                chip_root=chip_root,
                chip_cert=chip_root / "out" / "host" / "chip-cert",
                device_output_dir=pathlib.Path(temp_dir) / "device",
                use_test_attestation=True,
            )

        self.assertEqual(
            resolved,
            {
                "dac_cert": dac_cert,
                "dac_key": dac_key,
                "pai_cert": pai_cert,
                "cd": cd,
            },
        )

    def test_resolve_attestation_paths_reports_supported_pairs_for_missing_vid_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chip_root = pathlib.Path(temp_dir) / "connectedhomeip"
            attestation_dir = chip_root / "credentials" / "test" / "attestation"
            attestation_dir.mkdir(parents=True)

            (attestation_dir / "Chip-Test-PAI-FFF1-8000-Cert.der").write_text("", encoding="utf-8")
            (attestation_dir / "Chip-Test-DAC-FFF1-8000-Cert.der").write_text("", encoding="utf-8")
            (attestation_dir / "Chip-Test-DAC-FFF1-8000-Key.der").write_text("", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                generate_factory_data.resolve_attestation_paths(
                    row={"vendor_id": "0x1234", "product_id": "0x5678"},
                    row_index=0,
                    manifest_dir=pathlib.Path(temp_dir),
                    chip_root=chip_root,
                    chip_cert=chip_root / "out" / "host" / "chip-cert",
                    device_output_dir=pathlib.Path(temp_dir) / "device",
                    use_test_attestation=True,
                )

        message = str(context.exception)
        self.assertIn("Requested pair: 0x1234/0x5678", message)
        self.assertIn("Supported pairs in connectedhomeip test bundle: 0xFFF1/0x8000", message)


class GenerateAttestationChainTests(unittest.TestCase):
    def test_write_manifest_with_attestation_paths_preserves_existing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            manifest_path = temp_root / "device_manifest.csv"
            manifest_path.write_text(
                "serial_num,discriminator,passcode,vendor_id,product_id,hw_ver\n"
                "LFTD-0001,3840,20202021,0x1234,0x5678,1\n",
                encoding="utf-8",
            )
            output_path = temp_root / "manifest_with_attestation.csv"

            generate_attestation_chain.write_manifest_with_attestation_paths(
                manifest_path=manifest_path,
                output_path=output_path,
                rows=[
                    {
                        "serial_num": "LFTD-0001",
                        "discriminator": "3840",
                        "passcode": "20202021",
                        "vendor_id": "0x1234",
                        "product_id": "0x5678",
                        "hw_ver": "1",
                        "dac_cert": "/tmp/dac_cert.der",
                        "dac_key": "/tmp/dac_key.der",
                        "pai_cert": "/tmp/pai_cert.der",
                        "cd": "/tmp/cd.der",
                    }
                ],
            )

            with output_path.open(newline="", encoding="utf-8") as manifest_file:
                rows = list(csv.DictReader(manifest_file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hw_ver"], "1")
        self.assertEqual(rows[0]["dac_cert"], "/tmp/dac_cert.der")
        self.assertEqual(rows[0]["cd"], "/tmp/cd.der")

    def test_augment_rows_with_attestation_paths_reuses_pair_bundle(self) -> None:
        rows = [
            {
                "serial_num": "LFTD-0001",
                "discriminator": "3840",
                "passcode": "20202021",
                "vendor_id": "0x1234",
                "product_id": "0x5678",
            },
            {
                "serial_num": "LFTD-0002",
                "discriminator": "3841",
                "passcode": "20202022",
                "vendor_id": "0x1234",
                "product_id": "0x5678",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            bundle = {
                "pai_key_pem": temp_root / "pai_key.pem",
                "pai_cert_pem": temp_root / "pai_cert.pem",
                "pai_cert_der": temp_root / "pai_cert.der",
                "cd": temp_root / "cd.der",
            }
            device_assets = [
                {
                    "dac_cert": temp_root / "dac1.der",
                    "dac_key": temp_root / "dac1_key.der",
                    "pai_cert": temp_root / "pai1.der",
                    "cd": temp_root / "cd1.der",
                },
                {
                    "dac_cert": temp_root / "dac2.der",
                    "dac_key": temp_root / "dac2_key.der",
                    "pai_cert": temp_root / "pai2.der",
                    "cd": temp_root / "cd2.der",
                },
            ]

            with patch.object(
                generate_attestation_chain,
                "generate_pair_attestation_bundle",
                return_value=bundle,
            ) as mocked_pair, patch.object(
                generate_attestation_chain,
                "generate_device_attestation_credentials",
                side_effect=device_assets,
            ) as mocked_device:
                augmented_rows = generate_attestation_chain.augment_rows_with_attestation_paths(
                    rows=rows,
                    output_dir=temp_root / "attestation",
                    chip_cert_path=temp_root / "chip-cert",
                    vendor_name="Vendor",
                    product_name="Product",
                    valid_from="2021-06-28 14:23:43",
                    lifetime="4294967295",
                    device_type_hex="010D",
                )

        self.assertEqual(mocked_pair.call_count, 1)
        self.assertEqual(mocked_device.call_count, 2)
        self.assertEqual(augmented_rows[0]["dac_cert"], str((temp_root / "dac1.der").resolve()))
        self.assertEqual(augmented_rows[1]["cd"], str((temp_root / "cd2.der").resolve()))

    def test_generate_test_cd_reports_build_steps_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chip_root = pathlib.Path(temp_dir) / "connectedhomeip"
            signing_dir = chip_root / "credentials" / "test" / "certification-declaration"
            signing_dir.mkdir(parents=True)
            (signing_dir / "Chip-Test-CD-Signing-Cert.pem").write_text("cert", encoding="utf-8")
            (signing_dir / "Chip-Test-CD-Signing-Key.pem").write_text("key", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                generate_factory_data.generate_test_cd(
                    chip_cert=chip_root / "out" / "host" / "chip-cert",
                    chip_root=chip_root,
                    output_path=pathlib.Path(temp_dir) / "device" / "Chip-Test-CD.der",
                    vendor_id_hex="FFF1",
                    product_id_hex="8000",
                    device_type_hex="010D",
                )

        message = str(context.exception)
        self.assertIn("chip-cert tool not found", message)
        self.assertIn("gn gen out/host", message)
        self.assertIn("ninja -C out/host chip-cert", message)

    def test_verify_setup_payload_python_dependencies_accepts_ready_env(self) -> None:
        completed = unittest.mock.Mock(returncode=0, stdout="", stderr="")

        with patch.object(generate_factory_data.subprocess, "run", return_value=completed) as mocked_run:
            generate_factory_data.verify_setup_payload_python_dependencies(
                python_executable="/tmp/idf-python",
                requirements_path=pathlib.Path("/tmp/requirements.setuppayload.txt"),
                auto_install=True,
            )

        mocked_run.assert_called_once_with(
            [
                "/tmp/idf-python",
                "-c",
                generate_factory_data.SETUPPAYLOAD_IMPORT_CHECK,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_verify_setup_payload_python_dependencies_reports_missing_module(self) -> None:
        completed = unittest.mock.Mock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'stdnum'\n",
        )

        with patch.object(generate_factory_data.subprocess, "run", return_value=completed):
            with self.assertRaises(SystemExit) as context:
                generate_factory_data.verify_setup_payload_python_dependencies(
                    python_executable="/tmp/idf-python",
                    requirements_path=pathlib.Path("/tmp/requirements.setuppayload.txt"),
                    auto_install=False,
                )

        message = str(context.exception)
        self.assertIn("Factory generator Python env missing CHIP setup-payload deps.", message)
        self.assertIn("Python env: /tmp/idf-python", message)
        self.assertIn("Missing module: stdnum", message)
        self.assertIn(
            "Install with: /tmp/idf-python -m pip install -r /tmp/requirements.setuppayload.txt",
            message,
        )

    def test_verify_setup_payload_python_dependencies_auto_installs_then_accepts_env(self) -> None:
        missing = unittest.mock.Mock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'stdnum'\n",
        )
        ready = unittest.mock.Mock(returncode=0, stdout="", stderr="")

        with patch.object(generate_factory_data.subprocess, "run", side_effect=[missing, None, ready]) as mocked_run:
            generate_factory_data.verify_setup_payload_python_dependencies(
                python_executable="/tmp/idf-python",
                requirements_path=pathlib.Path("/tmp/requirements.setuppayload.txt"),
                auto_install=True,
            )

        self.assertEqual(mocked_run.call_count, 3)
        self.assertEqual(
            mocked_run.call_args_list[1].args[0],
            [
                "/tmp/idf-python",
                "-m",
                "pip",
                "install",
                "-r",
                "/tmp/requirements.setuppayload.txt",
            ],
        )
        self.assertEqual(mocked_run.call_args_list[1].kwargs, {"check": True})

    def test_verify_setup_payload_python_dependencies_reports_auto_install_failure(self) -> None:
        missing = unittest.mock.Mock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'stdnum'\n",
        )
        install_error = generate_factory_data.subprocess.CalledProcessError(
            2,
            [
                "/tmp/idf-python",
                "-m",
                "pip",
                "install",
                "-r",
                "/tmp/requirements.setuppayload.txt",
            ],
        )

        with patch.object(generate_factory_data.subprocess, "run", side_effect=[missing, install_error]):
            with self.assertRaises(SystemExit) as context:
                generate_factory_data.verify_setup_payload_python_dependencies(
                    python_executable="/tmp/idf-python",
                    requirements_path=pathlib.Path("/tmp/requirements.setuppayload.txt"),
                    auto_install=True,
                )

        message = str(context.exception)
        self.assertIn("Failed to auto-install CHIP setup-payload deps.", message)
        self.assertIn("pip exit code: 2", message)

    def test_collect_generator_pythonpath_entries_uses_cached_component_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            component_dir = (
                temp_root
                / ".espressif"
                / "tools"
                / "components"
                / "espressif"
                / "esp_secure_cert_mgr"
                / "2.9.2"
            )
            component_dir.mkdir(parents=True)
            zip_path = component_dir / "espressif__esp_secure_cert_mgr-v2.9.2.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("tools/esp_secure_cert/__init__.py", "")
                archive.writestr("tools/esp_secure_cert/tlv_format.py", "VALUE = 1\n")

            with patch.object(pathlib.Path, "home", return_value=temp_root):
                entries = generate_factory_data.collect_generator_pythonpath_entries(
                    temp_root / "missing-shim"
                )

        self.assertEqual(entries, [f"{zip_path}/tools"])

    def test_build_generator_pythonpath_keeps_existing_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            shim_root = temp_root / "_factory_generator_shim"
            shim_root.mkdir()

            with patch.object(pathlib.Path, "home", return_value=temp_root):
                pythonpath = generate_factory_data.build_generator_pythonpath(
                    existing_pythonpath="/tmp/existing",
                    shim_root=shim_root,
                )

        self.assertEqual(
            pythonpath,
            os.pathsep.join([str(shim_root), "/tmp/existing"]),
        )


class GenerateLabelAssetsTests(unittest.TestCase):
    def write_devices_csv(self, root: pathlib.Path) -> pathlib.Path:
        csv_path = root / "devices.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode",
                    "LFTD-0001,3840,20202021,0xFFF1,0x8000,Vendor,Product,/tmp/factory.bin,/tmp/factory.csv,/tmp/onboarding.csv,MT:TESTPAYLOAD,12345678901",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return csv_path

    def test_verify_segno_dependency_auto_installs_when_missing(self) -> None:
        fake_segno = unittest.mock.Mock()

        with patch.object(
            generate_label_assets,
            "load_segno_module",
            side_effect=[None, fake_segno],
        ), patch.object(
            generate_label_assets,
            "install_segno_dependency",
        ) as mocked_install:
            loaded = generate_label_assets.verify_segno_dependency("/tmp/tool-python")

        self.assertIs(loaded, fake_segno)
        mocked_install.assert_called_once_with("/tmp/tool-python")

    def test_verify_segno_dependency_reports_auto_install_failure(self) -> None:
        install_error = generate_label_assets.subprocess.CalledProcessError(
            2,
            [
                "/tmp/tool-python",
                "-m",
                "pip",
                "install",
                "segno",
            ],
        )

        with patch.object(
            generate_label_assets,
            "load_segno_module",
            return_value=None,
        ), patch.object(
            generate_label_assets,
            "install_segno_dependency",
            side_effect=install_error,
        ):
            with self.assertRaises(SystemExit) as context:
                generate_label_assets.verify_segno_dependency("/tmp/tool-python")

        message = str(context.exception)
        self.assertIn("Failed to auto-install QR SVG dependency.", message)
        self.assertIn("Python env: /tmp/tool-python", message)
        self.assertIn("Install command: /tmp/tool-python -m pip install segno", message)
        self.assertIn("pip exit code: 2", message)

    def test_main_renders_svg_when_segno_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            devices_csv = self.write_devices_csv(temp_root)
            output_dir = temp_root / "labels"
            resolved_output_dir = output_dir.resolve()
            fake_qr = unittest.mock.Mock()
            fake_segno = unittest.mock.Mock()
            fake_segno.make.return_value = fake_qr

            with patch.object(
                sys,
                "argv",
                [
                    "generate_label_assets.py",
                    "--devices-csv",
                    str(devices_csv),
                    "--output-dir",
                    str(output_dir),
                    "--render-qr-svg",
                ],
            ), patch.object(
                generate_label_assets, "verify_segno_dependency", return_value=fake_segno
            ):
                result = generate_label_assets.main()

            self.assertEqual(result, 0)
            fake_segno.make.assert_called_once_with("MT:TESTPAYLOAD")
            fake_qr.save.assert_called_once_with(
                resolved_output_dir / "LFTD-0001.svg",
                kind="svg",
                scale=8,
                border=2,
            )


class GenerateLabelHtmlTests(unittest.TestCase):
    def write_devices_csv(self, root: pathlib.Path) -> pathlib.Path:
        csv_path = root / "devices.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode",
                    "LFTD-0001,3840,20202021,0xFFF1,0x8000,Vendor,Product,/tmp/factory.bin,/tmp/factory.csv,/tmp/onboarding.csv,MT:TESTPAYLOAD,12345678901",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return csv_path

    def test_compute_layout_metrics_rejects_oversized_labels(self) -> None:
        with self.assertRaises(SystemExit) as context:
            generate_label_html.compute_layout_metrics(10.1, 15.0)

        self.assertIn("10 mm width x 15 mm height", str(context.exception))

    def test_compute_layout_metrics_scales_default_label_inside_border(self) -> None:
        layout = generate_label_html.compute_layout_metrics(10.0, 15.0)

        self.assertLess(layout.content_scale, 1.0)
        self.assertAlmostEqual(layout.content_scale, 0.93, places=2)
        self.assertAlmostEqual(layout.content_offset_x_mm, 0.0, places=4)
        self.assertAlmostEqual(layout.content_offset_y_mm, 0.175, places=3)

    def test_main_writes_portrait_label_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            devices_csv = self.write_devices_csv(temp_root)
            output_path = temp_root / "matter-labels.html"

            with patch.object(
                sys,
                "argv",
                [
                    "generate_label_html.py",
                    "--devices-csv",
                    str(devices_csv),
                    "--output",
                    str(output_path),
                ],
            ):
                result = generate_label_html.main()

            self.assertEqual(result, 0)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("--label-width: 10.0mm;", html)
            self.assertIn("--label-height: 15.0mm;", html)
            self.assertIn("brand-wordmark", html)
            self.assertIn("formatManualCode", html)
            self.assertIn("position: relative;", html)
            self.assertIn("position: absolute;", html)
            self.assertIn("calc(-50% + var(--content-offset-x))", html)
            self.assertIn("calc(-50% + var(--content-offset-y))", html)
            self.assertIn("download-button", html)
            self.assertIn("renderLabelToCanvas", html)
            self.assertIn('canvas.toDataURL("image/png")', html)
            self.assertIn("Download PNG", html)


class GenerateDeviceManifestTests(unittest.TestCase):
    def test_main_reuses_existing_manifest_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = pathlib.Path(temp_dir) / "device_manifest.csv"
            original = (
                "serial_num,discriminator,passcode,vendor_id,product_id,hw_ver,hw_ver_str,mfg_date,rd_id_uid\n"
                "LFTD-0001,3840,20202021,0xFFF1,0x8000,1,1.0,2026-04-22,ABCDEF0123456789ABCDEF0123456789\n"
            )
            manifest_path.write_text(original, encoding="utf-8")
            args = Namespace(
                count=10,
                output=str(manifest_path),
                serial_prefix="LFTD",
                start_index=1,
                serial_width=4,
                discriminator_start=3840,
                vendor_id="0xFFF1",
                product_id="0x8000",
                hw_ver="1",
                hw_ver_str="1.0",
                mfg_date="2026-04-22",
            )

            with patch.object(generate_device_manifest, "parse_args", return_value=args), patch.object(
                generate_device_manifest, "write_manifest"
            ) as mocked_write, patch("builtins.print") as mocked_print:
                result = generate_device_manifest.main()

            self.assertEqual(result, 0)
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original)
            mocked_write.assert_not_called()
            mocked_print.assert_called_once_with(
                f"Manifest exists at {manifest_path.resolve()}; reusing 1 rows (requested --count 10 ignored)"
            )

    def test_main_rejects_invalid_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = pathlib.Path(temp_dir) / "device_manifest.csv"
            manifest_path.write_text("serial_num\n", encoding="utf-8")
            args = Namespace(
                count=1,
                output=str(manifest_path),
                serial_prefix="LFTD",
                start_index=1,
                serial_width=4,
                discriminator_start=3840,
                vendor_id="0xFFF1",
                product_id="0x8000",
                hw_ver="1",
                hw_ver_str="1.0",
                mfg_date="2026-04-22",
            )

            with patch.object(generate_device_manifest, "parse_args", return_value=args):
                with self.assertRaises(SystemExit) as context:
                    generate_device_manifest.main()

        self.assertIn(
            "Manifest missing required columns: discriminator, passcode, vendor_id, product_id",
            str(context.exception),
        )


class GenerateFlashCommandTests(unittest.TestCase):
    def test_read_flasher_args_requires_expected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir)
            (build_dir / "flasher_args.json").write_text('{"flash_files": {}}', encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                generate_flash_command.read_flasher_args(build_dir)

        self.assertIn("flasher_args.json missing required keys", str(context.exception))

    def test_parse_factory_offset_rejects_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            partitions_csv = pathlib.Path(temp_dir) / "partitions.csv"
            partitions_csv.write_text("fctry,data,nvs\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                generate_flash_command.parse_factory_offset(partitions_csv)

        self.assertIn("Malformed partitions CSV line 1", str(context.exception))


class LightPipelineTests(unittest.TestCase):
    def test_prepare_idf_command_rewrites_idf_py_to_venv_python(self) -> None:
        idf_path = pathlib.Path("/tmp/esp-idf")
        idf_python = pathlib.Path("/tmp/python")

        command = light_pipeline.prepare_idf_command(
            ["idf.py", "-B", "build", "build"],
            idf_path=idf_path,
            idf_python=idf_python,
        )

        self.assertEqual(
            command,
            [
                "/tmp/python",
                "/tmp/esp-idf/tools/idf.py",
                "-B",
                "build",
                "build",
            ],
        )

    def test_detect_idf_python_uses_idf_tools_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            idf_path = temp_root / "esp-idf"
            tools_dir = idf_path / "tools"
            tools_dir.mkdir(parents=True)

            python_env_root = temp_root / ".espressif" / "python_env" / "idf9.9_py3.14_env"
            python_bin = python_env_root / "bin" / "python"
            python_bin.parent.mkdir(parents=True)
            python_bin.write_text("", encoding="utf-8")

            (tools_dir / "idf_tools.py").write_text(
                "\n".join(
                    [
                        "import os",
                        "",
                        "IDF_TOOLS_PATH_DEFAULT = '~/.espressif'",
                        "",
                        "class _Globals:",
                        "    idf_path = ''",
                        "    idf_tools_path = ''",
                        "",
                        "g = _Globals()",
                        "",
                        "def get_python_env_path():",
                        "    root = os.path.join(g.idf_tools_path, 'python_env', 'idf9.9_py3.14_env')",
                        "    return root, os.path.join(root, 'bin'), os.path.join(root, 'bin', 'python'), '9.9'",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"IDF_TOOLS_PATH": str(temp_root / ".espressif")}, clear=False):
                idf_python_env_path, idf_python = light_pipeline.detect_idf_python(idf_path)

        self.assertEqual(idf_python_env_path, python_env_root)
        self.assertEqual(idf_python, python_bin)

    def test_write_build_override_avoids_build_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build" / "light-c6-thread"

            override_path = light_pipeline.write_build_override(
                build_dir=build_dir,
                vendor_id="0xFFF1",
                product_id="0x8000",
                dac_provider="example",
            )

            self.assertEqual(
                override_path,
                pathlib.Path(temp_dir) / "build" / "generated-configs" / "light-c6-thread.sdkconfig.defaults.generated",
            )
            self.assertFalse(build_dir.exists())

    def test_write_build_override_sets_8mb_flash_and_repo_partition_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build" / "light-c6-thread"

            override_path = light_pipeline.write_build_override(
                build_dir=build_dir,
                vendor_id="0xFFF1",
                product_id="0x8000",
                dac_provider="example",
            )

            override_text = override_path.read_text(encoding="utf-8")
            self.assertIn("CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y", override_text)
            self.assertIn('CONFIG_ESPTOOLPY_FLASHSIZE="8MB"', override_text)
            self.assertIn(
                f'CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="{tool_paths.DEFAULT_PARTITIONS_CSV}"',
                override_text,
            )
            self.assertIn('CONFIG_CHIP_FACTORY_NAMESPACE_PARTITION_LABEL="fctry"', override_text)

    def test_default_partitions_csv_exists_and_includes_fctry_partition(self) -> None:
        self.assertTrue(tool_paths.DEFAULT_PARTITIONS_CSV.is_file())

        partition_lines = tool_paths.DEFAULT_PARTITIONS_CSV.read_text(encoding="utf-8").splitlines()
        self.assertIn("fctry,    data, nvs,     0x3E0000,  0x6000", partition_lines)

    def test_write_build_override_rejects_unsupported_example_dac_vid_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build" / "light-c6-thread"

            with self.assertRaises(SystemExit) as context:
                light_pipeline.write_build_override(
                    build_dir=build_dir,
                    vendor_id="0x1234",
                    product_id="0x5678",
                    dac_provider="example",
                )

        self.assertIn("Example DAC provider only supports Matter test credentials", str(context.exception))

    def test_write_build_override_allows_supported_example_dac_vid_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build" / "light-c6-thread"

            override_path = light_pipeline.write_build_override(
                build_dir=build_dir,
                vendor_id="0xFFF1",
                product_id="0x8000",
                dac_provider="example",
            )

            self.assertTrue(override_path.is_file())

    def test_cleanup_stale_build_dir_removes_known_generated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build" / "light-c6-thread"
            build_dir.mkdir(parents=True)
            stale_file = build_dir / "sdkconfig.defaults.generated"
            stale_log = build_dir / "log"
            stale_file.write_text("old", encoding="utf-8")
            stale_log.mkdir()

            light_pipeline.cleanup_stale_build_dir(build_dir)

            self.assertFalse(stale_file.exists())
            self.assertFalse(stale_log.exists())

    def test_build_flash_generation_command_uses_repo_partition_table(self) -> None:
        command = light_pipeline.build_flash_generation_command(
            output_dir=pathlib.Path("/tmp/out"),
            build_dir=pathlib.Path("/tmp/build"),
            port="/dev/ttyUSB0",
            baud="921600",
            serial="LGT0001",
            serial_index=None,
        )

        self.assertIn("--partitions-csv", command)
        partitions_index = command.index("--partitions-csv") + 1
        self.assertEqual(command[partitions_index], str(tool_paths.DEFAULT_PARTITIONS_CSV))

    def test_build_idf_command_uses_set_target_for_new_build_dir(self) -> None:
        command = light_pipeline.build_idf_command(
            build_dir=pathlib.Path("/tmp/build"),
            override_path=pathlib.Path("/tmp/generated.sdkconfig.defaults"),
            target="esp32c6",
        )

        self.assertEqual(command[-3:], ["set-target", "esp32c6", "build"])

    def test_build_idf_command_reuses_existing_build_dir_when_target_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build"
            build_dir.mkdir()
            (build_dir / "CMakeCache.txt").write_text(
                "\n".join(
                    [
                        "CMAKE_PROJECT_NAME:STATIC=light",
                        "IDF_TARGET:STRING=esp32c6",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            command = light_pipeline.build_idf_command(
                build_dir=build_dir,
                override_path=pathlib.Path("/tmp/generated.sdkconfig.defaults"),
                target="esp32c6",
            )

        self.assertEqual(command[-2:], ["reconfigure", "build"])

    def test_build_idf_command_uses_set_target_when_existing_build_target_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = pathlib.Path(temp_dir) / "build"
            build_dir.mkdir()
            (build_dir / "CMakeCache.txt").write_text(
                "IDF_TARGET:STRING=esp32h2\n",
                encoding="utf-8",
            )

            command = light_pipeline.build_idf_command(
                build_dir=build_dir,
                override_path=pathlib.Path("/tmp/generated.sdkconfig.defaults"),
                target="esp32c6",
            )

        self.assertEqual(command[-3:], ["set-target", "esp32c6", "build"])

    def test_validate_run_args_allows_monitor_without_flash_flag_when_port_present(self) -> None:
        manifest_path = pathlib.Path("/tmp/device_manifest.csv")
        args = Namespace(
            use_test_attestation=False,
            dac_provider="example",
            count=1,
            flash=False,
            monitor=True,
            port="/dev/ttyUSB0",
        )

        light_pipeline.validate_run_args(args, manifest_path)

    def test_validate_run_args_requires_port_for_monitor(self) -> None:
        manifest_path = pathlib.Path("/tmp/device_manifest.csv")
        args = Namespace(
            use_test_attestation=False,
            dac_provider="example",
            count=1,
            flash=False,
            monitor=True,
            port=None,
        )

        with self.assertRaises(SystemExit) as context:
            light_pipeline.validate_run_args(args, manifest_path)

        self.assertIn("--port required with --flash or --monitor", str(context.exception))

    def test_validate_run_args_allows_factory_mode_without_test_attestation(self) -> None:
        manifest_path = pathlib.Path("/tmp/device_manifest.csv")
        args = Namespace(
            vendor_id="0x1234",
            product_id="0x5678",
            use_test_attestation=False,
            dac_provider="factory",
            count=1,
            flash=False,
            monitor=False,
            port=None,
        )

        light_pipeline.validate_run_args(args, manifest_path)

    def test_validate_run_args_rejects_generated_manifest_with_unsupported_test_attestation_pair(self) -> None:
        manifest_path = pathlib.Path("/tmp/device_manifest.csv")
        args = Namespace(
            vendor_id="0x1234",
            product_id="0x5678",
            use_test_attestation=True,
            dac_provider="factory",
            count=1,
            flash=False,
            monitor=False,
            port=None,
        )

        with patch.object(
            light_pipeline,
            "validate_test_attestation_pair",
            side_effect=SystemExit("bad pair"),
        ) as mocked_validate:
            with self.assertRaises(SystemExit) as context:
                light_pipeline.validate_run_args(args, manifest_path)

        self.assertIn("bad pair", str(context.exception))
        mocked_validate.assert_called_once_with(
            vendor_id="0x1234",
            product_id="0x5678",
        )

    def test_validate_run_args_rejects_existing_manifest_with_unsupported_test_attestation_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = pathlib.Path(temp_dir) / "device_manifest.csv"
            manifest_path.write_text(
                "serial_num,discriminator,passcode,vendor_id,product_id,hw_ver,hw_ver_str,mfg_date,rd_id_uid\n"
                "LFTD-0001,3840,20202021,0x1234,0x5678,1,1.0,2026-04-23,ABCDEF0123456789ABCDEF0123456789\n",
                encoding="utf-8",
            )
            args = Namespace(
                vendor_id="0xFFF1",
                product_id="0x8000",
                use_test_attestation=True,
                dac_provider="factory",
                count=None,
                flash=False,
                monitor=False,
                port=None,
            )

            with patch.object(
                light_pipeline,
                "validate_test_attestation_pair",
                side_effect=SystemExit("bad pair"),
            ) as mocked_validate:
                with self.assertRaises(SystemExit) as context:
                    light_pipeline.validate_run_args(args, manifest_path)

        self.assertIn("Manifest row 2: bad pair", str(context.exception))
        mocked_validate.assert_called_once_with(
            vendor_id="0x1234",
            product_id="0x5678",
        )

    def test_run_command_can_suppress_captured_stdout_echo(self) -> None:
        completed = unittest.mock.Mock(stdout="esptool.py --chip esp32c6", stderr="")

        with patch.object(light_pipeline.subprocess, "run", return_value=completed), patch(
            "builtins.print"
        ) as mocked_print:
            stdout = light_pipeline.run_command(
                ["echo", "ignored"],
                cwd=pathlib.Path("/tmp"),
                dry_run=False,
                capture_output=True,
                print_captured_output=False,
                require_idf=False,
            )

        self.assertEqual(stdout, "esptool.py --chip esp32c6")
        mocked_print.assert_called_once_with("    $ echo ignored")

    def test_run_pipeline_flashes_when_port_present_without_flash_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            manifest_path = temp_root / "device_manifest.csv"
            manifest_path.write_text("serial_num\n", encoding="utf-8")
            output_dir = temp_root / "out"
            build_dir = temp_root / "build"
            recorded_commands: list[list[str]] = []

            args = Namespace(
                manifest=str(manifest_path),
                output_dir=str(output_dir),
                build_dir=str(build_dir),
                count=None,
                use_test_attestation=False,
                dac_provider="example",
                port="/dev/ttyUSB0",
                flash=False,
                monitor=False,
                erase=False,
                serial="LGT0001",
                serial_index=1,
                baud="921600",
                skip_build=True,
                skip_labels=True,
                dry_run=False,
                vendor_id="0xFFF1",
                product_id="0x8000",
                vendor_name="Vendor",
                product_name="Product",
                target="esp32c6",
                label_output_dir=str(temp_root / "labels"),
                label_html=str(temp_root / "labels.html"),
                label_csv=None,
                render_qr_svg=False,
                serial_prefix="LGT",
                start_index=1,
                serial_width=4,
                discriminator_start=3840,
                hw_ver="1",
                hw_ver_str="1.0",
                mfg_date=None,
            )

            def fake_run_command(command: list[str], **_: object) -> str:
                recorded_commands.append(command)
                if len(command) > 1 and command[1].endswith("generate_flash_command.py"):
                    return "esptool.py --chip esp32c6"
                return ""

            with patch.object(light_pipeline, "ensure_example_tree"), patch.object(
                light_pipeline, "run_command", side_effect=fake_run_command
            ):
                light_pipeline.run_pipeline(args)

        self.assertTrue(any(len(command) > 1 and command[1].endswith("generate_flash_command.py") for command in recorded_commands))
        self.assertIn(["esptool.py", "--chip", "esp32c6"], recorded_commands)
        self.assertIn(["idf.py", "-B", str(build_dir.resolve()), "-p", "/dev/ttyUSB0", "monitor"], recorded_commands)

    def test_run_pipeline_generates_attestation_manifest_for_factory_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            manifest_path = temp_root / "device_manifest.csv"
            output_dir = temp_root / "out"
            build_dir = temp_root / "build"
            recorded_commands: list[list[str]] = []

            args = Namespace(
                manifest=str(manifest_path),
                output_dir=str(output_dir),
                build_dir=str(build_dir),
                count=1,
                use_test_attestation=False,
                dac_provider="factory",
                port=None,
                flash=False,
                monitor=False,
                erase=False,
                serial=None,
                serial_index=1,
                baud="921600",
                skip_build=True,
                skip_labels=True,
                dry_run=False,
                vendor_id="0x1234",
                product_id="0x5678",
                vendor_name="Vendor",
                product_name="Product",
                target="esp32c6",
                label_output_dir=str(temp_root / "labels"),
                label_html=str(temp_root / "labels.html"),
                label_csv=None,
                render_qr_svg=False,
                serial_prefix="LGT",
                start_index=1,
                serial_width=4,
                discriminator_start=3840,
                hw_ver="1",
                hw_ver_str="1.0",
                mfg_date=None,
            )

            with patch.object(light_pipeline, "ensure_example_tree"), patch.object(
                light_pipeline, "run_command", side_effect=lambda command, **_: recorded_commands.append(command) or ""
            ):
                light_pipeline.run_pipeline(args)

        attestation_manifest = output_dir.resolve() / "attestation" / "manifest_with_attestation.csv"
        self.assertTrue(any(len(command) > 1 and command[1].endswith("generate_attestation_chain.py") for command in recorded_commands))
        factory_command = next(
            command for command in recorded_commands
            if len(command) > 1 and command[1].endswith("generate_factory_data.py")
        )
        self.assertIn(str(attestation_manifest), factory_command)

    def test_run_pipeline_prints_qr_and_svg_before_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            manifest_path = temp_root / "device_manifest.csv"
            manifest_path.write_text("serial_num\n", encoding="utf-8")
            output_dir = temp_root / "out"
            output_dir.mkdir()
            (output_dir / "devices.csv").write_text(
                "\n".join(
                    [
                        "serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode",
                        "LGT0001,3840,20202021,0xFFF1,0x8000,Vendor,Product,/tmp/factory.bin,/tmp/factory.csv,/tmp/onboarding.csv,MT:TESTPAYLOAD,12345678901",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            build_dir = temp_root / "build"
            label_output_dir = temp_root / "labels"
            label_output_dir.mkdir()
            (label_output_dir / "LGT0001.svg").write_text("<svg>qr</svg>", encoding="utf-8")
            events: list[tuple[str, object]] = []

            args = Namespace(
                manifest=str(manifest_path),
                output_dir=str(output_dir),
                build_dir=str(build_dir),
                count=None,
                use_test_attestation=False,
                dac_provider="example",
                port="/dev/ttyUSB0",
                flash=False,
                monitor=False,
                erase=False,
                serial="LGT0001",
                serial_index=1,
                baud="921600",
                skip_build=True,
                skip_labels=False,
                dry_run=False,
                vendor_id="0xFFF1",
                product_id="0x8000",
                vendor_name="Vendor",
                product_name="Product",
                target="esp32c6",
                label_output_dir=str(label_output_dir),
                label_html=str(temp_root / "labels.html"),
                label_csv=None,
                render_qr_svg=True,
                serial_prefix="LGT",
                start_index=1,
                serial_width=4,
                discriminator_start=3840,
                hw_ver="1",
                hw_ver_str="1.0",
                mfg_date=None,
            )

            def fake_run_command(command: list[str], **_: object) -> str:
                events.append(("run", command))
                if len(command) > 1 and command[1].endswith("generate_flash_command.py"):
                    return "esptool.py --chip esp32c6"
                return ""

            def fake_print(*args: object, **_: object) -> None:
                if args:
                    events.append(("print", args[0]))

            with patch.object(light_pipeline, "ensure_example_tree"), patch.object(
                light_pipeline, "run_command", side_effect=fake_run_command
            ), patch.object(
                light_pipeline, "print_qr_codes_to_terminal",
                side_effect=lambda **_: events.append(("qr", "terminal")),
            ), patch.object(
                light_pipeline, "print_qr_svgs_to_terminal",
                side_effect=lambda **_: events.append(("svg", "terminal")),
            ), patch("builtins.print", side_effect=fake_print):
                light_pipeline.run_pipeline(args)

        monitor_event = ("run", ["idf.py", "-B", str(build_dir.resolve()), "-p", "/dev/ttyUSB0", "monitor"])
        self.assertEqual(events[-1], monitor_event)
        self.assertLess(events.index(("qr", "terminal")), events.index(monitor_event))
        self.assertLess(events.index(("svg", "terminal")), events.index(monitor_event))
        summary_index = next(
            index for index, event in enumerate(events)
            if event[0] == "print" and str(event[1]).startswith("Devices CSV:")
        )
        self.assertLess(summary_index, events.index(monitor_event))

    def test_flash_only_keeps_monitor_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            output_dir = temp_root / "out"
            build_dir = temp_root / "build"
            recorded_commands: list[list[str]] = []

            args = Namespace(
                output_dir=str(output_dir),
                build_dir=str(build_dir),
                port="/dev/ttyUSB0",
                erase=False,
                serial="LGT0001",
                serial_index=1,
                baud="921600",
                dry_run=False,
                monitor=False,
            )

            def fake_run_command(command: list[str], **_: object) -> str:
                recorded_commands.append(command)
                if len(command) > 1 and command[1].endswith("generate_flash_command.py"):
                    return "esptool.py --chip esp32c6"
                return ""

            with patch.object(light_pipeline, "ensure_example_tree"), patch.object(
                light_pipeline, "run_command", side_effect=fake_run_command
            ):
                light_pipeline.flash_only(args)

        self.assertTrue(any(len(command) > 1 and command[1].endswith("generate_flash_command.py") for command in recorded_commands))
        self.assertIn(["esptool.py", "--chip", "esp32c6"], recorded_commands)
        self.assertNotIn(["idf.py", "-B", str(build_dir.resolve()), "-p", "/dev/ttyUSB0", "monitor"], recorded_commands)

    def test_apply_idf_exports_expands_path_placeholder(self) -> None:
        env = light_pipeline.apply_idf_exports(
            {"PATH": "/usr/bin:/bin", "IDF_PATH": "/old"},
            "\n".join(
                [
                    "noise line",
                    "PATH=/tmp/idf/bin:$PATH",
                    "IDF_PATH=/tmp/esp-idf",
                ]
            ),
        )

        self.assertEqual(env["PATH"], "/tmp/idf/bin:/usr/bin:/bin")
        self.assertEqual(env["IDF_PATH"], "/tmp/esp-idf")

    def test_build_matter_environment_adds_expected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = esp_matter_root / "connectedhomeip" / "connectedhomeip"

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ):
                env = light_pipeline.build_matter_environment({"PATH": "/usr/bin:/bin"})

        self.assertEqual(env["ESP_MATTER_PATH"], str(esp_matter_root))
        self.assertEqual(env["ZAP_INSTALL_PATH"], str(chip_root / ".environment" / "cipd" / "packages" / "zap"))
        self.assertTrue(
            env["PATH"].startswith(
                os.pathsep.join(
                    [
                        str(chip_root / ".environment" / "cipd" / "packages" / "pigweed"),
                        str(chip_root / "out" / "host"),
                    ]
                )
            )
        )

    def test_ensure_repo_patches_applied_applies_pending_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = temp_root / "esp-matter" / "connectedhomeip" / "connectedhomeip"
            patch_dir = temp_root / "patches"
            chip_root.mkdir(parents=True)
            patch_dir.mkdir()
            patch_path = patch_dir / "fix.patch"
            patch_path.write_text("patch", encoding="utf-8")

            apply_check = unittest.mock.Mock(returncode=0, stdout="", stderr="")
            apply_run = unittest.mock.Mock()

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ), patch.object(light_pipeline, "PATCHES_DIR", patch_dir), patch.object(
                light_pipeline.subprocess, "run", side_effect=[apply_check, apply_run]
            ) as mocked_run, patch("builtins.print") as mocked_print:
                light_pipeline.ensure_repo_patches_applied()

        mocked_print.assert_called_once_with("    Applying repo patch `fix.patch` to `connectedhomeip`")
        self.assertEqual(
            mocked_run.call_args_list[1],
            unittest.mock.call(
                ["git", "apply", str(patch_path)],
                cwd=chip_root,
                check=True,
            ),
        )

    def test_ensure_repo_patches_applied_skips_already_applied_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = temp_root / "esp-matter" / "connectedhomeip" / "connectedhomeip"
            patch_dir = temp_root / "patches"
            chip_root.mkdir(parents=True)
            patch_dir.mkdir()
            patch_path = patch_dir / "fix.patch"
            patch_path.write_text("patch", encoding="utf-8")

            apply_check = unittest.mock.Mock(returncode=1, stdout="", stderr="nope")
            reverse_check = unittest.mock.Mock(returncode=0, stdout="", stderr="")

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ), patch.object(light_pipeline, "PATCHES_DIR", patch_dir), patch.object(
                light_pipeline.subprocess, "run", side_effect=[apply_check, reverse_check]
            ) as mocked_run, patch("builtins.print") as mocked_print:
                light_pipeline.ensure_repo_patches_applied()

        mocked_print.assert_called_once_with("    Repo patch already applied: `fix.patch` to `connectedhomeip`")
        self.assertEqual(mocked_run.call_count, 2)
        self.assertEqual(
            mocked_run.call_args_list[1],
            unittest.mock.call(
                ["git", "apply", "--reverse", "--check", str(patch_path)],
                cwd=chip_root,
                check=False,
                text=True,
                capture_output=True,
            ),
        )

    def test_ensure_repo_patches_applied_falls_back_to_esp_matter_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = esp_matter_root / "connectedhomeip" / "connectedhomeip"
            patch_dir = temp_root / "patches"
            esp_matter_root.mkdir(parents=True)
            chip_root.mkdir(parents=True)
            patch_dir.mkdir()
            patch_path = patch_dir / "fix.patch"
            patch_path.write_text("patch", encoding="utf-8")

            chip_apply_check = unittest.mock.Mock(returncode=1, stdout="", stderr="chip apply failed")
            chip_reverse_check = unittest.mock.Mock(returncode=1, stdout="", stderr="chip reverse failed")
            esp_matter_apply_check = unittest.mock.Mock(returncode=0, stdout="", stderr="")
            apply_run = unittest.mock.Mock()

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ), patch.object(light_pipeline, "PATCHES_DIR", patch_dir), patch.object(
                light_pipeline.subprocess,
                "run",
                side_effect=[chip_apply_check, chip_reverse_check, esp_matter_apply_check, apply_run],
            ) as mocked_run, patch("builtins.print") as mocked_print:
                light_pipeline.ensure_repo_patches_applied()

        mocked_print.assert_called_once_with("    Applying repo patch `fix.patch` to `esp-matter`")
        self.assertEqual(
            mocked_run.call_args_list[3],
            unittest.mock.call(
                ["git", "apply", str(patch_path)],
                cwd=esp_matter_root,
                check=True,
            ),
        )

    def test_ensure_matter_bootstrap_runs_when_gn_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = esp_matter_root / "connectedhomeip" / "connectedhomeip"
            scripts_dir = chip_root / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "bootstrap.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            which_calls = [None, str(chip_root / ".environment" / "cipd" / "packages" / "pigweed" / "gn")]

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ), patch.object(light_pipeline.shutil, "which", side_effect=which_calls), patch.object(
                light_pipeline, "ensure_recursive_submodules"
            ), patch.object(
                light_pipeline, "ensure_repo_patches_applied"
            ), patch.object(
                light_pipeline.subprocess, "run"
            ) as mocked_run:
                env = light_pipeline.ensure_matter_bootstrap({"PATH": "/usr/bin:/bin"})

        mocked_run.assert_called_once_with(
            ["bash", str(scripts_dir / "bootstrap.sh"), "-p", "all,esp32"],
            cwd=chip_root,
            check=True,
            env=unittest.mock.ANY,
        )
        self.assertIn(str(chip_root / ".environment" / "cipd" / "packages" / "pigweed"), env["PATH"])
        self.assertIn(str(chip_root / "out" / "host"), env["PATH"])

    def test_ensure_matter_bootstrap_skips_when_gn_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            esp_matter_root = temp_root / "esp-matter"
            chip_root = esp_matter_root / "connectedhomeip" / "connectedhomeip"

            with patch.object(light_pipeline, "ESP_MATTER_ROOT", esp_matter_root), patch.object(
                light_pipeline, "CHIP_ROOT", chip_root
            ), patch.object(light_pipeline.shutil, "which", return_value="/tmp/gn"), patch.object(
                light_pipeline, "ensure_recursive_submodules"
            ), patch.object(
                light_pipeline, "ensure_repo_patches_applied"
            ), patch.object(
                light_pipeline.subprocess, "run"
            ) as mocked_run:
                env = light_pipeline.ensure_matter_bootstrap({"PATH": "/usr/bin:/bin"})

        mocked_run.assert_not_called()
        self.assertIn(str(chip_root / ".environment" / "cipd" / "packages" / "pigweed"), env["PATH"])
        self.assertIn(str(chip_root / "out" / "host"), env["PATH"])

if __name__ == "__main__":
    unittest.main()
