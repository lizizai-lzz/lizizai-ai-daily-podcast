---
name: lizz-biography-podcast
description: "「李自在AI人物志」访谈式（纪录片式 VO/SOT）播客生成与上传流水线。仅支持访谈形式：VO 旁白 + 人物真实原声 SOT，不支持纯旁白。在 biography-writer 已生成的传记终稿基础上，收集人物原声（B站等）→ 词级转写 → 剪辑 SOT → 合成 VO → 组装 60_podcast.mp3 → 合成品牌片头/片尾（固定 ElevenLabs BGM）→ 整期 episode.mp3 → config.json（可上传小宇宙）。Use when 用户要求给人物志新增一期、传记转播客、生成片头片尾、合并 episode.mp3、定时发布到小宇宙，或把人物传记做成「VO + 人物原声」的访谈纪录片。触发词：李自在AI人物志、人物志播客、传记转播客、访谈播客、纪录片播客、原声、SOT、VO、episode.mp3 合并、小宇宙上传。"
agent_created: true
---

# lizz-biography-podcast — 「李自在AI人物志」访谈式播客生成与上传

## 适用范围（仅访谈式，不支持纯旁白）

本 Skill 只产出**访谈式（纪录片式 VO/SOT）**人物志：

```
品牌片头 →（蒙太奇冷开场·可选）→（个人推荐·可选）→ 访谈正文（VO 旁白 + 人物原声 SOT，无 BGM）→ 片尾（固定 BGM 尾）
```

- **VO**：叙事旁白（火山引擎 TTS 合成），负责时代背景、前因后果、承接与解读。
- **SOT**：人物**真实公开原声片段**（B站等平台下载 + 词级转写后剪辑），让人物自己说话。
- **禁止纯旁白模式**：不生成单人朗读式 `50_podcast_script.md` / `60_podcast.mp3`；正片必须包含人物原声 SOT。

**前置**：已通过 `biography-writer` 完成传记正文 `40_final.md`（必存在）。访谈式还必须有：
- 人物原声素材：`00_raw/audio/*`（下载的 m4a/mp3）
- 词级时间戳转写：`00_raw/transcripts/*.json`（SOT 剪辑的唯一依据）

**输出**：`52_documentary_script.md`、`vo_*.txt`、`sot_*.mp3`、`60_podcast.mp3`（访谈正片）、`intro.mp3`、`outro_music.mp3`、`episode.mp3`、`config.json`；可上传小宇宙。

## 项目目录约定

```
~/李自在AI人物志/
├── E{NN}.{人物名}/
│   ├── 00_raw/
│   │   ├── audio/                   # 原声素材（bili audio 下载的 m4a）
│   │   ├── transcripts/             # 词级时间戳 JSON + md（SOT 剪辑依据）
│   │   └── voice_sources.md         # 素材清单 + SOT 候选（时间窗/时长/内容/节点）
│   ├── 10_source.md / 20_outline.md / 30_draft.md / 40_final.md
│   ├── 52_documentary_script.md     # 访谈脚本：VO/SOT 结构（标注来源与时长）
│   ├── vo_01.txt ~ vo_13.txt        # 旁白文本（每段一个文件，带情感标签）
│   ├── vo_*.mp3                     # 合成后的旁白
│   ├── sot_01.mp3 ~ sot_05.mp3      # 人物原声片段（剪切+响度归一）
│   ├── vo13_bgm.mp3                 # 收束段旁白 + BGM 垫入（可选，若收束段起 BGM）
│   ├── 60_podcast.mp3               # 访谈正片（VO/SOT 组装，正文无 BGM）
│   ├── montage_opening_music.mp3    # [可选] 蒙太奇冷开场
│   ├── personal_take.mp3            # [可选] 个人推荐（李自在口播）
│   ├── intro.mp3 / outro_music.mp3  # 品牌片头 / 带固定 BGM 片尾
│   ├── episode.mp3                  # 最终单集
│   ├── episode_meta.json            # 分段元数据（merge_audio 输出）
│   └── config.json                  # 上传配置（含小宇宙元数据）
└── ...
```

