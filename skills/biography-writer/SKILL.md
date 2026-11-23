---
name: biography-writer
description: "撰写 3000-4000 字中文人物传记的端到端 Skill。输入一个人物名字，通过 anysearch 收集生平履历与公开报道，通过 agent-reach 抓取 Twitter/X 等社交媒体公开发言，沉淀为母文；然后基于母文设计大纲、生成正文，用 de-AI-writing 去 AI 味。可选阶段：将传记终稿转成访谈式（VO 旁白 + 人物原声 SOT）播客正片并合成 MP3，不支持纯旁白。适用场景：帮我写一篇 X 的传记、为 X 撰写人物传记、生成 X 的人物特写、写一篇关于 X 的深度人物报道、把传记做成访谈播客。"
agent_created: true
---

# biography-writer — 中文人物传记生成流水线

## 适用范围

输入：一位公开人物的名字（默认偏向科技/商业人物，但可处理学者、艺术家、创作者等任何具有可检索公开资料的人物）。

输出：一篇 3000-4000 字的中文人物传记正文，Markdown 格式，已去除 AI 痕迹。

## 强制依赖

执行前必须确认以下 Skill 已安装；缺失则报错并停止：

| 依赖 | 用途 | 调用方式 |
|------|------|---------|
| `anysearch` | 生平履历搜索 + 公开报道检索 + URL 正文提取 | `<anysearch_cmd> search/extract ...` |
| `agent-reach` | Twitter/X、Reddit、Bilibili、小红书等公开社交发言 | `agent-reach doctor --json` 后按 backend 调用 |
| `de-AI-writing` | 终稿去 AI 味 | 读母文后用 Skill 工具加载 `/de-AI-writing` |

**可选依赖**（仅阶段 6 播客音频需要）：

| 依赖 | 用途 | 调用方式 |
|------|------|---------|
| `ai-daily-podcast` | 复用其单人 TTS 脚本 `generate_tts_solo.py` 合成 MP3 | `python3 scripts/generate_tts_solo.py ...` |
| 火山引擎 Seed-TTS | 实际 TTS 引擎 | 通过 `ai-daily-podcast` 脚本调用，环境变量 `VOLCENGINE_TTS_APPID/SPEAKER/ACCESS_TOKEN` |
| `aliyun-tingwu-transcribe` | 人物原声素材转写（获取词级时间戳，纪录片式 SOT 剪辑必需） | `python3 ../aliyun-tingwu-transcribe/scripts/transcribe_audio.py ...`（本仓库 `skills/aliyun-tingwu-transcribe/`） |

阶段 6 是可选阶段，缺失依赖时**只跳过阶段 6**，不影响阶段 1-5 主流程。
阶段 6 **仅支持访谈式（纪录片式 VO/SOT）**，不再支持纯旁白模式。必须有原声素材（用户提供或公开采访的音视频）；没有原声素材时**跳过阶段 6**，不降级为纯旁白。

若任一**强制**依赖缺失，告知用户具体缺失项与安装命令后停止，不要降级到通用搜索。

## 工作目录约定

每次任务在当前工作区根目录下创建：

```
biography-{人物英文 slug}/
├── 00_raw/                  # 搜索/抓取的原始素材，按来源分文件
│   ├── anysearch-bio.md
│   ├── anysearch-coverage.md
│   ├── anysearch-controversy.md
│   ├── social-twitter.md
│   └── social-others.md
├── 10_source.md             # 母文：结构化整理后的素材汇总（必产物）
├── 20_outline.md            # 大纲设计文档（必产物）
├── 30_draft.md              # 初稿正文（必产物）
├── 40_final.md              # 去 AI 味后的最终传记（交付物）
├── 52_documentary_script.md # [可选] 访谈式脚本（VO/SOT 标注，见 references/documentary-podcast-guide.md）
├── vo_*.txt                 # [可选] 每段 VO 旁白文本（情感标签）
├── sot_*.mp3                # [可选] 人物原声片段（词级句尾剪切）
└── 60_podcast.mp3           # [可选] 访谈正文组装（VO/SOT 交替，无 BGM）
```

slug 规则：人物英文名小写、空格转连字符，例如 `biography-sam-altman/`、`biography-elon-musk/`。

文件命名稳定，便于跨任务复用与人工核查。

## 流水线总览

按顺序执行，每阶段产出对应文件。**阶段 1-5 为主流程，不可跳过中间阶段**；**阶段 6 为可选阶段**，仅在用户显式要求生成播客/音频时触发。每个阶段开始前调用 `TaskCreate` 建立任务条目，结束后调用 `TaskUpdate` 标记完成，让用户看到进度。

