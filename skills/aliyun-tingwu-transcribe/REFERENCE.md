# 参考：阿里云百炼非实时语音识别 API

## 官方文档

- 非实时语音识别（含说话人分离、热词、敏感词过滤）：
  https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide
- 听悟产品定价（0.6 元/小时，含说话人分离）：
  https://help.aliyun.com/zh/model-studio/tingwu-meeting-summary-overview
- 获取 API Key：https://help.aliyun.com/zh/model-studio/get-api-key
- 听悟 API（需 AccessKey + OSS 授权，本 skill 未使用）：https://help.aliyun.com/zh/tingwu/api-tingwu-2023-09-30-createtask

## 调用链

```
提交: POST {base}/services/audio/asr/transcription
      header: Authorization: Bearer $DASHSCOPE_API_KEY
      header: X-DashScope-Async: enable
      body: {"model":"paraformer-v2",
             "input":{"file_urls":["<公网音频URL>"]},
             "parameters":{"diarization_enabled":true,"speaker_count":2}}
轮询: GET  {base}/tasks/{task_id}
结果: output.results[0].output.results[0].transcription_url
      （qwen3-asr 系列为 output.result.transcription_url）
```

`base` 默认 `https://dashscope.aliyuncs.com/api/v1`，可用环境变量 `DASHSCOPE_API_BASE` 覆盖。

## 结果 JSON 结构（paraformer-v2）

```json
{"transcripts":[{"channel_id":0,"sentences":[
  {"begin_time":0,"end_time":3565,"text":"...","sentence_id":1,"speaker_id":0,
   "words":[{"begin_time":0,"end_time":178,"text":"你","punctuation":""}]}
]}]}
```

`speaker_id` 即说话人编号；`sentences` 带起止毫秒时间戳，`words` 带词级时间戳。

## 模型选型

| 模型 | 特点 | 计费 |
|------|------|------|
| `paraformer-v2` | 中文为主、支持说话人分离，稳定便宜（默认） | 0.288 元/小时，10h/月免费 |
| `paraformer-1` | 通用中文，无说话人分离需求时可选 | 同上 |
| `qwen3-asr-flash-filetrans` | 最长 12h，支持说话人分离、情绪识别，多语种更好 | 按百炼官网定价 |
| `qwen-audio-3.0-asr-flash-filetrans` | 新版多模态 ASR，多语种与复杂场景强 | 按百炼官网定价 |

## 已知限制

- 仅接受公网 URL（本地文件需先传 OSS，脚本已内置）
- 说话人分离对清晰双人对话效果好，重音、多人交叉发言可能误标
- 英文专有名词（楼盘名、人名）可能识别不准，建议转写后人工校对