命名规则：`E{NN}.{人物名}`，中文优先，需要补充身份的写 `title + 人名`。

## 强制依赖

| 依赖 | 用途 | 来源 |
|---|---|---|
| `biography-writer` | 传记正文（40_final.md） | 本仓库 `skills/biography-writer/` |
| `volcengine-tts` | 火山引擎 Seed-TTS（片头/片尾/VO/个人推荐） | 本仓库 `skills/volcengine-tts/scripts/volcengine_tts.py` |
| `ai-daily-podcast` | 单人 TTS 合成脚本 `generate_tts_solo.py`（VO 合成） | 本仓库 `skills/ai-daily-podcast/scripts/generate_tts_solo.py` |
| `aliyun-tingwu-transcribe` | 原声转写（词级时间戳 JSON） | 本仓库 `skills/aliyun-tingwu-transcribe/` |
| `bili-cli` | B站搜索/音频下载（`bili search` / `bili audio --no-split`） | `pipx install bilibili-cli` |
| `ffmpeg` / `ffprobe` | 剪切、混音、包络、组装、探测 | Homebrew |
| 小宇宙 Cookie | 上传鉴权（可选，不上传时不需要） | `~/.xiaoyuzhou_auth.json`（`$XYZ_AUTH_FILE` 可覆盖） |

### 环境变量（`~/.zshrc`）

`VOLCENGINE_TTS_APPID` / `VOLCENGINE_TTS_ACCESS_TOKEN` / `VOLCENGINE_TTS_SPEAKER`（默认温暖男声 `zh_male_wennuanahu_uranus_bigtts`）。

### 固定 BGM（小宇宙固定曲目，不可换）

- 曲目：由 `config/profile.json` 的 `paths.bgm_biography` 指定（李自在默认 profile 用的是 ElevenLabs 生成的 Quiet_Reflections，145s，均值约 -18dB，连续织体，无静音空洞；**受 ElevenLabs 授权条款约束，不随本仓库分发，需自备同类曲目**）
- 用途：收束段（正文最后一段旁白）起垫入，延续到片尾口播结束，再渐强尾奏
- 选择 BGM 前先测电平：`ffmpeg -i <bgm> -af volumedetect -f null -`；**均值低于 -25dB 或含长静音空洞的曲目不可用**（曾踩坑：BGM 库冥想曲均值 -27dB 且稀疏，混入后几乎不可闻）

## 品牌文案（固定，不可改）

### 片头（约 12-15 秒）

```
[自然叙述地] 欢迎收听《李自在AI人物志》。我是李自在。
[平静地] 在数字的微光里，读懂改变世界的人。
[略带停顿] 今天我们要讲述的人物是，{人物名}。
```

### 片尾（约 20-25 秒，自动接 BGM 尾）

```
[平稳地] 以上就是本期《李自在AI人物志》的全部内容。
[平静地] 每一个在浪潮里折腾的灵魂，都在为未来的技术写下注释。
[自然叙述地] 如果你喜欢今天的内容，欢迎点赞、订阅并分享给身边的科技同路人。
[缓缓收束地] 感谢收听，我是李自在。我们下期再见。
```

### BGM 包络规则（实测固化）

BGM 从**正文最后一段旁白（收束段，如"……逝世"句）开始时**垫入，与片尾共用同一条连续包络：

| 时段 | BGM 音量 |
|---|---|
| 收束段旁白起，1.5s 淡入 | 0 → 0.125 |
| 旁白/片尾口播期间 | 0.125（压低，不盖人声） |
| 片尾口播读完后 1.5s 线性渐强 | 0.125 → 0.55 |
| 保持 4s | 0.55 |
| 3s 渐弱收尾 | 0.55 → 0 |