---

## 内容合规红线（所有阶段强制遵守）

传记面向中文受众发布，涉及地缘政治、主权、领土的表述必须符合中国大陆法律法规与平台审核标准。以下规则在**母文沉淀、传记生成、播客脚本改写**三个文本产出阶段全部生效，违反任一条视为不合格产物，必须改写。

### 必须遵守的表述规范

1. **台湾地区**：始终使用"中国台湾"或"台湾地区"，**严禁**出现"台湾作为国家""台湾总统""台湾政府""中华民国（作为现行政权）"等将台湾表述为主权国家的措辞。涉及人物在台湾的经历，用"赴台""在台""台湾地区"等中性地理表述。
2. **香港、澳门**：使用"中国香港""中国澳门"。回归前的历史事件可保留"英属香港""葡属澳门"等历史表述。
3. **涉藏、涉疆、涉港问题**：采用中国大陆官方立场表述，不引用分裂势力或外部势力的政治主张。
4. **国家领导人**：不发表贬损、侮辱性评价，不传播未经证实政治谣言。
5. **历史事件**：涉及二战、国共内战等敏感历史，采用中国大陆主流史观。

### 涉敏感内容时的改写策略

当素材中包含涉台/涉港/涉藏/涉疆等敏感内容（如人物有相关言论、争议、商业纠纷），**不回避事实，但调整表述角度**：

- **聚焦商业/产业影响**，淡化政治定性（例："言论引发中国大陆舆论批评"→"言论引发讨论"，"访问中国台湾"→"亚洲之行"或"赴台行程"）
- **不转述敏感原话**：若当事人的言论涉及主权定性，不直接引用原话，改用"部分言论引发争议"等概述
- **保持叙事完整性**：人物确实面临过的舆论危机可以写，但重点放在其商业应对（如赴华沟通、业务调整），而非政治细节
- **客观记录商业后果**：如股价波动、业务受限、市场反应等可正常陈述

### 自检清单（每个文本产出阶段交付前必查）

逐项扫描全文，命中任一项即触发改写：

- [ ] 搜索 `台湾` 并人工复核每处上下文，确认无"作为国家"的表述
- [ ] 搜索 `中华民国`，确认仅出现在 1949 年前的历史语境
- [ ] 搜索 `总统`/`总统府`/`行政院`，确认非指台湾地区所谓"政权机构"
- [ ] 搜索 `独立`/`独立公投`/`自决`，确认无支持分裂的表述
- [ ] 搜索国家领导人姓名，确认无侮辱性评价

---

### 阶段 1：素材收集（输出 `00_raw/*`）

**目标**：穷尽公开可检索的信息源，覆盖五个维度：① 基本生平履历；② 重要公开报道；③ 个人公开发言；④ 争议/批评视角；⑤ 行业上下文。

**Step 1.1 — 解析人物身份**

先快速搜索一次确认人物身份，避免同名混淆：

```bash
<anysearch_cmd> search "{人物名} 简介 身平 是谁" --max_results 5
```

若结果明显指向多个人物（同名），向用户确认后继续。

**Step 1.2 — 履历搜索（写入 `00_raw/anysearch-bio.md`）**

```bash
<anysearch_cmd> search "{人物名} biography life career timeline" --max_results 8
<anysearch_cmd> search "{人物名} 维基百科 百度百科 履历 经历" --max_results 8
<anysearch_cmd> search "{人物名} interview biography early life education" --max_results 5
```

对其中信息密度高的 3-5 个 URL 执行 `extract`：

```bash
<anysearch_cmd> extract "https://..."
```

写入文件时按 **来源 → 关键事实 → 原文摘录 → URL** 四段式记录，每条素材保留可追溯链路。

**Step 1.3 — 公开报道与深度访谈（写入 `00_raw/anysearch-coverage.md`）**

```bash
<anysearch_cmd> search "{人物名} 深度报道 长文 专访 特写" --max_results 8
<anysearch_cmd> search "{person name} profile feature interview in-depth" --max_results 8
<anysearch_cmd> search "{person name} New Yorker/Wired/Vanity Fair profile" --max_results 5
```

提取核心 3-5 篇全文。

**Step 1.4 — 争议与批评视角（写入 `00_raw/anysearch-controversy.md`）**

传记不能只写光环。主动搜索批评与争议，保证叙事张力：

```bash
<anysearch_cmd> search "{人物名} 争议 批评 质疑 反对" --max_results 8
<anysearch_cmd> search "{person name} criticism controversy backlash scandal" --max_results 8
```

**Step 1.5 — 社交媒体公开发言（写入 `00_raw/social-*.md`）**

