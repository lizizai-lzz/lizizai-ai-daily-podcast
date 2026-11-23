# 人物中文名对照表

> **用途**：行业洞见播客标题生成时，优先查本表确定人物的中文名。
> **维护规则**：
> - 每次通过 anysearch 查到新的中文名后，自动追加到本表
> - 只收录中文社区一致使用的中文名（多家中文媒体通用）
> - 英文社区通用但中文社区也常用英文的（如 Sam Altman、Dario Amodei），保留英文不音译
> - 业界通用的 ID/笔名（如 Swyx），保留 ID

## 中文社区通用中文名

| 英文原名 | 中文名 | 备注 |
|---------|--------|------|
| Jensen Huang | 黄仁勋 | NVIDIA CEO，中文社区通用 |
| Elon Musk | 马斯克 | 中文社区通用 |
| Andrew Ng | 吴恩达 | 中文社区通用 |
| Fei-Fei Li | 李飞飞 | 中文社区通用 |
| Kai-Fu Lee | 李开复 | 中文社区通用 |
| Demis Hassabis | 德米斯·哈萨比斯 | Google DeepMind CEO |
| Sundar Pichai | 桑达尔·皮查伊 | Google CEO |
| Satya Nadella | 萨提亚·纳德拉 | Microsoft CEO |
| Mark Zuckerberg | 扎克伯格 | Meta CEO，中文社区通用简称 |
| Bill Gates | 比尔·盖茨 | 中文社区通用 |
| Eric Schmidt | 埃里克·施密特 | 前 Google CEO |
| Garry Tan | 陈嘉兴 | Y Combinator CEO，中文社区通用（多家中文媒体一致使用） |

## 英文社区通用，中文社区也常用英文（保留英文不音译）

| 英文原名 | 处理方式 | 备注 |
|---------|---------|------|
| Sam Altman | 保留 Sam Altman | OpenAI CEO，中文社区通用英文 |
| Dario Amodei | 保留 Dario Amodei | Anthropic CEO，中文社区通用英文 |
| Greg Brockman | 保留 Greg Brockman | OpenAI 总裁 |
| Mira Murati | 保留 Mira Murati | 前 OpenAI CTO |
| Andrej Karpathy | 保留 Andrej Karpathy | 中文社区通用英文（不音译"安德烈·卡帕西"） |
| Yann LeCun | 保留 Yann LeCun | Meta 首席 AI 科学家，中文社区通用英文 |

## 业界通用 ID/笔名（保留 ID 不加 title）

| ID | 备注 |
|----|------|
| Swyx | AI 业界通用 ID，Latent Space 主理人 |
| Simon Willison | 中文社区也用英文（不音译） |

## 待查（未收录，需 anysearch 实时查询）

以下人物首次出现时需通过 anysearch 查询中文名，查到后追加到上方对应分类：

- Matt Turck（FirstMark）— 7/12 出现
- Guillermo Rauch（Vercel）— 7/11 出现
- Ethan Mollick（Wharton）— 7/8 出现
- Peter Steinberger — 7/9 出现

## 已查（通过 anysearch 验证，无通用中文名，用英文+title）

| 英文原名 | 处理方式 | anysearch 验证结果 | 首次出现 |
|---------|---------|-------------------|----------|
| David George | 「a16z 普通合伙人 David George」 | 中文媒体（TechNews 科技新報、腾讯新闻）一致使用英文 "David George"，不音译 | 7/13 |
| Thibault Sottiaux | 「OpenAI 核心产品负责人 Thibault Sottiaux」 | 中文媒体无一致音译（小娜学AI 称 Tibo/首席产品官），按规则用英文+title | 8/5 |

> **兜底规则**：anysearch 查不到通用中文名的，使用「`{title} {英文原名}`」格式，title 选取规则见 `modules/industry-insights.md` 的标题生成规则。
