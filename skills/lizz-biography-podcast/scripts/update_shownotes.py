#!/usr/bin/env python3
"""更新已上传单集的 Show Notes（description）。

通过小宇宙创作者后台的编辑页面，用 Playwright 模拟编辑单集 shownotes。
"""
import argparse
import json
import os
import sys
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_PATH = Path(os.environ.get("XYZ_AUTH_FILE", "~/.xiaoyuzhou_auth.json")).expanduser()
BASE_URL = "https://podcaster.xiaoyuzhoufm.com"
PODCAST_ID = "6a53643dd01e2a1f16e0f63e"
EDIT_URL_TMPL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/{{eid}}/edit"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def human_delay(min_s=0.5, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))


def human_type_delay():
    return random.randint(15, 40)


def load_config(episode_dir):
    config_path = os.path.join(episode_dir, "config.json")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def update_shownotes(page, episode_id, new_description):
    """更新单集的 Show Notes。"""
    edit_url = EDIT_URL_TMPL.format(eid=episode_id)
    print(f"  打开编辑页: {edit_url}")
    page.goto(edit_url, wait_until="networkidle", timeout=30000)

    if "accounts.xiaoyuzhoufm.com" in page.url:
        print("  ❌ Cookie 过期，请重新登录")
        return False

    human_delay(2.0, 3.0)

    # 关闭可能的弹窗
    for text in ["我知道了", "确定", "关闭"]:
        try:
            btn = page.locator(f'button:has-text("{text}")')
            for i in range(btn.count()):
                b = btn.nth(i)
                if b.is_visible():
                    b.click(timeout=2000)
                    human_delay(0.3, 0.6)
        except Exception:
            pass

    human_delay(0.5, 1.0)

    # 定位 Show Notes 编辑区（contenteditable）
    print("  定位 Show Notes 编辑区...")
    content_editable = page.locator('[contenteditable="true"]')
    ce_count = content_editable.count()
    print(f"  发现 {ce_count} 个 contenteditable 区域")

    if ce_count == 0:
        print("  ❌ 未找到可编辑区域")
        page.screenshot(path="/tmp/xyz_edit_debug.png", full_page=True)
        return False

    # Show Notes 通常是最大的 contenteditable，或者最后一个
    # 尝试每个，找到含有较多文本的那个
    target_idx = 0
    max_len = 0
    for i in range(ce_count):
        try:
            txt = content_editable.nth(i).inner_text()
            if len(txt) > max_len:
                max_len = len(txt)
                target_idx = i
        except Exception:
            pass

    print(f"  选择第 {target_idx} 个区域（现有文本 {max_len} 字）")

    target = content_editable.nth(target_idx)
    target.click()
    human_delay(0.3, 0.5)

    # 全选并删除
    page.keyboard.press("Meta+a")
    human_delay(0.2, 0.4)
    page.keyboard.press("Backspace")
    human_delay(0.3, 0.5)

    # 输入新内容
    print(f"  输入新 Show Notes（{len(new_description)} 字）...")
    page.keyboard.type(new_description, delay=human_type_delay())
    human_delay(1.0, 2.0)

    # 截图保存
    page.screenshot(path=f"/tmp/xyz_edit_{episode_id[:8]}_before_save.png", full_page=True)

    # 点击保存按钮
    print("  查找保存按钮...")
    saved = False
    btns = page.locator("button")
    for i in range(btns.count()):
        btn = btns.nth(i)
        try:
            text = btn.inner_text().strip()
        except Exception:
            continue
        if text in ("保存", "保存修改", "更新", "提交") and btn.is_visible():
            print(f"  点击「{text}」按钮")
            btn.scroll_into_view_if_needed(timeout=3000)
            human_delay(0.3, 0.6)
            btn.click(timeout=5000)
            saved = True
            break

    if not saved:
        # 尝试用 evaluate 点击
        try:
            save_btn = page.locator('button:has-text("保存")').first
            save_btn.click(timeout=5000)
            saved = True
        except Exception:
            pass

    if not saved:
        print("  ❌ 未找到保存按钮")
        return False

    human_delay(3.0, 5.0)
    print("  ✅ 保存完成")
    return True


def main():
    parser = argparse.ArgumentParser(description="更新小宇宙单集 Show Notes")
    parser.add_argument("--episode-dir", required=True, help="集数目录")
    parser.add_argument("--headed", action="store_true", help="显示浏览器")
    args = parser.parse_args()

    episode_dir = os.path.abspath(args.episode_dir)
    config = load_config(episode_dir)

    episode_id = config.get("episode", {}).get("episode_id")
    if not episode_id:
        print("[ERR] config.json 中没有 episode_id，请先上传单集", file=sys.stderr)
        sys.exit(1)

    description = config["episode"]["description"]
    title = config["episode"]["title"]

    print(f"📂 集数目录: {episode_dir}")
    print(f"🏷  标题: {title}")
    print(f"🆔 Episode ID: {episode_id}")
    print(f"📝 新 Show Notes（{len(description)} 字）:")
    print("-" * 50)
    print(description)
    print("-" * 50)
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            storage_state=str(COOKIE_PATH),
            viewport={"width": 1440, "height": 900},
            user_agent=USER_AGENT,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        if not args.headed:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
        page = context.new_page()
        success = update_shownotes(page, episode_id, description)
        browser.close()

    if success:
        print("\n✅ Show Notes 更新成功")
    else:
        print("\n❌ Show Notes 更新失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
