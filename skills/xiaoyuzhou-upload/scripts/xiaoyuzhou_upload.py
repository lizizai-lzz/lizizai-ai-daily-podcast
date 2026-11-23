#!/usr/bin/env python3
"""
小宇宙播客自动上传脚本

使用 Playwright 自动化上传 MP3 到小宇宙创作者后台。
支持 Cookie 复用登录、批量上传多条播客。
模拟真实浏览器指纹 + 随机延迟，降低被检测风险。

用法:
  python3 xiaoyuzhou_upload.py --date 2026-05-18           # 上传指定日期的播客
  python3 xiaoyuzhou_upload.py --date 2026-05-18 --type daily_brief  # 仅上传指定类型
  python3 xiaoyuzhou_upload.py --login                      # 重新登录（Cookie 过期时）
  python3 xiaoyuzhou_upload.py --date 2026-05-18 --headed   # 显示浏览器窗口
"""

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ─── 常量 ───────────────────────────────────────────────
PODCAST_ID = os.environ.get("PODCAST_SHOW_ID", "6a09a980f4ff26e89f601057")  # 默认：李自在AI日报
BASE_URL = "https://podcaster.xiaoyuzhoufm.com"
CREATE_EPISODE_URL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/create"
EPISODES_URL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode"
LOGIN_URL = f"{BASE_URL}/podcast"
COOKIE_PATH = Path(os.environ.get("XYZ_AUTH_FILE", "~/.xiaoyuzhou_auth.json")).expanduser()
NEWS_BASE = Path(os.path.expanduser("~/.daily-ai-news/data"))
PUBLIC_EPISODE_URL = "https://www.xiaoyuzhoufm.com/episode/{eid}"
AI_DECL_TEXT = "本音频为 AI 生成"

# ─── 浏览器指纹 ───────────────────────────────────────────
# Chrome 125 on macOS — 2026 年仍然常见的 UA
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def human_delay(min_s: float = 0.5, max_s: float = 2.5):
    """随机暂停，模拟人类操作节奏。"""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)
    return delay


def human_type_delay() -> int:
    """返回随机的逐字输入延迟（毫秒）。"""
    return random.randint(20, 60)


def _screenshot_path(podcast_type: str, stage: str, date: str) -> str:
    """返回调试截图保存路径（日报数据目录内，不使用 /tmp）。"""
    base = NEWS_BASE / date / "upload-logs" if date else NEWS_BASE / "upload-logs"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / f"xiaoyuzhou_{podcast_type}_{stage}.png")


def check_cookie_valid() -> bool:
    """检查 Cookie 文件是否存在且包含小宇宙域名的 cookie。"""
    if not COOKIE_PATH.exists():
        return False
    try:
        data = json.loads(COOKIE_PATH.read_text())
        cookies = data.get("cookies", [])
        xyz_cookies = [c for c in cookies if "xiaoyuzhoufm" in c.get("domain", "")]
        return len(xyz_cookies) > 0
    except (json.JSONDecodeError, KeyError):
        return False


def do_login():
    """打开浏览器让用户手动登录，登录成功后保存 Cookie。"""
    from playwright.sync_api import sync_playwright

    print("🔐 打开浏览器，请手动登录小宇宙创作者后台...")
    print("   登录成功后会自动保存 Cookie。")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = _new_context(browser, headless=False)
        page = context.new_page()

        page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        print(f"   登录页面已打开: {page.url}")

        # 等待登录成功（URL 变为 podcaster 后台）
        try:
            page.wait_for_url("**/podcast/**", timeout=180000)
        except Exception:
            page.wait_for_url("**/podcast*", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)

        # 保存 Cookie
        context.storage_state(path=str(COOKIE_PATH))
        print(f"✅ 登录成功！Cookie 已保存到 {COOKIE_PATH}")
        browser.close()


def _new_context(browser, headless: bool = True):
    """创建带有真实浏览器指纹的 context。"""
    from playwright.sync_api import Browser

    context = browser.new_context(
        storage_state=str(COOKIE_PATH) if COOKIE_PATH.exists() else None,
        viewport={"width": 1440, "height": 900},
        user_agent=USER_AGENT,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        color_scheme="light",
        # headless 模式下注入 WebGL vendor/renderer 避免被检测
        is_mobile=False,
        has_touch=False,
        java_script_enabled=True,
    )

    # 注入反检测脚本：覆盖 navigator.webdriver
    if headless:
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            // 覆盖 chrome 对象（headless 缺少这个）
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            // 覆盖 permissions 查询
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

    return context


