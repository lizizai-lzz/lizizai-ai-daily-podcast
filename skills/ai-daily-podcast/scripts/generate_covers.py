#!/usr/bin/env python3
"""Generate 1:1 podcast cover PNGs from HTML template using Playwright.

Usage:
    python3 generate_covers.py --date YYYY-MM-DD --output-dir /path/to/podcast/dir

The script reads cover data from stdin as JSON array:
    [
      {
        "type": "daily_brief",
        "seriesTag": "每日精选",
        "seriesEn": "DAILY BRIEF",
        "label": "头 版",
        "hit1": "万亿参数Agent模型开源上线",
        "hit2": "Notion开发者平台正式开放",
        "hit3": "Kimi K2.6登顶金融基准测试"
      },
      ...
    ]
"""

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PATH = SKILL_DIR / "templates" / "cover_template.html"

COVERS_CONFIG = {
    "daily_brief": {
        "seriesTag": "每日精选",
        "seriesEn": "DAILY BRIEF",
        "label": "头 版",
    },
    "opensource": {
        "seriesTag": "开源解读",
        "seriesEn": "OPEN SOURCE",
        "label": "开 源",
    },
    "industry_trends": {
        "seriesTag": "行业洞见",
        "seriesEn": "INDUSTRY INSIGHTS",
        "label": "洞 见",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generate podcast cover PNGs from HTML template")
    parser.add_argument("--date", required=True, help="Date string (YYYY-MM-DD)")
    parser.add_argument("--output-dir", required=True, help="Output directory for PNG files")
    parser.add_argument("--data", required=True, help="JSON string: list of cover data objects")
    parser.add_argument("--template", default=None, help="Custom template HTML path")
    args = parser.parse_args()

    covers = json.loads(args.data)
    output_dir = Path(args.output_dir)
    template_path = Path(args.template) if args.template else TEMPLATE_PATH
    template_url = template_path.as_uri()

    date_display = args.date.replace("-", "年", 1).replace("-", "月", 1) + "日"

    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1024, "height": 1024},
            device_scale_factor=2,
        )

        for cover in covers:
            page.goto(template_url)
            page.wait_for_load_state("networkidle")
            time.sleep(1.5)

            cover_type = cover.get("type", "daily_brief")
            defaults = COVERS_CONFIG.get(cover_type, COVERS_CONFIG["daily_brief"])

            js_data = json.dumps({
                "date": date_display,
                "audience": cover.get("audience", "独立开发者 · AI+教育"),
                "seriesTag": cover.get("seriesTag", defaults["seriesTag"]),
                "seriesEn": cover.get("seriesEn", defaults["seriesEn"]),
                "label": cover.get("label", defaults["label"]),
                "hit1": cover.get("hit1", ""),
                "hit2": cover.get("hit2", ""),
                "hit3": cover.get("hit3", ""),
            }, ensure_ascii=False)

            page.evaluate(f"window.setCoverData({js_data});")
            time.sleep(0.5)

            output_path = output_dir / f"cover_{cover_type}_{args.date}.png"
            el = page.locator(".cover")
            el.screenshot(path=str(output_path))

            size_mb = output_path.stat().st_size / (1024 * 1024)
            result = {
                "type": cover_type,
                "path": str(output_path),
                "size_mb": round(size_mb, 1),
            }
            results.append(result)
            print(f"✅ {output_path.name} ({size_mb:.1f}MB, 2048x2048)")

        browser.close()

    # Output JSON result for downstream consumption
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
