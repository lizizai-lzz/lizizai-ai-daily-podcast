---
name: industry-insight-podcast
description: 生成「李自在AI日报」行业洞见单集，支持两种选题模式：zhihu（默认，知乎大众 AI 热点选题，DeepSeek Search/Fetch 核验，必须理论支持，不依赖 AI 日报）和 dev（大咖言论版，从当天日报「观点与言论」模块选大咖原话观点，any-search 佐证 + DailyAINewsWiki 历史纵深，面向独立开发者）。两种模式共用 Gemini 大纲与逐字稿、刘飞音色配音、封面、成品校验和小宇宙定时发布，适用于单集制作与一周批量排期。
---

# Industry Insight Podcast — 独立行业洞见单集

## Profile（双轨制配置）

固定音色、目录约定、小宇宙节目 ID 等「李自在」品牌默认值，可被仓库 `config/profile.json` 覆盖；环境变量优先级更高（`PODCAST_SHOW_ID`、`XYZ_AUTH_FILE`、`PODCAST_SKILLS_ROOT`）。见仓库 `config/README.md`。

## 输出目标

只生产「李自在AI日报 | 行业洞见」这一条单人播客：

- 7 至 10 分钟
- 逐字稿去情感标签后 2000 至 3000 个汉字
- 面向普通消费者、上班族、家长、子女、学生和养宠人
- 单集只讲一个核心判断
- 默认排除 Agent 安全与漏洞两类核心主题，不扩大到隐私、监管、诈骗或内容安全
- 不读取 AI 日报，不依赖每日精选或开源解读

固定音色：

| 栏目 | 音色 |
| --- | --- |
| 行业洞见 | `zh_male_liufei_uranus_bigtts`（刘飞） |

## 运行模式（dev / zhihu）

每次运行前先确定模式。两种模式共用去重历史（`podcast_history.md` + `industry_topic_dedup_index.md`）、产物目录 `~/.daily-ai-news/data/{date}/industry_podcast/`、TTS、封面、上传与归档管线（Phase 0 去重与 Phase 5-9 完全一致），差异只在选题与写作规范：

| 维度 | zhihu（默认） | dev（大咖言论版） |
| --- | --- | --- |
| 选题来源 | 知乎大众 AI 热点（不读 AI 日报） | 当天日报「观点与言论」模块的大咖原话观点 |
| 写作规范模块 | `references/industry-insights.md` | `references/industry-insights-dev.md` |
| 受众 | 普通 AI 用户、职场人、学生、家长 | 独立开发者 / AI 创业者 |
| 标题格式 | 「人物:观点」或「话题:判断」 | 「人物:观点」唯一格式 |
| 佐证工具 | DeepSeek Search/Fetch + 来源 A/B/C/D 分级 | any-search 实时搜索（母文 ≥3 条佐证） |
| 理论支持（Phase 3） | 必须有 | 可选（有贴合理论时才加） |
| 产物差异 | 含 `industry_topic_selection` 与 `research_supplement` | 佐证并入 `source_brief_{date}.md`，不单写前两者 |
| 前置输入 | 无日报依赖 | 当天 `ai_news_{date}.md` 必须存在且可选出观点 |

**模式判定**：由调用方（自动化任务 prompt 或用户指令）显式指定；未指定时默认 zhihu。dev 模式下若日报缺失或「观点与言论」模块无可选观点（按模块的交叉提炼规则仍无），如实报告并停止，禁止改用知乎热点顶替。

dev 模式的选题（Phase 1）、佐证调研（Phase 2）、母文（Phase 4）、大纲与逐字稿写作规范全部以 `references/industry-insights-dev.md` 为准；Phase 5 调用 Gemini 时，系统提示词中的写作规范同样以该模块为准（01fish 观点输出体、6 种叙事结构、金句钉子段等）。

## 必需依赖

- `qiaomu-ds-search`（第三方，未随库分发，安装见 `docs/third-party.md`）：外部搜索、正文抓取、来源核验
- `agent-reach`（第三方，未随库分发，安装见 `docs/third-party.md`）：读取知乎公开搜索、问题和文章；登录墙或验证码必须如实记录
- `gemini-writer`（本仓库 `skills/` 自带）：生成大纲和逐字稿
- `volcengine-tts`（本仓库 `skills/` 自带）：提供底层 TTS 调用
- `xiaoyuzhou-upload`（本仓库 `skills/` 自带）：上传与定时发布

## 目录

默认产物目录：

```text
~/.daily-ai-news/data/{date}/industry_podcast/
├── industry_topic_selection_{date}.md
├── research_supplement_industry_{date}.md
├── source_brief_{date}.md
├── outline_{date}.md
├── script_industry_trends_{date}.md
├── config.json
├── cover_industry_trends_{date}.png
└── industry_trends_{date}.mp3
```

批量制作时，可额外生成：

