---
name: aliyun-tingwu-transcribe
description: 使用阿里云百炼语音识别（听悟同源 ASR，paraformer-v2）把本地音视频或公网音频转成带说话人分离、时间戳的 Markdown 文字稿。Use when 用户要转写音视频/音频为文字、语音转文字、会议/访谈/播客转写，或要求"说话人分离""区分说话人"；也用于需要把本地视频音频先转文字稿再分析的场景（如人物志素材采集）。
---

# 阿里云听悟式语音转文字（含说话人分离）

基于阿里云百炼「非实时语音识别」API（与通义听悟同源的 ASR 能力），异步转写音视频文件，输出带 `说话人N` 标签和时间戳的 Markdown 文字稿。

## 配置（一次性）

1. 环境变量 `DASHSCOPE_API_KEY`（百炼 API Key，已配置在 `~/.zshrc`）
2. 本地文件需要 OSS 公网中转，复用 `~/.config/aliyun-oss/config.json`（已存在）：
   ```json
   {"access_key_id":"LTAI...","access_key_secret":"...","endpoint":"oss-cn-hangzhou.aliyuncs.com",
    "bucket":"...","key_prefix":"transcribe","object_acl":"public-read",
    "public_base_url":"https://<bucket>.oss-cn-hangzhou.aliyuncs.com"}
   ```

## 快速开始

```bash
本技能目录/.venv/bin/python \
  本技能目录/scripts/transcribe_audio.py \
  /path/to/video.mp4 /path/to/audio.wav \
  --model paraformer-v2 --speaker-count 2 --output-dir ./transcripts
```

公网 URL 无需 OSS：

```bash
本技能目录/.venv/bin/python \
  本技能目录/scripts/transcribe_audio.py \
  "https://example.com/audio.mp3" --output-dir ./transcripts
```

每个输入生成两个文件：`<文件名>.json`（完整结果，含词级时间戳）和 `<文件名>.md`（带说话人标签的文字稿）。

## 参数速查

| 参数 | 默认 | 说明 |
|------|------|------|
| `--model` | `paraformer-v2` | 备选：`qwen3-asr-flash-filetrans`（12h 内文件）、`qwen-audio-3.0-asr-flash-filetrans`、`paraformer-1` |
| `--speaker-count` | `2` | 预估说话人数；单人音频设 `1`，多人设 `2` 或以上 |
| `--no-diarization` | 关 | 关闭说话人分离 |
| `--language-hints` | 无 | 语种提示，如 `--language-hints zh en`（qwen 系列生效） |
| `--output-dir` | `.` | 结果输出目录 |
| `--oss-key-prefix` | `transcribe` | OSS 对象前缀 |
| `--extra-param` | 无 | 额外参数 JSON，如 `--extra-param '{"enable_itn": false}'` |

## 工作流

1. 本地文件 → 上传 OSS 拿公网 URL（公网 URL 跳过此步）
2. POST 提交异步转写任务（`X-DashScope-Async: enable`，`diarization_enabled: true`）
3. 每 15 秒轮询任务状态，直到 `SUCCEEDED`
4. 下载 `transcription_url` 指向的 JSON，转成 Markdown 落盘

单文件 ≤ 12 小时、≤ 2GB；支持 wav/mp3/m4a/aac/ogg/mp4/mkv 等常见格式（建议 16kHz 单声道）。

## 计费（2026-08，按音频时长）

- `paraformer-v2`：0.288 元/小时；每月免费 10 小时（36,000 秒），每月 1 日自动续
- 听悟 ASR（百炼）：0.6 元/小时（含说话人分离、自动语种识别）
- 静音部分不计费（仅按识别出的语音时长计费）

## 注意事项

- 上传 OSS 的对象是 `public-read`，不要用此流程处理敏感内容
- 转写结果 URL 24 小时内有效，脚本已自动下载落盘
- 说话人分离对双人对话效果较好；多人会议建议设 `--speaker-count 3-4` 或换听悟产品
- 英文/多语种文件建议 `--model qwen3-asr-flash-filetrans --language-hints en zh`，并抽查英文专有名词

更多 API 细节见 [REFERENCE.md](REFERENCE.md)。
