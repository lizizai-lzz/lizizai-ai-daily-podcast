# Profile —— 双轨制配置

本仓库的所有技能采用**双轨制**：仓库内的默认值就是「李自在AI日报」品牌版的完整工作流（音色、品牌口播、节目 ID、目录约定），装完即用；想做成你自己的节目，只需一份 profile 覆盖品牌层。

## 优先级（从高到低）

1. **环境变量**：`PODCAST_BGM`（片头片尾 BGM 路径）、`PODCAST_SHOW_ID`（小宇宙节目 ID）、`XYZ_AUTH_FILE`（小宇宙登录 cookie 路径）、`PODCAST_SKILLS_ROOT`（技能安装根目录）、`VOLCENGINE_TTS_APPID` / `VOLCENGINE_TTS_ACCESS_TOKEN` / `DASHSCOPE_API_KEY` 等 API 密钥
2. **`config/profile.json`**（本文件同目录，不存在则跳过）
3. **`config/profile.default.json`**（李自在品牌默认值，与各 SKILL.md 中写死的值一致）

## 使用方法

```bash
cd lizizai-ai-daily-podcast
cp config/profile.example.json config/profile.json
# 编辑 config/profile.json，填入你的节目名、音色 ID、小宇宙节目 ID……
```

执行技能时，agent 在 Phase 0 会先读 `config/profile.json`；脚本侧由环境变量和内建默认值兜底，两条路都不通时才需要手工干预。

## 设计说明

- **为什么品牌文案不写进脚本**：品牌口播（开场/收尾、公众号名、主持人名）是生成脚本时的提示词素材，由 agent 按 profile 注入；脚本只处理音频与路径，保证双轨互不干扰。
- **音色 ID 均为火山引擎公共音色**，非克隆音色；想要专属声音请参考 `skills/volcengine-tts/SKILL.md` 的声音克隆能力（Seed-ICL），并把克隆音色 ID 填进 profile。
- **`paths.bgm_biography` 留空**：人物志 BGM（ElevenLabs 生成曲）受其授权条款约束不随库分发，需自备电平达标的曲目（均值 > -25dB、无长静音空洞，详见 `skills/lizz-biography-podcast/SKILL.md`）。
