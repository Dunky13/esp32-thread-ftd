# Examples

This page gives concrete examples of commands and generated data.

## Example: Fast Test-ID Build

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --vendor-id 0xFFF1 \
  --product-id 0x8000 \
  --vendor-name "Example Vendor" \
  --product-name "Example Thread Light"
```

Use this with default `--dac-provider example`.

## Example: Custom VID/PID Build

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --dac-provider factory \
  --vendor-id 0x1234 \
  --product-id 0x5678 \
  --vendor-name "My Vendor" \
  --product-name "My Thread Light"
```

Use this when example DAC mode cannot accept your IDs.

## Example: Flash One Device

```bash
python3 tools/light_pipeline.py flash \
  --port /dev/ttyUSB0 \
  --serial-index 1
```

## Example Manifest Row

```csv
serial_num,discriminator,passcode,vendor_id,product_id,hw_ver,hw_ver_str,mfg_date,rd_id_uid
LGT-0001,3840,20202021,0xFFF1,0x8000,1,1.0,2026-04-23,00112233445566778899AABBCCDDEEFF
```

## Example Manifest Row With Explicit Attestation Files

```csv
serial_num,discriminator,passcode,vendor_id,product_id,dac_cert,dac_key,pai_cert,cd
LGT-0001,3840,20202021,0x1234,0x5678,/abs/path/dac_cert.der,/abs/path/dac_key.der,/abs/path/pai_cert.der,/abs/path/cd.der
```

## Example `devices.csv` Row

```csv
serial_num,discriminator,passcode,vendor_id,product_id,vendor_name,product_name,factory_bin,factory_csv,onboarding_csv,qrcode,manualcode
LGT-0001,3840,20202021,0xFFF1,0x8000,Example Vendor,Example Thread Light,/abs/path/factory_partition.bin,/abs/path/nvs_partition.csv,/abs/path/onboarding_codes.csv,MT:EXAMPLEPAYLOAD,34970112332
```

## Example: Patch-Aware Build

```bash
python3 tools/light_pipeline.py run \
  --count 1 \
  --apply-patches
```

Use this only if you intentionally want pending repo patches applied into `esp-matter/`.

## Example: Dry Run

```bash
python3 tools/light_pipeline.py run --count 1 --dry-run
python3 tools/light_pipeline.py flash --port /dev/ttyUSB0 --serial-index 1 --dry-run
```

## Related Docs

- CLI options: [`cli.md`](./cli.md)
- manifest schema: [`manifest.md`](./manifest.md)
- commissioning: [`commissioning.md`](./commissioning.md)
