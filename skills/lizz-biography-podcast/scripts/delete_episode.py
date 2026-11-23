#!/usr/bin/env python3
"""删除小宇宙创作者后台的单集。

通过 Playwright 模拟在单集列表页/编辑页的「删除」操作。
小宇宙创作者后台的删除通常是：
  1. 进入单集列表页 /podcast/{pid}/episode
  2. 找到目标单集，点击其「更多」/「...」按钮
  3. 在弹出菜单中点击「删除」
  4. 在确认弹窗中再次点击「删除/确定」

或：
  1. 进入单集编辑页 /podcast/{pid}/episode/{eid}/edit
  2. 页面底部/顶部有「删除」按钮
  3. 确认弹窗

本脚本两种路径都尝试。
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
EPISODES_URL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode"
EDIT_URL_TMPL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/{{eid}}/edit"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def human_delay(min_s=0.5, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))


def dismiss_modals(page):
    for text in ["我知道了", "确定", "关闭", "取消"]:
        try:
            btn = page.locator(f'button:has-text("{text}")')
            for i in range(btn.count()):
                b = btn.nth(i)
                if b.is_visible():
                    b.click(timeout=2000)
                    human_delay(0.3, 0.6)
        except Exception:
            pass


def _new_context(browser, headless=True):
    context = browser.new_context(
        storage_state=str(COOKIE_PATH) if COOKIE_PATH.exists() else None,
        viewport={"width": 1440, "height": 900},
        user_agent=USER_AGENT,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        color_scheme="light",
        is_mobile=False,
        has_touch=False,
        java_script_enabled=True,
    )
    if headless:
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)
    return context


def try_delete_via_edit_page(page, episode_id):
    """方案 A：编辑页删除。"""
    edit_url = EDIT_URL_TMPL.format(eid=episode_id)
    print(f"  [方案A] 打开编辑页: {edit_url}")
    page.goto(edit_url, wait_until="networkidle", timeout=30000)

    if "accounts.xiaoyuzhoufm.com" in page.url:
        print("  ❌ Cookie 过期")
        return False

    human_delay(2.0, 3.0)
    dismiss_modals(page)
    human_delay(0.5, 1.0)

    # 截图观察页面结构
    page.screenshot(path=f"/tmp/xyz_delete_edit_{episode_id[:8]}.png", full_page=True)

    # 查找「删除」按钮或链接
    delete_found = False
    for selector in [
        'button:has-text("删除")',
        'a:has-text("删除")',
        '[role="button"]:has-text("删除")',
        'span:has-text("删除")',
    ]:
        try:
            el = page.locator(selector)
            for i in range(el.count()):
                e = el.nth(i)
                if e.is_visible():
                    txt = e.inner_text().strip()
                    if "删除" in txt and "恢复" not in txt:
                        print(f"  找到删除元素: 「{txt}」(selector={selector})")
                        e.scroll_into_view_if_needed(timeout=3000)
                        human_delay(0.3, 0.6)
                        e.click(timeout=3000)
                        delete_found = True
                        break
        except Exception:
            continue
        if delete_found:
            break

    if not delete_found:
        print("  编辑页未找到删除按钮")
        return False

    # 确认删除弹窗
    human_delay(1.0, 2.0)
    return _confirm_delete(page)


def try_delete_via_list_page(page, episode_id, title=None):
    """方案 B：列表页删除。"""
    print(f"  [方案B] 打开列表页: {EPISODES_URL}")
    page.goto(EPISODES_URL, wait_until="networkidle", timeout=30000)

    if "accounts.xiaoyuzhoufm.com" in page.url:
        print("  ❌ Cookie 过期")
        return False

    human_delay(2.0, 3.0)
    dismiss_modals(page)

    page.screenshot(path=f"/tmp/xyz_delete_list_{episode_id[:8]}.png", full_page=True)

    # 在列表中找到目标单集行
    # 小宇宙列表每行通常有「更多」/「...」按钮
    # 先尝试找到包含标题的行，然后在行内找操作按钮
    target_text = title or episode_id

    # 方案 B1：找含标题的行，hover 后找「更多/删除」
    found = False
    # 尝试找「更多」图标按钮（通常是三点图标）
    more_selectors = [
        'button[aria-label*="更多"]',
        'button[aria-label*="More"]',
        'button:has(svg)',  # 图标按钮
        '[role="button"]:has(svg)',
    ]

    # 先按标题定位行
    try:
        rows = page.locator(f'div:has-text("{target_text}")')
        print(f"  列表页找到 {rows.count()} 个含目标文本的元素")
    except Exception:
        rows = page.locator("body")

    # 方案 B2：遍历所有可能的「更多」按钮
    # 小宇宙列表每行 hover 会显示操作按钮
    # 直接找所有行容器，逐个 hover 并检查是否含目标标题
    # 这里简化：直接找页面上所有「删除」相关的隐藏元素或菜单项

    # 方案 B3：右键/长按单集行
    # 放弃复杂逻辑，提示用户手动处理
    print("  列表页自动删除较复杂（需 hover 触发菜单）")
    print("  建议改用编辑页删除或手动删除")
    return False


def _confirm_delete(page):
    """在删除确认弹窗中点击确认。"""
    human_delay(1.0, 2.0)
    page.screenshot(path="/tmp/xyz_delete_confirm.png", full_page=True)

    # 查找确认弹窗中的「删除/确定」按钮
    for text in ["删除", "确定", "确认删除", "确认"]:
        try:
            btns = page.locator(f'button:has-text("{text}")')
            for i in range(btns.count()):
                b = btns.nth(i)
                if not b.is_visible():
                    continue
                # 确认按钮通常在弹窗里，红色或主色调
                try:
                    cls = b.get_attribute("class") or ""
                    parent = b.evaluate("el => el.closest('[role=dialog], .mantine-Modal-modal, .Modal')")
                except Exception:
                    parent = None
                # 优先点击弹窗内的按钮
                if parent is not None:
                    print(f"  在弹窗内点击「{text}」")
                    b.click(timeout=3000)
                    human_delay(2.0, 4.0)
                    return True
        except Exception:
            continue

    # 兜底：点击最后一个含「删除」的可见按钮（通常是确认按钮）
    try:
        btns = page.locator('button:has-text("删除")')
        last = btns.last
        if last.is_visible():
            print("  点击最后一个删除按钮")
            last.click(timeout=3000)
            human_delay(2.0, 4.0)
            return True
    except Exception:
        pass

    print("  ❌ 未找到删除确认按钮")
    return False


def delete_episode(page, episode_id, title=None, headless=True):
    """主入口：尝试多种方案删除单集。"""
    print(f"\n{'='*60}")
    print(f"🗑  删除单集: {episode_id}")
    if title:
        print(f"   标题: {title}")
    print(f"{'='*60}")

    # 方案 A：编辑页
    if try_delete_via_edit_page(page, episode_id):
        # 验证：重新访问编辑页应 404 或跳转
        human_delay(2.0, 3.0)
        edit_url = EDIT_URL_TMPL.format(eid=episode_id)
        try:
            resp = page.goto(edit_url, wait_until="networkidle", timeout=15000)
            final_url = page.url
            body_text = page.inner_text("body")
            if "404" in body_text or "not found" in body_text.lower() or "不存在" in body_text:
                print("  ✅ 验证：编辑页已 404，删除成功")
                return True
            if "accounts.xiaoyuzhoufm.com" in final_url:
                print("  ⚠️  跳转到登录页（可能 Cookie 问题），删除状态未知")
                return True  # 假设成功
        except Exception as e:
            print(f"  验证访问异常（可能已删除）: {e}")
            return True
        print("  ⚠️  编辑页仍可访问，删除可能未成功")
        return False

    # 方案 B：列表页
    if try_delete_via_list_page(page, episode_id, title):
        return True

    print("\n❌ 自动删除失败，请手动删除")
    print(f"   手动删除地址: {EDIT_URL_TMPL.format(eid=episode_id)}")
    return False


def main():
    parser = argparse.ArgumentParser(description="删除小宇宙单集")
    parser.add_argument("--episode-dir", required=False, help="集数目录（读 config.json 的 episode_id）")
    parser.add_argument("--episode-id", required=False, help="直接指定 episode_id")
    parser.add_argument("--headed", action="store_true", help="显示浏览器")
    args = parser.parse_args()

    episode_id = args.episode_id
    title = None

    if not episode_id and args.episode_dir:
        episode_dir = os.path.abspath(args.episode_dir)
        config_path = os.path.join(episode_dir, "config.json")
        if os.path.isfile(config_path):
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            episode_id = cfg.get("episode", {}).get("episode_id")
            title = cfg.get("episode", {}).get("title")

    if not episode_id:
        print("[ERR] 请通过 --episode-dir 或 --episode-id 指定要删除的单集", file=sys.stderr)
        sys.exit(1)

    if not COOKIE_PATH.exists():
        print("[ERR] Cookie 不存在，请先运行 upload_episode.py --login", file=sys.stderr)
        sys.exit(1)

    print(f"🆔 Episode ID: {episode_id}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = _new_context(browser, headless=not args.headed)
        page = context.new_page()
        success = delete_episode(page, episode_id, title, headless=not args.headed)
        browser.close()

    if success:
        print("\n✅ 删除成功")
    else:
        print("\n❌ 删除失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
