#!/usr/bin/env python3
"""
「李自在AI人物志」小宇宙单集上传播放器

将合并后的 episode.mp3 上传到小宇宙「李自在AI人物志」节目。
基于 xiaoyuzhou-upload skill 的 Playwright 浏览器自动化策略改写，
适配本节目的单集上传场景。

与 xiaoyuzhou-upload 的差异：
- 目标 podcast_id: 6a53643dd01e2a1f16e0f63e（李自在AI人物志）
- 标题格式: E01.人物名：亮点总结（不再拼日期和类型标签）
- 单集上传（读 config.json 的 episode 字段，而非 podcasts 数组）
- 不上传封面

上传后通过 create-free API 响应 + list API 主动验证双重确认，确保 100% 拿到 eid。

用法：
    python3 upload_episode.py --episode-dir E01.山姆奥特曼
    python3 upload_episode.py --episode-dir E01.山姆奥特曼 --headed   # 调试模式
    python3 upload_episode.py --login                                  # 首次登录保存 Cookie
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── 常量 ───────────────────────────────────────────────
PODCAST_ID = "6a53643dd01e2a1f16e0f63e"  # 李自在AI人物志
BASE_URL = "https://podcaster.xiaoyuzhoufm.com"
API_BASE = "https://podcaster-api.xiaoyuzhoufm.com/v1"
CREATE_EPISODE_URL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/create"
EPISODES_URL = f"{BASE_URL}/podcast/{PODCAST_ID}/episode"
LOGIN_URL = f"{BASE_URL}/podcast"
COOKIE_PATH = Path(os.environ.get("XYZ_AUTH_FILE", "~/.xiaoyuzhou_auth.json")).expanduser()
PUBLIC_EPISODE_URL = "https://www.xiaoyuzhoufm.com/episode/{eid}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 定时发布最大提前量（天）。与 generate_config.py / 小宇宙 picker 保持一致。
# 实测 2026-07：小宇宙创作者后台 DateTimePicker 最多可选 14 天内。
_SCHEDULE_MAX_DAYS = 14


def human_delay(min_s: float = 0.5, max_s: float = 2.5):
    time.sleep(random.uniform(min_s, max_s))


def human_type_delay() -> int:
    return random.randint(20, 60)


def check_cookie_valid() -> bool:
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
    """打开浏览器让用户手动登录，保存 Cookie。"""
    from playwright.sync_api import sync_playwright

    print("🔐 打开浏览器，请手动登录小宇宙创作者后台...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = _new_context(browser, headless=False)
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        try:
            page.wait_for_url("**/podcast/**", timeout=180000)
        except Exception:
            page.wait_for_url("**/podcast*", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        context.storage_state(path=str(COOKIE_PATH))
        print(f"✅ 登录成功！Cookie 已保存到 {COOKIE_PATH}")
        browser.close()


def _new_context(browser, headless: bool = True):
    from playwright.sync_api import Browser

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
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)
    return context


def load_config(episode_dir: str) -> dict:
    """读取集数目录下的 config.json。"""
    config_path = os.path.join(episode_dir, "config.json")
    if not os.path.isfile(config_path):
        print(f"[ERR] 找不到 config.json: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def dismiss_modals(page):
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
                try:
                    b.scroll_into_view_if_needed(timeout=3000)
                    b.click(timeout=3000)
                    human_delay(0.3, 0.8)
                    continue
                except Exception:
                    pass
                try:
                    b.evaluate("el => el.click()")
                    human_delay(0.3, 0.8)
                except Exception:
                    pass
        except Exception:
            pass


def _extract_eid_from_response(body):
    """从 create-free API 响应中尽可能鲁棒地提取 eid。

    小宇宙 create-free API 响应可能是：
        {"data": {"eid": "xxx"}, ...}
        {"data": {"id": "xxx"}, ...}
        {"data": {"_id": "xxx"}, ...}
        {"eid": "xxx"}
        {"data": "xxx"}  （字符串）
    """
    if not body:
        return None
    if not isinstance(body, dict):
        return None

    # 顶层直接有 eid
    for key in ("eid", "episode_id", "id", "_id"):
        v = body.get(key)
        if isinstance(v, str) and len(v) >= 8:
            return v

    # data 字段
    data = body.get("data")
    if isinstance(data, dict):
        for key in ("eid", "episode_id", "id", "_id"):
            v = data.get(key)
            if isinstance(v, str) and len(v) >= 8:
                return v
    elif isinstance(data, str) and len(data) >= 8:
        return data

    return None


def verify_episode_in_list(page, title: str, max_scrolls: int = 8):
    """通过浏览器拦截 list API 响应，找精确 title 匹配。

    实现方式：先导航到节目单集列表页，再滚动到底部触发分页，
    期间拦截 POST /v1/episode/list 的响应累积所有单集。

    Args:
        page: Playwright page（cookie 已注入）
        title: 要匹配的单集标题（精确匹配）
        max_scrolls: 最大滚动次数（每次可能触发一页加载）

    Returns:
        (eid, status) 或 (None, None)
    """
    captured_episodes = []

    def on_list_response(resp):
        if "episode/list" in resp.url and resp.request.method == "POST":
            try:
                body = resp.json()
                if isinstance(body, dict) and isinstance(body.get("data"), list):
                    captured_episodes.extend(body["data"])
            except Exception:
                pass

    page.on("response", on_list_response)

    try:
        # 必须回到列表页：创建成功后 URL 会停在单集详情/统计页（含 /podcast/ 且不含 /episode/create），
        # 仅滚动当前页不会触发 episode/list API，导致二次确认误报"查无此单集"。
        target_url = f"{BASE_URL}/podcast/{PODCAST_ID}/episode"
        page.goto(target_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # 滚动到底部触发分页
        for i in range(max_scrolls):
            prev_count = len(captured_episodes)
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(800)
            # 没有新数据进来就停止
            if len(captured_episodes) == prev_count and i >= 2:
                break
    finally:
        page.remove_listener("response", on_list_response)

    # 精确匹配 title
    for ep in captured_episodes:
        if not isinstance(ep, dict):
            continue
        ep_title = ep.get("title") or ""
        ep_eid = ep.get("eid")
        ep_status = ep.get("status")
        if ep_title == title and ep_eid:
            return ep_eid, ep_status

    return None, None


def upload_episode(page, config: dict) -> dict:
    """上传单个集到小宇宙。"""
    ep = config["episode"]
    title = ep["title"]
    description = ep["description"]
    audio_path = ep["audio"]["path"]
    duration_human = ep["audio"].get("duration_human", "?")

    print(f"\n{'='*60}")
    print(f"📡 上传: {title}")
    print(f"   时长: {duration_human} | 音频: {audio_path}")
    scheduled_at = config.get("scheduled_at")
    if scheduled_at:
        print(f"   发布模式: ⏰ 定时发布 @ {scheduled_at}")
    else:
        print(f"   发布模式: 🚀 立即发布")
    print(f"{'='*60}")

    result = {
        "title": title,
        "success": False,
        "error": None,
        "episode_id": None,
        "episode_url": None,
        "public_url": None,
        "verify_source": None,  # "api" | "list" | "url" | None
        "scheduled_at_local": None,  # 实际写入 picker 的本地时间
    }

    api_results = []

    def on_api_response(response):
        if "create-free" in response.url or "create" in response.url:
            entry = {"url": response.url, "status": response.status, "raw": None, "eid": None}
            try:
                body = response.json()
                entry["raw"] = body
                entry["eid"] = _extract_eid_from_response(body)
            except Exception:
                pass
            api_results.append(entry)
            status = "✅" if response.status == 200 else "❌"
            eid_str = f" eid={entry['eid']}" if entry["eid"] else ""
            print(f"  📡 API: {status} create → {response.status}{eid_str}")

    page.on("response", on_api_response)

    try:
        # Step 1: 打开创建页
        print("  [1/9] 打开创建单集页面...")
        page.goto(CREATE_EPISODE_URL, wait_until="networkidle", timeout=30000)
        if "accounts.xiaoyuzhoufm.com" in page.url:
            result["error"] = "Cookie 已过期，请运行 --login"
            return result
        human_delay(2.0, 3.5)

        # Step 2: 关弹窗
        print("  [2/9] 关闭弹窗...")
        for attempt in range(3):
            if dismiss_modals(page):
                break
            human_delay(0.8, 1.5)

        # Step 3: 上传音频（新 UI：先点击「点击上传播客」打开弹窗，
        # 弹窗内才有 accept 含 audio 的 file input）
        print("  [3/9] 上传音频文件...")
        human_delay(0.5, 1.5)
        zone = page.locator('div[aria-haspopup="dialog"]:has-text("点击上传播客")').first
        if zone.count() > 0:
            zone.click(position={"x": 60, "y": 40})
            human_delay(1.2, 2.2)
            print("         已打开上传弹窗")
        audio_input = page.locator('input[type="file"][accept*="audio"]').first
        if audio_input.count() == 0:
            all_files = page.locator('input[type="file"]')
            audio_input = all_files.last
        audio_input.set_input_files(audio_path)
        print("         音频已选择，等待处理...")

        # Step 4: 等待音频处理
        print("  [4/9] 等待音频处理...")
        for i in range(240):
            human_delay(1.0, 1.5)
            body = page.inner_text("body")
            if ":" in body and ("·" in body or "MB" in body or "秒" in body or "分钟" in body
                                 or "已上传" in body or "处理完成" in body):
                print(f"         ✅ 音频处理完成（~{(i+1)}s）")
                break
        else:
            print("         ⚠️  等待超时，继续执行...")

        # 处理完成后收起上传弹窗（新 UI）
        try:
            close_btn = page.locator('button:has-text("收起")').first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click(timeout=5000)
                human_delay(1.0, 2.0)
                print("         ✅ 已收起上传弹窗")
        except Exception:
            pass

        dismiss_modals(page)
        human_delay(1.0, 2.0)

        # Step 5: 输入标题
        print("  [5/9] 输入标题...")
        human_delay(0.3, 1.0)
        title_input = page.locator('input[name="title"]')
        title_input.click()
        human_delay(0.2, 0.5)
        page.keyboard.press("Meta+a")
        human_delay(0.1, 0.3)
        page.keyboard.press("Backspace")
        human_delay(0.2, 0.5)
        page.keyboard.type(title, delay=human_type_delay())
        human_delay(0.5, 1.5)

        # Step 6: 输入 Show Notes
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

        # Step 7: 勾选 checkbox
        print("  [7/9] 勾选 checkbox...")
        human_delay(0.3, 1.0)
        _check_ai_generated(page)
        human_delay(0.3, 1.0)
        _check_agreement(page)

        # Step 7.5: 定时发布（如果配置了）
        scheduled_at_iso = config.get("scheduled_at")
        if scheduled_at_iso:
            print(f"  [7.5/9] 设置定时发布：{scheduled_at_iso}")
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(scheduled_at_iso)
                ok = _set_scheduled_publish(page, dt)
                if not ok:
                    result["error"] = "定时发布 UI 自动化失败（见上方错误），请手动选择或调整发布时间"
                    result["warning"] = "未成功设置定时发布；如继续，脚本会立即发布"
                    print(f"  ❌ {result['error']}")
                    # 询问用户是否继续
                    try:
                        ans = input("  是否继续（会立即发布）？(y/N) > ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        ans = "n"
                    if ans != "y":
                        page.screenshot(path=f"/tmp/lizz_bio_{config['episode_num']}_sched_fail.png",
                                        full_page=True)
                        return result
                else:
                    result["scheduled_at_local"] = dt.astimezone().isoformat(timespec="seconds")
            except Exception as e:
                print(f"  ❌ 解析 scheduled_at 失败: {e}")
                result["error"] = f"scheduled_at 解析失败: {e}"
                return result
        else:
            print(f"  [7.5/9] 发布模式：立即发布")

        page.screenshot(path=f"/tmp/lizz_bio_{config['episode_num']}_pre_submit.png", full_page=True)

        # Step 8: 点击创建
        print("  [8/9] 点击创建按钮...")
        human_delay(1.0, 2.5)
        _click_create(page)

        # Step 9: 等待创建完成 + 多重确认
        print("  [9/9] 等待创建完成...")
        human_delay(5.0, 8.0)

        current_url = page.url
        print(f"  当前 URL: {current_url}")

        # ─── 确认 1：从 create API 响应直接拿 eid ───
        for r in reversed(api_results):
            if r.get("status") == 200 and r.get("eid"):
                result["episode_id"] = r["eid"]
                result["verify_source"] = "api"
                result["success"] = True
                print(f"  ✅ 从 create API 响应中获取 eid: {r['eid']}")
                break

        # ─── 确认 2：URL 跳转 ───
        if not result["episode_id"]:
            if "/episode/" in current_url and "/create" not in current_url and "/podcast/" in current_url:
                # URL 形如 /podcast/{pid}/episode/{eid}
                parts = current_url.rstrip("/").split("/episode/")
                if len(parts) == 2 and parts[0].endswith(PODCAST_ID):
                    eid_candidate = parts[1].split("/")[0].split("?")[0]
                    if len(eid_candidate) >= 12 and eid_candidate != PODCAST_ID:
                        result["episode_id"] = eid_candidate
                        result["verify_source"] = "url"
                        result["success"] = True
                        print(f"  ✅ 从跳转 URL 中提取 eid: {eid_candidate}")

        # ─── 确认 3：list API 主动验证（最可靠）───
        if not result["episode_id"]:
            print(f"  🔍 create API 和 URL 都未拿到 eid，主动调 list API 验证...")
            human_delay(2.0, 3.0)
            eid, status = verify_episode_in_list(page, title)
            if eid:
                result["episode_id"] = eid
                result["verify_source"] = "list"
                result["success"] = True
                print(f"  ✅ list API 验证通过，eid: {eid}（status={status}）")
            else:
                result["error"] = (
                    f"创建后三重验证均未拿到 eid：create API 响应里没 eid，"
                    f"URL 未跳转到编辑页，list API 中未找到精确标题匹配。"
                    f"可能是网络异常、create API 返回 4xx，或标题输入有误。"
                )
                page.screenshot(path=f"/tmp/lizz_bio_{config['episode_num']}_debug.png", full_page=True)
                print(f"  ❌ {result['error']}")

        # ─── 始终再做一次 list 验证：确认单集真实落地 ───
        # 即使 create API 返回了 eid，也再确认一遍 list 里能找到
        if result["episode_id"]:
            human_delay(1.5, 2.5)
            eid_check, status_check = verify_episode_in_list(page, title)
            if eid_check and eid_check == result["episode_id"]:
                result["status"] = status_check
                print(f"  ✅ 二次确认：list API 中找到 eid={eid_check}（status={status_check}）")
            elif eid_check:
                # list 找到了同标题但 eid 不一样——Mantine 在我们填表单时会触发"草稿 create"，
                # 返回的 eid 可能是被丢弃的草稿。**list 里存在的才是真单集**，以其为准。
                old_eid = result["episode_id"]
                result["episode_id"] = eid_check
                result["verify_source"] = "list"
                result["status"] = status_check
                print(
                    f"  ⚠️  二次确认：API 返回 eid={old_eid} 在 list 中不存在；"
                    f"已切换到 list 中真实落地的 eid={eid_check}（status={status_check}）"
                )
            else:
                # list 里完全找不到——非常可疑，可能 create API 假成功
                print(f"  ⚠️  二次确认：list API 中未找到标题「{title}」，单集可能未真正落地")
                print(f"      create API 返回 eid={result['episode_id']}，但 list 里查无此单集")
                # 不强制失败，但严重警告
                result["warning"] = "create API 返回 eid 但 list 中查无此单集，请手动登录小宇宙后台确认"

        # 构建 URL（即使 verify_source 是 list 也能拼出 url）
        if result["episode_id"]:
            result["episode_url"] = f"{BASE_URL}/podcast/{PODCAST_ID}/episode/{result['episode_id']}"
            result["public_url"] = PUBLIC_EPISODE_URL.format(eid=result["episode_id"])

    except Exception as e:
        result["error"] = str(e)
        try:
            page.screenshot(path=f"/tmp/lizz_bio_{config['episode_num']}_error.png", full_page=True)
        except Exception:
            pass

    return result


def _check_ai_generated(page):
    ai_cb = page.locator('input[name="isAIGC"]')
    if ai_cb.count() > 0:
        if not ai_cb.is_checked():
            ai_cb.click(force=True)
            print("         ✅ 已勾选 AI 生成声明")
        return
    # 新版页面：AI 声明是 Mantine Switch（input[role="switch"]），
    # 位于包含「本音频为 AI 生成」文案的区块内，data-checked 控制状态。
    try:
        switches = page.locator('input[role="switch"]')
        for i in range(switches.count()):
            sw = switches.nth(i)
            if not sw.is_visible():
                continue
            sec = sw.evaluate('''el => {
                let n = el;
                for (let k = 0; k < 8 && n; k++) {
                    n = n.parentElement;
                    if (!n) break;
                    const t = (n.innerText || "").replace(/\\s+/g, " ").trim();
                    if (t.length > 4) return t;
                }
                return "";
            }''')
            if "AI" in sec or "音频" in sec:
                checked = sw.get_attribute("data-checked")
                if checked != "true":
                    sw.click(force=True)
                    human_delay(0.4, 0.8)
                print("         ✅ 已勾选 AI 生成声明")
                return
    except Exception as e:
        print(f"         ⚠️  AI 生成 switch 处理异常: {e}")
    print("         ⚠️  未找到 AI 生成 switch")


def _check_agreement(page):
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
                    label.click()
                    human_delay(0.5, 1.0)
                    cb = label.locator('input[type="checkbox"]')
                    if cb.count() > 0:
                        if cb.is_checked():
                            print(f"         ✅ 已勾选服务协议")
                            return
                        cb.click(force=True)
                        if cb.is_checked():
                            print(f"         ✅ 已勾选服务协议")
                            return
                    else:
                        print(f"         ✅ 已点击协议 label")
                        return
        except Exception:
            continue
    # Fallback：遍历 checkbox 排除 isAIGC 和追光任务
    try:
        checkboxes = page.locator('input[type="checkbox"]')
        for i in range(checkboxes.count() - 1, -1, -1):
            cb = checkboxes.nth(i)
            try:
                if not cb.is_visible():
                    continue
                name = cb.get_attribute("name") or ""
                if name == "isAIGC":
                    continue
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
                        print(f"         ✅ 已勾选服务协议（fallback）")
                        return
            except Exception:
                continue
    except Exception:
        pass
    print("         ⚠️  未找到服务协议 checkbox")


def _click_create(page):
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
            return
    try:
        create_btn = page.locator('button:has-text("创建")').last
        create_btn.scroll_into_view_if_needed(timeout=5000)
        create_btn.click(timeout=5000)
    except Exception:
        create_btn.evaluate("el => el.click()")


# ─── 定时发布相关 ────────────────────────────────────────────

# 中文数字月份（与 Mantine DateTimePicker 的 aria-label 完全一致）
_MONTHS_ZH = [
    "一月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "十一月", "十二月",
]


def _fmt_aria_day(dt):
    """生成日期按钮的 aria-label 字符串。例：dt=2026-07-20 → '20 七月 2026'。"""
    return f"{dt.day} {_MONTHS_ZH[dt.month - 1]} {dt.year}"


def _set_scheduled_publish(page, dt_local) -> bool:
    """在小宇宙创建单集页切换到「定时发布」模式，并设置指定时间。

    Args:
        page: Playwright page（已打开 /podcast/.../episode/create）
        dt_local: 带 tzinfo 的 datetime（已转成小宇宙所在时区，Asia/Shanghai）

    Returns:
        True 成功；False 任何步骤失败（不抛异常，让上层决定是否终止上传）。
    """
    from datetime import datetime

    # 把 dt 转成「日历上看到」的本地时间分量（用于选日期 + 填时分）
    # Mantine DateTimePicker 默认使用浏览器时区。我们启动时强制 timezone_id=Asia/Shanghai，
    # 所以这里直接用 dt.astimezone() 即可。
    local = dt_local.astimezone().replace(second=0, microsecond=0)
    aria_label = _fmt_aria_day(local)

    # 1) 开启「定时发布」：新版页面是带 data-active 的 Mantine Group，
    #    行首是 <p>定时发布</p> 标签，点击标签（冒泡到 Group）切换开关。
    try:
        label = page.locator('p:has-text("定时发布")').first
        if label.count() == 0:
            label = page.locator('text=定时发布').first
        group = label.locator('xpath=ancestor::div[contains(@class,"mantine-Group-root")][1]')
        group.scroll_into_view_if_needed(timeout=5000)
        human_delay(0.3, 0.8)
        if group.get_attribute("data-active") != "true":
            label.click(timeout=5000)
            human_delay(0.8, 1.5)
            if group.get_attribute("data-active") != "true":
                group.click(timeout=5000)
                human_delay(0.8, 1.5)
        print(f"    ⏰ 已切换到「定时发布」")
    except Exception as e:
        print(f"    [ERR] 点击「定时发布」开关失败: {e}")
        return False

    # 2) 点击「设定发布时间」打开 DateTimePicker
    try:
        picker_btn = page.locator(
            'button.mantine-DateTimePicker-input, '
            'button:has-text("设定发布时间")'
        ).first
        picker_btn.scroll_into_view_if_needed(timeout=3000)
        human_delay(0.3, 0.8)
        picker_btn.click(timeout=5000)
        human_delay(1.0, 2.0)
        print(f"    📅 DateTimePicker 已打开")
    except Exception as e:
        print(f"    [ERR] 打开 DateTimePicker 失败: {e}")
        return False

    # 3) 选日期：button[aria-label="20 七月 2026"]
    try:
        # 提前检查：目标日期是否被 picker 禁用（超过 14 天上限或过去时间）
        day_btn = page.locator(f'button[aria-label="{aria_label}"]').first
        is_disabled = False
        if day_btn.count() > 0:
            is_disabled = day_btn.evaluate(
                "el => el.disabled || el.getAttribute('data-disabled') === 'true'"
            )
        if is_disabled:
            delta = (local.date() - datetime.now().date()).days
            print(
                f"    [ERR] 目标日期 {aria_label} 在 picker 中被禁用\n"
                f"           原因：距离今天 {delta} 天（小宇宙定时发布最多 14 天）"
            )
            return False
        # 如果目标日期不可见（比如跨月），先切月份
        if day_btn.count() == 0 or not day_btn.is_visible():
            # 找 calendarHeader 里 data-direction="next" 的按钮
            next_btn = page.locator(
                'button[data-direction="next"]:not([disabled])'
            ).first
            for _ in range(13):  # 最多跨 13 个月
                if day_btn.count() > 0 and day_btn.is_visible():
                    break
                # 等 next 按钮可点（picker 可能还在初始化）
                for _w in range(20):
                    if next_btn.is_enabled():
                        break
                    human_delay(0.2, 0.4)
                    next_btn = page.locator(
                        'button[data-direction="next"]:not([disabled])'
                    ).first
                try:
                    next_btn.click(timeout=5000)
                except Exception as e:
                    print(f"    [WARN] 点 next 失败: {e}")
                    break
                human_delay(0.5, 0.8)
                day_btn = page.locator(f'button[aria-label="{aria_label}"]').first
            else:
                if day_btn.count() == 0 or not day_btn.is_visible():
                    print(f"    [ERR] 找不到日期按钮 aria-label='{aria_label}'")
                    return False
        # 翻月后再次检查 disabled
        if day_btn.count() > 0:
            now_disabled = day_btn.evaluate(
                "el => el.disabled || el.getAttribute('data-disabled') === 'true'"
            )
            if now_disabled:
                delta = (local.date() - datetime.now().date()).days
                print(
                    f"    [ERR] 目标日期 {aria_label} 在 picker 中被禁用\n"
                    f"           原因：距离今天 {delta} 天（小宇宙定时发布最多 14 天）"
                )
                return False
        day_btn.click(timeout=5000)
        human_delay(0.5, 1.0)
        print(f"    📆 已选日期 {aria_label}")
    except Exception as e:
        print(f"    [ERR] 选日期失败: {e}")
        return False

    # 4) 填时分：两个 placeholder='--' 的 input
    try:
        time_inputs = [
            inp for inp in page.locator('input[placeholder="--"]').all()
            if inp.is_visible()
        ]
        if len(time_inputs) < 2:
            # popover 可能已被日期点击关闭——重开并重选
            picker_btn = page.locator(
                'button.mantine-DateTimePicker-input, '
                'button:has-text("设定发布时间")'
            ).first
            picker_btn.click(timeout=5000)
            human_delay(1.0, 2.0)
            day_btn = page.locator(f'button[aria-label="{aria_label}"]').first
            day_btn.click(timeout=5000)
            human_delay(0.5, 1.0)
            time_inputs = [
                inp for inp in page.locator('input[placeholder="--"]').all()
                if inp.is_visible()
            ]
        if len(time_inputs) < 2:
            print(f"    [ERR] 找不到时分输入框（找到 {len(time_inputs)} 个）")
            return False

        hh, mm = local.hour, local.minute
        hh_text = f"{hh:02d}"
        mm_text = f"{mm:02d}"

        # Mantine TimeInput 把每个时段（小时/分钟）当成一个独立 input。
        # 输完第一个段后 picker 会自动跳到第二个 input；我们直接给两个 input
        # 都 set value + 触发 React onChange（用 .fill() 不行——会被 Mantine 的
        # input mask 吞掉，这里用 evaluate 模拟完整的事件链）。
        for idx, val in enumerate([hh_text, mm_text]):
            ti = time_inputs[idx]
            ti.click(timeout=3000)
            human_delay(0.3, 0.6)
            ti.evaluate(
                """(el, v) => {
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeInputValueSetter.call(el, v);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                val,
            )
            human_delay(0.4, 0.7)

        # 时段填完后，按 Enter 确认当前 picker 状态（Mantine TimeInput 在 onComplete 时
        # 才把值 commit 到受控 state）。如果 picker 没自动跳到下一个段，再人工 Tab。
        try:
            page.keyboard.press("Enter")
            human_delay(0.4, 0.6)
        except Exception:
            pass
        # 把焦点切走，避免某个 input 的 onBlur 清空值
        try:
            page.keyboard.press("Tab")
            human_delay(0.3, 0.5)
        except Exception:
            pass
        print(f"    ⏱  已填时分 {hh:02d}:{mm:02d}")
    except Exception as e:
        print(f"    [ERR] 填时分失败: {e}")
        return False

    # 5) 点确认（✓ 按钮或回车）
    try:
        confirm_btn = page.locator(
            'button[data-dates-confirm], '
            'button[aria-label*="确认"], '
            'button:has-text("确定"), '
            'button:has-text("完成")'
        ).first
        if confirm_btn.count() > 0 and confirm_btn.is_visible():
            try:
                confirm_btn.click(timeout=5000)
            except Exception:
                confirm_btn.evaluate("el => el.click()")
            human_delay(0.8, 1.5)
            print(f"    ✅ 已确认时间")
        else:
            # 退而求其次：按 Escape 关闭 popover（很多 DateTimePicker 在两个 input 失焦后自动确认）
            page.keyboard.press("Escape")
            human_delay(0.5, 1.0)
            print(f"    ✅ 已按 Esc 关闭（依赖自动确认）")
    except Exception as e:
        print(f"    [WARN] 点确认失败（可能不影响）: {e}")

    # 6) 验证：DateTimePicker 按钮文本应该变成 "YYYY-MM-DD HH:MM"
    try:
        human_delay(0.5, 1.0)
        picker_btn_now = page.locator(
            'button.mantine-DateTimePicker-input, '
            'button:has-text("设定发布时间")'
        ).first
        text_now = picker_btn_now.inner_text().strip()
        if text_now and "设定发布时间" not in text_now:
            print(f"    📋 按钮文本已更新: {text_now!r}")
        else:
            print(f"    [WARN] DateTimePicker 按钮文本未更新: {text_now!r}")
    except Exception:
        pass

    return True