def load_config(date: str, config_path: str | None = None) -> dict:
    """加载指定 config.json，默认使用日期对应的日报播客目录。"""
    config_path = (
        Path(config_path).expanduser()
        if config_path
        else NEWS_BASE / date / "podcast" / "config.json"
    )
    if not config_path.exists():
        print(f"❌ 找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


def verify_files(podcast: dict) -> bool:
    """验证音频文件是否存在（封面已改为可选）。"""
    ok = True
    if not Path(podcast["audio"]["path"]).exists():
        print(f"  ❌ 音频文件不存在: {podcast['audio']['path']}")
        ok = False
    # 封面非必需，跳过验证
    return ok


def dismiss_modals(page):
    """关闭所有可能的弹窗（帮助弹窗、通知等）。

    策略：先尝试 scrollIntoView + click，失败则用 JS click 兜底。
    """
    dismissed = False
    for text in ["我知道了", "确定", "关闭"]:
        try:
            btn = page.locator(f'button:has-text("{text}")')
            count = btn.count()
            if count == 0:
                continue
            for i in range(count):
                b = btn.nth(i)
                if not b.is_visible():
                    continue
                # 策略 1: 滚动到元素可见区域再点击
                try:
                    b.scroll_into_view_if_needed(timeout=3000)
                    b.click(timeout=3000)
                    dismissed = True
                    human_delay(0.3, 0.8)
                    continue
                except Exception:
                    pass
                # 策略 2: JavaScript 直接 click（无视 viewport 限制）
                try:
                    b.evaluate("el => el.click()")
                    dismissed = True
                    human_delay(0.3, 0.8)
                except Exception:
                    pass
        except Exception:
            pass
    return dismissed


def _close_upload_modal(page) -> bool:
    """关闭「上传播客」弹窗，确保 Mantine 遮罩不再拦截页面点击。

    2026-09-24 起创建页不再直接暴露音频 file input，音频只能经「上传播客」弹窗
    上传；该弹窗没有关闭图标（只有「收起」），上传完成后遮罩
    div.mantine-Modal-overlay 会拦截后续对标题等页面元素的点击。
    弹窗支持 Escape 关闭，且实测关闭后音频仍保留在创建页（显示「音频 · MM:SS」）。
    """
    overlay = page.locator("div.mantine-Modal-overlay")
    if overlay.count() == 0:
        return False

    for _ in range(2):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        human_delay(0.6, 1.0)
        if overlay.count() == 0:
            return True

    # 兜底：JS 移除残留遮罩（不影响弹窗外的页面状态）
    try:
        page.evaluate(
            "() => document.querySelectorAll('div.mantine-Modal-overlay')"
            ".forEach(el => el.remove())"
        )
        human_delay(0.3, 0.6)
        return overlay.count() == 0
    except Exception:
        return False


def format_episode_title(
    podcast: dict, config: dict, type_label: str | None = None
) -> str:
    """拼接小宇宙播客标题：{M月D日}{类型标签}｜{原标题}

    示例: "8月19日行业洞见｜模型没有护城河"
    设计原则：小宇宙列表标题两行显示，官方推荐 25 字以内。
    完整标题（前缀+原标题）应控制在 30 字符以内，因此前缀不携带年份。
    """
    TYPE_LABELS = {
        "daily_brief": "每日精选",
        "opensource": "开源解读",
        "industry_trends": "行业洞见",
    }
    date_str = config.get("date", "")  # "2026-05-18"
    # 转为 "8月19日"（省略年份，小宇宙列表自带发布日期）
    parts = date_str.split("-")
    if len(parts) == 3:
        month = int(parts[1])
        day = int(parts[2])
        date_cn = f"{month}月{day}日"
    else:
        date_cn = date_str

    podcast_type = podcast.get("type", "")
    label = type_label or TYPE_LABELS.get(podcast_type, podcast_type)
    original_title = podcast.get("title", "")

    return f"{date_cn}{label}｜{original_title}"


def _normalize_title(value: str) -> str:
    """统一全角、空白和提示用标点，用于上传前查重。"""
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", value)
    value = value.replace("｜", "").replace(":", "")
    return re.sub(r"\s+", "", value).casefold()


def _episode_exists(page, title: str) -> bool:
    """在小宇宙后台按标题检索，判断同名单集是否已经存在。"""
    search_term = title.split("｜", 1)[-1] or title
    url = f"{EPISODES_URL}?page=1&keyword={quote(search_term)}&tab=all"
    page.goto(url, wait_until="networkidle", timeout=30000)
    human_delay(1.0, 2.0)
    if "accounts.xiaoyuzhoufm.com" in page.url:
        raise RuntimeError("Cookie 已过期，需要重新登录 (--login)")

    body = page.locator("body").inner_text()
    target = _normalize_title(title)
    normalized_lines = {_normalize_title(line) for line in body.splitlines()}
    return target in normalized_lines or target in _normalize_title(body)


def _set_schedule_at(page, schedule_at: str) -> str:
    """在创建页设置小宇宙定时发布时间，并返回页面确认后的时间。"""
    try:
        parsed = datetime.fromisoformat(schedule_at)
    except ValueError as exc:
        raise ValueError(f"定时发布时间格式无效: {schedule_at}") from exc
    if parsed <= datetime.now():
        raise ValueError(f"定时发布时间必须晚于当前时间: {schedule_at}")

    root = page.locator(
        '[data-sentry-component="SchedulePublicationTimingPicker"]'
    ).first
    if root.count() == 0:
        raise RuntimeError("创建页未找到定时发布控件")

    schedule_switch = root.locator('[role="switch"]').first
    if not schedule_switch.is_checked():
        root.locator("label").first.click(force=True)
        human_delay(0.5, 1.0)
    if not schedule_switch.is_checked():
        raise RuntimeError("定时发布开关未成功启用")

    date_button = root.locator('[data-dates-input="true"]').first
    if date_button.get_attribute("aria-expanded") != "true":
        date_button.click(force=True)
        human_delay(0.5, 1.0)

    dialog = page.locator('[data-dates-dropdown="true"]').first
    dialog.wait_for(state="visible", timeout=10000)

    month_names = {
        1: "一月",
        2: "二月",
        3: "三月",
        4: "四月",
        5: "五月",
        6: "六月",
        7: "七月",
        8: "八月",
        9: "九月",
        10: "十月",
        11: "十一月",
        12: "十二月",
    }
    date_label = f"{parsed.day} {month_names[parsed.month]} {parsed.year}"
    day_button = dialog.get_by_role("button", name=date_label, exact=True)
    if day_button.count() != 1:
        raise RuntimeError(f"定时发布日历中找不到日期: {date_label}")
    day_button.click()
    human_delay(0.2, 0.5)

    time_fields = dialog.get_by_role("spinbutton")
    if time_fields.count() < 2:
        raise RuntimeError("定时发布弹窗中找不到小时和分钟输入框")
    for index, value in enumerate((f"{parsed.hour:02d}", f"{parsed.minute:02d}")):
        field = time_fields.nth(index)
        field.click()
        page.keyboard.press("Meta+a")
        for char in value:
            page.keyboard.press(char)
        human_delay(0.2, 0.5)

    submit = dialog.locator(".mantine-DateTimePicker-submitButton").first
    if submit.count() == 0:
        raise RuntimeError("定时发布弹窗中找不到确认按钮")
    submit.click()
    human_delay(0.5, 1.0)

    expected = parsed.strftime("%Y-%m-%d %H:%M:00")
    actual = root.locator('input[name="pubDate"]').input_value()
    if actual != expected:
        raise RuntimeError(
            f"定时发布时间校验失败，期望 {expected}，页面值为 {actual or '空'}"
        )
    return actual


def upload_episode(page, podcast: dict, index: int, total: int,
                   config: dict = None, create_api_results: list = None,
                   type_label: str | None = None,
                   schedule_at: str | None = None) -> dict:
    """上传单个播客到小宇宙。返回结果 dict。

    流程：
    1. 打开创建单集页面
    2. 关闭弹窗
    3. 上传音频
    4. 等待音频处理
    5. 输入标题（拼接日期+类型标签）
    6. 输入 Show Notes
    7. 可选：设置定时发布时间
    8. 勾选「本音频为 AI 生成」+ 「阅读并同意服务协议」
    9. 点击创建
    10. 通过 API 响应确认创建成功
    11. 若创建页已无 AI 声明开关，则在单集编辑页兜底勾选并保存

    Args:
        config: 完整的 config.json 数据，用于获取日期
        create_api_results: 传入一个 list，用于收集 create-free API 的响应结果
    """
    podcast_type = podcast["type"]
    title = format_episode_title(podcast, config or {}, type_label=type_label)
    description = podcast.get("description", "")
    audio_path = podcast["audio"]["path"]
    duration_human = podcast["audio"].get("duration_human", "?")
    date_str = (config or {}).get("date", "")

    print(f"\n{'='*60}")
    print(f"📡 [{index}/{total}] 上传: {title}")
    print(f"   类型: {podcast_type} | 时长: {duration_human}")
    print(f"{'='*60}")

    result = {
        "type": podcast_type,
        "title": title,
        "success": False,
        "error": None,
    }

    try:
        if podcast.get("xiaoyuzhou_url"):
            result["success"] = True
            result["skipped"] = True
            result["public_url"] = podcast["xiaoyuzhou_url"]
            print("  ⏭️  config.json 已记录该单集，跳过重复上传")
            return result

        print("  [0/9] 检查后台是否已有同名单集...")
        if _episode_exists(page, title):
            result["success"] = True
            result["skipped"] = True
            result["error"] = None
            print("  ⏭️  后台已存在同名标题，跳过重复上传")
            return result
        print("         未发现同名单集，继续创建")

        # ── Step 1: 打开创建页面 ──
        print("  [1/9] 打开创建单集页面...")
        page.goto(CREATE_EPISODE_URL, wait_until="networkidle", timeout=30000)

        if "accounts.xiaoyuzhoufm.com" in page.url:
            result["error"] = "Cookie 已过期，需要重新登录 (--login)"
            return result

        # 等待 SPA 完全渲染
        human_delay(2.0, 3.5)

        # ── Step 2: 关闭帮助弹窗 ──
        print("  [2/9] 关闭弹窗...")
        for attempt in range(3):
            if dismiss_modals(page):
                print(f"         已关闭弹窗（第 {attempt+1} 次尝试）")
                break
            human_delay(0.8, 1.5)

        # ── Step 3: 上传音频 ──
        print("  [3/9] 上传音频文件...")
        human_delay(0.5, 1.5)
        audio_uploaded = False
        # 方式 1（2026-09-24 起已失效，保留快速探测）: 页面直接暴露音频 file input
        try:
            audio_input = page.locator('input[type="file"][accept*="audio/mpeg"]').first
            audio_input.wait_for(state='attached', timeout=2000)
            audio_input.set_input_files(audio_path)
            audio_uploaded = True
        except Exception:
            pass
        # 方式 2（新版 2026-08-04）: 点击上传区打开「上传播客」对话框，
        # 对对话框内的 file input 设置文件（页面上已不再直接暴露音频 input）
        if not audio_uploaded:
            try:
                page.locator('text=点击上传播客').first.click(timeout=5000)
                human_delay(0.5, 1.2)
                dialog_input = page.locator(
                    '[role="dialog"] input[type="file"][accept*="audio"]'
                ).first
                try:
                    dialog_input.wait_for(state='attached', timeout=15000)
                except Exception:
                    # 2026-10-19 后台 Mantine 弹窗未稳定暴露 role=dialog；
                    # 此时弹窗内通常只剩一个文件输入框，回退到可见 file input。
                    dialog_input = page.locator(
                        'input[type="file"]:visible'
                    ).first
                    dialog_input.wait_for(state='attached', timeout=5000)
                dialog_input.set_input_files(audio_path)
                audio_uploaded = True
                # 弹窗必须关掉，否则遮罩会拦截后续的标题/Show Notes 输入
                human_delay(0.5, 1.0)
                if _close_upload_modal(page):
                    print("         已关闭上传播客弹窗")
                else:
                    print("         ⚠️  上传播客弹窗未关闭，尝试继续...")
            except Exception as e:
                result["error"] = f"音频上传失败: {e}"
                return result
        print("         音频已选择，等待处理...")

        # ── Step 4: 等待音频处理完成 ──
        print("  [4/9] 等待音频处理...")
        duration_known = bool(duration_human) and duration_human != "?"
        for i in range(90):
            human_delay(1.0, 1.5)
            body = page.inner_text("body")
            if duration_known:
                if duration_human in body or f"0{duration_human}" in body:
                    print(f"         ✅ 音频处理完成（~{i+1}s，页面显示时长 {duration_human}）")
                    break
            elif ":" in body and ("·" in body or "MB" in body or "秒" in body):
                print(f"         ✅ 音频处理完成（~{i+1}s）")
                break
        else:
            print("         ⚠️  等待超时，继续执行...")

        _close_upload_modal(page)
        dismiss_modals(page)
        human_delay(1.0, 2.0)

        # ── Step 5: 输入标题 ──
        print("  [5/9] 输入标题...")
        human_delay(0.3, 1.0)
        _close_upload_modal(page)  # 防御：遮罩未清干净会拦截标题输入
        title_input = page.locator('input[name="title"]')
        try:
            title_input.click(timeout=10000)
        except Exception:
            _close_upload_modal(page)
            title_input.click(timeout=15000)
        human_delay(0.2, 0.5)
        page.keyboard.press("Meta+a")
        human_delay(0.1, 0.3)
        page.keyboard.press("Backspace")
        human_delay(0.2, 0.5)
        page.keyboard.type(title, delay=human_type_delay())
        human_delay(0.5, 1.5)

        # ── Step 6: 输入 Show Notes ──
        print("  [6/9] 输入 Show Notes...")
        human_delay(0.3, 1.0)
        content_editable = page.locator('[contenteditable="true"]')
        content_editable.click()
        human_delay(0.2, 0.5)
        page.keyboard.press("Meta+a")
        human_delay(0.1, 0.3)
        page.keyboard.press("Backspace")
        human_delay(0.2, 0.5)
        page.keyboard.type(description, delay=human_type_delay())
        human_delay(0.5, 1.5)

        # ── Step 6.5: 设置定时发布 ──
        if schedule_at:
            print(f"  [6.5/9] 设置定时发布: {schedule_at}")
            result["scheduled_for"] = _set_schedule_at(page, schedule_at)
            print(f"         ✅ 已确认定时发布: {result['scheduled_for']}")

        # ── Step 7: 勾选 checkbox ──
        print("  [7/9] 勾选 checkbox...")
        human_delay(0.3, 1.0)
        ai_declared = _check_ai_generated(page)
        human_delay(0.3, 1.0)
        if not _check_agreement(page):
            raise RuntimeError("服务协议未成功勾选，已中止创建")

        # 截图预检
        page.screenshot(path=_screenshot_path(podcast_type, "pre_submit", date_str), full_page=True)

        # ── Step 8: 点击创建 ──
        print("  [8/9] 点击创建按钮...")
        human_delay(1.0, 2.5)
        _click_create(page)

        # ── Step 9: 等待创建完成 ──
        print("  [9/9] 等待创建完成...")
        human_delay(5.0, 8.0)

        # 检查是否成功：通过 API 响应（如果有）或 URL 跳转
        current_url = page.url
        print(f"  当前 URL: {current_url}")

        # 检查 API 响应（如果 create_api_results 被外部填充）
        api_success = False
        if create_api_results is not None and len(create_api_results) > 0:
            last = create_api_results[-1]
            if last.get("status") == 200:
                api_success = True
                eid = last.get("episode_id")
                result["success"] = True
                if eid:
                    result["episode_id"] = eid
                    result["episode_url"] = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/{eid}"
                    result["public_url"] = PUBLIC_EPISODE_URL.format(eid=eid)
                    print(f"  ✅ 创建成功！Episode ID: {eid}")
                    print(f"  🔗 公开链接: {result['public_url']}")
                else:
                    print(f"  ✅ 创建成功！（API 返回 200）")

        if not api_success:
            if "/episode/" in current_url and "/create" not in current_url:
                result["success"] = True
                result["episode_url"] = current_url
                print(f"  ✅ 创建成功！（URL 跳转确认）")
            elif "/episode" in current_url and "/create" not in current_url:
                result["success"] = True
                result["episode_url"] = current_url
                print(f"  ✅ 创建成功（已跳转到列表页）")
            else:
                # 最后手段：直接请求 API 确认（之前调试发现创建实际已成功但 URL 不跳转）
                page.screenshot(path=_screenshot_path(podcast_type, "debug", date_str), full_page=True)
                # 导航到节目列表页检查
                page.goto(EPISODES_URL, wait_until="networkidle", timeout=15000)
                human_delay(2.0, 3.0)
                page_text = page.inner_text("body")
                if title in page_text:
                    result["success"] = True
                    result["episode_url"] = EPISODES_URL
                    print(f"  ✅ 创建成功！（通过列表页确认标题存在）")
                else:
                    result["error"] = f"创建后未跳转，列表页也未找到标题，截图: {_screenshot_path(podcast_type, 'debug', date_str)}"
                    result["debug_url"] = current_url

        # ── Step 10: 兜底补齐 AI 生成声明（创建页已无该开关，改在编辑页设置）──
        if result["success"] and not ai_declared:
            eid = result.get("episode_id") or _last_episode_id(create_api_results) \
                or _extract_episode_id(page)
            if eid:
                print("  [10/9] 补齐 AI 生成声明...")
                result["ai_declared"] = _ensure_ai_declaration(page, eid)
            else:
                print("  ⚠️  未取得 Episode ID，无法补齐 AI 生成声明")
                result["ai_declared"] = False
        else:
            result["ai_declared"] = bool(result["success"])

    except Exception as e:
        result["error"] = str(e)
        try:
            page.screenshot(path=_screenshot_path(podcast_type, "error", date_str), full_page=True)
        except Exception:
            pass

    return result


def _check_ai_generated(page):
    """尝试在创建页勾选「本音频为 AI 生成」。返回是否已确认勾选。

    注意：2026-09 起创建页不再暴露该开关（声明改到单集编辑页的「填写声明」区），
    此函数通常会返回 False，由 _ensure_ai_declaration 在创建后兜底补齐。
    """
    # 方法 1：通过 name 属性定位
    ai_cb = page.locator('input[name="isAIGC"]')
    if ai_cb.count() > 0:
        if not ai_cb.is_checked():
            ai_cb.click(force=True)
            print("         ✅ 已勾选 AI 生成声明（via name=isAIGC）")
        else:
            print("         ✅ AI 生成声明已勾选")
        return ai_cb.is_checked()

    # 方法 1.5（新版 2026-08-04）: Mantine Switch（EpisodeAISettingSection）
    try:
        ai_switch = page.locator(
            'input[data-sentry-source-file="EpisodeAISettingSection.tsx"]'
        )
        if ai_switch.count() > 0:
            if not ai_switch.first.is_checked():
                ai_switch.first.click(force=True)
                human_delay(0.3, 0.5)
            if ai_switch.first.is_checked():
                print("         ✅ 已勾选 AI 生成声明（via Switch）")
                return True
    except Exception:
        pass

    # 方法 2：通过附近文字定位
    for label_text in ["本音频为 AI 生成", "AI 生成", "AIGC"]:
        try:
            label = page.locator(f'label:has-text("{label_text}")')
            if label.count() > 0:
                cb = label.locator('input[type="checkbox"]')
                if cb.count() > 0 and not cb.is_checked():
                    cb.click(force=True)
                    print(f"         ✅ 已勾选 AI 生成声明（via 文字: {label_text}）")
                    return cb.is_checked()
                # 也尝试点击 label 本身
                label.first.click()
                human_delay(0.3, 0.5)
                print(f"         ✅ 已点击 AI 生成 label（via 文字: {label_text}）")
                return True
        except Exception:
            continue

    # 方法 3：通过 Mantine Checkbox 的 data 属性
    try:
        mcb = page.locator('.mantine-Checkbox-root').filter(has_text="AI")
        if mcb.count() > 0:
            mcb.first.click()
            print("         ✅ 已点击 AI 生成 Mantine Checkbox")
            return True
    except Exception:
        pass

    print("         ⚠️  未找到 AI 生成 checkbox，可能需要手动勾选")
    return False


def _find_ai_decl_switch(page) -> int:
    """在单集编辑页「填写声明」区定位 AI 声明开关，返回索引（未找到为 -1）。"""
    try:
        return page.evaluate(
            """(label) => {
                const switches = [...document.querySelectorAll('[role="switch"]')];
                for (let i = 0; i < switches.length; i++) {
                    let row = switches[i], n = switches[i];
                    for (let k = 0; k < 6 && n; k++) {
                        n = n.parentElement;
                        if (!n) break;
                        const t = (n.innerText || '').trim();
                        if (t && t.length < 60) { row = n; break; }
                    }
                    if ((row.innerText || '').includes(label)) return i;
                }
                return -1;
            }""",
            AI_DECL_TEXT,
        )
    except Exception:
        return -1


def _ensure_ai_declaration(page, episode_id: str) -> bool:
    """创建后兜底：在单集编辑页勾选「本音频为 AI 生成」并保存。失败不影响上传结果。"""
    edit_url = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/{episode_id}/edit"
    try:
        page.goto(edit_url, wait_until="domcontentloaded", timeout=30000)
        human_delay(3.0, 5.0)
        dismiss_modals(page)
        page.keyboard.press("Escape")
        human_delay(0.5, 1.0)

        index = _find_ai_decl_switch(page)
        if index < 0:
            print("         ⚠️  编辑页未找到 AI 声明开关，需手动勾选")
            return False

        switch = page.locator('[role="switch"]').nth(index)
        if switch.is_checked():
            print("         ✅ AI 生成声明已是勾选状态")
            return True

        switch.evaluate("el => el.click()")
        human_delay(0.8, 1.5)
        if not switch.is_checked():
            print("         ⚠️  AI 声明开关点击后未生效，需手动勾选")
            return False

        save_btn = page.locator('button:has-text("更新")').last
        if save_btn.count() == 0:
            print("         ⚠️  未找到「更新」按钮，AI 声明未保存")
            return False
        save_btn.scroll_into_view_if_needed()
        human_delay(0.3, 0.8)
        save_btn.click(timeout=8000)
        human_delay(3.0, 5.0)

        page.goto(edit_url, wait_until="domcontentloaded", timeout=30000)
        human_delay(3.0, 5.0)
        index = _find_ai_decl_switch(page)
        saved = index >= 0 and page.locator('[role="switch"]').nth(index).is_checked()
        print("         ✅ 已保存 AI 生成声明" if saved else "         ⚠️  AI 声明保存后校验失败")
        return saved
    except Exception as e:
        print(f"         ⚠️  补齐 AI 声明失败: {e}")
        return False


def _extract_episode_id(page):
    """从单集列表页链接中提取 episode id。"""
    try:
        hrefs = page.eval_on_selector_all(
            "a[href*='/episode/']", "els => els.map(e => e.getAttribute('href'))"
        )
    except Exception:
        return None
    for href in hrefs or []:
        match = re.search(r"/episode/([0-9a-zA-Z]{10,})", href or "")
        if match:
            return match.group(1)
    return None


def _last_episode_id(api_results):
    """从 create-free API 响应记录中取出最近一次的 episode id。"""
    for entry in reversed(api_results or []):
        if entry.get("episode_id"):
            return entry["episode_id"]
    return None


def _check_agreement(page):
    """精确勾选「阅读并同意《小宇宙创作中心服务协议》」checkbox。"""
    # 方法 0：当前创建页的协议 checkbox 由 FooterBanner 渲染，外层没有 label，
    # 且 Mantine 的原生 input 视觉上不可见，不能用 is_visible() 过滤。
    try:
        agreement = page.locator(
            'input[type="checkbox"]'
            '[data-sentry-source-file="FooterBanner.tsx"]'
        )
        if agreement.count() == 1:
            if not agreement.is_checked():
                agreement.click(force=True)
                human_delay(0.3, 0.8)
            if agreement.is_checked():
                print("         ✅ 已勾选服务协议")
                return True
    except Exception:
        pass

    # 方法 1：通过文字内容精确匹配 label，然后点击
    for label_text in ["同意", "协议", "服务协议", "创作中心服务协议"]:
        try:
            labels = page.locator(f'label:has-text("{label_text}")')
            for i in range(labels.count()):
                label = labels.nth(i)
                try:
                    text = label.inner_text()
                except Exception:
                    continue
                if "协议" in text or "同意" in text:
                    # Mantine 的 label 与 input 是兄弟节点，必须通过 for 找到 input。
                    checkbox_id = label.get_attribute("for")
                    cb = (
                        page.locator(f'input[type="checkbox"][id="{checkbox_id}"]')
                        if checkbox_id
                        else label.locator('input[type="checkbox"]')
                    )
                    if cb.count() == 0:
                        continue
                    cb.first.click(force=True)
                    human_delay(0.5, 1.0)
                    if cb.first.is_checked():
                        print("         ✅ 已勾选服务协议")
                        return True
        except Exception:
            continue

    # 方法 2：遍历所有可见 checkbox，排除 isAIGC 和「追光任务」，勾选服务协议
    try:
        checkboxes = page.locator('input[type="checkbox"]')
        # 从后往前找，协议 checkbox 通常是最后一个可见的
        for i in range(checkboxes.count() - 1, -1, -1):
            cb = checkboxes.nth(i)
            try:
                if not cb.is_visible():
                    continue
                name = cb.get_attribute("name") or ""
                if name == "isAIGC":
                    continue  # 跳过 AI 生成 checkbox
                # 排除「关联追光任务」checkbox
                section = cb.evaluate(
                    'el => { let s = el.closest("section, div[class*=Card]"); '
                    'return s ? s.innerText.substring(0, 50) : ""; }'
                )
                if "追光" in section:
                    continue
                if not cb.is_checked():
                    cb.click(force=True)
                    human_delay(0.3, 0.5)
                    if cb.is_checked():
                        print(f"         ✅ 已勾选服务协议（fallback: checkbox #{i+1}）")
                        return True
            except Exception:
                continue
    except Exception:
        pass

    print("         ⚠️  未找到服务协议 checkbox，可能需要手动勾选")
    return False


def _click_create(page):
    """点击创建按钮。"""
    clicked = False
    btns = page.locator("button")
    for i in range(btns.count()):
        btn = btns.nth(i)
        try:
            text = btn.inner_text().strip()
        except Exception:
            continue
        if text == "创建" and btn.is_visible():
            try:
                btn.scroll_into_view_if_needed(timeout=3000)
                human_delay(0.3, 0.8)
                btn.click(timeout=5000)
            except Exception:
                btn.evaluate("el => el.click()")
            clicked = True
            break

    if not clicked:
        # 兜底：查找包含"创建"文字的最后一个可见按钮
        try:
            create_btn = page.locator('button:has-text("创建")').last
            create_btn.scroll_into_view_if_needed(timeout=3000)
            human_delay(0.3, 0.8)
            create_btn.click(timeout=5000)
        except Exception:
            create_btn.evaluate("el => el.click()")


def _save_public_urls(
    date: str, config: dict, results: list, config_path: str | None = None
):
    """将上传成功的公开链接写回 config.json，供后续工作流使用。"""
    config_path = (
        Path(config_path).expanduser()
        if config_path
        else NEWS_BASE / date / "podcast" / "config.json"
    )
    if not config_path.exists():
        print(f"  ⚠️  config.json 不存在，跳过保存公开链接")
        return

    updated = False
    for r in results:
        if not r.get("success") or not r.get("public_url"):
            continue
        podcast_type = r["type"]
        for p in config.get("podcasts", []):
            if p["type"] == podcast_type:
                p["xiaoyuzhou_url"] = r["public_url"]
                updated = True
                print(f"  💾 已保存 {podcast_type} 公开链接到 config.json")
                break

    if updated:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"  ✅ config.json 已更新: {config_path}")