通过 `agent-reach`。先健康检查：

```bash
agent-reach doctor --json
```

根据 active_backend 调用：

```bash
# Twitter/X 公开发言（首选 twitter-cli）
twitter search "from:{handle}" -n 30 2>/dev/null || \
  opencli twitter search "from:{handle}" -f yaml

# 若不知道 handle，先查
twitter search "{person name}" -n 10
```

注意：
- 只采集**公开发言**，不抓取私信、不触发任何写操作。
- 优先抓取**有信息密度**的内容：观点、立场、宣告、争议帖，而非日常寒暄。
- 同步抓取 Reddit/Bilibili/小红书上的相关讨论作为补充视角，但 Reddit 与小红书通常需要登录态，失败时记录在文件中并继续，不阻塞流程。

**Step 1.6 — 阶段产物自检**

`00_raw/` 目录下至少包含 4 个文件，总素材不少于 5000 字。若不足，回到 Step 1.2 扩展搜索关键词。

**Step 1.7 — 人物原声素材收集（纪录片式播客必需，可后续补做）**

若用户要制作纪录片式播客（VO/SOT）或提供了人物音视频素材，按 `references/voice-material-collection.md` 执行：
1. agent-reach 负责「发现 + 下载」：YouTube（yt-dlp，字幕优先、音频兜底）、B站（bili-cli `audio` 命令）、小宇宙、X
2. 统一用 `aliyun-tingwu-transcribe` 转写（**词级时间戳 JSON 必须落盘**到 `00_raw/transcripts/`）
3. 产出 `00_raw/voice_sources.md`：素材清单 + SOT 候选（时间窗、时长、内容、对应大纲节点）

此步可与阶段 2-5 并行推进；阶段 6 剪辑 SOT 时以本目录为准。

---

### 阶段 2：母文沉淀（输出 `10_source.md`）

**目标**：把零散原始素材整理成结构化母文，是后续创作的唯一事实来源。

**操作**：读取 `references/source-doc-template.md`，按其结构整理 `00_raw/*` 内容。母文必须包含以下章节（无内容写"暂无资料"，不可省略）：

```
# {人物名} — 母文

## 1. 基础档案
（生卒年、国籍、身份标签、所在机构、主要领域）

## 2. 时间线（按年份）
| 年份 | 事件 | 来源 |
|---|---|---|
| ... | ... | [来源](url) |

## 3. 关键人生节点（5-10 个）
### 节点 1：xxx
- 背景
- 经过
- 影响
- 来源

## 4. 重要作品 / 产品 / 成就
（按时间或重要度排列，每项附引用）

## 5. 公开发言摘录
（按主题归类：技术观 / 商业观 / 价值观 / 争议言论）

## 6. 公开报道视角
### 6.1 正面报道
### 6.2 中立/分析报道
### 6.3 批评报道

## 7. 争议与不同声音

## 8. 行业上下文
（同代人、竞争对手、所属浪潮）

## 9. 待澄清问题
（素材中矛盾或缺失的关键信息，标注为生成时需要做合理推断的点）
```

**硬性要求**：
- 每条事实必须挂来源 URL，无来源的事实写入"待澄清问题"。
- 不做主观评价，不做叙事化加工，保持信息密度。
- 母文完成后向用户简报：素材规模、覆盖维度、待澄清问题清单。

---

### 阶段 3：大纲设计（输出 `20_outline.md`）

**目标**：基于母文，结合人物类型，生成最契合的传记结构。

**操作**：读取 `references/outline-design-prompt.md`，按其中的指令执行。核心步骤：

1. **识别人物类型**：科技/商业人物 / 学者/科学家 / 艺术家/创作者 / 其他。
2. **选择叙事骨架**（按类型动态选择，而非固定模板）：
   - **科技/商业人物** → 产品/公司交织式（关键产品决策 + 公司里程碑交替推进）
   - **学者/科学家** → 学术里程碑式（关键论文/发现为锚点，思想演进为主线）
   - **艺术家/创作者** → 作品序列式（每部作品为一章，围绕创作观展开）
   - **其他** → 编年体与转折点混合式
3. **设计 6-8 个章节**，每章包含：标题、覆盖时间区间、核心事件、关键引言素材、本章要传递的认知/感受、预计字数。
4. **总字数预算**：3000-4000 字，章节字数按重要性加权。
5. **首尾设计**：开篇钩子 + 收束章。
6. 输出大纲后**向用户展示**，等待用户确认或调整后才进入阶段 4。

---

### 阶段 4：传记生成（输出 `30_draft.md`）

