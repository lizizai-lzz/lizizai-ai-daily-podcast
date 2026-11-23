# config.json 结构定义（李自在AI人物志）

每集一个小宇宙上传配置文件，由 `generate_config.py` 生成，`upload_episode.py` 消费。

## 版本

- `v1.0`：旧版（milestone-only description）
- `v1.1`：当前版本（新增 `intro + 时点 + 页脚` description 结构 + `scheduled_at` 定时发布）

## 完整结构（v1.1）

```json
{
  "version": "1.1",
  "podcast_name": "李自在AI人物志",
  "podcast_id": "6a53643dd01e2a1f16e0f63e",
  "episode_num": 5,
  "person": "杨植麟",
  "highlight": "把长上下文做成中国大模型的旗帜",
  "intro": "月之暗面创始人。从清华到 CMU，从 Transformer-XL 到 Kimi K3，一个汕头摇滚鼓手出身的科学家，把中国开源大模型推到了全球聚光灯下。",
  "title_override": "杨植麟：Kimi K3 模型背后的那个男人",
  "scheduled_at": "2026-07-20T09:00:00+08:00",
  "generated_at": "2026-07-19T10:30:00",
  "episode": {
    "title": "杨植麟：Kimi K3 模型背后的那个男人",
    "description": "Markdown 格式 Show Notes（见下方 description 结构说明）",
    "description_mode": "intro+timestamps",
    "audio": {
      "path": "/绝对路径/episode.mp3",
      "size_mb": 18.78,
      "format": "mp3",
      "duration_seconds": 1641.32,
      "duration_human": "27:21",
      "bitrate": "96k",
      "sample_rate": 24000
    },
    "script": {
      "path": "/绝对路径/50_podcast_script.md",
      "chars": 9015
    },
    "segments": {
      "intro": { "path": "...", "duration": 10.368, "duration_human": "0:10" },
      "main":  { "path": "...", "duration": 1613.96, "duration_human": "26:53" },
      "outro": { "path": "...", "duration": 17.16, "duration_human": "0:17" }
    },
    "episode_id": "6600a1b2c3d4e5f6a7b8c9d0",
    "episode_url": "https://podcaster.xiaoyuzhoufm.com/podcast/6a53643dd01e2a1f16e0f63e/episode/6600a1b2c3d4e5f6a7b8c9d0",
    "xiaoyuzhou_url": "https://www.xiaoyuzhoufm.com/episode/6600a1b2c3d4e5f6a7b8c9d0",
    "uploaded_at": "2026-07-19T10:55:12",
    "upload_status": "SCHEDULED",
    "upload_verify_source": "api",
    "scheduled_at_local": "2026-07-20T09:00:00+08:00"
  }
}
```

## 字段说明

### 顶层

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | 是 | 配置版本，当前 `"1.1"` |
| `podcast_name` | 是 | 小宇宙节目名：`李自在AI人物志` |
| `podcast_id` | 是 | 小宇宙节目 ID：`6a53643dd01e2a1f16e0f63e` |
| `episode_num` | 是 | 集数编号（整数） |
| `person` | 是 | 人物名（含 title，如 "Midjourney 创始人 David Holz"） |
| `highlight` | 是 | 亮点总结（≤15 字，用于默认标题拼接） |
| `intro` | 否 | 人物简短介绍（30-80 字），提供后启用新的「介绍 + 时点 + 页脚」description 结构 |
| `title_override` | 否 | 自定义标题，覆盖默认 `E{NN}.{person}：{highlight}` 格式 |
| `scheduled_at` | 否 | 定时发布时间（ISO 8601，含时区）。不传或为 `null` = 立即发布。例如 `"2026-07-20T09:00:00+08:00"` |
| `generated_at` | 是 | 生成时间 ISO 8601 |
| `episode` | 是 | 单集元数据（见下） |

