---
name: ai-daily-podcast
description: 生成「李自在AI日报」播客。每日精选与开源解读基于 AI 日报；行业洞见独立从知乎大众 AI 热点选题，用 DeepSeek Search/Fetch 收集和核验外部材料，不依赖 AI 日报。支持完整三栏、日报套餐或行业洞见单集。
---
# AI Daily Podcast — 日报套餐 + 独立行业洞见

## Overview

支持两种运行模式：

- **日报套餐**：每日精选 + 开源解读基于当日 AI 日报；行业洞见仍独立研究。
- **独立行业洞见**：只需要一个日期和公共研究输入，从知乎找题并用外部材料核验，不读取 AI 日报。

三个栏目可内容互补，但行业洞见不再是 AI 日报的下游产物。

| 播客 | 格式 | 时长 | 字数 | 定位 |
| --- | --- | --- | --- | --- |
| 每日精选 | 双人联播（李自在 + 肖然交替）+ 情感标签 + 条目间翻页音效 | 8-12 分钟 | 2400-3600 字 | 10 条最有话题性的 AI 热点新闻，两位主持一人一条、每条由一位主持从事实读到点评读到过渡，条目之间才换人 |
| 开源解读 | 单人深度解读 + 情感标签 | 8-10 分钟 | 2000-2800 字 | 5 个与独立开发者直接相关的开源项目，重点是你能不能用它赚钱或提效 |
| 行业洞见 | 单人深度分析 + 情感标签 | 7-10 分钟 | 2000-3000 字 | 独立从知乎大众 AI 热点里只讲一个普通用户关心的问题，用外部论据讲深讲透；不依赖 AI 日报，默认避开 Agent 安全与漏洞题 |

**核心设计原则：同组生成时三条播客内容零重叠。每日精选和开源解读通过知识库注入历史连续性；行业洞见通过知乎讨论、DeepSeek 外部检索和公开原文建立自己的连续性。**

**栏目专属规则全部收在各模块文件里**：每日精选的标题法与口语化生成规范、开源解读的单项目标题法与五维评选、行业洞见的知乎热点选题法与「母文 → 大纲 → 逐字稿」三段式流程，都在 `modules/` 下对应文件里。**生成到哪一栏，才读哪一栏**，见下方「栏目模块」表。


## 栏目模块（各自的标题规则、文风、格式约束都在这里）

| 栏目 | 模块文件 | 什么时候读 |
| --- | --- | --- |
| 每日精选 | `modules/daily-brief.md` | 生成每日精选脚本时**完整读取**（含标题法、双人播报规则、口语化生成规范与外部范例） |
| 开源解读 | `modules/opensource.md` | 生成开源解读脚本时**完整读取**（含单项目标题法、五维评选、解读模板） |
| 行业洞见 | `modules/industry-insights.md` | 生成行业洞见脚本时**完整读取**（含知乎大众热点选题、人物/话题双标题法、母文→大纲→逐字稿三段式） |

**三个模块互不通用**：不要把某一栏的文风、标题法、密度线套到另一栏上。栏目之间只共享本文件里的流水线、config.json 结构、后处理和交付规则。

## When to Use

- 用户提供 AI 日报 Markdown 文件并要求生成播客
- 用户说"生成播客""做播客""播客生成"且上下文涉及 AI 日报
- 用户要求执行每日播客工作流
- 用户要求只做一期行业洞见，或明确说选题和素材不依赖 AI 日报
- 用户要求从知乎 AI 热点、公共讨论或外部研究出发制作行业洞见播客

## Prerequisites

### 必须的技能

- `content-to-podcast` — 播客脚本格式模板和写作规范
- `podcast-generation` — 火山引擎播客 TTS 生成 MP3
- `llm-wiki`（Karpathy LLM Wiki）— 为每日精选和开源解读提供历史连续性；行业洞见只在确有背景价值时可选查询
- `qiaomu-ds-search` — **行业洞见强制依赖**：通过 DeepSeek 官方 Search / Fetch 补充检索、抓取正文、核验来源和冲突
- `agent-reach` 或 `chrome:control-chrome` — **行业洞见强制依赖**：读取知乎公开搜索结果、问题和高赞回答；浏览器不可用时允许使用其他公开只读搜索，但必须记录限制
- `any-search` — 行业洞见可选补充；DeepSeek 搜索不可用或需要二次交叉核验时使用

### 环境变量

以下环境变量需在 `~/.zshrc` 中配置：

| 变量 | 说明 | 用途阶段 |
| --- | --- | --- |
| `VOLCENGINE_TTS_APPID` | 火山引擎 APP ID | Phase 3 全部 MP3 |
| `VOLCENGINE_TTS_ACCESS_TOKEN` | 火山引擎 Access Token | Phase 3 全部 MP3 |
| `VOLCENGINE_TTS_SPEAKER` | 火山引擎单人 TTS 音色 ID | 仅作开源解读的历史回退；行业洞见不使用该变量 |

每日精选的双人音色固定在脚本参数里，不走环境变量：

| 角色 | 音色 ID | 说明 |
| --- | --- | --- |
| A 李自在（男） | `zh_male_wennuanahu_uranus_bigtts` | 温暖阿虎，长期使用的品牌音色 |
| B 肖然（女） | `zh_female_vv_uranus_bigtts` | 与男声同代（uranus），播报腔稳定 |

单人口播音色：

| 栏目 | 音色 ID | 说明 |
| --- | --- | --- |
| 开源解读 | 读取 `VOLCENGINE_TTS_SPEAKER` | 保留原有开源栏目音色 |
| 行业洞见 | `zh_male_liufei_uranus_bigtts` | **固定使用刘飞，必须在命令中显式传入，不读取 `VOLCENGINE_TTS_SPEAKER`** |

> 火山账号的 saturn 系列音色不可用（报 `resource ID is mismatched with speaker related resource`），换音色时从 uranus / moon / mars 系列里挑。

> **TTS 引擎决定（2026-09-29）**：本播客**继续用火山引擎 API**，不切本地模型。
> 2026-09-28 试过本地 IndexTTS-2 + `kepu-male`/`lizizai` 克隆音色（audio.cpp，Metal，RTF 2.57），
> 三项没有解决所以暂不接入：① 语速比火山快 17%（5.15 对 4.39 字/秒），模块里的字数标准要重标；
> ② 英文术语发音不稳（ASR 回读把 `HeyGen` 听成"黑"、`diff` 听成"di"，而稿子里英文词很密）；
> ③ 情感控制要走 emo 文本/向量，与现有 `[情感标签]` 语法不是一套，需要额外映射。
> 试听样本留在 `~/.daily-ai-news/data/2026-09-28/podcast/sample_opensource_indextts_kepu_2026-09-28.mp3`。
> 重新评估前不要再动引擎选型。

