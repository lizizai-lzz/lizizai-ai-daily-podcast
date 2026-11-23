---
name: duo-podcast-tts
description: 端到端生成双人对话播客（角色化文字稿 + MP3 音频）。支持自定义男女音色 ID 与角色定位；未指定时按选题自动推荐音色与角色（参考 Qwen-TTS 音色目录与角色定位指南）。Use when 用户要求生成双人播客/双人对话音频、把选题或文字稿变成双人播客、指定男女音色制作对话节目，或提到"双人播客""AI夜话""角色播客""两人对话音频"等。
---

# 双人播客生成（duo-podcast-tts）

## 工作流

1. 解析需求（选题、受众、时长、是否指定音色/角色）
2. 角色定位 + 音色推荐（未指定时按选题推荐）
3. 写双人文字稿 + dialogue JSON
4. 合成音频（默认阿里云 Qwen-TTS，`qwen3-tts-flash` 模型）
5. 交付 MP3 + 文字稿 + 复现命令

## 前置条件

- `DASHSCOPE_API_KEY`：阿里云百炼 API Key，写在 `~/.zshrc` 即可；脚本自动从环境变量或 `~/.zshrc` 读取（`tts_common.load_api_keys`）
- Python3（stdlib 即可）+ ffmpeg
- 输出目录：默认 `/tmp/duo_podcast_{topic}/`，用户另有指定时遵循

## Step 1 解析需求

确认并记录：
- 选题主题（必填）与目标听众
- 期望时长（默认 4-8 分钟 ≈ 20-30 句）
- 是否指定男女音色 ID、男女角色定位、男生/女生主导比例（默认男生主导 60-75%）

## Step 2 角色定位与音色推荐

- **未指定音色/角色**：读 [references/persona-guide.md](references/persona-guide.md) 按选题匹配角色原型，读 [references/voice-catalog.md](references/voice-catalog.md) 挑选男女音色，向用户说明推荐理由和备选
- **用户指定音色**：先查 [references/voice-catalog.md](references/voice-catalog.md) 确认存在；不存在时给出相近音色候选
- 默认模型 `qwen3-tts-flash`（48 个中文音色）。注意：`qwen3-tts-instruct-flash` 的音色集合不同，指定音色换模型前必须先实测
- 备选引擎：MiniMax speech-2.8（`scripts/minimax_speech_tts.py`，支持 emotion 参数 + 语气词标签，需要 `MINIMAX_CN_API_KEY`）

## Step 3 写稿

产出两个文件（同名同目录）：
- `{topic}_script.md`：可读文字稿（角色标注版）
- `{topic}_dialogue.json`：机器对话

dialogue JSON 格式：

```json
[
  {"speaker": "host", "emotion": "平静", "text": "……"},
  {"speaker": "guest", "emotion": "好奇", "text": "……"}
]
```

写作规则（详见 persona-guide.md）：
- 口吻贴合角色设定（方言/儿化/专业术语浓度按角色来）
- 每句 20-100 字，短句推进，问句收尾制造对话感
- 按角色主导比例分配说话量（如男生 70% = 更多、更长的分析段）
- 结尾给一句可转发金句 + 一个互动提问
- 年份与数字用中文口语（一九八四年、百分之九十八），TTS 更稳
- `emotion` 取值：平静/认真/好奇/惊讶/开心/坚定/神秘/悲伤

## Step 4 合成

```bash
PY=python3
cd <本技能目录>
$PY scripts/aliyun_cosyvoice_tts.py \
  --dialogue {topic}_dialogue.json \
  --model qwen3-tts-flash \
  --voice-host <男音色ID> \
  --voice-guest <女音色ID> \
  --output /tmp/duo_podcast_{topic}/episode.mp3
```

- 逐行合成（每行一次 API 调用），段间自动插入 0.35 秒停顿（`--pause` 可调）
- 失败排查：音色不支持 → 换目录内音色；key 缺失 → 检查 `~/.zshrc` 的 export 行

## Step 5 交付

- 交付 MP3（应用内可直接播放）+ 文字稿 + dialogue JSON + 复现命令
- 说明：使用的音色与角色、时长、成本估算、可调整点（音色/角色/停顿/主导比例）
- 需要对比时，用 MiniMax 脚本生成第二版供用户试听

## 参考

- 音色目录（48 个中文音色 + 常用搭配）：[references/voice-catalog.md](references/voice-catalog.md)
- 角色定位与写作指南：[references/persona-guide.md](references/persona-guide.md)