- 总尾奏时长 = 口播结束 + 8.5s；禁止拼接/循环/剪切重复，必须取单段连续旋律，音量用平滑包络无断层。
- **跨段连续性**：收束段与片尾的 BGM 用同一源文件的两个连续偏移（收束段用 `atrim=end=<vo13时长>`，片尾用 `atrim=start=<vo13时长>`），保证接缝处音量与旋律无缝。

### 情感标签约束（强制）

沿用 `biography-writer/references/podcast-script-guide.md` 的标签规范：禁综艺感标签（`[热情欢快]` 等）、禁任何含"语速/放慢/加快/提速/减速"字样的标签；中性标签（`[平静地]`/`[平稳地]`/`[平静叙述地]`/`[自然叙述地]`）占 70% 以上，点睛标签（`[语调略沉]`/`[平静引用地]`/`[缓缓收束地]` 等）全文不超过 8 处。

## 流水线总览

### 阶段 0：原声素材收集（B站优先；用户要求"不用国外素材"时只用 B站）

#### 0.1 搜索方向

按大纲关键节点确定方向，同一人物至少覆盖 3-4 个方向：综合采访/访谈、成长故事/纪录片、演讲/发布会、争议/危机/回应、播客/对谈、人物专题。筛选优先级：**人物本人长篇讲述 > 剪辑片段**。

```bash
# B站（稳定，无需登录）
bili search "{人物名} 记者招待会" --type video -n 10
opencli bilibili search "{人物名} 答记者问" -f yaml
# YouTube（仅当用户未限制国外素材时使用，需代理 + Chrome cookies + EJS）
yt-dlp --proxy http://127.0.0.1:7897 --cookies-from-browser chrome --remote-components ejs:github \
  --dump-json "ytsearch5:{name} interview" 2>/dev/null | jq -r '.title, .duration_string, .webpage_url'
```

候选记录到 `00_raw/voice_sources.md`：平台/标题/URL 或 BV/时长/覆盖节点/备注。

#### 0.2 下载音频

```bash
cd "{episode_dir}"
bili audio BVxxxxxxxx --no-split -o "00_raw/audio/"
```

- `--no-split` 保存完整 m4a（跳过 PyAV 切分），后续用 ffmpeg 处理。
- 实测（E08 朱镕基）：短片段（25s-2.5min）秒级下载；输出按视频标题命名，中文文件名可直接使用。

#### 0.3 转写（词级时间戳，SOT 剪辑唯一依据）

```bash
python3 ../aliyun-tingwu-transcribe/scripts/transcribe_audio.py \
  "00_raw/audio/xxx.m4a" --speaker-count 2 --output-dir "00_raw/transcripts/"
```

- **必须用技能自带 venv**：`本技能 venv 或装好 oss2 的 python3`（系统 python3 缺 oss2）。
- 缺依赖先装：`pip install oss2`。
- JSON（词级毫秒时间戳）必须落盘保留；md 供人工阅读。转写前需 OSS 配置 `~/.config/aliyun-oss/config.json`。
- 实测：每个 25s-2.5min 片段转写约 15-60s。

#### 0.4 SOT 候选筛选

对照大纲关键节点，从转写稿挑出情绪到位、信息密度高、20-45 秒、自成一段的人物原话，记入 `voice_sources.md`：素材名、时间窗、时长、转写文字、对应大纲节点。**只选人物本人原话**，第三方评论一律转 VO。

### 阶段 1：就绪检查

1. `40_final.md` 必存在（缺失 → 先运行 biography-writer，停止）。
2. `00_raw/transcripts/*.json` 必存在（词级时间戳；缺失 → 执行阶段 0）。
3. 目标：5-8 段 SOT，覆盖 5-8 个情绪关键点/人生转折点；正片总时长 8-20 分钟。

### 阶段 2：访谈脚本（52_documentary_script.md + vo_*.txt）

按 `biography-writer/references/documentary-podcast-guide.md` 改写：

