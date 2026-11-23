# 第三方技能安装指引

主流水线引用了 4 个未随本仓库分发的第三方技能（版权归原作者所有）。它们服务于「选题调研」阶段，不装也能跑通核心链路，但行业洞见的知乎选题与来源核验会受限。

## 必装（行业洞见强制依赖）

### qiaomu-ds-search —— DeepSeek 官方 Search/Fetch

外部搜索、正文抓取、来源交叉核验。行业洞见的来源分级（A/B/C/D）依赖它做互补查询与反证搜索。

- 作者：向阳乔木
- 安装：按原仓库 README 安装到你的技能目录，并配置 DeepSeek API Key
- 缺失时的降级：SKILL.md 允许「浏览器不可用时使用其他公开只读搜索，但必须记录限制」

### agent-reach —— 各平台只读内容抓取

读取知乎公开搜索结果、问题和高赞回答；也用于传记收集阶段抓取社交媒体公开发言。

- 仓库：<https://github.com/Panniantong/Agent-Reach>
- 缺失时的降级：行业洞见可改用 any-search 或其他公开搜索，知乎热度数据不可见时如实记录「不可见」，禁止估算

## 可选

### any-search —— 实时搜索引擎聚合

DeepSeek 搜索不可用或需要二次交叉核验时的补充；dev（大咖言论）模式的母文佐证工具。

- 仓库：<https://github.com/anysearch-ai/anysearch-skill>
- 注意：原项目对脚本完整性有校验要求，请按其 README 原样安装，不要修改脚本

### llm-wiki —— Karpathy LLM 知识库（MIT）

为每日精选和开源解读提供历史连续性（实体页、日报页、主题综述）。它是一个**知识库型技能**：安装框架后，知识条目随你的日报流水线自行积累，从零开始的前几天连续性简报会以「知识库为空」正常通过。

- 作者：sdyckjq-lab（MIT License）

## 不随库分发的自有环节说明

| 环节 | 原依赖 | 本仓库状态 |
| --- | --- | --- |
| 脚本格式模板（content-to-podcast） | WorkBuddy 平台打包技能 | 未随库分发；缺失时按各栏目模块的格式规范执行，不影响流水线 |
| de-AI 去 AI 味改写 | de-AI-writing | 未随库分发；SKILL.md Phase 2.6A 已内联全部核心规则，无该技能时 agent 直接按内联规则执行 |
| 转写（aliyun-tingwu-transcribe） | — | **已随库分发**（`skills/aliyun-tingwu-transcribe/`），需 `pip install oss2` |
| TTS（volcengine-tts） | — | **已随库分发**（`skills/volcengine-tts/`） |

## 安装后的目录布局

推荐整体安装，脚本会自动互相定位：

```
<你的技能根目录>/          # 亦可用 $PODCAST_SKILLS_ROOT 指定
├── lizizai-ai-daily-podcast/   # 本仓库整体（或拆开后的各 skill）
├── qiaomu-ds-search/
├── agent-reach/
├── any-search/
└── llm-wiki/
```

若把本仓库 `skills/` 下的技能拆散安装，`$PODCAST_SKILLS_ROOT` 指到包含它们的根目录即可。
