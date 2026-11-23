# 火山引擎语音播客大模型 WebSocket v3 API 参考

## API 概览

- **请求路径**：`wss://openspeech.bytedance.com/api/v3/sami/podcasttts`
- **协议**：WebSocket 二进制协议 v1
- **服务资源ID**：`volc.service_type.10050`
- **控制台开通**：https://console.volcengine.com/speech/service/10028

---

## 鉴权 Headers

| Key | 是否必须 | 说明 |
|-----|---------|------|
| `X-Api-App-Id` | 是 | 火山引擎控制台获取的 APP ID |
| `X-Api-Access-Key` | 是 | 火山引擎控制台获取的 Access Token |
| `X-Api-Resource-Id` | 是 | 固定值：`volc.service_type.10050` |
| `X-Api-App-Key` | 是 | 固定值：`aGjiRDfUWi` |
| `X-Api-Request-Id` | 否 | 客户端请求ID，建议UUID |

---

## 请求参数

### 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `action` | number | 是 | 0 | 0=文本/URL总结生成，3=对话文本直接生成，4=prompt联网生成 |
| `input_id` | string | 否 | — | 请求标识 |
| `input_text` | string | 否 | — | 输入文本（最长32k），action=0时与input_url二选一 |
| `prompt_text` | string | 否 | — | 主题词（action=4必填），如"火山引擎"、"怎么平衡工作和生活" |
| `nlp_texts` | []object | 否 | — | 对话文本列表（action=3必填） |
| `input_info` | object | 否 | — | 输入辅助信息 |
| `speaker_info` | object | 否 | — | 发音人信息 |
| `audio_config` | object | 否 | — | 音频参数 |
| `use_head_music` | bool | 否 | — | 是否使用开头音效 |
| `aigc_watermark` | bool | 否 | — | 是否添加AIGC水印 |

### nlp_texts 字段（action=3）

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 每轮对话文本，不超过300字符 |
| `speaker` | string | 发音人ID，如 `zh_male_dayixiansheng_v2_saturn_bigtts` |

### input_info 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `input_url` | string | 网页链接或可下载文件链接（PDF/DOC/TXT） |
| `only_nlp_text` | bool | 只输出对话文本，不生成音频 |
| `return_audio_url` | bool | 返回完整播客音频下载链接（1h有效） |
| `input_text_max_length` | number | action=0模式下最大处理字符数，建议≤12000 |

### speaker_info 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `random_order` | bool | 发音人是否随机顺序开始，默认true |
| `speakers` | []string | 播客发音人ID列表，只能选2个 |

### audio_config 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `format` | string | 音频格式：mp3/ogg_opus/pcm/aac |
| `sample_rate` | number | 采样率：16000/24000/48000 |
| `speech_rate` | number | 语速：[-50,100]，100=2倍速，-50=0.5倍速 |

---

## 默认发音人

| 角色 | 发音人ID | 说明 |
|------|---------|------|
| 男主持 | `zh_male_dayixiansheng_v2_saturn_bigtts` | 大一先生 v2 |
| 女主持 | `zh_female_mizaitongxue_v2_saturn_bigtts` | 米在同学 v2 |

> 2026-03-20 更新：支持TTS和ICL复刻音色（复刻音色APPID需与播客服务同一账号）

---

## 事件流

| Event Code | 名称 | 方向 | 说明 |
|-----------|------|------|------|
| 150 | SessionStarted | 下行 | 会话开始 |
| 360 | PodcastRoundStart | 下行 | 新轮次开始（含round_idx和speaker） |
| 361 | PodcastRoundResponse | 下行 | 轮次音频内容 |
| 362 | PodcastRoundEnd | 下行 | 轮次结束（含audio_duration, start_time, end_time） |
| 363 | PodcastEnd | 下行 | 播客结束（含audio_url和meta_info） |
| 152 | SessionFinished | 下行 | 会话结束 |
| 154 | UsageResponse | 下行 | 用量信息 |
| 2 | FinishConnection | 上行 | 客户端主动关闭连接 |
| 52 | ConnectionFinished | 下行 | 连接关闭成功 |

---

## 请求示例

### action=0 文本总结模式

```json
{
    "input_id": "test_podcast",
    "input_text": "分析下当前的大模型发展",
    "action": 0,
    "use_head_music": false,
    "audio_config": {
        "format": "mp3",
        "sample_rate": 24000,
        "speech_rate": 0
    },
    "speaker_info": {
        "random_order": true,
        "speakers": [
            "zh_male_dayixiansheng_v2_saturn_bigtts",
            "zh_female_mizaitongxue_v2_saturn_bigtts"
        ]
    }
}
```

### action=0 URL模式

```json
{
    "input_id": "test_podcast",
    "action": 0,
    "use_head_music": false,
    "audio_config": {
        "format": "mp3",
        "sample_rate": 24000,
        "speech_rate": 0
    },
    "input_info": {
        "input_url": "https://mp.weixin.qq.com/s/CiN0XRWQc3hIV9lLLS0rGA"
    }
}
```

### action=3 对话文本模式

```json
{
    "input_id": "test_podcast",
    "action": 3,
    "use_head_music": false,
    "audio_config": {
        "format": "mp3",
        "sample_rate": 24000,
        "speech_rate": 0
    },
    "nlp_texts": [
        {
            "speaker": "zh_male_dayixiansheng_v2_saturn_bigtts",
            "text": "今天我们要聊的是火山引擎的一些重磅发布。"
        },
        {
            "speaker": "zh_female_mizaitongxue_v2_saturn_bigtts",
            "text": "来看看都有哪些亮点哈。"
        }
    ]
}
```

### action=4 联网主题模式

```json
{
    "input_id": "test_podcast",
    "action": 4,
    "prompt_text": "火山引擎",
    "use_head_music": false,
    "audio_config": {
        "format": "mp3",
        "sample_rate": 24000,
        "speech_rate": 0
    }
}
```

---

## 错误码

| Code | Message | 说明 |
|------|---------|------|
| 20000000 | ok | 成功 |
| 45000000 | quota exceeded for types: concurrency | 并发限流 |
| 40000010 | PodcastTTS invalid param | 参数错误 |
| 55000000 | 服务端error | 服务端通用错误 |
| 50302102 | content filter / content length | 安全审核过滤 / 文本超长 |

---

## Python SDK

官方提供 Python SDK，下载地址：
```
volcengine.speech.volc_speech_python_sdk_1.0.0.25.tar.gz
```

安装：
```bash
mkdir -p volcengine_podcasts_demo
tar xvzf volcengine.speech.volc_speech_python_sdk_*.tar.gz -C ./volcengine_podcasts_demo
cd volcengine_podcasts_demo
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip3 install -e .
```

调用：
```bash
python3 examples/volcengine/podcasts.py --appid <appid> --access_token <access_token> --text "介绍下火山引擎"
```