**目标**：按大纲逐章生成初稿正文。

**操作**：读取 `references/biography-generation-prompt.md`，严格按其写作规则生成。核心约束：

- **每章一次性生成**，不要把一章拆成多次 prompt。
- **严格基于母文素材**，不可杜撰事实、不可编造引语、不可虚构场景。
- **母文未覆盖但需要呈现的关键节点**：必须在大纲的"待澄清问题"中有标注，生成时用**合理推断**并明确标注（如"据同期同事回忆"、"根据公开访谈推断"），不可伪装成确凿事实。
- **叙事而非罗列**：避免"简历扩写"。每个事件都要进入**场景、人物、冲突、选择、后果**。
- **章节字数控制**：按大纲预算执行，单章不低于 400 字、不高于 1000 字。
- **引语使用**：人物公开发言的引语要带引号并保留原话，转述时用间接引语。
- **过渡自然**：章节之间不写"上一章我们说到…"这类讲义式衔接。

全篇完成后，向用户展示初稿，等待反馈（默认直接进入阶段 5，除非用户要求修改）。

---

### 阶段 5：去 AI 味（输出 `40_final.md`）

**目标**：清除生成痕迹，让传记读起来像专业非虚构作者的笔下作品。

**操作**：

1. 调用 `Skill` 工具加载 `de-AI-writing`：
   ```
   Skill(skill="de-AI-writing")
   ```
2. 按其规则对 `30_draft.md` 全文做去 AI 味改写：
   - 优先处理段落同构、路标词、二分对照、协作口吻。
   - 保持原意、保持事实精度、保持章节结构。
   - 不引入新的评价、不新增事实。
3. 改写结果写入 `40_final.md`。

**最终交付**：调用 `present_files` 展示 `40_final.md`，并在对话中给出：
- 总字数
- 各章节标题列表
- 母文中标记为"待澄清"的处理方式说明
- 主要素材来源数量统计

---

### 阶段 6（可选）：访谈式播客正片（输出 `52_documentary_script.md` + `vo_*.txt` + `sot_*.mp3` + `60_podcast.mp3`）

**触发条件**（满足任一即执行，否则不自动进入）：
- 用户明确要求"转成访谈播客"/"纪录片播客"/"带人物原声"/"VO/SOT"
- 用户提供人物原声音视频素材，或要求采集公开原声
- 用户在传记完成后追加访谈式音频需求

**目标**：把传记终稿改写为访谈式（VO 旁白 + SOT 人物原声）正片，合成可收听的 `60_podcast.mp3`。

> 本阶段只产出访谈正片。品牌片头/片尾、固定 BGM、整期组装与上传走 `lizz-biography-podcast` skill。

**Step 6.1 — 原声素材收集与转写**

按 `references/voice-material-collection.md` 执行：
1. 优先用用户提供的音视频；没有则用 agent-reach 搜索/下载（B站 `bili audio` 优先；用户限制"不用国外素材"时只用 B站）。
2. 统一用 `aliyun-tingwu-transcribe` 转写（开启说话人分离），**原始 JSON（含词级时间戳）存档到 `00_raw/transcripts/`**，这是 SOT 精确剪辑的唯一依据；候选 SOT 记入 `00_raw/voice_sources.md`。
3. 转写需要 oss2 依赖：`pip install oss2`（或用 `skills/aliyun-tingwu-transcribe/.venv/bin/python`，仓库不打包 venv，需自行创建）。

**Step 6.2 — 改写访谈脚本（`52_documentary_script.md` + `vo_*.txt`）**

严格按 `references/documentary-podcast-guide.md` 执行：
1. 从 `40_final.md` 选取 5-8 个情绪关键点/人生转折点作为 SOT（每段 20-45 秒，**只用人物本人或用户明确同意纳入的对话方原声**，第三方评论一律转 VO 讲述）。
2. VO 负责时代、背景、困境、前因后果的铺垫与承接，**引语让给 SOT，旁白不重复原声内容**。
3. 每段 VO 写成独立 `vo_{n}.txt`（带情感标签；中性标签 ≥70%，点睛 ≤8 处，禁语速/综艺标签）。
4. 合规自检（强制）：播客音频会经过平台内容审核，比纯文本更敏感，必须执行「内容合规红线」自检清单，不通过不得进入 TTS。

**Step 6.3 — VO 合成**

```bash
source ~/.zshrc && python3 scripts/generate_tts_solo.py \
  --content-file biography-{slug}/vo_{n}.txt --output-file biography-{slug}/vo_{n}.mp3
```

逐段合成（每段独立调火山引擎 Seed-TTS），合成后逐段 `ffprobe` 探测时长。

