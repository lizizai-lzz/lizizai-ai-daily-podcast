---
name: volcengine-tts
description: 使用火山引擎豆包大模型语音合成（Seed-TTS 2.0 / Seed-ICL 2.0）进行高质量文本转语音。支持 HTTP Chunk 流式协议、SSML/语音标签、情感控制、声音克隆。适用于需要将文本合成 MP3 音频的场景。
agent_created: true
---

# Volcengine TTS — 火山引擎豆包语音合成

基于火山引擎豆包大模型语音合成 API 的高质量 TTS 工具。使用 HTTP Chunk（NDJSON）协议流式合成音频，最终输出 MP3 文件。

## 特性

- **Seed-TTS 2.0 模型**：使用最新的官方 2.0 音色（`seed-tts-2.0`）
- **Seed-ICL 2.0 声音克隆**：支持自定义克隆声音（`seed-icl-2.0`）
- **HTTP Chunk 协议**：一次性提交文本，流式接收 NDJSON 音频片段
- **语音标签支持**：支持 `[情感]文本` 方括号标记和 `<cot>` XML 标签
- **情感控制**：通过 `context_texts` 实现自然语言情感描述
- **MP3 输出**：默认输出 MP3 格式（可选 WAV），自动用 ffmpeg 重封装保证兼容性

## 环境要求

- Python 3.10+
- `requests` 库（`pip install requests`）
- **ffmpeg**（用于 MP3 重封装，避免多片段拼接爆音）
- 火山引擎控制台获取的凭证：
  - `VOLCENGINE_TTS_APPID`：应用 ID（纯数字）
  - `VOLCENGINE_TTS_ACCESS_TOKEN`：API 访问密钥
  - `VOLCENGINE_TTS_SPEAKER`：默认 Speaker voice_type（可选）

## 快速开始

```bash
# 最简单的用法 — 纯文本合成
python scripts/volcengine_tts.py \
  --text "你好，我是李自在。欢迎收听今天的AI日报。" \
  --output /tmp/tts_output.mp3

# 带情感标签的合成
python scripts/volcengine_tts.py \
  --text "[温柔开心]大家好！[严肃认真]今天我们来聊一个重要的话题。" \
  --output /tmp/tts_emotion.mp3

# 指定音色和采样率
python scripts/volcengine_tts.py \
  --text "这是一段测试音频。" \
  --speaker "zh_male_wennuanahu_uranus_bigtts" \
  --output /tmp/tts_custom.mp3 \
  --format mp3 \
  --sample-rate 24000
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--text` | （必填） | 要合成的文本，支持语音标签 |
| `--output` | （必填） | 输出音频文件路径 |
| `--speaker` | 环境变量 `VOLCENGINE_TTS_SPEAKER` | Speaker voice_type，即控制台中的音色标识符（如 `zh_male_wennuanahu_uranus_bigtts`） |
| `--app-id` | 环境变量 `VOLCENGINE_TTS_APPID` | 火山引擎应用 ID |
| `--access-key` | 环境变量 `VOLCENGINE_TTS_ACCESS_TOKEN` | API 访问密钥 |
| `--format` | `mp3` | 音频格式：`mp3` 或 `wav` |
| `--sample-rate` | `24000` | 采样率 |
| `--uid` | `workbuddy` | 用户标识，用于日志和计费 |
| `--no-ffmpeg` | `false` | 跳过 ffmpeg 重封装（可能导致多片段拼接爆音） |

## 语音标签（Voice Tags）

### 方括号标记 — `[情感]文本`

在文本中使用 `[情感描述]` 标记来控制每段话的语气：

```
[开心]你好呀！[温柔]今天辛苦了。[害羞]你别这么说嘛。
```

- 标记会被自动拆分为多段独立调用
- 每段通过 `context_texts` 参数传递情感描述
- 情感描述越具体效果越好，建议使用场景化描述：

