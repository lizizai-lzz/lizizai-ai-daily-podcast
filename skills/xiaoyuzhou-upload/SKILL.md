---
name: xiaoyuzhou-upload
description: >
  小宇宙播客自动上传 Skill。通过 Playwright 浏览器自动化，将本地 MP3 文件上传到小宇宙创作者后台。
  适用于已通过 podcast-generation / ai-daily-podcast 等技能生成播客 MP3 后，需要自动发布到小宇宙平台的场景。
  支持批量上传、Cookie 复用登录、标题自动拼接（日期+类型+原标题）、AI 生成声明勾选、服务协议勾选。
  当用户要求上传播客到小宇宙、发布播客、或提到"小宇宙上传"时触发。
  Triggers: "小宇宙上传", "上传播客", "发布播客", "xiaoyuzhou", "小宇宙发布", "播客上传", "upload podcast to xiaoyuzhou"
agent_created: true
---

# 小宇宙播客自动上传

## 概述

将本地 MP3 播客文件通过 Playwright 浏览器自动化上传到小宇宙创作者后台。脚本模拟真实浏览器指纹和人类操作节奏，支持批量上传多条播客。

## 前置条件

1. **Python 依赖**: `playwright`（需预装，`pip install playwright && playwright install chromium`）
2. **Cookie 文件**: 首次使用必须先登录保存 Cookie 到 `~/.xiaoyuzhou_auth.json`（`$XYZ_AUTH_FILE` 可覆盖）
3. **config.json**: 播客元数据文件，位于 `~/.daily-ai-news/data/{日期}/podcast/config.json`

## config.json 结构

```json
{
  "date": "2026-05-18",
  "podcasts": [
    {
      "type": "daily_brief",
      "title": "Grok Imagine发布 + Ring开源万亿模型",
      "description": "Show Notes 文本...",
      "audio": {
        "path": "~/.daily-ai-news/data/2026-05-18/podcast/daily_brief.mp3",
        "duration_human": "8:57",
        "size_human": "6.1M"
      }
    }
  ]
}
```

## 使用方式

### 首次登录（保存 Cookie）

```bash
python3 scripts/xiaoyuzhou_upload.py --login
```

打开浏览器窗口，手动扫码/登录小宇宙创作者后台，登录成功后自动保存 Cookie。

### 上传指定日期的播客

```bash
python3 scripts/xiaoyuzhou_upload.py --date 2026-05-18
```

批量上传 config.json 中所有播客到节目「李自在AI日报」（默认 ID `6a09a980f4ff26e89f601057`，可用 `$PODCAST_SHOW_ID` 覆盖为你自己的节目）。

上传前默认执行幂等检查：

- `config.json` 已记录 `xiaoyuzhou_url` 时直接跳过。
- 未记录时，按标题在小宇宙后台搜索；发现同名单集（忽略全角/半角冒号和空白差异）也跳过。
- 因此重复运行 Skill、定时任务和手工上传不会创建第二条同名节目。
- 行业洞见按周批量生成并预排期时，必须停用独立的每日行业洞见上传任务，避免同一期同时走“预排期”和“当日上传”两条路径。

### 仅上传指定类型

```bash
python3 scripts/xiaoyuzhou_upload.py --date 2026-05-18 --type daily_brief
```

可选类型: `daily_brief`（每日精选）, `opensource`（开源解读）, `industry_trends`（行业洞见）

### 显示浏览器窗口（调试用）

```bash
python3 scripts/xiaoyuzhou_upload.py --date 2026-05-18 --headed
```

### 定时发布

使用创建页原生的「定时发布」控件，在创建单集时直接填写预约时间：

```bash
python3 scripts/xiaoyuzhou_upload.py \
  --date 2026-05-18 \
  --schedule-at "2026-05-18 10:30:00"
```

- 时间按 `Asia/Shanghai` 解释，必须晚于当前时间。
- 小宇宙对当天发布设有约四小时的最小提前量；被平台自动夹到更晚时间时，脚本会中止提交。
- 脚本会启用定时开关、选择日期、填写小时和分钟，并核对页面生成的 `pubDate`。
- 定时设置失败时不会点击创建，避免先发布再补改时间。

### 使用自定义配置或临时加更标签

独立单集、临时加更或非默认目录的产物，可以显式传入 config 和标题类型标签：

```bash
python3 scripts/xiaoyuzhou_upload.py \
  --date 2026-05-18 \
  --config /path/to/config.json \
  --type industry_trends \
  --label "临时加更"
```

此时标题格式为 `{M月D日}{label}｜{原标题}`，不会使用默认的“行业洞见”标签。

## 标题格式

脚本自动拼接标题为 `{M月D日}{类型标签}｜{原标题}`，映射关系：

| type | 类型标签 |
|------|----------|
| `daily_brief` | 每日精选 |
| `opensource` | 开源解读 |
| `industry_trends` | 行业洞见 |

示例: `8月19日行业洞见｜模型没有护城河`

**长度约束（2026-08-19 起强制）**：小宇宙列表标题最多显示 2 行，官方推荐 25 字以内。完整标题（前缀+原标题）必须控制在 **30 字符以内**：
- 前缀 `{M月D日}{类型标签}｜` 固定约 9 字符（省略年份，小宇宙列表自带发布日期）
- 每日精选 / 开源解读：原标题 15-20 字（信息完整优先，见 ai-daily-podcast Skill 标题规则）
- 行业洞见：原标题视觉宽度 ≤ 20（英文/数字按 2 字符 ≈ 1 字宽计，见 ai-daily-podcast Skill 标题规则）