def upload_all(
    date: str,
    podcast_type: str = None,
    headless: bool = True,
    config_path: str | None = None,
    type_label: str | None = None,
    schedule_at: str | None = None,
):
    """上传指定日期的播客到小宇宙。"""
    from playwright.sync_api import sync_playwright

    if not check_cookie_valid():
        print("❌ Cookie 不存在或已失效，请先运行: python3 xiaoyuzhou_upload.py --login")
        sys.exit(1)

    config = load_config(date, config_path=config_path)
    podcasts = config["podcasts"]

    if podcast_type:
        podcasts = [p for p in podcasts if p["type"] == podcast_type]
        if not podcasts:
            print(f"❌ 找不到类型为 '{podcast_type}' 的播客")
            sys.exit(1)

    print(f"📂 日期: {date} | 播客数量: {len(podcasts)}")
    for p in podcasts:
        print(f"   - {p['type']}: {p['title']}")
        if not verify_files(p):
            print("❌ 文件验证失败，中止上传")
            sys.exit(1)
    print("✅ 文件验证通过")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = _new_context(browser, headless=headless)
        page = context.new_page()

        # 全局 API 响应监听器：捕获 create-free 调用结果
        shared_api_results = []

        def on_api_response(response):
            if "episode/hosted/create-free" in response.url:
                entry = {"status": response.status, "episode_id": None, "body": None}
                try:
                    body = response.json()
                    entry["body"] = body
                    eid = body.get("data", {}).get("eid") or body.get("eid")
                    if eid:
                        entry["episode_id"] = eid
                except Exception:
                    try:
                        entry["body"] = response.text()[:500]
                    except Exception:
                        pass
                shared_api_results.append(entry)
                status = "✅" if response.status == 200 else "❌"
                print(f"  📡 API: {status} create-free → {response.status}")

        page.on("response", on_api_response)

        for i, podcast in enumerate(podcasts, 1):
            result = upload_episode(page, podcast, i, len(podcasts),
                                    config=config, create_api_results=shared_api_results,
                                    type_label=type_label,
                                    schedule_at=schedule_at)
            results.append(result)
            if i < len(podcasts):
                delay = random.uniform(5.0, 10.0)
                print(f"  ⏳ 等待 {delay:.1f} 秒后继续下一个...")
                time.sleep(delay)

        browser.close()

    # 结果汇总
    print(f"\n{'='*60}")
    print("📊 上传结果汇总")
    print(f"{'='*60}")
    success_count = 0
    skipped_count = 0
    for r in results:
        if r.get("skipped"):
            status = "⏭️ 已存在，跳过"
        else:
            status = "✅ 成功" if r["success"] else f"❌ 失败: {r['error']}"
        print(f"  {r['type']}: {r['title']}")
        print(f"    状态: {status}")
        if r.get("episode_url"):
            print(f"    后台URL: {r['episode_url']}")
        if r.get("public_url"):
            print(f"    🔗 公开链接: {r['public_url']}")
        if r.get("scheduled_for"):
            print(f"    ⏰ 定时发布: {r['scheduled_for']}")
        if r.get("skipped"):
            skipped_count += 1
        elif r["success"]:
            success_count += 1
    print(
        f"\n总计: {success_count} 成功, "
        f"{skipped_count} 跳过, {len(results) - success_count - skipped_count} 失败"
    )

    # 将公开链接写回 config.json
    _save_public_urls(date, config, results, config_path=config_path)

    return results


def main():
    parser = argparse.ArgumentParser(description="小宇宙播客自动上传")
    parser.add_argument("--date", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--type", help="播客类型: daily_brief, opensource, industry_trends")
    parser.add_argument("--config", default=None,
                        help="自定义 config.json 路径；默认读取日报播客目录")
    parser.add_argument("--label", default=None,
                        help="覆盖小宇宙标题中的类型标签，如“临时加更”")
    parser.add_argument(
        "--schedule-at",
        default=None,
        help="定时发布时间，格式 YYYY-MM-DDTHH:MM:SS 或 YYYY-MM-DD HH:MM:SS",
    )
    parser.add_argument("--login", action="store_true", help="重新登录（保存 Cookie）")
    parser.add_argument("--headed", action="store_true", help="显示浏览器界面")

    args = parser.parse_args()

    if args.login:
        do_login()
        return

    if not args.date:
        print("❌ 请指定日期: --date YYYY-MM-DD")
        parser.print_help()
        sys.exit(1)

    upload_all(
        args.date,
        args.type,
        headless=not args.headed,
        config_path=args.config,
        type_label=args.label,
        schedule_at=args.schedule_at,
    )


if __name__ == "__main__":
    main()
