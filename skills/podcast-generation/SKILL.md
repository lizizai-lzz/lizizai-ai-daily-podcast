---
name: podcast-generation
description: 使用火山引擎语音播客大模型 WebSocket API 生成双人对话式播客音频。支持文本总结、对话脚本、联网主题三种模式。当用户要求生成播客、制作音频节目、将文章转为对话式播客时触发。Triggers: "生成播客", "制作播客", "播客生成", "转播客", "podcast", "对话式播客", "音频节目", "文章转播客", "语音播客"
---

# 播客生成 Skill

## 概述

本 Skill 通过**火山引擎语音播客大模型 WebSocket API**（`wss://openspeech.bytedance.com/api/v3/sami/podcasttts`）端到端生成双人对话式播客音频。支持三种生成模式：

| 模式 | action | 输入 | 说明 |
|------|--------|------|------|
| **文本总结** | 0 | 长文本 / 网页链接 | 模型自动总结内容并生成播客 |
| **对话脚本** | 3 | 预写对话文本 | 豆包API生成脚本 → 播客TTS合成音频 |
| **联网主题** | 4 | 简短主题词 | 模型联网搜索后生成播客 |

## 核心优势

相比之前"豆包API生成脚本 + 逐行TTS"的方案，WebSocket播客API具有：

- **端到端生成**：一个API调用完成「内容理解→对话生成→音频合成」全流程
- **更自然的对话**：播客模型专门训练，对话节奏、附和、停顿更拟真
- **更快的速度**：流式返回，边生成边接收
- **音频URL**：可直接获取完整播客音频下载链接
- **联网能力**：action=4 支持根据主题联网搜索生成

## 环境要求