## File Structure

```
ai-daily-podcast/
├── SKILL.md                              # 本文件：路由 + 三条共用流水线
├── modules/                              # 三个栏目模块，按需加载（渐进式披露）
│   ├── daily-brief.md                    # 每日精选：标题法 + 双人规则 + 口语化生成规范
│   ├── opensource.md                     # 开源解读：单项目标题法 + 五维评选 + 解读模板
│   └── industry-insights.md              # 行业洞见：知乎大众热点选题 + 双标题法 + 母文→大纲→逐字稿
├── templates/
│   └── cover_template.html               # 封面 HTML 模板（复古中文报纸风格）
├── scripts/
│   ├── generate_covers.py                # Playwright 截图脚本：HTML → PNG
│   ├── generate_news_broadcast.py        # 每日精选双人联播 TTS（A/B 交替 + 翻页音效 + 片头片尾 BGM）
│   ├── generate_tts_solo.py              # 单人 TTS 脚本（开源解读、行业洞见 + 片头片尾 BGM）
│   ├── podcast_audio.py                  # 三条共用：片头/片尾 BGM 默认值、切曲、拼接 MP3
│   ├── check_broadcast_speakers.py       # 校验每日精选「一条新闻一位主持」是否被违反
│   ├── check_oral_voice.py               # 校验逐字稿的口播声纹（语气词/人称/问句密度）
│   ├── finalize_podcast.py               # Phase 3C：回填 config.json、校验产物、追加 BGM 署名
│   ├── append_host_clip.py               # 手动工具：给成品 MP3 追加「李自在真人彩蛋」（不在每日流水线内）
│   └── generate_podcast_dual.py          # 对话式双人 TTS（历史遗留，当前未接入工作流）
├── references/
│   ├── config-schema.md                  # config.json 结构定义和字段说明
│   ├── content-matrix.md                 # 内容互补矩阵：三条播客的模块分配规则
│   ├── topic-selection.md                # Phase 1 选题判断提示词（三条共用）
│   ├── industry-research.md              # 行业洞见独立研究：知乎 → DeepSeek → 来源分级 → 冲突
│   ├── theory-support.md                 # 行业洞见理论模块：主理论、竞争解释、原始来源与边界
│   └── voice-samples.md                  # 口播声纹样本：12 段真实中文播客开头的转写与密度
```

## Workflow

### Phase 0: 初始化

1. 确定运行模式：
   - **日报套餐**：本轮包含每日精选和/或开源解读
   - **独立行业洞见**：本轮只生成行业洞见
2. 确认输出目录（默认 `~/.daily-ai-news/data/{date}/podcast/`），不存在则创建。
3. **仅当本轮包含每日精选或开源解读时**，确认 AI 日报源文件路径（默认 `~/.daily-ai-news/data/{date}/ai_news_{date}.md`）并读取全文。行业洞见单集不检查、不读取该文件。
4. **仅当本轮包含每日精选或开源解读时**，加载 DailyAINewsWiki 历史上下文：
   - 读取 `index.md`
   - 扫描 `wiki/sources/`，读取最近 3-7 天日报页
   - 扫描 `wiki/synthesis/`
   - 扫描 `wiki/entities/`
   > 行业洞见不依赖 Wiki 日报页。只有在某个实体确有历史背景价值时才可选检索 entity/synthesis 页面，不能把该查询当成行业洞见的前置条件。
   > **验证检查点**：日报驱动栏目必须在相应 topic selection 中记录知识库查询情况。行业洞见则记录知乎检索和 DeepSeek 调研情况，不要求记录 Wiki 查询。
5. **⚠️ 强制步骤（不可跳过）：读取播客选题历史档案**。使用 Read 工具读取 `~/.daily-ai-news/history/podcast_history.md`（不存在则创建空档案）。该文件是跨栏目和跨运行模式的去重依据。
   - 提取近 7 天内**开源解读**已选入的项目列表（含主题标签）
   - 提取近 7 天内**每日精选**已选入的新闻标题列表
   - 提取近 7 天内**行业洞见**已深度解读的观点列表
   - **主题标签统计**：汇总近 7 天内出现 ≥2 次的主题标签（如 `security`、`token-optim`），标记为"主题饱和"
   - **开头手法记录**：提取近 7 天内三条播客各自用过的开头手法（如每日精选用过"头条先行""冲突对立"，开源解读用过"痛点引入"，行业洞见用过"大问题"），供 Phase 2 脚本生成时执行"7 天轮换约束"，下一期必须避开已用的手法

6. **输出连续性简报**：
   - 日报套餐写入 `topic_selection_{date}.md` 附录。
   - 独立行业洞见写入 `industry_topic_selection_{date}.md` 的历史去重部分。

   内容按本轮模式裁剪：
   - **知识库查询记录**：逐一列出查询了哪些目录/文件、查询结果是否为空
   - **播客历史档案查询记录**：列出 podcast_history.md 中近 7 天已选入的项目/新闻/观点清单 + 主题饱和标签
   - **本周已深度覆盖的话题**：列出近期反复出现的主题，标记为"不建议重复报道"（基于 daily/ 页面和 podcast_history.md 双重查询结果）
   - **今日新出现的信号**：日报套餐看日报；行业洞见看知乎新问题、新高赞回答和新增外部证据
   - **可延续的叙事线索**：识别可以"第四集"式的持续追踪故事线（如 Anthropic 融资进度、OpenAI 模型迭代、某开源项目周变化等）
   - **历史上下文**：日报套餐使用 Wiki；行业洞见使用此前行业洞见记录和相关外部来源

```
输出目录结构：
{date}/podcast/
├── topic_selection_{date}.md          # 日报套餐选题判断（日报驱动栏目）
├── industry_topic_selection_{date}.md # 独立行业洞见选题判断（不依赖日报）
├── research_supplement_industry_{date}.md # 行业洞见外部调研与来源分级
├── knowledge_audit_{date}.md          # 知识库查询审计记录（内部文件，不上传）
├── script_daily_brief_{date}.md       # 每日精选脚本
├── script_opensource_{date}.md        # 开源解读脚本
├── script_industry_trends_{date}.md   # 行业洞见脚本
├── config.json                        # 本轮 1-3 条播客的元数据配置
├── cover_daily_brief_{date}.png       # 每日精选封面图（2048×2048）
├── cover_opensource_{date}.png        # 开源解读封面图（2048×2048）
├── cover_industry_trends_{date}.png   # 行业洞见封面图（2048×2048）
├── daily_brief_{date}.mp3             # 每日精选音频
├── opensource_{date}.mp3              # 开源解读音频
└── industry_trends_{date}.mp3         # 行业洞见音频
```

