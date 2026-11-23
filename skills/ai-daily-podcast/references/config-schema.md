# config.json 结构定义

播客上传准备配置文件，在 Phase 2.5 生成，Phase 3 完成后回填音频和封面元数据。

## 完整结构

```json
{
  "version": "1.0",
  "date": "YYYY-MM-DD",
  "source": "日报套餐填 AI 日报；独立行业洞见填 research_supplement 或 source_brief",
  "generated_at": "ISO 8601 时间戳",
  "podcasts": [
    {
      "type": "daily_brief | opensource | industry_trends",
      "title": "15-20字的具体标题（每日精选=头条新闻法/开源解读=单项目标题法/行业洞见=人物:观点或话题:判断）",
      "subtitle": "副标题，补充标题未尽之意（20-40字）",
      "description": "Markdown格式的内容简介（150-300字）",
      "script_path": "脚本文件绝对路径",
      "audio": {
        "path": "MP3文件绝对路径",
        "size": "文件大小（如 5.8MB）或 null",
        "format": "mp3",
        "duration_seconds": 时长秒数(float)或 null,
        "duration_human": "可读时长（如 8:24）或 null",
        "bitrate": "比特率（如 96kbps）或 null"
      },
      "cover": {
        "path": "封面图绝对路径",
        "template": "cover_template.html",
        "data": {
          "seriesTag": "每日精选 | 开源解读 | 行业洞见",
      "seriesEn": "DAILY BRIEF | OPEN SOURCE | INDUSTRY INSIGHTS",
      "label": "头 版 | 开 源 | 洞 见",
      "audience": "可选，受众标签，默认 独立开发者 · AI+教育",
          "hit1": "核心新闻1（≤15字）",
          "hit2": "核心新闻2（≤15字）",
          "hit3": "核心新闻3（≤15字）"
        },
        "size": "文件大小（如 2.4MB）或 null",
        "format": "png",
        "dimensions": "2048x2048"
      }
    }
  ]
}
```

## 字段说明

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | 是 | 配置格式版本，当前为 `"1.0"` |
| `date` | string | 是 | 播出日期，格式 `YYYY-MM-DD` |
| `source` | string | 是 | 日报套餐填 AI 日报路径；独立行业洞见填 `research_supplement_industry_{date}.md` 或 `source_brief_{date}.md` |
| `generated_at` | string | 是 | config.json 生成时间，ISO 8601 格式 |
| `podcasts` | array | 是 | 本轮播客的元数据数组，1-3 个元素。独立行业洞见只有 1 个 |

### 单条播客字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 播客类型：`daily_brief`、`opensource`、`industry_trends` |
| `title` | string | 是 | 15-20 字的具体标题：每日精选=当天最劲爆的 1 条新闻；开源解读=主角项目名+亮点；行业洞见=「人物:观点」或「话题:判断」，视觉宽 ≤ 20 |
| `subtitle` | string | 是 | 副标题，20-40 字，补充标题未尽之意，适合播客平台展示 |
| `description` | string | 是 | Markdown 格式内容简介，150-300 字 |
| `script_path` | string | 是 | 口播脚本文件绝对路径 |
| `audio.path` | string | 是 | MP3 输出文件绝对路径 |
| `audio.size` | string\|null | Phase 3 回填 | 文件大小（人类可读，如 `5.8MB`） |
| `audio.format` | string | 是 | 固定 `"mp3"` |
| `audio.duration_seconds` | number\|null | Phase 3 回填 | 时长秒数（浮点），通过 `ffprobe` 获取 |
| `audio.duration_human` | string\|null | Phase 3 回填 | 可读时长（如 `8:24`），由秒数换算 |
| `audio.bitrate` | string\|null | Phase 3 回填 | 比特率（如 `96kbps`），通过 `ffprobe` 获取 |
| `cover.path` | string | 是 | 封面图输出文件绝对路径 |
| `cover.template` | string | 是 | 固定 `"cover_template.html"`（HTML 封面模板） |
| `cover.data` | object | 是 | 封面模板注入数据（见下方 cover.data 字段说明） |
| `cover.size` | string\|null | Phase 3 回填 | 文件大小（如 `2.4MB`） |
| `cover.format` | string | 是 | 固定 `"png"` |
| `cover.dimensions` | string | 是 | 固定 `"2048x2048"`（Playwright deviceScaleFactor=2） |

### cover.data 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `seriesTag` | string | 是 | 系列中文名，决定 Badge 配色：每日精选(墨黑)/开源解读(深靛蓝)/行业洞见(深赭棕) |
| `seriesEn` | string | 是 | 系列英文标签：`DAILY BRIEF` / `OPEN SOURCE` / `INDUSTRY INSIGHTS` |
| `label` | string | 是 | 头条标签：`头 版` / `开 源` / `洞 见` |
| `audience` | string | 否 | 报头与页脚受众标签；默认 `独立开发者 · AI+教育`，行业洞见可按本期受众覆盖 |
| `hit1` | string | 是 | 核心新闻 1，不超过 15 字 |
| `hit2` | string | 否 | 核心新闻 2，不超过 15 字 |
| `hit3` | string | 否 | 核心新闻 3，不超过 15 字 |

## Phase 2.5 生成规则

在 Phase 2.5 时：
- 所有 `null` 字段先用 `null` 占位
- `audio.format` 固定填 `"mp3"`
- `cover.format` 固定填 `"png"`
- `cover.template` 固定填 `"cover_template.html"`
- `cover.data` 必须在此阶段完成（Phase 3B 需要读取）
- `title` 和 `description` 必须在此阶段完成
- `description` 不要写 BGM 署名，`finalize_podcast.py` 会给本轮播客自动补
- `audio.path` 与 `cover.path` 可以写 `~`，Phase 3C 会展开成绝对路径

## Phase 3C 回填规则

Phase 3 所有任务完成后，跑一条幂等命令，不要手工取值改 JSON：

```bash
python3 scripts/finalize_podcast.py --date {YYYY-MM-DD}
```

脚本执行四件事：

1. 展开 `audio.path` / `cover.path` 里的 `~`
2. 回填 `audio.size`、`audio.duration_seconds`、`audio.duration_human`、`audio.bitrate`、`cover.size`、`cover.dimensions`（封面尺寸直接读 PNG 头）
3. 给本轮每条播客的 `description` 各追加 `Music: "Inspired" by Kevin MacLeod (incompetech.com), CC BY 4.0`（已存在则跳过）
4. 校验文件存在性、封面是否为 2048×2048、字段是否仍为空；有问题则列出并以退出码 1 结束，此时禁止上传

## description 字段格式要求

```markdown
## 今日焦点

[核心话题的简短描述，2-3 句话]

## 关键内容

- [内容点1]
- [内容点2]
- [内容点3]

## 一句话总结

[提炼最核心的一个观点或行动建议]
```