- `industry_week_plan_{start}_to_{end}.md`
- `source_ledger_{start}_to_{end}.md`

## 渐进式加载

| 文件 | 何时读取 |
| --- | --- |
| `references/industry-research.md` | Phase 1 选题和 DeepSeek 调研前完整读取 |
| `references/industry-insights.md` | 生成选题、大纲、逐字稿或修改稿件前完整读取（zhihu 模式） |
| `references/industry-insights-dev.md` | **dev 模式**（大咖言论版）：选题、母文、大纲、逐字稿写作规范；完整读取并替代 `industry-insights.md` |
| `references/theory-support.md` | 母文阶段完整读取，理论与脚本检查时再次读取 |
| `references/voice-samples.md` | 写逐字稿前读取 |
| `references/gemini-writing.md` | 调用 Gemini 生成大纲和逐字稿前完整读取 |
| `references/publishing.md` | TTS、封面、成品校验、定时上传前完整读取 |
| `references/config-schema.md` | 生成 `config.json` 前读取 |
| `~/.daily-ai-news/history/podcast_history.md` | Phase 0 和选题前必读，用于近 7 天去重 |
| `~/.daily-ai-news/history/industry_topic_dedup_index.md` | Phase 0 和选题前必读，用于全历史主题族去重 |

## Workflow

### Phase 0：范围和去重

1. 确定本次是单集还是批量排期。
2. 单集需要目标日期；批量排期需要起止日期和每天数量。
3. 读取 `~/.daily-ai-news/history/industry_topic_dedup_index.md`，先排除历史已用主题族和硬拦截项。
4. 读取 `~/.daily-ai-news/history/podcast_history.md`，提取近 7 天行业洞见观点、主题和开头手法。
5. 用标题和关键词补扫 `~/.daily-ai-news/data/*/podcast/script_industry_trends_*.md`；旧标题只写“行业趋势 + 日期”时，打开对应 `source_brief_*.md` 核对。
6. 检查全部历史是否已做过相同问题、同一机制或高度相邻场景。相邻主题必须同时具备新事件、新证据、新机制和不同行动，缺一项不得选。
7. 记录知乎访问限制、历史去重结果和候选来源计划。

### Phase 1：选题

> **dev 模式**：跳过本节知乎步骤，完整读取 `references/industry-insights-dev.md` 并按其规则从当天日报「观点与言论」模块选题（`references/industry-research.md` 不读取，无知乎热度环节）。以下步骤仅适用 zhihu 模式。

1. 完整读取 `references/industry-research.md` 和 `references/industry-insights.md`。
2. 从知乎 AI 大众热点中找至少 3 个候选，优先工作、收入、教育、消费、家庭、医疗、学习和生活方式。
3. 记录标题、链接、可达的浏览量/关注数/回答数/近期高赞；不可见就写“不可见”，禁止估算。
4. 按大众相关性、知乎热度、论据强度、新鲜度和行动价值五维评分。
5. 选择不低于 7 分的最高分主题。
6. 不把知乎个人经历当统计事实；知乎只是需求信号。
7. 批量排期时先做候选池，再分配到不同日期，避免连续多天重复同一机制。

### Phase 2：补充调研和原文台账

> **dev 模式**：佐证调研按 `industry-insights-dev.md` 的 Phase 4 母文规则执行（any-search 拆子主题搜佐证，≥3 条），佐证台账并入 `source_brief_{date}.md`，不单写 `research_supplement`。以下步骤仅适用 zhihu 模式。

1. 围绕一个核心判断拆出 3 至 5 个研究子问题。
2. 用 `qiaomu-ds-search` 做互补查询，至少包含一条反证或替代解释。
3. 对政策、论文、官方统计和中心事实 Fetch 正文，不只依赖搜索摘要。
4. 每期至少 3 条外部可信来源，其中至少 1 条 A 级。
5. 来源分为 A/B/C/D；D 级知乎或营销内容不得提供逐字稿事实数据。
6. 单集写 `research_supplement_industry_{date}.md`。
7. 批量制作写总 `source_ledger_{start}_to_{end}.md`，列出所有原文链接、日期、样本、结论、等级和限制。
8. 明确相关性、因果、预测和单篇研究不可外推的边界。

### Phase 3：理论支持

> **dev 模式**：本 Phase 可选——母文素材中有能解释观点机制的理论时，按同样格式加入「## 理论支持」；没有则跳过，不强制。

1. 完整读取 `references/theory-support.md`。
2. 每期母文增加 `## 理论支持`：
   - 一个主理论
   - 一个竞争或补充解释
   - 原始论文、专著或权威综述链接
   - 理论能解释和不能解释的部分
   - 一句普通人能听懂的口播翻译
3. 理论只解释机制，不能代替数据，也不能给听众贴依恋类型、人格或心理疾病标签。
4. 理论与证据冲突时保留冲突，不强行让事实服从理论。