### Phase 1: 选题判断

**⚠️ 三栏通用内容硬排除（每日精选、开源解读、行业洞见全部适用）**：

只排除以下两类内容：

1. **Agent 安全**：以智能体运行边界、沙箱隔离、权限与身份、提示注入、工具投毒、供应链攻击、越权执行、红队攻防为主要议题。
2. **漏洞**：以漏洞发现、复现、利用、披露、补丁、CVE、代码扫描或攻击事件为主要议题。

不要扩大解释。隐私、监管、合规、诈骗、内容安全、可靠性、模型对齐等话题，只有在核心议题实际属于上述两类时才排除，否则仍可正常入选。

1. **日报套餐**：加载 `references/content-matrix.md` 和 `references/topic-selection.md`。
2. **行业洞见**：完整读取 `references/industry-research.md` 和 `references/theory-support.md`。行业洞见不分析日报模块，不使用日报观点作为选题入口。
3. **日报驱动栏目**参考 Phase 0 连续性简报，并应用：
   - **新鲜度优先**：优先选取本周首次出现的话题；已被连续多天报道的话题降权
   - **连续性叙事**：对持续演进的话题（如某公司融资、某模型迭代），选取当日最新进展，脚本中可引用知识库中的前情提要（"上周二我们聊到 XX 刚融完 B 轮，今天它的 C 轮已经到账了"）
   - **避免"冷重启"**：不假设听众第一次听，引用知识库中的历史上下文时，用自然的方式带出背景
   - 行业洞见用知乎热度、外部证据和播客历史做连续性与去重，不读取日报。
4. 日报套餐逐模块分析日报内容；独立行业洞见执行 `references/industry-research.md` 的知乎发现、候选评分和外部研究。
5. **⚠️ 播客历史去重硬规则（强制执行）**：
   - **项目级去重**：对照 podcast_history.md 近 7 天已选入的开源项目清单，**任何已出现的项目一律不得再次入选开源解读**。若日报当日候选项目中有历史命中，必须替换为未覆盖项目，并在 topic_selection 文件中记录"❌ {项目} — 近 7 天已在 {日期} 选入，已替换"
   - **新闻级去重**：对照 podcast_history.md 近 7 天已选入的每日精选新闻清单，**标题实质相同的新闻不得再次入选**。如当日某新闻有重大进展（如融资轮次升级、产品正式发布），可作为"故事线延续"引用，但标题应反映最新进展，不得与历史条目完全相同
   - **主题级去重**：统计当日候选项目的主题标签，若某主题标签在近 7 天内已出现 ≥1 次，则该主题下的项目降权；若已出现 ≥2 次（标记为"主题饱和"），则**同主题项目原则上不再入选**，除非该项目有显著差异化亮点
   - **dedup_check 输出（强制）**：在 topic_selection 文件的开源解读章节末尾，必须输出一张去重检查表，格式如下：
     ```markdown
     ### 去重检查表（dedup_check）
     | 候选项目 | 历史命中？ | 处理 |
     |---------|-----------|------|
     | xxx/yyy | 7/3 已选入 | ❌ 替换为 zzz |
     | aaa/bbb | 无 | ✅ 入选 |
     ```
6. 生成选题文件：
  - 日报套餐写 `topic_selection_{date}.md`，包含每日精选、开源解读和行业洞见。
  - 独立行业洞见写 `industry_topic_selection_{date}.md`，包含至少 3 个候选、知乎热度、五维评分、最终判断和来源计划。
  - 行业洞见候选必须来自知乎 AI 大众热点，再用至少 3 条外部可信来源核验；Agent 安全与漏洞题默认排除。
7. 同组生成时确保 **三条播客之间零内容重叠**；单独生成行业洞见时只与近 7 天行业洞见记录去重。

### Phase 2: 脚本生成 + 元数据配置

**并行约束**：同组生成多条脚本时，把相互独立的脚本任务并行执行；只生成独立行业洞见时直接完成单条，不为了“凑并行”生成无关栏目。

**每个 Agent 只读自己那一个模块文件**（渐进式披露：不要把一个栏目的文风和规则套到另一个栏目上）。

| 脚本 | 模块文件（完整读取） | 格式参考 |
| --- | --- | --- |
| 每日精选 | `modules/daily-brief.md` | 双人联播 `A:`/`B:` + `[情感描述]` 情感标签 + `===` 分隔条目 |
| 开源解读 | `modules/opensource.md` | 单人播报 + `[情感描述]` 情感标签 |
| 行业洞见 | `modules/industry-insights.md` | 单人播报 + `[情感描述]` 情感标签 |

每条脚本的生成流程（**v2：Gemini 起稿 + 执行 LLM 微调**，2026-11-24 起）：
1. 读取对应的模块文件（只读自己那一个）
2. 读取选题判断结果中该播客的分配内容
3. 加载本研究上下文：
   - 每日精选、开源解读：按模块要求查询 DailyAINewsWiki。
   - 行业洞见：读取 `industry_topic_selection_{date}.md`、`research_supplement_industry_{date}.md`、`source_brief_{date}.md`。不读取 AI 日报，不把 Wiki 日报页作为前置条件。

   各模块要查什么，见对应模块文件的「生成前的知识与库查询」一节。

   > **验证检查点**：每条脚本生成后，必须将知识库或 DeepSeek 搜索执行情况写入独立审计文件 `knowledge_audit_{date}.md`（**不要**写入脚本文件本身，否则审计文本会被 TTS 朗读或出现在飞书文档中）。格式如下：
   > ```markdown
   > ## {播客类型} 研究查询审计
   > - wiki/entities/ (org): ✅ 已查询 | 匹配: OpenAI, Anthropic | 无匹配: Perplexity
   > - wiki/entities/ (person): ✅ 已查询 | 匹配: Sam Altman | 无匹配: Dario Amodei
   > - wiki/sources/: ✅ 已查询 | 读取: daily-2026-05-24, daily-2026-05-25
   > - wiki/synthesis/: ✅ 已查询 | 结果: 为空
   > - DeepSeek 调研（行业洞见专用）: ✅ Search 7 条 / Fetch 5 条 | 主题: 校招数据、初级岗位、学徒期、政策原文、反证
   > - 来源质量: ✅ A 级 2 条 / B 级 3 条 / C 级 1 条 | 待核验: 1 条
   > - 知乎热度: ✅ 357 万浏览 / 3378 关注 / 1163 回答
   > - 母文文件: ✅ source_brief_{date}.md 已生成（{N} 条佐证）
   > - 大纲文件: ✅ outline_{date}.md 已生成（选定结构: {A/B/C/D/E/F}）
   > ```
   > 行业洞见不使用 `wiki/sources/` 这一行；改为记录知乎热度、DeepSeek Search/Fetch 数量、来源等级、反证和待核验项。
   > 本轮生成的脚本共用一个审计文件，每条播客一个章节。此文件仅用于内部验证，不上传到飞书或小宇宙。

