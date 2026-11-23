#!/usr/bin/env python3
"""
「李自在AI人物志」片头/片尾品牌音频生成器

复用 volcengine-tts skill 的 synthesize() 接口，与 biography-writer、
ai-daily-podcast 共用同一套火山引擎 Seed-TTS 引擎，保证音色统一。

片头模板（约 12-15 秒）：
    [自然叙述地] 欢迎收听《李自在AI人物志》。我是李自在。
    [平静地] 在数字的微光里，读懂改变世界的人。
    [略带停顿] 今天我们要讲述的人物是{人物名}。

片尾模板（约 20-25 秒）：
    [平稳地] 以上就是本期《李自在AI人物志》的全部内容。
    [平静地] 每一个在浪潮里折腾的灵魂，都在为未来的技术写下注释。
    [自然叙述地] 如果你喜欢今天的内容，欢迎点赞、订阅并分享给身边的科技同路人。
    [缓缓收束地] 感谢收听，我是李自在。我们下期再见。

用法：
    python3 generate_brand_audio.py --episode-dir E01.山姆奥特曼 --person 山姆奥特曼
    python3 generate_brand_audio.py --episode-dir E01.山姆奥特曼 --person 山姆奥特曼 --position outro
    python3 generate_brand_audio.py --episode-dir E01.山姆奥特曼 --person 山姆奥特曼 --speaker zh_male_wennuanahu_uranus_bigtts
"""

import argparse
import os
import sys
import time

# ─── 品牌文案模板 ──────────────────────────────────────────
# 情感标签遵循 biography-writer 的 podcast-script-guide.md 规范：
# - 禁用任何语速控制类标签（[放慢语速]/[加快语速]/[放慢]/[加快]/[提速]/[减速] 等）
# - 节奏感由文字本身的标点和断句承担

INTRO_TEMPLATE = (
    "[自然叙述地] 欢迎收听《李自在AI人物志》。我是李自在。\n\n"
    "[平静地] 在数字的微光里，读懂改变世界的人。\n\n"
    "[略带停顿] 今天我们要讲述的人物是，{person}。"
)

OUTRO_TEMPLATE = (
    "[平稳地] 以上就是本期《李自在AI人物志》的全部内容。\n\n"
    "[平静地] 每一个在浪潮里折腾的灵魂，都在为未来的技术写下注释。\n\n"
    "[自然叙述地] 如果你喜欢今天的内容，欢迎点赞、订阅并分享给身边的科技同路人。\n\n"
    "[缓缓收束地] 感谢收听，我是李自在。我们下期再见。"
)


def synthesize_with_retry(text, output_path, speaker_id, app_id, access_key,
                          audio_format="mp3", sample_rate=24000, uid="lizz-bio",
                          max_retries=3):
    """调用 volcengine_tts.synthesize，带重试。"""
    import _paths
    _vts = _paths.skill_dir("volcengine-tts")
    if not _vts:
        raise ImportError(
            "volcengine-tts skill not found; set $PODCAST_SKILLS_ROOT "
            "or install it next to this skill")
    sys.path.insert(0, str(_vts / "scripts"))
    from volcengine_tts import synthesize

    for attempt in range(max_retries):
        try:
            synthesize(
                text=text,
                speaker_id=speaker_id,
                app_id=app_id,
                access_key=access_key,
                output_path=output_path,
                audio_format=audio_format,
                sample_rate=sample_rate,
                uid=uid,
                use_ffmpeg=True,
            )
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            raise RuntimeError("TTS output file is empty or missing")
        except Exception as e:
            print(f"  [TTS ERR] Attempt {attempt+1}/{max_retries}: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                print(f"  Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"  All {max_retries} attempts failed.", file=sys.stderr)
                return False


def main():
    parser = argparse.ArgumentParser(description="「李自在AI人物志」片头/片尾品牌音频生成")
    parser.add_argument("--episode-dir", required=True,
                        help="集数目录（绝对或相对路径），如 E01.山姆奥特曼")
    parser.add_argument("--person", required=True,
                        help="人物名（会填入片头模板），如「黄仁勋」「Midjourney 创始人 David Holz」")
    parser.add_argument("--position", choices=["intro", "outro", "both"], default="both",
                        help="生成片头/片尾/两者（默认 both）")
    parser.add_argument("--speaker", default=None,
                        help="火山引擎音色 ID（默认读 VOLCENGINE_TTS_SPEAKER 环境变量）")
    parser.add_argument("--app-id", default=None,
                        help="火山引擎 APP ID（默认读 VOLCENGINE_TTS_APPID 环境变量）")
    parser.add_argument("--access-key", default=None,
                        help="火山引擎 Access Token（默认读 VOLCENGINE_TTS_ACCESS_TOKEN 环境变量）")
    args = parser.parse_args()

    app_id = args.app_id or os.environ.get("VOLCENGINE_TTS_APPID")
    access_key = args.access_key or os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")
    speaker_id = args.speaker or os.environ.get("VOLCENGINE_TTS_SPEAKER")

    if not app_id:
        print("[ERR] --app-id 或 VOLCENGINE_TTS_APPID 环境变量必填", file=sys.stderr)
        sys.exit(1)
    if not access_key:
        print("[ERR] --access-key 或 VOLCENGINE_TTS_ACCESS_TOKEN 环境变量必填", file=sys.stderr)
        sys.exit(1)
    if not speaker_id:
        print("[ERR] --speaker 或 VOLCENGINE_TTS_SPEAKER 环境变量必填", file=sys.stderr)
        sys.exit(1)

    # 归一化目录为绝对路径
    episode_dir = os.path.abspath(args.episode_dir)
    if not os.path.isdir(episode_dir):
        print(f"[ERR] 集数目录不存在: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    intro_path = os.path.join(episode_dir, "intro.mp3")
    outro_path = os.path.join(episode_dir, "outro.mp3")

    print(f"集数目录: {episode_dir}")
    print(f"人物: {args.person}")
    print(f"音色: {speaker_id}")
    print(f"生成范围: {args.position}")
    print()

    results = {}

    if args.position in ("intro", "both"):
        intro_text = INTRO_TEMPLATE.format(person=args.person)
        print(f"[INTRO] 文案:\n{intro_text}\n")
        print(f"[INTRO] 合成中... → {intro_path}")
        if synthesize_with_retry(intro_text, intro_path, speaker_id, app_id, access_key):
            size = os.path.getsize(intro_path)
            print(f"[INTRO] ✅ 成功 ({size/1024:.1f}KB) → {intro_path}")
            results["intro"] = intro_path
        else:
            print(f"[INTRO] ❌ 失败", file=sys.stderr)
            sys.exit(1)

    if args.position in ("outro", "both"):
        outro_text = OUTRO_TEMPLATE
        print(f"\n[OUTRO] 文案:\n{outro_text}\n")
        print(f"[OUTRO] 合成中... → {outro_path}")
        if synthesize_with_retry(outro_text, outro_path, speaker_id, app_id, access_key):
            size = os.path.getsize(outro_path)
            print(f"[OUTRO] ✅ 成功 ({size/1024:.1f}KB) → {outro_path}")
            results["outro"] = outro_path
        else:
            print(f"[OUTRO] ❌ 失败", file=sys.stderr)
            sys.exit(1)

    print(f"\n{'='*50}")
    print("品牌音频生成完成")
    for k, v in results.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