**Step 6.4 — SOT 剪切（实测踩坑，必须遵守）**

用词级 JSON 定位句尾，按以下规范剪切：
1. **`-ss` 必须放 `-i` 之前（输入 seek）**：`-ss` 在 `-i` 后与 `loudnorm` 组合会让中段切片输出全静音。
2. 淡入 0.3s；淡出起点 = **句尾 + 0.7s**（过早会被反馈"话没说完被减弱"）、时长 0.4s；剪切终点 = 句尾 + 0.6s；若下一句紧接无空隙，终点 = 句尾本身，**绝不允许切在句中**。
3. 响度归一：`loudnorm=I=-16:TP=-1.5:LRA=11`；统一 `aresample=24000,aformat=channel_layouts=mono`。
4. 验证：`ffmpeg ... -af volumedetect` 确认有声；必要时把切片再转写核对句子完整。

**Step 6.5 — 组装正片（`60_podcast.mp3`）**

按脚本顺序 VO/SOT 交替，段间 0.35s 停顿、**无 BGM**，统一 24000Hz 单声道 96kbps MP3（用 ffmpeg `concat` filter 组装）。

**Step 6.6 — 验证与交付**

```bash
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -of default=noprint_wrappers=1 biography-{slug}/60_podcast.mp3
```

交付 `52_documentary_script.md`、`vo_*.txt`、`sot_*.mp3` 与 `60_podcast.mp3`，对话中给出音频时长（分秒）、文件大小（MB）、脚本字数、使用的音色 ID。

**音色建议**：默认 `zh_male_wennuanahu_uranus_bigtts`（温暖男声）。如用户未指定，用此默认值；如用户偏好女声，可换 `zh_female_shaoergushi_moon_bigtts`（少儿故事女声，叙事感强）。

---

## 错误处理

| 情况 | 处理 |
|------|------|
| anysearch 无 API Key | 用匿名访问继续；若频控严重，告知用户并暂停 |
| anysearch API 持续超时 | **fallback 到内置 WebSearch + WebFetch 工具**，按相同五维度（履历/报道/争议/发言/上下文）采集，在母文中标注"素材来自 WebSearch fallback" |
| agent-reach Twitter backend 全部不可用 | 跳过 Twitter 抓取，在母文中标注，用其他社交平台（Reddit/Bilibili/小红书）的公开讨论补位 |
| agent-reach OpenCLI `--from` 过滤器返回非目标账号推文 | **这是已知 bug**：`opencli twitter search "..." --from {handle}` 可能返回包含关键词的其他账号推文。改用 `opencli twitter user-posts {handle}` 子命令，或从公开报道中补全言论 |
| 人物公开资料极少（<2000 字可用素材） | 暂停并告知用户，建议换人物或补充定向素材 |
| 用户在大纲阶段要求重新设计 | 回到阶段 3 重新执行，保留前一版到 `20_outline_v1.md` |
| 用户在初稿阶段要求修改 | 局部修订 `30_draft.md`，不重跑阶段 1-3 |
| 阶段 6 无原声素材（用户未提供且公开源不可得） | 跳过阶段 6，不降级为纯旁白；告知用户需先提供/采集原声 |
| 阶段 6 缺 `ai-daily-podcast` skill | 告知用户该 skill 是 VO 合成的前置依赖，给出安装方式后跳过阶段 6 |
| 阶段 6 缺火山引擎环境变量 | 告知用户需配置 `VOLCENGINE_TTS_APPID/SPEAKER/ACCESS_TOKEN` 后跳过阶段 6 |
| 阶段 6 TTS 某段合成失败 | 脚本自带 3 次重试；全失败时告知用户具体失败段落，保留已成功的分段文件供排查 |

## 触发词与示例

**传记正文（阶段 1-5）**：
- "帮我写一篇 {X} 的传记"
- "为 {X} 撰写人物传记"
- "写一篇关于 {X} 的深度人物特写"
- "用 biography-writer 写 {X}"
- "生成 {X} 的人物传记"

**追加播客音频（触发阶段 6）**：
- "把这篇传记转成访谈播客（带人物原声）"
- "给 {X} 的传记配上原声片段做成纪录片"
- "生成访谈式有声版"
- "转成 VO/SOT 纪录片"

调用者传入格式示例：
> 帮我写一篇 Sam Altman 的人物传记

或细化指令：
> 用 biography-writer 写一篇关于 Hinton 的传记，侧重学术思想演进

或两阶段串联：
> 帮我写一篇 Sam Altman 的传记，写完转成访谈式播客（VO + 原声 SOT）