4. **Phase 2A（Gemini 起稿，每日精选与开源解读适用）**：完整读取 `references/gemini-writing.md`，按其中「系统提示词模板 A / B」构造该栏目系统提示词，组装用户内容（选题清单+素材要点+wiki 衔接+标题主角+开头手法），调用 `gemini_call.py` 生成初稿并存档到 `{date}/podcast/.gemini/`。Gemini 只负责"说话的方式"，事实边界以日报素材为准。
5. **Phase 2B（执行 LLM 微调，强制）**：按 `references/gemini-writing.md` 的「Phase 2B 微调清单」逐条修订 Gemini 初稿：事实边界核对、声纹达标、情感标签、数字单位、格式合规、受众钩子与趣味抽查。完成后写入 `script_{type}_{date}.md`。
6. 行业洞见不适用本两段式（其 Gemini 流程见 industry-insight-podcast 的 Phase 5），仍按自己的母文→大纲→逐字稿流程执行，写入 `script_{type}_{date}.md`。

#### Phase 2.5: 生成 config.json

本轮请求的脚本全部完成后，立即生成 `config.json`。`podcasts` 允许 1-3 条：独立行业洞见只有一条 `industry_trends`；日报套餐可包含两条或三条。

**加载** `references/config-schema.md` 获取 config.json 的完整结构定义。

config.json 生成流程：

1. **为每条播客确定元数据**：
  - `title`（标题）：
    - **每日精选**：使用「头条新闻法」（15-20 字，信息完整优先）。**规则见 `modules/daily-brief.md`**
    - **开源解读**：使用「单项目标题法」（15-20 字，必须点名项目）。**规则见 `modules/opensource.md`**
    - **行业洞见**：有人物原话时使用「人物:观点」，公共话题使用「话题:判断」，原标题视觉宽度 ≤ 20。**规则见 `modules/industry-insights.md`**

    > 三个标题法各有自检清单，写标题前先读对应模块的标题章节，不要凭记忆写。
  - `description`（内容简介）：Markdown 格式，150-300 字，提炼脚本核心内容和关键观点，适合作为播客平台展示文案。**不要手写 BGM 署名**，`finalize_podcast.py` 会给本轮播客自动追加 CC BY 4.0 署名行
  - `audio.path`、`cover.path`：写 `~` 或绝对路径都可以，`finalize_podcast.py` 会统一展开成绝对路径
  - `audio.size`、`audio.duration_seconds`、`audio.duration_human`、`audio.bitrate`、`cover.size`、`cover.dimensions`：本阶段一律填 `null`，Phase 3C 由 `finalize_podcast.py` 统一回填，**不要手工用 `ls`/`ffprobe` 取值**

2. **封面图数据**：为每条播客准备封面 HTML 模板注入数据
  - `seriesTag`（系列中文名）：每日精选→"每日精选"，开源解读→"开源解读"，行业洞见→"行业洞见"
  - `seriesEn`（系列英文标签）：每日精选→"DAILY BRIEF"，开源解读→"OPEN SOURCE"，行业洞见→"INDUSTRY INSIGHTS"
  - `label`（头条标签）：每日精选→"头 版"，开源解读→"开 源"，行业洞见→"洞 见"
  - `hit1`/`hit2`/`hit3`（核心新闻 1-3 条）：每条不超过 15 字，从脚本内容中选取最核心的新闻标题
  - 封面通过 HTML 模板 + Playwright 截图生成，无需图片提示词

4. **config.json 示例结构**（在 Phase 2.5 阶段，音频和封面相关的 size/format/duration 字段先填 `null`，Phase 3 完成后回填）：

```json
{
  "version": "1.0",
  "date": "2026-05-17",
  "source": "~/.daily-ai-news/data/2026-05-17/ai_news_2026-05-17.md",
  "podcasts": [
    {
      "type": "daily_brief",
      "title": "15-20字的具体标题（头条新闻法/单项目标题法）",
      "description": "Markdown格式的内容简介\n\n## 核心话题\n\n- 话题1简介\n- 话题2简介\n\n## 关键观点\n\n观点摘要...",
      "script_path": "~/.daily-ai-news/data/2026-05-17/podcast/script_daily_brief_2026-05-17.md",
      "audio": {
        "path": "~/.daily-ai-news/data/2026-05-17/podcast/daily_brief_2026-05-17.mp3",
        "size": null,
        "format": "mp3",
        "duration_seconds": null,
        "duration_human": null,
        "bitrate": "96kbps"
      },
      "cover": {
        "path": "~/.daily-ai-news/data/2026-05-17/podcast/cover_daily_brief_2026-05-17.png",
        "template": "cover_template.html",
        "data": {
          "seriesTag": "每日精选",
          "seriesEn": "DAILY BRIEF",
          "label": "头 版",
          "hit1": "不超过15字的核心新闻1",
          "hit2": "不超过15字的核心新闻2",
          "hit3": "不超过15字的核心新闻3"
        },
        "size": null,
        "format": "png",
        "dimensions": "2048x2048"
      }
    }
  ]
}
```

5. **写入 config.json** 到输出目录

**独立行业洞见的顶层 source**：填写 `research_supplement_industry_{date}.md` 或 `source_brief_{date}.md` 的路径，不填 AI 日报。日报套餐中的行业洞见仍使用自己的研究文件作为脚本依据，日报只服务每日精选和开源解读。

### Phase 2.6: 脚本后处理（de-AI 润色 → 标签 → 数字 → **口播校验** → 覆盖写入）

本轮请求的脚本生成完毕后，**强制依次执行 2.6A→2.6E**，不允许跳过任何一步。**2.6D 口播逐字稿校验未 PASS（硬指标）之前，禁止进入 Phase 3 录音。**

#### 2.6A: de-AI-writing 去 AI 味润色

使用 `de-AI-writing` Skill 对每条脚本进行保真改写。核心处理项目：

1. **清理二分对照壳**：`不是 A 而是 B`、`不在于 A 而在于 B`、`一半在 A 一半在 B` 全文最多保留 1 处
2. **清理协作口吻**：`我先来看`、`下面我们`、`一条一条来看`、`接下来我们聊` 等
3. **清理路标词**：`更关键`、`换句话说`、`值得注意的是`、`与此同时` 全文合计不超过 2 次
4. **清理讲义动作**：`拆一拆`、`盘一盘`、`聊一聊`、`说白了`、`划重点`
5. **打破段落同构**：避免连续多段都是"观点句 + 解释 + 总结"结构，部分段尾停在事实或引语上
6. **清理教程腔二人称**：禁用套话"你会发现/你能用/你试试"；**口播对话人称「你/我们/我」必须保留**（见 2.6D），不要为去 AI 味把人称一起删掉
7. **段尾收束多样化**：不要每段都以抽象结论收尾，允许停在事实、数据、引语、具体后果上