def _prompt_publish_at() -> str:
    """在 CLI 中询问用户输入发布时间。空输入 = 立即发布。"""
    print()
    print("⏰  定时发布？")
    print("   请输入未来发布时间（ISO 8601，Asia/Shanghai 或 UTC+8）：")
    print("   例如：2026-07-20T09:00:00  或  2026-07-20 09:00  或  2026-07-20T01:00:00Z")
    print("   留空直接回车 = 立即发布（默认）。")
    print("   输入 q 取消上传。")
    while True:
        try:
            raw = input("   发布时间 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return ""
        if raw.lower() in ("q", "quit", "cancel"):
            print("  已取消上传")
            sys.exit(0)
        if not raw:
            return ""
        # 校验
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from generate_config import parse_publish_at
            _dt, norm = parse_publish_at(raw)
            return norm
        except ValueError as e:
            print(f"   ❌ {e}")
            print("   请重新输入，或留空 = 立即发布，输入 q 取消。")
            continue
        except ImportError:
            # generate_config 不可用时退到轻量校验
            from datetime import datetime, timedelta, timezone
            s = raw.replace(" ", "T", 1)
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                print(f"   ❌ 无法解析为 ISO 8601：{raw!r}")
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            if dt <= datetime.now(tz=dt.tzinfo):
                print("   ❌ 发布时间必须是未来时间")
                continue
            return dt.isoformat(timespec="seconds")


def _save_upload_result(episode_dir: str, config: dict, result: dict):
    """把上传结果（eid/urls/timestamp）写回 config.json。

    即使 result 没有 public_url，只要 episode_id 存在也回写——
    这样后续 update_shownotes.py 才能工作。
    """
    if not result.get("success"):
        return False
    eid = result.get("episode_id")
    if not eid:
        return False

    ep = config.setdefault("episode", {})
    ep["episode_id"] = eid
    if result.get("episode_url"):
        ep["episode_url"] = result["episode_url"]
    if result.get("public_url"):
        ep["xiaoyuzhou_url"] = result["public_url"]
    ep["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
    if result.get("status"):
        ep["upload_status"] = result["status"]
    if result.get("verify_source"):
        ep["upload_verify_source"] = result["verify_source"]
    if result.get("scheduled_at_local"):
        ep["scheduled_at_local"] = result["scheduled_at_local"]

    config_path = os.path.join(episode_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存上传结果到 config.json")
    print(f"     episode_id: {eid}")
    if result.get("public_url"):
        print(f"     xiaoyuzhou_url: {result['public_url']}")
    return True


def main():
    parser = argparse.ArgumentParser(description="「李自在AI人物志」小宇宙单集上传")
    parser.add_argument("--episode-dir", required=False,
                        help="集数目录（如 E01.山姆奥特曼）")
    parser.add_argument("--login", action="store_true",
                        help="重新登录（保存 Cookie）")
    parser.add_argument("--headed", action="store_true",
                        help="显示浏览器界面（调试）")
    parser.add_argument("--publish-at", default=None,
                        help="[可选] 定时发布时间，ISO 8601 格式。\n"
                             "  支持：'2026-07-20T09:00:00+08:00' / '2026-07-20T09:00:00Z' / \n"
                             "        '2026-07-20T09:00:00'（默认 Asia/Shanghai）/ '2026-07-20T09:00'\n"
                             "  优先级：CLI > config.json 的 scheduled_at > 运行期询问用户。\n"
                             "  若都没有，默认立即发布。")
    args = parser.parse_args()

    if args.login:
        do_login()
        return

    if not args.episode_dir:
        print("[ERR] 请指定 --episode-dir", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    episode_dir = os.path.abspath(args.episode_dir)
    if not os.path.isdir(episode_dir):
        print(f"[ERR] 集数目录不存在: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    if not check_cookie_valid():
        print("[ERR] Cookie 不存在或已失效，请先运行: python3 upload_episode.py --login",
              file=sys.stderr)
        sys.exit(1)

    config = load_config(episode_dir)
    audio_path = config["episode"]["audio"]["path"]
    if not os.path.isfile(audio_path):
        print(f"[ERR] 音频文件不存在: {audio_path}", file=sys.stderr)
        sys.exit(1)

    # 解析发布模式：CLI > config > 询问用户
    scheduled_at = None
    if args.publish_at:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from generate_config import parse_publish_at
            _dt, scheduled_at = parse_publish_at(args.publish_at)
        except (ImportError, ValueError) as e:
            print(f"[ERR] --publish-at 不合法: {e}", file=sys.stderr)
            sys.exit(1)
    elif config.get("scheduled_at"):
        scheduled_at = config["scheduled_at"]
        print(f"  ℹ️  使用 config.json 中已配置的 scheduled_at: {scheduled_at}")
    else:
        # 询问用户
        scheduled_at = _prompt_publish_at()
        if scheduled_at:
            config["scheduled_at"] = scheduled_at

    if scheduled_at:
        print(f"⏰  发布模式：定时发布 @ {scheduled_at}")
    else:
        print(f"🚀  发布模式：立即发布")

    print(f"📂 集数目录: {episode_dir}")
    print(f"📡 节目: {config['podcast_name']} ({config['podcast_id']})")
    print(f"🎵 音频: {audio_path}")
    print(f"🏷  标题: {config['episode']['title']}")
    print()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = _new_context(browser, headless=not args.headed)
        page = context.new_page()
        result = upload_episode(page, config)
        browser.close()

    # 汇总
    print(f"\n{'='*60}")
    print("📊 上传结果")
    print(f"{'='*60}")
    status = "✅ 成功" if result["success"] else f"❌ 失败: {result['error']}"
    print(f"  {result['title']}")
    print(f"  状态: {status}")
    if scheduled_at:
        print(f"  发布模式: ⏰ 定时发布 @ {scheduled_at}")
        if result.get("scheduled_at_local"):
            print(f"  实际写入 picker: {result['scheduled_at_local']}")
    else:
        print(f"  发布模式: 🚀 立即发布")
    if result.get("episode_id"):
        print(f"  Episode ID: {result['episode_id']}")
    if result.get("status"):
        print(f"  单集 status: {result['status']}")
    if result.get("verify_source"):
        print(f"  验证来源: {result['verify_source']}")
    if result.get("public_url"):
        print(f"  🔗 公开链接: {result['public_url']}")
    if result.get("warning"):
        print(f"  ⚠️  警告: {result['warning']}")

    _save_upload_result(episode_dir, config, result)

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