## 核心技术要点

### 浏览器自动化策略

- **Cookie 复用**: 手动登录一次，保存 `storage_state` 到 `~/.xiaoyuzhou_auth.json`（`$XYZ_AUTH_FILE` 可覆盖），后续复用
- **React/Mantine SPA**: `fill()` 不触发 React 状态更新，必须使用 `keyboard.type()` 模拟输入
- **浏览器指纹**: 自定义 user-agent、viewport 1440×900、locale zh-CN、timezone Asia/Shanghai、反 webdriver 检测注入
- **随机延迟**: 每步操作间随机暂停 0.5-2.5 秒，模拟人类节奏

### 创建成功检测

小宇宙 SPA 创建成功后 URL **不会跳转**。脚本通过以下方式确认：

1. **API 响应监听**: 全局 `page.on("response")` 捕获 `POST /v1/episode/hosted/create-free` 返回 200
2. **列表页确认**: 若 API 未捕获到，导航到节目列表页检查标题是否存在

### 小宇宙 DOM 结构（2026-08-04 验证）

| 元素 | 选择器 |
|------|--------|
| 音频上传 | 新版：点击 `text=点击上传播客` 打开「上传播客」对话框，对话框内有 `input[type="file"][accept*="audio/mpeg"]`（页面本身不再暴露音频 input，仅剩 2 个图片 input） |
| 标题输入 | `input[name="title"]` |
| Show Notes | `[contenteditable="true"]` |
| AI 生成声明 | 新版为 Mantine Switch：`input[data-sentry-source-file="EpisodeAISettingSection.tsx"]`（旧版 `input[name="isAIGC"]` 已失效） |
| 服务协议 | 通过 label 文字"同意"/"协议"点击 |
| 追光任务 | checkbox #9，**不需要勾选**，需排除 |
| 创建按钮 | `button:has-text("创建")` |

**AI 生成声明（2026-09-09 起平台改版）**：
- 创建页不再暴露 `isAIGC` / `EpisodeAISettingSection` 开关，创建时勾选会失败但并不影响创建成功。
- 声明改到单集编辑页「填写声明」区：两个 `[role="switch"]`，行文字分别为「不允许单集被 AI 总结」「本音频为 AI 生成」。
- 脚本在创建成功后自动执行 **Step 10**：打开 `{BASE_URL}/podcast/{PODCAST_ID}/episode/{eid}/edit`，勾选「本音频为 AI 生成」，点击「更新」，再重新加载校验；失败只告警不影响上传结果。

**file input 说明**（2026-08-04 起）：
- 创建单集页面仅剩 2 个 file input，均为 `accept="image/jpeg,image/png,image/webp"`（封面 / 单集封面）
- 音频 file input 仅出现在点击「点击上传播客」后打开的对话框内，accept 为 `audio/wav,audio/x-wav,audio/mpeg,audio/mp3,audio/x-m4a`
- 脚本已内置兼容逻辑：优先尝试页面直暴露的音频 input，失败则走对话框上传

**上传播客弹窗必须显式关闭**（2026-09-24 起，新增 `_close_upload_modal`）：
- 该弹窗没有关闭图标，只有一个「收起」按钮；上传完成后遮罩 `div.mantine-Modal-overlay` 会持续拦截后续点击。
- 症状：Step 5 输入标题时报 `Locator.click: Timeout`，调用日志里出现 `mantine-Modal-overlay ... intercepts pointer events`，整条上传失败。
- 处理：`set_input_files` 成功后立即按 `Escape` 关闭弹窗（实测关闭后音频仍保留在创建页，正文显示「音频 · MM:SS」），并在 Step 4 / Step 5 前各调用一次 `_close_upload_modal` 做防御。
- 同时 Step 4 的音频处理完成判定改为核对 `duration_human`（如 `6:25`）是否出现在页面，避免用宽泛的「含冒号」条件误判。
- 观察：同日创建页重新出现 `input[data-sentry-source-file="EpisodeAISettingSection.tsx"]` 开关，Step 7 可直接勾选（不再依赖 Step 10 兜底）。

### Checkbox 勾选策略

1. AI 生成: 通过 `input[name="isAIGC"]` + `click(force=True)` 精确定位
2. 服务协议: 通过 label 文字点击（Mantine Checkbox 推荐方式），fallback 为遍历所有可见 checkbox 排除 isAIGC 和追光任务
3. **追光任务（checkbox #9）**: 通过 section 文字包含"追光"来识别并跳过

## 工作流程

执行此 Skill 时，按以下步骤操作：

1. **检查前置条件**: 确认 Cookie 文件存在（`~/.xiaoyuzhou_auth.json`（`$XYZ_AUTH_FILE` 可覆盖）），不存在则提示运行 `--login`
2. **加载 config.json**: 读取 `~/.daily-ai-news/data/{日期}/podcast/config.json`
3. **验证文件**: 检查所有 MP3 文件路径是否存在
4. **执行上传**: 运行 `python3 scripts/xiaoyuzhou_upload.py --date {日期} [--type {类型}] [--schedule-at "YYYY-MM-DD HH:MM:SS"] [--headed]`
5. **报告结果**: 解析脚本输出，汇报每条播客的上传状态、公开链接和定时发布时间

## 注意事项

- Cookie 有效期有限，过期后需重新运行 `--login`
- 调试期间可能产生重复/测试单集，需在小宇宙后台手动清理
- 封面上传已跳过（非必需），如需恢复封面功能需重新开发
- 脚本路径: `scripts/xiaoyuzhou_upload.py`