**执行方式**：加载 `de-AI-writing` Skill 的保真改写规则，依次对本轮每条脚本执行润色。保留原意、信息厚度和核心判断，不新增事实、案例、数据、结论。

#### 2.6B: 情感标签修正

逐段检查每条脚本的情感标签，执行以下修正：

1. **禁用语速控制类标签（强制）**：`[放慢语速]`、`[加快语速]`、`[放慢]`、`[加快]`、`[提速]`、`[减速]` 及任何含"语速/放慢/加快/提速/减速"字样的方括号标签一律删除。节奏感由文字本身的标点和断句承担（逗号轻顿、句号停顿、独立成段呼吸），不靠括号指令注入
2. **情感流畅度检查**：相邻两段的情感标签之间情绪过渡要自然，不能从 `[严肃认真地]` 突然跳到 `[热情欢快地]`（如确需转折，中间加一段中性缓冲如 `[平静地]`）
3. **标签去重**：同一标签全文不超过 3 次，相邻两段不用同一标签
4. **条目内单一主持校验（每日精选专属，强制）**：检查每个 `===` 区块（首块开场、末块收尾除外）内是否只有一种前缀。执行

   ```bash
   python3 ~/.codex/skills/ai-daily-podcast/scripts/check_broadcast_speakers.py {script_daily_brief_path}
   ```

   必须输出 `PASS`。出现 `FAIL` 说明一条新闻被拆成了两人对话，必须把另一位主持的话并入本条主持的口吻（或删掉重复信息），改到 PASS 才能进 Phase 3 录音

#### 2.6C: 数字与单位转换

对每条脚本执行以下强制性转换（违反任意一条视作不合格）：

**日期与时间**（禁止使用斜杠、横杠、冒号）：
- 年月日/日期 ➔ 纯中文汉字：`7/20` 或 `7-20` ➔ `7月20日`（或 `七月二十日`）；`2024/08/15` ➔ `二零二四年八月十五日`
- 时刻/时间段 ➔ 中文口语：`14:00` ➔ `下午2点`；`08:30:00` ➔ `早上8点30分`
- 音频时长：`2:30` ➔ `2分30秒`

**度量衡与技术单位**（英文单位必须汉化）：
- 像素：`10px` ➔ `10像素`
- 重量：`50kg` ➔ `50公斤`；`50g` ➔ `50克`
- 长度/距离：`100m` ➔ `100米`；`5km` ➔ `5公里`；`3cm` ➔ `3厘米`
- 温度：`37℃` 或 `37°C` ➔ `37摄氏度`
- 数据存储：`100MB` ➔ `100兆`；`1GB` ➔ `1 G B`
- 货币与符号：`$100` ➔ `100美元`；`¥50` ➔ `50元`；`10%` ➔ `百分之十`

**年份与数值区分**（读法差异）：
- 年份四位数：必须逐位念，写为中文数字 — `2024年` ➔ `二零二四年`（避免 TTS 念成"两千零二十四"）；`90年代` ➔ `九十年代`
- 数量/金额：保留自然口语数字或转换为汉字 — `2024个` ➔ `两千零二十四个`（或保留 `2024个`）；"2"在量词前读"两"：`2亿` ➔ `两亿`、`2次` ➔ `两次`

**分数、小数与比例**：
- 分数：`1/2` ➔ `二分之一`；`3/4` ➔ `四分之三`
- 小数：`3.14` ➔ `3点14`（或 `三点一四`）
- 比例/比分：`1:3` ➔ `1比3`；`3:0 获胜` ➔ `3比0获胜`

**电话号码与编号**：
- 数字逐位读出，"1"通常读"幺"：`1380000` ➔ `1 3 8 0 0 0 0`（数字间加空格断句，或写为 `一三八零零零零`）

#### 2.6D: 口播逐字稿校验（本轮生成的全部脚本适用，强制，录音前门禁）

> **适用范围**：三条各有自己的口语化规范和人称密度线，**不要互相套用**。语气词 / TTS 禁区标准三栏目相同（2026-10-13）。

本步在 2.6A–C 改完稿之后、**2.6E 覆盖写入与 Phase 3 录音之前**执行。生成完口播逐字稿必须校验；不过检不得进火山 TTS。

**1. 必读**：`references/voice-samples.md` + 对应模块「口语化生成规范」  
（每日精选 `modules/daily-brief.md` / 开源解读 `modules/opensource.md` / 行业洞见 `modules/industry-insights.md`）

**2. 本轮每条脚本分别跑检查**（`--type` 不可省、不可串用）：

```bash
python3 ~/.codex/skills/ai-daily-podcast/scripts/check_oral_voice.py --type daily_brief {script_daily_brief_path}
python3 ~/.codex/skills/ai-daily-podcast/scripts/check_oral_voice.py --type opensource {script_opensource_path}
python3 ~/.codex/skills/ai-daily-podcast/scripts/check_oral_voice.py --type industry {script_industry_path}
```

**3. 硬指标（FAIL → 退出码 1 → 必须改稿重跑，禁止进 Phase 3）**

| 栏目 | 人称词 / 千字 | 问句 / 千字 | 书面连接词 | 平均句长 |
| --- | --- | --- | --- | --- |
| 每日精选 | ≥ 20 | ≥ 2.5 | ≤ 2 | 8–18 |
| 开源解读 | ≥ 25 | ≥ 2.5 | ≤ 2 | 8–18 |
| 行业洞见 | ≥ 25 | ≥ 2.5 | ≤ 2 | 8–18 |

FAIL 时回去补「人在场」：判断句用「我/我们/你」起头，加真问句。**不要**往专名和数字后塞语气词凑数，也不要把句子拆短当解法。

**4. 语气词密度（仅 WARN）与 TTS 禁区（硬 FAIL）**

- 句尾语气词密度：软建议约 **2–5/千字，宁少勿滥**；不足或 >8 只 WARN（不单独改退出码）
- **TTS 禁区（硬 FAIL）**：专有名词后、数字/评分后、纯事实陈述句尾出现 啊/呢/吧/嘛/呀 → 退出码 1，必须清掉后重跑；问句里的语气词可留

**5. 通过标准**

- 本轮生成的每条脚本都须退出码 0（硬指标 PASS，且 TTS 禁区无命中）
- 若仅有语气词密度 WARN（无禁区）：可覆盖写入并录音，但优先压到约 2–5
- 每日精选另须 `check_broadcast_speakers.py` PASS（见 2.6B）
- 全部通过后才允许 2.6E 覆盖写入，并进入 Phase 3

