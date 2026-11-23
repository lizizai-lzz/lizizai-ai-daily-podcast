# 行业洞见 config.json

每一期只包含一条 `industry_trends`。

```json
{
  "version": "1.0",
  "date": "2026-11-04",
  "source": "/absolute/path/research_supplement_industry_2026-11-04.md",
  "generated_at": "2026-11-03T22:48:23+08:00",
  "podcasts": [
    {
      "type": "industry_trends",
      "title": "AI客服:转人工为什么越来越难",
      "subtitle": "一句话补充标题",
      "description": "150-300 字的节目简介",
      "script_path": "/absolute/path/script_industry_trends_2026-11-04.md",
      "audio": {
        "path": "/absolute/path/industry_trends_2026-11-04.mp3",
        "size": null,
        "format": "mp3",
        "duration_seconds": null,
        "duration_human": null,
        "bitrate": "96kbps"
      },
      "cover": {
        "path": "/absolute/path/cover_industry_trends_2026-11-04.png",
        "template": "cover_template.html",
        "data": {
          "seriesTag": "行业洞见",
          "seriesEn": "INDUSTRY INSIGHTS",
          "label": "洞 见",
          "audience": "消费者 · AI服务",
          "hit1": "核心事实一",
          "hit2": "核心事实二",
          "hit3": "行动判断"
        },
        "size": null,
        "format": "png",
        "dimensions": "2048x2048"
      }
    }
  ]
}
```

## 规则

- `type` 必须是 `industry_trends`
- `source` 必须是当期研究文件或母文，不得是 AI 日报
- `title` 使用「话题:判断」或「人物:观点」，视觉宽度不超过 20
- `cover.data.seriesTag` 固定为“行业洞见”
- `cover.data.hit1` 至 `hit3` 各不超过 15 字
- 音频和封面路径使用绝对路径
- Phase 3 前元数据字段填 `null`
- 生成音频、封面并追加推广后运行：

```bash
python3 scripts/finalize_podcast.py \
  --date {date} \
  --podcast-dir ~/.daily-ai-news/data/{date}/industry_podcast
```

上传成功后，可写回：

- `scheduled_publish_at`
- `xiaoyuzhou_url`
- `xiaoyuzhou_backend_url`
