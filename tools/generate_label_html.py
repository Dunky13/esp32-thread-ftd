#!/usr/bin/env python3
"""Generate a printable HTML label sheet for Matter onboarding labels."""

from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass

from fleet_data import build_label_rows, filter_rows_by_serial, load_device_rows
from tool_paths import DEFAULT_DEVICES_CSV_PATH, DEFAULT_LABEL_HTML_PATH

LABEL_BORDER_WIDTH_MM = 0.35


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Matter Labels</title>
  <style>
    :root {{
      --page-pad: {page_pad_mm}mm;
      --label-width: {label_width_mm}mm;
      --label-height: {label_height_mm}mm;
      --label-gap: {label_gap_mm}mm;
      --label-border-width: {label_border_width_mm}mm;
      --content-width: {content_width_mm}mm;
      --content-height: {content_height_mm}mm;
      --content-scale: {content_scale};
      --content-offset-x: {content_offset_x_mm}mm;
      --content-offset-y: {content_offset_y_mm}mm;
      --border: #111827;
      --muted: #4b5563;
      --bg: #f7f7f5;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: var(--page-pad);
      background: linear-gradient(180deg, #ffffff 0%, var(--bg) 100%);
      color: #111827;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}

    .sheet {{
      display: inline-flex;
      flex-wrap: wrap;
      gap: var(--label-gap);
      justify-content: center;
      align-items: flex-start;
      width: fit-content;
      max-width: calc(100vw - (var(--page-pad) * 2));
    }}

    .label-item {{
      display: grid;
      gap: 1.1mm;
      justify-items: center;
    }}

    .label {{
      flex: 0 0 var(--label-width);
      width: var(--label-width);
      height: var(--label-height);
      border: var(--label-border-width) solid var(--border);
      border-radius: 1mm;
      background: #ffffff;
      display: grid;
      place-items: center;
      position: relative;
      overflow: hidden;
      break-inside: avoid;
      page-break-inside: avoid;
      box-shadow: 0 0.5mm 1.4mm rgba(0, 0, 0, 0.08);
    }}

    .label-content {{
      position: absolute;
      top: 50%;
      left: 50%;
      display: grid;
      grid-template-rows: auto 1fr auto;
      justify-items: center;
      align-items: start;
      gap: 0.55mm;
      padding: 0.55mm 0.55mm 0.7mm;
      transform: translate(
        calc(-50% + var(--content-offset-x)),
        calc(-50% + var(--content-offset-y))
      ) scale(var(--content-scale));
      transform-origin: center center;
    }}

    .header-stack {{
      display: grid;
      justify-items: center;
      gap: 0.3mm;
      width: 100%;
    }}

    .brand {{
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0.45mm;
      width: 100%;
      padding-top: 0.05mm;
    }}

    .brand-icon {{
      width: 1.65mm;
      height: 1.65mm;
      flex: 0 0 auto;
    }}

    .brand-wordmark {{
      font-size: 1.95mm;
      font-weight: 300;
      line-height: 1;
      letter-spacing: 0.04mm;
      white-space: nowrap;
    }}

    .serial-number {{
      width: 100%;
      text-align: center;
      font-size: 1.05mm;
      line-height: 1;
      font-weight: 600;
      letter-spacing: 0.05mm;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}

    .qr-wrap {{
      display: grid;
      align-content: center;
      justify-items: center;
      width: 100%;
    }}

    .qr-box {{
      width: 8.2mm;
      height: 8.2mm;
      display: grid;
      place-items: center;
      overflow: hidden;
      background: #fff;
    }}

    .qr-box canvas,
    .qr-box img {{
      width: 100%;
      height: 100%;
      display: block;
    }}

    .qr-fallback {{
      padding: 0.8mm;
      font-size: 1mm;
      line-height: 1.25;
      color: var(--muted);
      text-align: center;
      word-break: break-all;
    }}

    .label-actions {{
      display: flex;
      justify-content: center;
      width: 100%;
    }}

    .download-button {{
      border: 0;
      border-radius: 999px;
      background: #111827;
      color: #ffffff;
      font: inherit;
      font-size: 1.35mm;
      line-height: 1;
      font-weight: 600;
      letter-spacing: 0.03mm;
      padding: 0.9mm 1.8mm;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease;
    }}

    .download-button:hover {{
      transform: translateY(-0.15mm);
    }}

    .download-button:disabled {{
      opacity: 0.65;
      cursor: progress;
      transform: none;
    }}

    .manual-code {{
      width: 100%;
      text-align: center;
      font-size: 1.32mm;
      line-height: 1;
      font-weight: 500;
      letter-spacing: 0.03mm;
      padding: 0 0.2mm;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}

    @media print {{
      @page {{
        margin: 0;
      }}

      body {{
        min-height: auto;
        display: block;
        padding: var(--page-pad);
        background: #fff;
      }}

      .label-actions {{
        display: none;
      }}

      .label {{
        box-shadow: none;
      }}
    }}
  </style>
</head>
<body>
  <main class="sheet" id="sheet"></main>

  <script id="label-data" type="application/json">{json_payload}</script>
  <script src="https://cdn.jsdelivr.net/npm/qrcode/build/qrcode.min.js"></script>
  <script>
    const labels = JSON.parse(document.getElementById("label-data").textContent);
    const sheet = document.getElementById("sheet");
    const MM_PER_INCH = 25.4;
    const EXPORT_DPI = 600;
    const DEFAULT_CONTENT_WIDTH_MM = 10.0;
    const DEFAULT_CONTENT_HEIGHT_MM = 15.0;
    const BRAND_ICON_PATH = "M152 134.4c21.5 17.5 47.1 29.2 74.4 34.2V22.9l29.7-17.1 29.6 17.1v145.6c27.3-4.9 52.9-16.7 74.5-34.2l53.8 31.1c-87.6 86.6-228.5 86.6-316.1 0zm65.5 371.8C248.7 387 178.1 264.9 59.3 232.5v62.3c25.9 9.9 48.9 26.2 66.8 47.4L0 414.9v34.2l29.7 17 126.1-72.8c9.4 26.1 12 54.2 7.6 81.5zm235.3-273.7C334 265 263.6 387.1 294.8 506.2l54-31.2c-4.4-27.4-1.7-55.4 7.6-81.5l126 72.7 29.6-17.1v-34.2l-126.1-72.8c17.9-21.2 40.9-37.5 66.8-47.4z";

    function make(tag, className, text) {{
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }}

    function renderFallback(container, payload) {{
      const fallback = make("div", "qr-fallback", payload);
      container.replaceChildren(fallback);
    }}

    function renderQr(container, payload) {{
      if (!window.QRCode) {{
        renderFallback(container, payload);
        return;
      }}

      requestAnimationFrame(() => {{
        const boxSize = Math.max(1, Math.floor(container.getBoundingClientRect().width));
        const pixelRatio = Math.max(1, Math.ceil(window.devicePixelRatio || 1));

        window.QRCode.toCanvas(payload, {{
          margin: 0,
          width: boxSize * pixelRatio,
          color: {{
            dark: "#000000",
            light: "#ffffff"
          }}
        }}, (error, canvas) => {{
          if (error) {{
            renderFallback(container, payload);
            return;
          }}

          canvas.style.width = `${{boxSize}}px`;
          canvas.style.height = `${{boxSize}}px`;
          container.replaceChildren(canvas);
        }});
      }});
    }}

    function formatManualCode(value) {{
      const digits = String(value || "").replace(/\\D/g, "");
      if (digits.length === 11) {{
        return `${{digits.slice(0, 4)}}-${{digits.slice(4, 7)}}-${{digits.slice(7)}}`;
      }}
      return String(value || "");
    }}

    function readCssMm(name) {{
      return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)) || 0;
    }}

    function mmToPixels(mm, dpi = EXPORT_DPI) {{
      if (mm <= 0) {{
        return 0;
      }}
      return Math.max(1, Math.round((mm * dpi) / MM_PER_INCH));
    }}

    function textHeight(metrics, fallbackPx) {{
      const measured = Math.ceil(
        (metrics.actualBoundingBoxAscent || 0) + (metrics.actualBoundingBoxDescent || 0)
      );
      return Math.max(1, measured || fallbackPx || 0);
    }}

    function drawRoundedRect(ctx, x, y, width, height, radius) {{
      const maxRadius = Math.min(radius, width / 2, height / 2);
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {{
        ctx.roundRect(x, y, width, height, maxRadius);
        return;
      }}
      ctx.moveTo(x + maxRadius, y);
      ctx.arcTo(x + width, y, x + width, y + height, maxRadius);
      ctx.arcTo(x + width, y + height, x, y + height, maxRadius);
      ctx.arcTo(x, y + height, x, y, maxRadius);
      ctx.arcTo(x, y, x + width, y, maxRadius);
      ctx.closePath();
    }}

    function computeExportMetrics() {{
      const labelWidthMm = readCssMm("--label-width");
      const labelHeightMm = readCssMm("--label-height");
      const borderWidthMm = readCssMm("--label-border-width");
      const availableWidthMm = Math.max(labelWidthMm - (borderWidthMm * 2), 0);
      const availableHeightMm = Math.max(labelHeightMm - (borderWidthMm * 2), 0);
      const contentScale = Math.min(
        availableWidthMm / DEFAULT_CONTENT_WIDTH_MM,
        availableHeightMm / DEFAULT_CONTENT_HEIGHT_MM
      );
      const renderedWidthMm = DEFAULT_CONTENT_WIDTH_MM * contentScale;
      const renderedHeightMm = DEFAULT_CONTENT_HEIGHT_MM * contentScale;
      const contentLeftMm = borderWidthMm + ((availableWidthMm - renderedWidthMm) / 2);
      const contentTopMm = borderWidthMm + ((availableHeightMm - renderedHeightMm) / 2);

      return {{
        labelWidthPx: mmToPixels(labelWidthMm),
        labelHeightPx: mmToPixels(labelHeightMm),
        borderWidthPx: mmToPixels(borderWidthMm),
        borderRadiusPx: mmToPixels(1.0),
        contentScale,
        contentLeftPx: mmToPixels(contentLeftMm),
        contentTopPx: mmToPixels(contentTopMm),
        contentWidthPx: mmToPixels(renderedWidthMm),
        contentHeightPx: mmToPixels(renderedHeightMm),
        paddingX: mmToPixels(0.55 * contentScale),
        paddingTop: mmToPixels(0.55 * contentScale),
        paddingBottom: mmToPixels(0.7 * contentScale),
        gap: mmToPixels(0.55 * contentScale),
        headerGap: mmToPixels(0.3 * contentScale),
        brandFontPx: mmToPixels(1.95 * contentScale),
        iconSizePx: mmToPixels(1.65 * contentScale),
        iconGapPx: mmToPixels(0.45 * contentScale),
        qrSizePx: mmToPixels(8.2 * contentScale),
        serialFontPx: mmToPixels(1.05 * contentScale),
        manualFontPx: mmToPixels(1.32 * contentScale),
      }};
    }}

    function qrToCanvas(payload, width) {{
      return new Promise((resolve, reject) => {{
        if (!window.QRCode) {{
          reject(new Error("QRCode renderer unavailable"));
          return;
        }}
        window.QRCode.toCanvas(payload, {{
          margin: 0,
          width,
          color: {{
            dark: "#000000",
            light: "#ffffff"
          }}
        }}, (error, canvas) => {{
          if (error) {{
            reject(error);
            return;
          }}
          resolve(canvas);
        }});
      }});
    }}

    async function renderLabelToCanvas(label) {{
      const metrics = computeExportMetrics();
      const canvas = document.createElement("canvas");
      canvas.width = metrics.labelWidthPx;
      canvas.height = metrics.labelHeightPx;

      const ctx = canvas.getContext("2d");
      if (!ctx) {{
        throw new Error("Canvas context unavailable");
      }}

      const strokeInset = metrics.borderWidthPx / 2;
      drawRoundedRect(
        ctx,
        strokeInset,
        strokeInset,
        metrics.labelWidthPx - metrics.borderWidthPx,
        metrics.labelHeightPx - metrics.borderWidthPx,
        metrics.borderRadiusPx
      );
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.strokeStyle = "#111827";
      ctx.lineWidth = metrics.borderWidthPx;
      ctx.stroke();

      const brandText = "matter";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#111827";
      ctx.font = `${{metrics.brandFontPx}}px "Avenir Next", "Segoe UI", sans-serif`;

      const brandMetrics = ctx.measureText(brandText);
      const brandTextWidth = brandMetrics.width;
      const brandHeight = textHeight(brandMetrics, metrics.brandFontPx);
      const brandWidth = metrics.iconSizePx + metrics.iconGapPx + brandTextWidth;
      const brandX = metrics.contentLeftPx + ((metrics.contentWidthPx - brandWidth) / 2);
      const brandY = metrics.contentTopPx + metrics.paddingTop;

      const iconPath = new Path2D(BRAND_ICON_PATH);
      ctx.save();
      ctx.translate(brandX, brandY + ((brandHeight - metrics.iconSizePx) / 2));
      ctx.scale(metrics.iconSizePx / 512, metrics.iconSizePx / 512);
      ctx.fill(iconPath);
      ctx.restore();

      ctx.fillText(
        brandText,
        brandX + metrics.iconSizePx + metrics.iconGapPx,
        brandY
      );

      const serialText = label.serial_num || "";
      ctx.font = `600 ${{metrics.serialFontPx}}px "Avenir Next", "Segoe UI", sans-serif`;
      const serialMetrics = ctx.measureText(serialText);
      const serialHeight = textHeight(serialMetrics, metrics.serialFontPx);
      const serialX = metrics.contentLeftPx + ((metrics.contentWidthPx - serialMetrics.width) / 2);
      const serialY = brandY + brandHeight + metrics.headerGap;
      ctx.fillText(serialText, serialX, serialY);

      const manualText = formatManualCode(label.manualcode);
      ctx.font = `600 ${{metrics.manualFontPx}}px "Avenir Next", "Segoe UI", sans-serif`;
      const manualMetrics = ctx.measureText(manualText);
      const manualHeight = textHeight(manualMetrics, metrics.manualFontPx);
      const manualX = metrics.contentLeftPx + ((metrics.contentWidthPx - manualMetrics.width) / 2);
      const manualY = (
        metrics.contentTopPx +
        metrics.contentHeightPx -
        metrics.paddingBottom -
        manualHeight
      );
      ctx.fillText(manualText, manualX, manualY);

      const qrCanvas = await qrToCanvas(label.qrcode, metrics.qrSizePx);
      const qrRegionTop = serialY + serialHeight + metrics.gap;
      const qrRegionBottom = manualY - metrics.gap;
      const qrY = qrRegionTop + Math.max(0, Math.floor((qrRegionBottom - qrRegionTop - metrics.qrSizePx) / 2));
      const qrX = metrics.contentLeftPx + Math.floor((metrics.contentWidthPx - metrics.qrSizePx) / 2);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(qrCanvas, qrX, qrY, metrics.qrSizePx, metrics.qrSizePx);

      return canvas;
    }}

    async function downloadLabelPng(label, button) {{
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = "Rendering...";
      try {{
        const canvas = await renderLabelToCanvas(label);
        const link = document.createElement("a");
        link.download = `${{label.serial_num}}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
        button.textContent = "Saved";
      }} catch (error) {{
        console.error(error);
        button.textContent = "Retry PNG";
      }} finally {{
        window.setTimeout(() => {{
          button.disabled = false;
          button.textContent = originalText;
        }}, 900);
      }}
    }}

    function makeBrand() {{
      const brand = make("header", "brand");
      brand.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" viewBox="0 0 512 512" class="brand-icon"><path d="M152 134.4c21.5 17.5 47.1 29.2 74.4 34.2V22.9l29.7-17.1 29.6 17.1v145.6c27.3-4.9 52.9-16.7 74.5-34.2l53.8 31.1c-87.6 86.6-228.5 86.6-316.1 0zm65.5 371.8C248.7 387 178.1 264.9 59.3 232.5v62.3c25.9 9.9 48.9 26.2 66.8 47.4L0 414.9v34.2l29.7 17 126.1-72.8c9.4 26.1 12 54.2 7.6 81.5zm235.3-273.7C334 265 263.6 387.1 294.8 506.2l54-31.2c-4.4-27.4-1.7-55.4 7.6-81.5l126 72.7 29.6-17.1v-34.2l-126.1-72.8c17.9-21.2 40.9-37.5 66.8-47.4z" style="fill:#0c1221"/></svg>
        <div class="brand-wordmark">matter</div>
      `;
      return brand;
    }}

    labels.forEach((label) => {{
      const item = make("section", "label-item");
      const card = make("div", "label");
      const content = make("div", "label-content");
      const header = make("div", "header-stack");
      const brand = makeBrand();
      const serialNumber = make("div", "serial-number", label.serial_num);
      header.append(brand, serialNumber);

      const qrWrap = make("div", "qr-wrap");
      const qrBox = make("div", "qr-box");
      qrWrap.append(qrBox);

      const manualCode = make("div", "manual-code", formatManualCode(label.manualcode));
      const actions = make("div", "label-actions");
      const downloadButton = make("button", "download-button", "Download PNG");
      downloadButton.type = "button";
      downloadButton.setAttribute("aria-label", `Download ${{label.serial_num}} as PNG`);
      downloadButton.addEventListener("click", () => {{
        void downloadLabelPng(label, downloadButton);
      }});
      actions.append(downloadButton);

      content.append(header, qrWrap, manualCode);
      card.append(content);
      item.append(card, actions);
      sheet.append(item);
      renderQr(qrBox, label.qrcode);
    }});
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a printable HTML label sheet from Matter fleet data.",
    )
    parser.add_argument(
        "--devices-csv",
        default=str(DEFAULT_DEVICES_CSV_PATH),
        help="Fleet summary CSV produced by generate_factory_data.py.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_LABEL_HTML_PATH),
        help="HTML file to write.",
    )
    parser.add_argument(
        "--serial",
        action="append",
        help="Limit output to one or more serials. Repeat to include multiple devices.",
    )
    parser.add_argument(
        "--label-width-mm",
        type=float,
        default=10.0,
        help="Printed label width in millimeters. Max 10 mm.",
    )
    parser.add_argument(
        "--label-height-mm",
        type=float,
        default=15.0,
        help="Printed label height in millimeters. Max 15 mm.",
    )
    return parser.parse_args()


@dataclass(frozen=True)
class LayoutMetrics:
    content_width_mm: float
    content_height_mm: float
    content_scale: float
    content_offset_x_mm: float
    content_offset_y_mm: float
    page_pad_mm: float
    label_gap_mm: float


def compute_layout_metrics(label_width_mm: float, label_height_mm: float) -> LayoutMetrics:
    if label_width_mm <= 0 or label_height_mm <= 0:
        raise SystemExit("Label width and height must be greater than 0.")
    if label_width_mm > 10.0 or label_height_mm > 15.0:
        raise SystemExit("Label size exceeds max supported size of 10 mm width x 15 mm height.")

    content_width_mm = 10.0
    content_height_mm = 15.0
    available_width_mm = max(label_width_mm - (LABEL_BORDER_WIDTH_MM * 2), 0.0)
    available_height_mm = max(label_height_mm - (LABEL_BORDER_WIDTH_MM * 2), 0.0)
    content_scale = min(
        available_width_mm / content_width_mm,
        available_height_mm / content_height_mm,
    )
    rendered_width_mm = content_width_mm * content_scale
    rendered_height_mm = content_height_mm * content_scale

    return LayoutMetrics(
        content_width_mm=content_width_mm,
        content_height_mm=content_height_mm,
        content_scale=content_scale,
        content_offset_x_mm=(available_width_mm - rendered_width_mm) / 2,
        content_offset_y_mm=(available_height_mm - rendered_height_mm) / 2,
        page_pad_mm=min(4.0, max(1.0, min(label_width_mm, label_height_mm) * 0.25)),
        label_gap_mm=min(2.0, max(0.8, min(label_width_mm, label_height_mm) * 0.1)),
    )


def main() -> int:
    args = parse_args()
    devices_csv = pathlib.Path(args.devices_csv).resolve()
    output_path = pathlib.Path(args.output).resolve()
    if not devices_csv.is_file():
        raise SystemExit(f"Devices CSV not found: {devices_csv}")

    rows = load_device_rows(devices_csv)
    selected_rows = filter_rows_by_serial(rows, args.serial)
    label_rows = build_label_rows(selected_rows, include_passcode=False)
    layout = compute_layout_metrics(args.label_width_mm, args.label_height_mm)
    json_payload = json.dumps(label_rows).replace("</", "<\\/")

    html_output = HTML_TEMPLATE.format(
        json_payload=json_payload,
        label_width_mm=args.label_width_mm,
        label_height_mm=args.label_height_mm,
        label_border_width_mm=LABEL_BORDER_WIDTH_MM,
        content_width_mm=layout.content_width_mm,
        content_height_mm=layout.content_height_mm,
        content_scale=layout.content_scale,
        content_offset_x_mm=layout.content_offset_x_mm,
        content_offset_y_mm=layout.content_offset_y_mm,
        page_pad_mm=layout.page_pad_mm,
        label_gap_mm=layout.label_gap_mm,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")
    print(f"Wrote printable HTML labels to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