### Phase 4：母文

生成 `source_brief_{date}.md`，至少包含：

1. 核心判断
2. 知乎来源和热度限制
3. 3 至 5 个研究子问题
4. 支持、反驳、补充三类材料
5. 来源等级、样本口径和限制
6. 生活类比
7. 意外元素
8. 具体开头场景
9. 1 至 2 个行动
10. 理论支持
11. 原文链接表

母文后先给用户看选题和核心判断；用户要求直接继续时再进入写作。

### Phase 5：Gemini 大纲和逐字稿

1. 完整读取 `references/gemini-writing.md`。
2. 按 `gemini-writer` 流程构造系统提示词，并在调用 API 前展示给用户确认。
3. 上下文必须包含当期选题、母文、原文台账和理论支持。
4. 使用 Gemini 生成大纲和逐字稿；输出后拆分并保存：
   - `outline_{date}.md`
   - `script_industry_trends_{date}.md`
5. Gemini 不得新增母文外事实。若输出中有未经台账支持的细节，删除或降低表述强度。

### Phase 6：逐字稿门禁

按顺序执行：

1. 去 AI 味：清理二分对照壳、路标词、协作口吻和讲义动作。
2. 情感标签：相邻标签不重复，同一标签全文最多 2 次，禁用任何语速标签。
3. 数字和单位：日期、年份、百分比、金额适合中文口播。
4. 运行：

```bash
python3 scripts/check_oral_voice.py \
  --type industry {script_path}
```

硬指标：

- 人称词 ≥ 25/千字
- 真问句 ≥ 2.5/千字
- 书面连接词 ≤ 2
- 平均句长 8 至 18
- TTS 禁区无命中

未 PASS 禁止录音。

### Phase 7：配置、配音和封面

完整读取 `references/publishing.md`。

1. 生成只含 `industry_trends` 的 `config.json`。
2. 使用刘飞音色：

```bash
uv run --with requests python3 \
  scripts/generate_tts_solo.py \
  --content-file {script_path} \
  --output-file {mp3_path} \
  --speaker zh_male_liufei_uranus_bigtts
```

3. 脚本会对 `industry_trends` 文件名自动兜底到刘飞，禁止依赖 `VOLCENGINE_TTS_SPEAKER`。
4. 生成 2048×2048 封面。
5. 追加生效期内的栏目推广。
6. 运行 `finalize_podcast.py` 回填并校验音频、封面和 config。
7. 检查时长、码率、响度、峰值、文件存在性和封面尺寸。

### Phase 8：小宇宙发布

1. 使用 `xiaoyuzhou-upload`，上传时显式传 `--config`、`--type industry_trends` 和 `--schedule-at`。
2. 标题自动拼接为 `{M月D日}行业洞见｜{标题}`，完整长度不得超过 30 字符。
3. 同一天发布至少预留约 4 小时。
4. 上传前依靠标题查重，防止重复创建。
5. 上传后回读：
   - 同名单集数量为 1
   - `pubDate` 正确
   - 「本音频为 AI 生成」已开启
   - 服务协议已勾选
6. 把 `scheduled_publish_at`、公开链接和后台链接写回 config。

### Phase 9：历史归档

在 `~/.daily-ai-news/history/podcast_history.md` 顶部只追加行业洞见：

- 核心观点
- 来源摘要
- 开头手法
- 可选结构

批量制作按日期分别写记录。

然后同步更新 `~/.daily-ai-news/history/industry_topic_dedup_index.md`：

- 在对应主题族加入日期、标题、核心机制和可复用行动。
- 如果出现新的重复边界，补充“哪些角度已做、哪些仍可差异化”。
- 索引是去重入口，原始记录仍以 `podcast_history.md` 为准。

## 批量一周排期

用户要求一次做多天时：

1. 先生成周排期，不立即录音。
2. 每天至少 3 个知乎候选，最终各选 1 个。
3. 五期应覆盖不同生活场景，例如消费服务、情感、家庭健康、娱乐和宠物。
4. 先批量完成母文和理论支持，再统一检查主题重叠。
5. 经用户确认后批量生成 Gemini 大纲和稿。
6. 每期单独通过口播门禁后再配音。
7. 配音、封面、成品校验完成后逐集上传。
8. 定时时间若用户指定“每天晚上 6 点”，统一使用 `18:00:00`。

## 固定禁止项

- 不读取或引用 AI 日报。
- 不做 Agent 安全、提示词注入、漏洞利用、CVE 或攻击链选题。
- 不把知乎热度当事实证据。
- 不写没有原文链接的政策数字、论文结论或产品准确率。
- 不使用 `VOLCENGINE_TTS_SPEAKER` 决定行业洞见音色。
- 不在口播校验 FAIL 时录音。
- 不上传缺少 `finalize_podcast.py` 校验的成品。
- 不重复创建同名单集。
