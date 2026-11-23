# Gemini 写作流程

## 要求

大纲和逐字稿必须通过 `gemini-writer` 生成。不得用普通问答模型临时替代，也不得在母文之外自行补事实。

## 顺序

1. 完整读取本仓库 `skills/gemini-writer/SKILL.md`。
2. 读取其 `references/prompt_engineering.md` 和 `references/context_assembly.md`。
3. 构造系统提示词，覆盖角色、任务、受众、语气、工作流和限制。
4. 将系统提示词展示给用户，得到确认后才允许调用 Gemini。
5. 组装上下文：选题、母文、原文台账、理论支持和输出格式。
6. 调用 Gemini，保存原始响应或生成稿。
7. 拆出大纲和逐字稿，分别写入产物目录。
8. 对逐字稿执行去 AI 味、数字汉化和口播门禁。

## 推荐模型

- 优先 `gemini-3.8-flash`
- 默认 `gemini-flash-latest`
- 模型返回 503 时等待或换用仍可用的 Gemini 型号
- 模型返回 429 时检查配额，不得伪造输出
- 长响应在代理上被断开时，可改为流式调用，或把“大纲”和“逐字稿”拆成两次 Gemini 调用

## 标准调用

```bash
python3 ../gemini-writer/scripts/gemini_call.py \
  --system {system_prompt} \
  --content {context} \
  --output {merged_output} \
  --model gemini-3.8-flash \
  --raw-json
```

## 合并输出格式

```text
===OUTLINE===
大纲内容

===SCRIPT===
逐字稿内容
```

响应必须以 `finishReason=STOP` 结束，并同时存在两个区块。缺失任一区块视为失败。

## 逐字稿约束

- 2000 至 3000 个汉字
- 单人播报
- 第一行只有 `# 标题`
- 其余为 `[情感描述] 文本`
- 一个核心判断
- 主理论只解释机制
- 竞争解释和反证必须保留
- 1 至 2 个具体行动
- 不新增母文外数字或案例

## 失败处理

- 长度不足：补论证，不重复观点灌水
- 人称或问句不足：把第三人称判断改成“我/你/我们”，增加真问题
- 理论被写成证明：改为“这个机制可以帮助理解”，并保留研究边界
- 输出含 URL 或多余标题：删除后再做口播门禁
- 输出被截断：重做该次调用，不使用半成品
