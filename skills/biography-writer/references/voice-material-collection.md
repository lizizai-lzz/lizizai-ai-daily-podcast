# 人物原声素材收集工作流（纪录片式 SOT 前置）

> 目标：为纪录片式人物志（VO/SOT）收集人物真实公开采访/对谈/演讲/播客的**原始音频或视频**，转写为带词级时间戳的 JSON，并筛选出适合做 SOT 的候选片段。
> 分工：agent-reach 负责「发现 + 下载」，aliyun-tingwu-transcribe 负责「词级转写」，本工作流负责「归档 + 筛选」。

## 一、能力边界（实测）

| 环节 | 工具 | 可用性 |
|---|---|---|
| YouTube 搜索 | `yt-dlp --dump-json "ytsearch5:关键词"` | ✅ |
| YouTube 字幕 | `yt-dlp --write-sub --write-auto-sub --sub-lang zh-Hans,zh,en --skip-download` | ✅ 优先用字幕 |
| YouTube 下载音频 | `yt-dlp -f "bestaudio" -x --audio-format mp3` | ⚠️ 常撞风控（429 / bot 验证），兜底：`--cookies-from-browser chrome` |
| B站 搜索/详情 | `bili search "词" --type video -n 5` / `bili video BVxxx` | ✅ 无需登录 |
| B站 下载音频 | `bili audio BVxxx`（输出 ASR-ready WAV） | ✅ |
| B站 字幕 | `opencli bilibili subtitle BVxxx` | ✅ 桌面 Chrome |
| 小宇宙单集 | `~/.agent-reach/tools/xiaoyuzhou/transcribe.sh --polish "URL"` | ✅ 转写无词级时间戳，仅作参考 |
| X 检索 | `opencli twitter search "词" -f yaml` | ✅ 找账号/讨论，视频媒体有限 |
| 本地/用户提供文件 | 直接入库 | ✅ |

> ⚠️ **禁止用 yt-dlp 读 B站**（风控 412 拦截）；B站一律用 bili-cli / OpenCLI。

## 二、执行流程

### Step 1：发现素材（agent-reach）

按人物志大纲（`20_outline.md`）的关键节点，列出要收集的素材类型：创业史访谈、早期采访、争议回应、公开演讲、播客对谈等。

```bash
# YouTube
yt-dlp --dump-json "ytsearch8:{人物名} 采访" 2>/dev/null | jq -r '.title, .id, .duration_string, .webpage_url' 
# B站
bili search "{人物名} 采访" --type video -n 8
# X（找账号与公开讨论）
opencli twitter search "{人物名}" --limit 10 -f yaml
```

筛选标准：信息密度高（人物本人长篇讲述 > 剪辑片段）、画质/音质可用、可下载。候选记录到 `00_raw/voice_sources.md`：

```markdown
| 平台 | 标题 | URL/BV号 | 时长 | 覆盖节点 | 备注 |
|---|---|---|---|---|---|
| B站 | ... | BVxxx | 42:00 | 创业史 | 优先 |
```

### Step 2：获取音频/字幕

**优先级：字幕（免转写）> 音频下载 > 视频下载。**

```bash
# YouTube 字幕（首选，直接可读）
yt-dlp --write-sub --write-auto-sub --sub-lang "zh-Hans,zh,en" --skip-download -o "/tmp/%(id)s" "URL"
# YouTube 音频（字幕缺失时；风控时加 --cookies-from-browser chrome）
yt-dlp -f "bestaudio" -x --audio-format mp3 --cookies-from-browser chrome -o "/tmp/%(id)s.%(ext)s" "URL"
# B站 音频
bili audio BVxxx
# 小宇宙：直接转写
~/.agent-reach/tools/xiaoyuzhou/transcribe.sh --polish "https://www.xiaoyuzhoufm.com/episode/EPISODE_ID"
```

### Step 3：词级转写（aliyun-tingwu-transcribe，SOT 剪辑唯一依据）

对**拿到音频/视频文件**的素材统一走：

```bash
python3 ../aliyun-tingwu-transcribe/scripts/transcribe_audio.py \
  "<素材文件>" --speaker-count 2 --output-dir <episode_dir>/00_raw/transcripts/
```

- 开启说话人分离，输出 `<素材名>.json`（含**词级时间戳**）+ `.md` 文字稿
- 原始 JSON 是 SOT 精确剪辑的依据，**必须落盘归档**
- 只有字幕/无词级时间戳的素材（YouTube 字幕、小宇宙转写）标注"无词级时间戳"，SOT 剪辑时用字幕时间轴人工对齐

### Step 4：SOT 候选筛选（写回 `voice_sources.md`）

对照 `20_outline.md` 的情绪关键点/人生转折点，从转写稿中挑出候选 SOT：

- 人物本人原话（第三方评论/博主观点一律不做 SOT）
- 信息密度高、情绪到位、自成一段（20-45 秒）
- 记录：素材名、句子/词级时间窗、转写文字、对应大纲节点

```markdown
### 候选 SOT
| 素材 | 时间窗 | 时长 | 内容摘要 | 对应节点 |
|---|---|---|---|---|
| interview.mp3 | 06:15–06:52 | 37s | 「儿子，你这是在杀我」+车里哭 | 大学负债 |
```

## 三、产物归档

```
00_raw/
├── voice_sources.md        # 素材清单 + SOT 候选（必产出）
└── transcripts/            # 原始转写 JSON（词级时间戳）+ md
```

阶段 6 模式 B（纪录片式）直接读取本目录：SOT 按 `voice_sources.md` 候选 + JSON 词级句尾剪切。