| 有效示例 | 说明 |
|---|---|
| `[用温柔甜蜜的声音]` | 有画面感 |
| `[边哭边说，很伤心]` | 具体行为描述 |
| `[开心到快要尖叫了]` | 程度明确 |
| `[用ASMR悄悄话的声音，非常轻柔]` | 场景+细节 |

### COT 标签 — `<cot text=情感>文本</cot>`

适用于 Seed-ICL 2.0 克隆音色的一次性调用：

```
<cot text=开心>你好呀！</cot><cot text=温柔>今天辛苦了。</cot>
```

### 使用方式选择

| 场景 | 推荐方式 | 原因 |
|---|---|---|
| 情感一致性要求高 | 方括号标记（逐句调用） | 每句独立控制，粒度更细 |
| 简单快速合成 | COT 标签（一次调用） | 只需一次 API 调用 |
| 无情感需求 | 纯文本 | 直接一次调用 |

## 模型路由规则

脚本自动根据 Speaker voice_type 判断使用的模型：

| voice_type 特征 | 自动路由到 | Resource ID |
|---|---|---|
| `S_xxx`（克隆声音） | Seed-ICL 2.0 | `seed-icl-2.0` |
| `*_uranus_bigtts` / `saturn_*` | Seed-TTS 2.0 | `seed-tts-2.0` |
| `*_mars_bigtts` / `*_moon_bigtts` / `ICL_*` | Seed-TTS 1.0 | `seed-tts-1.0` |

> **如何找到 Speaker voice_type**：在火山引擎控制台 → 语音技术 → 音色管理中，每个音色都有一个 `voice_type` 标识符（如 `zh_male_wennuanahu_uranus_bigtts`）。这个值就是你需要的 `--speaker` 参数。注意：音色名称（如"温暖阿虎"）不是 speaker 参数，必须使用 voice_type 标识符。

## API 协议细节

### 端点

```
POST https://openspeech.bytedance.com/api/v3/tts/unidirectional
```

### 请求头

```
Content-Type: application/json
X-Api-App-Id: <APP_ID>
X-Api-Access-Key: <ACCESS_KEY>
X-Api-Resource-Id: seed-tts-2.0
```

### 响应格式（NDJSON）

```json
{"code":0,"data":"<base64 音频片段>"}
{"code":0,"data":"<base64 音频片段>"}
{"code":20000000}
```

- `code === 0` + `data`：音频片段，base64 解码后拼入 buffer
- `code === 20000000`：流结束标记
- 其他 code：错误

### 关键注意事项

1. **`additions` 必须是字符串**：`json.dumps({...})`，传对象会被静默忽略
2. **克隆音色需要 `model_type: 4`**：放在 additions 字符串内部
3. **响应不能用 `.json()` 解析**：必须 `.text()` 后按 `\n` 分割逐行解析
4. **MP3 拼接可能爆音**：用 `ffmpeg -c copy` 重封装修复

## 与其他 Skill 配合

- **daily-ai-news**：AI 日报生成后，使用本 Skill 合成语音版本
- **content-to-podcast**：播客脚本生成后，使用本 Skill 合成音频
- **podcast-generation**：可与本 Skill 互为替代或补充
- **fishaudio-tts**：类似功能但使用 FishAudio API，可根据需求选择

## 故障排除

| 症状 | 原因 | 解决方案 |
|---|---|---|
| 401 错误 | Header 名错误 | 合成用 `X-Api-App-Id`（非 `X-Api-App-Key`） |
| 空音频 | `--speaker` 填了音色名称而非 voice_type | 使用控制台中的 voice_type 标识符（如 `zh_male_wennuanahu_uranus_bigtts`），不要填中文名称 |
| 情感不生效 | `additions` 传了对象 | 必须 `json.dumps()` 序列化为字符串 |
| 播放器卡顿/爆音 | MP3 片段直接拼接 | 确保安装 ffmpeg，脚本会自动重封装 |
| `code` 非零 | API 错误 | 检查 speaker ID 和 resource ID 是否匹配 |
