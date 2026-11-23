# 配音、封面、校验和定时发布

## 音色

行业洞见固定使用：

```text
zh_male_liufei_uranus_bigtts
```

即使 `VOLCENGINE_TTS_SPEAKER` 配置为其他值，也必须显式传 `--speaker`。脚本还会在文件名包含 `industry_trends` 时自动兜底到刘飞。

## 配音

```bash
source ~/.zshrc
uv run --with requests python3 \
  scripts/generate_tts_solo.py \
  --content-file {script_path} \
  --output-file {mp3_path} \
  --speaker zh_male_liufei_uranus_bigtts
```

片头 5 秒、片尾 8 秒 BGM 由脚本内置。

## 封面

```bash
python3 \
  scripts/generate_covers.py \
  --date {date} \
  --output-dir {podcast_dir} \
  --data '[{"type":"industry_trends","seriesTag":"行业洞见","seriesEn":"INDUSTRY INSIGHTS","label":"洞 见","audience":"{audience}","hit1":"{hit1}","hit2":"{hit2}","hit3":"{hit3}"}]'
```

## config.json

- `type` 固定为 `industry_trends`
- `source` 指向研究文件或母文
- `audio` 和 `cover` 路径写绝对路径
- `title`、`subtitle`、`description` 和 `cover.data` 按当期内容填写

## 推广拼接

```bash
python3 scripts/apply_podcast_promotion.py \
  --date {date} \
  --podcast-dir {podcast_dir}
```

默认读取本 Skill 的 `assets/promotions/default.json`。

## 成品校验

```bash
python3 scripts/finalize_podcast.py \
  --date {date} \
  --podcast-dir {podcast_dir}
```

必须检查：

- MP3 存在且时长合理
- 96kbps
- 封面 2048×2048
- config 无空字段
- BGM 署名存在
- 平均响度约 −22dB，峰值不削波

## 小宇宙定时发布

```bash
python3 ../xiaoyuzhou-upload/scripts/xiaoyuzhou_upload.py \
  --date {date} \
  --config {config_path} \
  --type industry_trends \
  --schedule-at "{YYYY-MM-DD HH:MM:SS}"
```

规则：

- 完整标题不超过 30 字符
- 当天发布时间至少晚于当前时间约 4 小时
- 上传脚本会按标题查重，已存在则跳过
- AI 生成声明必须勾选

## 上传后回读

逐集检查：

1. 后台搜索标题，同名单集数量为 1
2. 编辑页 `pubDate` 与目标时间一致
3. 「本音频为 AI 生成」为开启状态
4. config 写入 `scheduled_publish_at`、公开链接和后台链接

## 批量定时

用户指定连续日期和每天 18:00 时，逐集调用：

```text
2026-11-04 18:00:00
2026-11-05 18:00:00
...
```

不要复用同一个 `--schedule-at` 给不同日期。