- **VO 段**：每段 40-90 秒（约 120-260 字），负责铺垫/承接；**引语让给 SOT**，旁白不重复原声内容。每段 VO 单独存 `vo_{NN}.txt`（带情感标签），13 段左右。
- **SOT 段**：标注 `【SOT｜人物名原声，XX秒｜来源：…】` + 原声转写文字 + 时间窗。
- 正文组装顺序：VO/SOT 交替，段间 0.35s 停顿，无 BGM。
- 脚本合规自检：涉台/港/疆/藏表述按 biography-writer 内容合规红线处理；播客比文本更敏感，不通过不得进 TTS。

### 阶段 3：VO 旁白合成

```bash
source ~/.zshrc
for i in 01 02 ... 13; do
  python3 ../ai-daily-podcast/scripts/generate_tts_solo.py \
    --content-file "vo_${i}.txt" --output-file "vo_${i}.mp3"
done
```

- 每段独立合成（约 10-70s/段），13 段总耗时约 1 分钟。
- 合成后逐段 `ffprobe` 探测时长，记录用于时点计算。

### 阶段 4：SOT 剪切（实测踩坑全部固化）

用词级 JSON 定位句子边界，按以下规范剪切：

```bash
# 通用模板：-ss 必须在 -i 之前（输入 seek）！
ffmpeg -y -hide_banner -loglevel error \
  -ss <句首秒> -t <时长> -i "00_raw/audio/xxx.m4a" \
  -af "afade=t=in:st=0:d=0.3,apad=pad_dur=1.5,afade=t=out:st=<淡出起点>:d=0.4,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=24000,aformat=channel_layouts=mono" \
  -c:a libmp3lame -b:a 96k sot_XX.mp3
```

**踩坑 1（必须遵守）**：`-ss` 放在 `-i` **之后**（输出 seek）与 `loudnorm` 组合时，中段切片会输出**全静音**（实测 E08 sot_03 完全无声，max_volume -91dB）。`-ss` 必须放 `-i` 之前（输入 seek）。

**踩坑 2（必须遵守）**：给 BGM/素材做 `atrim` 后再用 `volume='if(lt(t,...))'` 包络时，`atrim` 会保留源时间戳，导致包络的 `t` 从源偏移起算、判定错乱（实测 BGM 尾奏在 17s 后消失）。**必须在 atrim 后加 `asetpts=PTS-STARTPTS`**。

**淡出时机（听感关键）**：
- 词级句尾 + 0.6s 为剪切终点；淡出起点 = **句尾 + 0.7s**（曾因只晚 0.4s 被反馈"话没说完就被减弱"），淡出时长 0.4s。
- 若下一句紧接、无空隙（词级上一句 end_time == 下一句 begin_time），剪切终点 = 句尾本身（`-t = 句尾-句首`），淡出落在句尾前，**绝不允许切在句中**（曾踩坑：终点落在下一句开头残留半句"我们市政府的人"）。

**验证（每段必做）**：
```bash
ffmpeg -hide_banner -i sot_XX.mp3 -af volumedetect -f null - 2>&1 | grep max_volume   # 必须有声（>-30dB）
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 sot_XX.mp3
```
- 逐秒窗口 RMS 检查无静音空洞（用 ffmpeg 解码 s16le + Python 计算）。
- 必要时把剪切产物再转写一遍，核对句子是否完整、无半句残留。

### 阶段 5：访谈正片组装（60_podcast.mp3）

按 `52_documentary_script.md` 顺序，VO/SOT 交替，段间插入 0.35s 静音，**正文无 BGM**：

```bash
# 先生成停顿片
ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 0.35 -c:a libmp3lame -b:a 96k sil_035.mp3
# 用 Python 拼 filter_complex：每个输入 aresample=24000 + aformat mono，再 concat=n=...:v=0:a=1
# 输出 -c:a libmp3lame -b:a 96k 60_podcast.mp3
```

### 阶段 6：收束段 BGM + 品牌片头/片尾

#### 6.1 品牌片头/片尾口播

```bash
source ~/.zshrc && python3 scripts/generate_brand_audio.py \
  --episode-dir "~/李自在AI人物志/E{NN}.{人物名}" \
  --person "{人物名}" --position both
```