参照（2026-09-28）：真实播客人称/问句远高于我们当时的稿；句长本来就对，缺的是说话的人。2026-10-13 起语气词改为软建议，口语主指标是人称与真问句。

#### 2.6E: 覆盖写入

处理完成后，用处理后的内容覆盖本轮生成的脚本文件。

### Phase 3: MP3 + 封面图生成

**前置条件（强制）**：Phase 2.6D 口播逐字稿校验本轮每条脚本均 PASS，TTS 禁区无命中（硬 FAIL 项已清）；若包含每日精选，`check_broadcast_speakers.py` 必须 PASS。未满足则退回 2.6 改稿，禁止开录。

本阶段只为请求的栏目生成 MP3 和封面。独立行业洞见只有 1 个 MP3 和 1 张封面；日报套餐按实际栏目数量执行。

#### 3A: MP3 生成

**并行约束**：同组有多条 MP3 时并行生成；独立行业洞见直接生成单条。

**每日精选（双人联播）**：使用联播脚本，A/B 两条音色按条目交替，条目之间自动插入翻页音效：

```bash
source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_news_broadcast.py \
  --content-file {script_path} \
  --output-file {output_mp3_path} \
  --male-voice zh_male_wennuanahu_uranus_bigtts \
  --female-voice zh_female_vv_uranus_bigtts
```

> 脚本稿必须是 `A:` / `B:` 行、条目之间单独一行的 `===`。**切换点只能在 `===` 上**：每个新闻区块由一位主持从事实读到点评读到过渡，另一位在这一条里一行都不出（开场与收尾区块除外，那里要放品牌口播）。`generate_news_broadcast.py` 会在合成前做这项校验，发现条目内混用 A/B 就报错拒绝录制，改稿后再跑，或明确用 `--allow-multi-speaker-items` 沿用旧版混播稿。翻页音效默认 −8dB（`--sfx-volume` 可调）；改稿后用 `--work-dir {dir} --reuse` 只重录内容变化的条目（缓存键是文本哈希）。

**开源解读（单人）**：使用单人 TTS 脚本（火山引擎 Seed-TTS，支持 `[情感标签]`）：

```bash
source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_tts_solo.py \
  --content-file {script_path} \
  --output-file {output_mp3_path}
```

> 开源解读读取 `VOLCENGINE_TTS_SPEAKER`，也可用 `--speaker` 覆盖。

**行业洞见（单人）**：必须显式指定刘飞音色，禁止依赖环境变量：

```bash
source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_tts_solo.py \
  --content-file {script_path} \
  --output-file {output_mp3_path} \
  --speaker zh_male_liufei_uranus_bigtts
```

> 行业洞见的固定音色是 `zh_male_liufei_uranus_bigtts`。即使 `VOLCENGINE_TTS_SPEAKER` 仍配置为其他音色，行业洞见也必须通过 `--speaker` 使用刘飞。
> 脚本还有程序级兜底：当 `--content-file` 的文件名包含 `industry_trends` 时，即使漏传 `--speaker`，也会自动使用刘飞；显式 `--speaker` 仍优先。

> 单人脚本的第一行 H1 标题不会进音频：预处理器整行丢弃它，标题只进 `config.json` 和封面（联播脚本对 `#` 行同样跳过）。写脚本时不必为「标题会不会被念出来」做额外处理。

#### 3A.1: 生效期内的栏目推广（可选，必须在 3C 回填前完成）

推广配置优先读取 `assets/promotions/{date}.json`，不存在时回退到 `assets/promotions/default.json`。配置在 `active_from` 到 `active_until` 之间生效；本轮 MP3 生成完成后、`finalize_podcast.py` 回填前执行：

```bash
python3 ~/.codex/skills/ai-daily-podcast/scripts/apply_podcast_promotion.py --date {date}
```

- 脚本读取配置并解析相对路径，内部复用 `append_host_clip.py`，不维护第二套拼接逻辑。
- 推广配置可以列出三条播客；脚本只处理当前 `config.json` 中实际存在的栏目，因此独立行业洞见单集不会因缺少其他两栏而失败。
- 拼接脚本必须幂等；同一日期、同一类型重跑时依靠标记文件跳过。
- 推广音频必须已完成响度、起止点和内容回读校验。原声来源、截取区间、转写和授权说明写在推广目录的 `metadata.json`。
- 拼接完成后立即运行 `finalize_podcast.py`（Phase 3C），确保 `config.json` 与飞书、小宇宙拿到的是拼接后的真实时长。
- `default.json` 的「AI 播客全流程制作 Skill 开源仓库」（本仓库）推广从 2026-11-26 起长期生效，追加到每日精选、开源解读、行业洞见三条播客。资产目录为 `assets/opensource-promo-2026-11-26/`（纯 AI TTS 合成，无授权素材，随库分发）。此前的《李自在AI实战》推广（2026-10-27 起）已于 2026-11-26 永久下线，旧资产目录未随库分发。

**片头/片尾 BGM（三条共用，脚本内置默认值，无需传参）**：每日精选、开源解读、行业洞见用同一首固定曲目、同一段切片，片头 5 秒、片尾 8 秒，三条听感一致。默认值集中在 `scripts/podcast_audio.py`，两个渲染脚本共用同一套实现和参数，改一处三条同时生效。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--intro-music` | `/Users/louie/Music/BGM_Library/05_Inspired_Cinematic.mp3` | 固定片头/片尾曲（钢琴+弦乐，CC BY 4.0） |
| `--intro-music-offset` | `84` | 取曲中能量最饱满、无静音空洞的片段起点 |
| `--intro-music-duration` | `5` | 片头纯音乐时长（人声前） |
| `--intro-music-volume` | `-11` dB | 实测与主持人声压平（片头音乐均值 −22.7dB） |
| `--outro-music-duration` | `8` | 片尾尾奏（1.5s 渐入 → 保持 → 3s 渐出） |
| `--no-music` | — | 临时关闭片头片尾音乐（两条脚本都支持） |

> **署名义务（CC BY 4.0）**：所用曲目来自 Kevin MacLeod（incompetech.com），可商用但必须署名。署名行由 Phase 3C 的 `finalize_podcast.py` 自动追加到本轮每条播客的 `description` 末尾（`Music: "Inspired" by Kevin MacLeod (incompetech.com), CC BY 4.0`），脚本生成侧不需要也不应该手写这一行。

**完整三栏并行模板（仅本轮确实生成三条时使用）**：

```
Bash(run_in_background=true): source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_news_broadcast.py --content-file script_daily_brief_...md --output-file daily_brief_....mp3 --female-voice zh_female_vv_uranus_bigtts
Bash(run_in_background=true): source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_tts_solo.py --content-file script_opensource_...md --output-file opensource_....mp3
Bash(run_in_background=true): source ~/.zshrc && python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_tts_solo.py --content-file script_industry_trends_...md --output-file industry_trends_....mp3
```

#### 3B: 封面图生成（HTML 模板 + Playwright 截图）

**并行约束**：同组有多张封面时与 MP3 并行生成；独立行业洞见只生成一张行业洞见封面。

使用技能内置的 HTML 封面模板 `templates/cover_template.html`（复古中文报纸风格）+ Playwright 截图脚本 `scripts/generate_covers.py` 生成 2048×2048 PNG 封面。

**封面配色方案**（模板自动根据 `seriesTag` 切换）：

| 系列 | Badge 背景色 | Badge 文字色 |
| --- | --- | --- |
| 每日精选 | 墨黑 `#0d0d0d` | 米白 `#f4edd8` |
| 开源解读 | 深靛蓝 `#1b2a4a` | 暖白 `#e8e4d9` |
| 行业洞见 | 深赭棕 `#4a3222` | 米色 `#e8dcc8` |