### episode 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 小宇宙标题。若 `title_override` 提供，使用该值；否则格式 `E{NN}.{person}：{highlight}` |
| `description` | 是 | Show Notes，Markdown 格式（见下方 description 结构说明） |
| `description_mode` | 是 | description 生成模式：`intro+timestamps` / `fallback-milestones` |
| `audio.path` | 是 | episode.mp3 绝对路径 |
| `audio.size_mb` | 是 | 文件大小 MB |
| `audio.format` | 是 | 固定 `"mp3"` |
| `audio.duration_seconds` | 是 | 时长秒数（浮点） |
| `audio.duration_human` | 是 | 可读时长 `M:SS` |
| `audio.bitrate` | 是 | 比特率（`96k`） |
| `audio.sample_rate` | 是 | 采样率（`24000`） |
| `script.path` | 否 | 脚本文件路径（用于字数统计） |
| `script.chars` | 否 | 脚本纯文本字数 |
| `segments` | 否 | 三段构成（intro/main/outro），来自 merge_audio.py |
| `xiaoyuzhou_url` | 上传后回填 | 上传成功后的小宇宙公开链接 |
| `episode_url` | 上传后回填 | 小宇宙后台 URL |
| `episode_id` | 上传后回填 | 小宇宙 episode ID |
| `uploaded_at` | 上传后回填 | 上传时间 |
| `upload_status` | 上传后回填 | 小宇宙单集状态：`NORMAL`（已发布）/ `SCHEDULED`（定时发布） |
| `upload_verify_source` | 上传后回填 | eid 来源：`api` / `url` / `list` |
| `scheduled_at_local` | 上传后回填（仅定时发布） | 实际写入 DateTimePicker 的本地时间（ISO 8601），与顶层 `scheduled_at` 相同时无需单独看 |

## description 结构说明

### 主推模式：intro + 时点 + 页脚（v1.1）

调用 `generate_config.py` 时同时提供 `--intro` 且 `40_final.md` 存在，启用此模式。

**结构**：

```
{人物简短介绍，30-80 字，单段}

## 时点

{MM:SS} {章节1标题}
{MM:SS} {章节2标题}
...
{MM:SS} {章节N标题}

---
「李自在AI人物志」——在数字的微光里，读懂改变世界的人。
```