产物：`intro.mp3`（约 10.5s）、`outro.mp3`（口播，约 17s）。

#### 6.2 收束段 BGM（vo13_bgm.mp3）

固定 BGM 从正文最后一段旁白（收束段 VO13）起垫入：

```bash
# vo13_bgm.mp3：BGM 源偏移 0 起，淡入 1.5s → 0.125，持续到 VO13 结束
ffmpeg -y -hide_banner -loglevel error -i vo_13.mp3 -i "$BGM" \
  -filter_complex "[1:a]atrim=end=<vo13时长>,asetpts=PTS-STARTPTS,volume='if(lt(t,1.5),0.125*t/1.5,0.125)':eval=frame[bg];[0:a][bg]amix=inputs=2:duration=first:normalize=0,aresample=24000,aformat=channel_layouts=mono[out]" \
  -map "[out]" -c:a libmp3lame -b:a 96k vo13_bgm.mp3
```

#### 6.3 片尾 BGM（outro_music.mp3）

BGM 源偏移从 `<vo13时长>` 继续（与收束段无缝），口播期间 0.125，口播结束（约 13.27s）后 1.5s 渐强到 0.55、保持 4s、3s 渐弱：

```bash
ffmpeg -y -hide_banner -loglevel error -i outro.mp3 -i "$BGM" \
  -filter_complex "[1:a]atrim=start=<vo13时长>:end=<vo13时长+22>,asetpts=PTS-STARTPTS,volume='if(lt(t,13.27),0.125,if(lt(t,14.77),0.125+0.425*(t-13.27)/1.5,if(lt(t,18.77),0.55,if(lt(t,21.77),0.55*(1-(t-18.77)/3),0))))':eval=frame[bg];[0:a][bg]amix=inputs=2:duration=longest:normalize=0,aresample=24000,aformat=channel_layouts=mono[out]" \
  -map "[out]" -c:a libmp3lame -b:a 96k outro_music.mp3
```

- 13.27s 是片尾口播的实测结束点，须用 `ffmpeg -af silencedetect` 复核每期实际值。
- 混音后必查：`ffprobe` 时长 + 分段 RMS，确认口播期 BGM 压低、尾奏清晰（约 -17~-22dB）。

### 阶段 7：整期组装（episode.mp3）

顺序：`intro.mp3` → `60_podcast.mp3`（含 vo13_bgm 收束段）→ `outro_music.mp3`。统一重采样 **24000Hz 单声道、96kbps MP3**，用 ffmpeg `concat=n=3` filter。自检：时长 = 各段之和（误差 < 5s）。

### 阶段 8：episode_meta.json + config.json（可不上传）

#### 8.1 生成 episode_meta.json

按 `merge_audio.py` 输出格式写：`output_path / duration_seconds / duration_human / size_bytes / size_mb / bitrate / sample_rate / segments{intro,main,outro}`（含各段 path/duration/duration_human）。

#### 8.2 生成 config.json

```bash
python3 scripts/generate_config.py \
  --episode-dir "..." --highlight "≤15字" --intro "30-80字人物介绍" [--title "自定义标题"] [--publish-at "ISO8601"]
```

- 标题默认 `E{NN}.{人物名}：{highlight}`。
- **description 时点必须按实际段落时长重算**（不是章节字数比例）：片头结束为起点，按 VO/SOT 实际时长 + 0.35s 停顿逐段累计；每个 SOT 一条时点，标题用段落主题（如"原声：地雷阵与万丈深渊"）。生成后用脚本重写 `config.json` 的 description。
- 上传后回写 episode_id / xiaoyuzhou_url（脚本自动处理）。

#### 8.3 上传（可选）

```bash
python3 scripts/upload_episode.py \
  --episode-dir "..." [--publish-at "..."] [--headed]
```

新 UI 注意：先点「点击上传播客」打开弹窗，弹窗内才是 file input；AI 声明用 `input[role="switch"]` + `data-checked`；定时发布用 Mantine Group `data-active`；音频处理完成标志 = 页面出现 `mm:ss` + MB/分钟。