**执行命令**：

```bash
/Users/louie/.local/pipx/venvs/agent-reach/bin/python3 \
  ~/.codex/skills/ai-daily-podcast/scripts/generate_covers.py \
  --date {date} \
  --output-dir {output_dir} \
  --data '{JSON数组字符串}'
```

其中 `--data` 参数为一个 JSON 数组，每条播客的封面数据结构：

```json
[
  {
    "type": "daily_brief",
    "seriesTag": "每日精选",
    "seriesEn": "DAILY BRIEF",
    "label": "头 版",
    "hit1": "不超过15字的核心新闻1",
    "hit2": "不超过15字的核心新闻2",
    "hit3": "不超过15字的核心新闻3"
  },
  ...
]
```

> **注**：封面数据已写入 config.json 的 `cover.data` 字段，可直接从 config.json 提取传给脚本。

**完整三栏并行执行模板（3 个 MP3 + 1 组封面，仅三栏全部生成时使用）**：

```
Bash(run_in_background=true): source ~/.zshrc && python3 ... generate_news_broadcast.py --content-file script_daily_brief_...md --output-file daily_brief_....mp3 --female-voice zh_female_vv_uranus_bigtts
Bash(run_in_background=true): source ~/.zshrc && python3 ... generate_tts_solo.py --content-file script_opensource_...md --output-file opensource_....mp3
Bash(run_in_background=true): source ~/.zshrc && python3 ... generate_tts_solo.py --content-file script_industry_trends_...md --output-file industry_trends_....mp3
Bash(run_in_background=true): /Users/louie/.local/pipx/venvs/agent-reach/bin/python3 ~/.codex/skills/ai-daily-podcast/scripts/generate_covers.py --date {date} --output-dir {output_dir} --data '[...]'
```

#### 3C: 回填 config.json

所有 MP3 和封面图生成完成后，跑一条命令即可（幂等，可重复执行）：

```bash
python3 ~/.codex/skills/ai-daily-podcast/scripts/finalize_podcast.py --date {date}
```

该脚本负责四件事，不再需要手工 `ls`/`ffprobe`/改 JSON：

1. 把 `audio.path`、`cover.path` 里的 `~` 展开成绝对路径（小宇宙上传脚本不展开 `~`）
2. 回填 `audio.size` / `duration_seconds` / `duration_human` / `bitrate`，封面回填 `size` / `dimensions`（直接读 PNG 头，不依赖尺寸工具）
3. 给本轮每条播客的 `description` 各追加 CC BY 4.0 BGM 署名（已存在则不重复追加）
4. 校验：文件缺失、封面不是 2048×2048、字段仍为空，任一命中就列出问题并以退出码 1 结束，**此时禁止上传**

### Phase 4: 交付

1. 列出所有生成文件的摘要表（包含 MP3、封面图、config.json）
2. 确认 Phase 3C 的 `finalize_podcast.py` 退出码为 0（这一步同时保证 config.json 无空字段、封面尺寸正确、BGM 署名已写入）
3. **⚠️ 强制步骤（不可跳过）：追加写入播客选题历史档案**。使用 Edit 工具在 `~/.daily-ai-news/history/podcast_history.md` 的**顶部**（`---` 分隔线之下）插入当日记录，格式如下：
   ```markdown
   ## {YYYY-MM-DD}

   ### 开源解读（{N} 个）
   | 项目 | 主题标签 | 摘要 |
   |------|---------|------|
   | owner/repo | tag1, tag2 | 一句话描述 |

   **开头手法**：{当日选用的开头手法名称，如"痛点引入"/"当日最强项目"/"趋势观察"/"反直觉判断"/"独立开发者视角"}

   ### 每日精选（{N} 条）
   | 新闻 | 模块来源 |
   |------|---------|
   | 新闻标题 | 来源模块 |

   **开头手法**：{当日选用的开头手法名称，如"头条先行"/"冲突对立"/"趋势钩子"/"场景代入"/"反常信号"}

   ### 行业洞见
   | 观点 | 来源 |
   |------|------|
   | 核心观点 | 来源 |

   **开头手法**：{当日选用的开头手法名称，如"大问题"/"具体场景"/"反直觉数据"/"日常切入"}

   ---
   ```
   - 主题标签必须为英文 kebab-case，最多 3 个，用于主题级去重
   - **开头手法字段是"7 天轮换约束"的执行依据**，Phase 1 选题判断时必须先查近 7 天各播客用过的开头手法，避开重复
   - 独立行业洞见只追加 `行业洞见` 章节，不补写未生成的每日精选或开源解读
   - 若档案超过 30 天的记录，可在月初清理时将旧记录移至 `podcast_archive.md`
4. 交付本轮实际生成的文件。独立行业洞见至少交付 MP3、封面、config、研究对象选择、补充调研、母文、大纲和脚本
5. 更新工作记忆

## Writing Rules（适用于本轮生成的全部脚本）