| 环境变量 | 必填 | 说明 | 获取方式 |
|---------|------|------|---------|
| `VOLCENGINE_TTS_APPID` | ✅ | 火山引擎APP ID | [语音技术控制台](https://console.volcengine.com/speech/service/10028) 开通播客服务 |
| `VOLCENGINE_TTS_ACCESS_TOKEN` | ✅ | 火山引擎Access Token | 同上 |

以下仅在 **action=3**（对话脚本模式）时需要：

| 环境变量 | 说明 | 获取方式 |
|---------|------|---------|
| `DOUBAO_API_KEY` | 豆包大模型API密钥 | [火山方舟控制台](https://console.volcengine.com/ark) |
| `DOUBAO_ENDPOINT_ID` | 推理接入点ID | 火山方舟 → 在线推理 |

## 工作流

### Step 1: 理解需求

确认以下信息：
- **源内容**：文本、文件路径或网页链接
- **生成模式**：文本总结(action=0)、对话脚本(action=3)、联网主题(action=4)
- **输出路径**：播客文件保存位置（默认 `./generated-podcasts/`）

### Step 2: 调用生成脚本

#### 模式一：文本总结生成播客（action=0，默认）

最简单的方式，输入文本或URL，模型端到端生成播客：

```bash
# 从文本生成
python3 scripts/generate.py \
  --content "要转换为播客的长文本内容……" \
  --output-file ./generated-podcasts/output.mp3 \
  --transcript-file ./generated-podcasts/output-transcript.md

# 从URL生成
python3 scripts/generate.py \
  --action 0 \
  --input-url "https://mp.weixin.qq.com/s/xxxxx" \
  --output-file ./generated-podcasts/output.mp3
```

#### 模式二：对话脚本生成播客（action=3）

先用豆包API生成对话脚本，再用播客TTS合成：

```bash
python3 scripts/generate.py \
  --action 3 \
  --content "要转换的内容" \
  --output-file ./generated-podcasts/output.mp3 \
  --script-file ./generated-podcasts/output-script.json \
  --transcript-file ./generated-podcasts/output-transcript.md \
  --locale zh --style tech
```

#### 模式三：联网主题生成播客（action=4）

输入简短主题，模型联网搜索后生成播客：

```bash
python3 scripts/generate.py \
  --action 4 \
  --prompt-text "火山引擎" \
  --output-file ./generated-podcasts/output.mp3
```

### Step 3: 输出处理

生成完成后：
1. 告知用户生成结果（模式、音频大小）
2. 同时提供 MP3 音频文件
3. 如果有音频URL，提供有效期1小时的下载链接
4. 如需调整，可修改脚本 JSON 后用 action=3 重新生成

## 完整参数说明

```bash
python3 scripts/generate.py \
  [--content TEXT | --content-file FILE] \  # 源内容（二选一）
  --output-file PATH \                      # 输出MP3路径（必填）
  [--script-file PATH] \                    # 脚本JSON输出路径
  [--transcript-file PATH] \                # 文字稿输出路径
  [--action {0,3,4}] \                      # 生成模式（默认0）
  [--input-url URL] \                       # 网页链接（action=0）
  [--prompt-text TEXT] \                    # 主题词（action=4）
  [--locale {zh,en}] \                      # 语言（默认zh）
  [--style {tech,news,knowledge,casual}] \  # 风格（action=3专用）
  [--max-lines N] \                         # 最大对话行数（默认60，action=3）
  [--use-head-music]                        # 添加开头音效
```

## 播客风格说明（action=3专用）

| 风格 | 说明 | 适用场景 |
|------|------|---------|
| `tech` | 技术解读型 | 技术文档、API指南、开发者教程 |
| `news` | 新闻资讯型 | 行业动态、新闻快讯、趋势分析 |
| `knowledge` | 知识科普型 | 学术论文、科普文章、学习资料 |
| `casual` | 轻松聊天型 | 生活分享、趣味话题、个人见解 |

## 使用示例

### 示例 1：从文章内容一键生成播客

用户："帮我把这篇文章转成播客"

```bash
python3 scripts/generate.py \
  --content "量子计算正在改变密码学的未来。传统RSA加密算法面临威胁……" \
  --output-file ./generated-podcasts/quantum-crypto.mp3
```

### 示例 2：从网页URL生成播客

用户："把这个链接的内容做成播客"

```bash
python3 scripts/generate.py \
  --action 0 \
  --input-url "https://mp.weixin.qq.com/s/xxxxx" \
  --output-file ./generated-podcasts/web-article.mp3
```

### 示例 3：从主题词联网生成播客

用户："生成一期关于大模型发展的播客"

```bash
python3 scripts/generate.py \
  --action 4 \
  --prompt-text "2026年大模型发展趋势" \
  --output-file ./generated-podcasts/llm-trends.mp3
```

### 示例 4：精细控制对话脚本

用户："帮我用技术风格生成播客"

```bash
python3 scripts/generate.py \
  --action 3 \
  --content-file ./articles/ai-agent-guide.md \
  --output-file ./generated-podcasts/ai-agent.mp3 \
  --script-file ./generated-podcasts/ai-agent-script.json \
  --transcript-file ./generated-podcasts/ai-agent-transcript.md \
  --locale zh --style tech
```

## 注意事项

- **播客服务开通**：需在[火山引擎控制台](https://console.volcengine.com/speech/service/10028)开通「语音播客大模型」
- **音频URL有效期**：通过 `return_audio_url` 获取的音频链接有效期为1小时
- **文本长度限制**：action=0 模式下最长 32k 字符，建议不超过 12000 字
- **单轮对话限制**：action=3 模式下每轮不超过 300 字符，总文本不超过 10000 字符
- **生成耗时**：约 2-10 分钟（取决于内容长度和模型负载），超时上限 600 秒
- **安全审核**：内容会经过安全审核过滤，敏感内容可能生成失败（错误码 50302102）

## 重试与容错机制

generate.py 内置了多层容错保障，确保长时间音频生成任务的可靠性：

### 1. WebSocket 生成阶段

| 机制 | 说明 |
|------|------|
| **超时保护** | 默认 600 秒超时（可配置），超时后自动断开 WebSocket |
| **进度监控** | 每 30 秒输出进度日志：已用时间、完成轮次、音频块数、空闲时间 |
| **线程监控** | WebSocket 运行在独立线程，主线程监控线程存活状态 |
| **异常检测** | WebSocket 线程意外退出时，检查是否有可用音频数据并报告 |

### 2. 音频下载阶段

| 机制 | 说明 |
|------|------|
| **分块下载** | 使用流式下载，避免大文件内存溢出 |
| **下载重试** | 最多 3 次重试，超时 120 秒/次 |
| **指数退避** | 重试间隔递增（5s → 10s → 15s） |
| **断点检测** | 下载完成后验证文件大小（< 1KB 视为异常） |

### 3. 整体重试（CLI 模式）

CLI 调用自动启用整体重试：

- **最大重试次数**：3 次
- **指数退避**：10s → 20s → 40s
- **可重试错误**：TimeoutError、ConnectionError、WebSocket 连接关闭、503/502/429 HTTP 错误
- **输出验证**：每次成功后检查输出文件大小，过小则触发重试

### 手动调用时的重试建议

通过 Python 脚本调用时，建议使用重试包装：

```python
from generate import _generate_podcast_with_retry

result = _generate_podcast_with_retry(
    max_retries=3,
    retry_delay=10,
    content="...",
    output_file="output.mp3",
    action=0,
)
```

或在自动化场景中，在外部添加重试：

```bash
# Shell 层面简单重试
for i in 1 2 3; do
  python3 generate.py --content-file input.md --output-file output.mp3 && break
  echo "Attempt $i failed, waiting 30s..."
  sleep 30
done
```

## 模板

- [技术解读模板](templates/tech-explainer.md)
- [新闻资讯模板](templates/news-digest.md)

## 技术参考

- [火山引擎语音播客大模型文档](references/podcast-system-prompt.md)
- [播客API WebSocket v3协议](https://www.volcengine.com/docs/6561/1668014)