## 实测经验与踩坑速查（E08 朱镕基）

| 环节 | 问题 | 修复 |
|---|---|---|
| 转写 | 系统 python3 缺 oss2 | 用装好 oss2 的 python3（或 transcribe 技能 venv） |
| SOT 剪切 | `-ss` 在 `-i` 后 + loudnorm → 整段静音 | `-ss` 放 `-i` 前（输入 seek） |
| SOT 剪切 | 淡出只晚句尾 0.4s → 听感"话没说完被减弱" | 淡出起点 = 句尾 + 0.7s，时长 0.4s |
| SOT 剪切 | 终点落在下一句开头 → 残留半句 | 无空隙时终点 = 句尾本身，禁切句中 |
| BGM 混音 | `atrim` 保留源时间戳 → 包络 t 错乱、尾奏消失 | atrim 后加 `asetpts=PTS-STARTPTS` |
| BGM 选择 | 库内冥想曲均值 -27dB 且稀疏 → 混入后不可闻 | 先测 `volumedetect`；均值 <-25dB 或静音空洞多的曲目不用；固定用 ElevenLabs_Quiet_Reflections |
| BGM 时机 | 从片尾 8.5s 才起 → 用户反馈"太晚/没 BGM" | 从正文收束段（VO13"……逝世"句）起垫入，延续到片尾 |
| BGM 音量 | 旁白期 0.25 偏大 | 旁白期 0.125，口播结束后渐强 0.55 |
| 时点 | 按章节字数比例 → 与实际段落不符 | 按 VO/SOT 实际时长 + 0.35s 停顿逐段累计 |

## 错误处理

| 情况 | 处理 |
|---|---|
| 40_final.md 缺失 | 停止，先运行 biography-writer |
| transcripts JSON 缺失 | 执行阶段 0 采集 + 转写 |
| 转写缺 oss2 | venv pip install oss2 |
| SOT 剪切产物静音 | 检查 `-ss` 是否在 `-i` 前；`volumedetect` 验证 |
| 火山引擎环境变量缺失 | 停止，提示配置 |
| BGM 曲目电平过低/有空洞 | 换曲或 loudnorm 归一化后再混 |
| 上传时页面跳转登录 | 停止，运行 `--login` |
| create API 返回 200 但没 eid | 三重验证 fallback（API→URL→list） |
| 上传后 list 二次确认查无此单集 | 多为误报：创建后 URL 停在单集详情页，脚本未回列表页、未触发 list API（已修复：验证前强制回到列表页）。真正未发布时看 `reviewStatus`：`PENDING`＝平台审核中（勾选 AI 生成的单集强制审核），公开页显示"找不到了"，后台无"发布"按钮可点，只能等审核通过（E08 实测） |

### 上传后的状态判定（E08 实测固化）

- 公开页可用性判定：已发布单集 HTML 含 `og:title`/`<title>E{NN}... - 李自在AI人物志`；未发布则页面内容为"找不到了"（HTTP 仍是 200，SPA 假象）。
- 后台状态判定：list API 中 `status=NORMAL / reviewStatus=APPROVED` 才是已公开；`status=INITIALIZED / reviewStatus=PENDING` 为「单集审核中」，后台编辑页显示"单集资料正在审核，可以修改后提交"，公开链接暂时 404。
- AI 生成单集：勾选「本音频为 AI 生成」后强制进审核队列，创作者侧无发布/绕过入口；不要取消勾选规避审核（违反平台规范）。E01–E07 均为 APPROVED，审核通过后会正常上线。

## 触发词与示例

- "帮我把 E09.xxx 的传记做成访谈式人物志（VO/SOT）"
- "给 E08 生成片头片尾并合并 episode.mp3"
- "E09 定时发布，明早 8 点"
- "把这篇传记转成有人物原声的访谈播客"

调用示例：

> 帮我把 E09.xxx 做成访谈式人物志（VO 旁白 + 原声 SOT），亮点总结「xxx」，定时明早 8 点发布