- 口语化表达，句子简短，单句不超过 25 字为佳
- 不用 emoji、表格、代码块、URL
- 所有事实必须来自本轮源稿或行业洞见研究文件，不编造
- 话题之间用自然过渡，不用"接下来我们聊..."这种机械过渡
- **情感标签**（全部播客）：必须使用 `[情感描述] 文本` 格式（火山引擎 TTS 情感标签），每段至少 2-3 个情感变化
- **开源解读 / 行业洞见（单人）**：观点要有明确立场，像一个人在电台里跟你认真分析
- **行业洞见音色（强制）**：`generate_tts_solo.py` 必须带 `--speaker zh_male_liufei_uranus_bigtts`；不得省略后回退到 `VOLCENGINE_TTS_SPEAKER`
- **语速标签禁令（强制）**：`[放慢语速]`、`[加快语速]`、`[放慢]`、`[加快]`、`[提速]`、`[减速]` 及任何含"语速/放慢/加快/提速/减速"字样的方括号标签一律禁用。节奏感由文字标点和断句承担（逗号轻顿、句号停顿、独立成段呼吸），不靠括号指令注入
- **数字与单位转换规则（强制，详见 Phase 2.6C）**：日期时间禁止斜杠/横杠/冒号（`7/20` ➔ `7月20日`）；英文单位必须汉化（`10px` ➔ `10像素`、`$100` ➔ `100美元`、`10%` ➔ `百分之十`）；年份四位数逐位念（`2024年` ➔ `二零二四年`）；"2"在量词前读"两"（`2亿` ➔ `两亿`）
- **脚本后处理（强制）**：本轮每条脚本生成后必须执行 Phase 2.6 全程 — (A) de-AI-writing → (B) 情感标签修正 → (C) 数字与单位转换 → **(D) 口播逐字稿校验（硬指标 PASS，含 TTS 禁区无命中）** → (E) 覆盖写入。**2.6D 未通过禁止进 Phase 3 录音**
- **口播逐字稿校验（三条全部适用，强制）**：写成"人在说话"，不是"念稿"。硬指标：每日精选人称 ≥ 20，开源/洞见人称 ≥ 25；问句 ≥ 2.5；书面连接词 ≤ 2；平均句长 8–18。语气词软建议约 2–5/千字（仅 WARN），遵守 TTS 禁区（专名/数字/事实句尾不加语气词）。写作前读 `references/voice-samples.md` 与对应模块规范；**生成后必须跑** `check_oral_voice.py --type {daily_brief|opensource|industry}`，硬 FAIL（含 TTS 禁区）未清之前不得录音。**不要把句子拆短当作解法，也不要堆语气词凑密度**。行业洞见另守：写作骨架（倒叙、三层论证）不许写进稿子当路标
- **连续性规则**：
  - 每日精选、开源解读必须查询 `/Users/louie/Documents/DailyAINewsWiki/`，从历史记录提取上下文。
  - 行业洞见必须查询 `podcast_history.md`、知乎和外部研究材料；不要求查询 Wiki 日报页，也不得引用 AI 日报。
  - 所有查询与来源审计写入独立审计文件，不写进脚本正文。
- **栏目专属写作规则见各模块文件**：每日精选的双人播报规则在 `modules/daily-brief.md`「双人播报规则」，开源解读的三档模板与诚实度约束在 `modules/opensource.md`，行业洞见的 01fish 观点体与金句菜单在 `modules/industry-insights.md`。本节只列三条共用规则

## 品牌口播（固定，每期必含）

每条播客脚本必须包含以下固定品牌口播，位置和内容不可更改：

### 开场品牌口播（脚本前两段）
> A: "欢迎收听**李自在AI日报**，我是李自在。"
> B: "我是肖然。"

每日精选是双人联播：A 是李自在（男声），B 是肖然（女声），肖然的名字只在开场出现这一次，后续条目不重复自我介绍。开源解读与行业洞见仍是单人播报，开场品牌口播由李自在一人说。

### 收尾交叉推荐（收尾品牌口播之前）
- 每日精选：推荐开源解读版 + 行业洞见版
- 开源解读：推荐每日精选版 + 行业洞见版
- 日报套餐中的行业洞见：推荐每日精选版 + 开源解读版
- 独立行业洞见单集：可以推荐“每日精选版”和“开源解读版”作为更多内容入口，但不要说“今天的热点/今天的开源项目”

### 收尾品牌口播（脚本最后一段）
日报套餐：

> "以上就是今天的全部内容。想看完整日报文字版，关注公众号**李自在AI**。觉得有用的话，帮我转发给做 AI 的朋友，我们明天见。"

独立行业洞见：

> "以上就是这期行业洞见的全部内容。想看更多 AI 文字内容，关注公众号**李自在AI**。觉得有用的话，帮我转发给关心 AI 的朋友，我们下期见。"

## Progressive Loading

为控制上下文大小，采用渐进式加载：

**第一层（栏目模块，最关键）**：`modules/` 下的三个文件是三条播客各自的完整规范。**生成哪一条，只读哪一个文件**，不要把三个模块一起读进来。

| 文件 | 何时加载 |
| --- | --- |
| `modules/daily-brief.md` | Phase 2 生成每日精选脚本时，**只读这一个模块** |
| `modules/opensource.md` | Phase 2 生成开源解读脚本时，**只读这一个模块** |
| `modules/industry-insights.md` | Phase 2 生成行业洞见脚本时，**只读这一个模块** |
| `~/.daily-ai-news/history/podcast_history.md` | Phase 0 初始化时，**去重核心数据源**，近 7 天播客已选入的项目/新闻/观点 |
| `/Users/louie/Documents/DailyAINewsWiki/index.md` | Phase 0 初始化时，了解知识库覆盖范围 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/sources/daily-*.md` | 日报套餐 Phase 0 初始化时，为每日精选/开源解读建立连续性基线 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/synthesis/` | 日报套餐 Phase 0；行业洞见可选，仅作背景 |
| `references/content-matrix.md` | Phase 1 选题判断时 |
| `references/topic-selection.md` | Phase 1 选题判断时 |
| `references/industry-research.md` | 生成行业洞见时，必须在选题前完整读取；日报套餐中的行业洞见也一样 |
| `references/theory-support.md` | 行业洞见母文阶段完整读取；社会行为、关系、消费、健康、内容和家庭题强制加入理论支持 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/entities/`（type: org/model/tool） | Phase 2 日报驱动栏目；行业洞见仅在确有历史背景价值时可选查询 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/entities/`（type: person） | Phase 2 日报驱动栏目；行业洞见仅在确有历史背景价值时可选查询 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/entities/`（type: model/tool） | Phase 2 开源解读脚本生成时，检索项目迭代记录 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/sources/daily-*.md` | Phase 2 每日精选/开源解读生成时衔接前后日报道 |
| `/Users/louie/Documents/DailyAINewsWiki/wiki/synthesis/` | Phase 2 日报驱动栏目；行业洞见可选 |
| `references/config-schema.md` | Phase 2.5 生成 config.json 时 |
| `references/gemini-writing.md` | Phase 2A/2B 生成每日精选与开源解读脚本时（完整读取；含两栏目系统提示词模板与微调清单） |

**不要**在 Skill 加载时一次性读取所有 modules 和 references 文件；也不要为了"保险"把三条的模块都读一遍。