**时点格式**（参考 [小宇宙官方规范](https://post.xiaoyuzhoufm.com/timespot/)）：

- 小宇宙支持两种时点格式：
  - `HH:MM:SS`（小时:分钟:秒，用于 ≥ 1 小时的单集）
  - `MM:SS`（分钟:秒，用于 < 1 小时的单集）
- 60 进制必须正确（`01:59:59` 合法，`01:61:61` 非法）
- 时点 + 一个空格 + 章节标题，每行一个时点
- 小宇宙 App 会自动识别时点并支持一键跳转

**时点分配逻辑**：

1. 第一个章节的时点 = 片头时长（intro_duration，约 10-15 秒）
2. 后续章节的时点 = 前一章节时点 + (前章节字数 / 总字数) × 正片时长
3. 章节从 `40_final.md` 的 `##` 二级标题自动提取，按文档顺序

**章节标题精简规则**：

- 去掉 Markdown 加粗 `**xxx**`
- 去掉中文双破折号 `——` 及其后的副标题（保留主标题）
- 去掉末尾的冒号

**示例**：

```
月之暗面创始人。从清华到 CMU，从 Transformer-XL 到 Kimi K3，一个汕头摇滚鼓手出身的科学家，把中国开源大模型推到了全球聚光灯下。

## 时点

00:10 开篇：2026 年 7 月 17 日，凌晨
01:39 第一章：汕头出来的"摇滚鼓手"
04:22 第二章：Hinton 弟子的弟子
07:25 第三章：盘古、循环智能，与第一次创业的伏笔
09:51 第四章：月球背面
13:19 第五章：坠入暗面
17:38 第六章：K2 的全球回响
21:07 第七章：K3 的暗面
25:48 收束：雪山没有尽头

---
「李自在AI人物志」——在数字的微光里，读懂改变世界的人。
```

### Fallback 模式：milestones（v1.0 兼容）

未提供 `--intro` 或 `40_final.md` 不存在时启用。

结构：`## 本期人物 + ## 关键里程碑 + 页脚`，里程碑从 `10_source.md` 的「## 3. 关键人生节点」提取。

## 命名约定

- **集数目录**：`E{NN}.{人物名}/`，如 `E01.山姆奥特曼/`、`E12.Midjourney 创始人 David Holz/`
- **集数编号**：两位数字零填充（`E01`、`E02`…`E12`）
- **人物名**：中文优先；非常知名的人物直接写人名（如「黄仁勋」）；需要补充身份的写成 `title + 人名`（如「Midjourney 创始人 David Holz」）
- **亮点总结**：≤15 字，提炼本期核心价值点，不写"震撼""颠覆"等虚词
- **人物介绍**：30-80 字，建议包含「身份标签 + 1-2 个最关键事实 + 一句钩子」

## 小宇宙标题规则

**默认格式**：`E{NN}.{人物名}：{亮点总结}`

- 冒号使用中文全角 `：`
- 集数零填充到两位
- 人物名与目录名一致
- 亮点总结是 `--highlight` 参数，≤15 字

**自定义格式**（`--title` 提供）：完全使用用户传入的标题，不做任何拼接。

示例：
- `E01.山姆奥特曼：用OpenAI点燃全球AI浪潮`（默认）
- `E03.黄仁勋：把GPU卖给全人类`（默认）
- `杨植麟：Kimi K3 模型背后的那个男人`（自定义，--title）

## CLI 参数

```bash
python3 generate_config.py \
  --episode-dir "~/李自在AI人物志/E05.杨植麟" \
  --highlight "把长上下文做成中国大模型的旗帜" \
  --intro "月之暗面创始人。从清华到 CMU，从 Transformer-XL 到 Kimi K3，一个汕头摇滚鼓手出身的科学家，把中国开源大模型推到了全球聚光灯下。" \
  --title "杨植麟：Kimi K3 模型背后的那个男人"
```

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `--episode-dir` | ✅ | - | 集数目录绝对路径 |
| `--highlight` | ✅ | - | 亮点总结（≤15 字，用于默认标题拼接） |
| `--episode-num` | 否 | 从目录名解析 | 集数编号 |
| `--person` | 否 | 从目录名解析 | 人物名 |
| `--title` | 否 | `E{NN}.{person}：{highlight}` | 自定义标题（完全覆盖默认拼接） |
| `--intro` | 否 | - | 人物简短介绍，30-80 字。提供后启用新的 description 结构 |
| `--output` | 否 | `config.json` | 输出文件名 |
| `--publish-at` | 否 | - | 定时发布时间（ISO 8601）。不传 = 立即发布。例：`"2026-07-20T09:00:00+08:00"` |

## 定时发布

v1.1 起支持。`scheduled_at` 字段在 config.json 顶层，传递方式有三种：

| 优先级 | 来源 | 备注 |
|---|---|---|
| 1️⃣ | `upload_episode.py --publish-at '2026-07-20T09:00:00+08:00'` | 命令行参数，**最高优先级** |
| 2️⃣ | config.json 顶层 `scheduled_at` 字段 | 由 `generate_config.py --publish-at` 写入 |
| 3️⃣ | 运行期 stdin 询问 | 都没有时会提示「请输入发布时间」，留空 = 立即发布，输入 `q` = 取消上传 |

### 解析规则

- **ISO 8601** 格式，推荐含时区：`2026-07-20T09:00:00+08:00`
- 兼容：UTC（`...Z`）、无时区（按 Asia/Shanghai 解释）、短格式（`2026-07-20T09:00`）、空格分隔（`2026-07-20 09:00:00`）
- **必须是未来时间**（早于当前时刻会被拒绝）
- 超过 1 年的发布时间会被拒绝（疑似误传）
- 失败时脚本会退出码 1 并打印具体原因

### UI 自动化流程

`upload_episode.py` 在 Step 7 勾完 checkbox 之后、Step 8 点「创建」之前，插入 Step 7.5：

1. 点击「定时发布」radio button
2. 点击「设定发布时间」打开 Mantine DateTimePicker
3. 选目标日期（`button[aria-label="20 七月 2026"]`）
4. 填入 HH:MM（两个 `input[placeholder="--"]`）
5. 点确认（✓）按钮
6. 验证 DateTimePicker 按钮文本已更新为选定时间

UI 失败时会询问用户是否继续（默认 N → 终止本次上传，截图存到 `/tmp/lizz_bio_{NN}_sched_fail.png`）。

### 上传后状态

- `upload_status = "SCHEDULED"`（来自 list API）
- `upload_verify_source = "api" / "url" / "list"`（v2 验证机制，见 SKILL.md）
- `scheduled_at_local` 记录实际写入 picker 的本地时间
