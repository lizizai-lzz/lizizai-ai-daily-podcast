#!/usr/bin/env python3
"""在指定日期的播客 MP3 结尾拼接「李自在真人彩蛋」插播音频。

幂等设计：每个类型拼接成功后，在播客目录写入独立标记文件
`.{type}_host_clip_applied_{date}`，重跑时自动跳过已拼接的类型，
避免把彩蛋重复拼到同一 MP3。

用法：
    python3 append_host_clip.py --date 2026-09-03
    python3 append_host_clip.py --date 2026-09-03 --podcast-dir /path/to/podcast
    python3 append_host_clip.py --date 2026-09-03 --clip /path/to/clip.mp3 --types daily_brief industry_trends

默认拼接 industry_trends，插播文件默认取本 Skill 的
assets/ai-practice-promo-2026-10-27/promo.mp3。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

NEWS_BASE = Path.home() / ".daily-ai-news"
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CLIP = SKILL_DIR / "assets" / "ai-practice-promo-2026-10-27" / "promo.mp3"


def duration_seconds(path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def append_clip(podcast_dir: Path, type_: str, date: str, clip: Path) -> dict:
    """把 clip 拼接到 {type}_{date}.mp3 末尾并做时长校验。"""
    src = podcast_dir / f"{type_}_{date}.mp3"
    if not src.exists():
        raise FileNotFoundError(f"缺少播客文件: {src}")

    marker = podcast_dir / f".{type_}_host_clip_applied_{date}"
    if marker.exists():
        final_dur = duration_seconds(src)
        print(f"SKIP: {type_} 已拼接过（标记存在），当前时长 {final_dur:.1f}s")
        return {
            "type": type_,
            "status": "skipped",
            "final_duration_seconds": round(final_dur, 2),
            "size_bytes": src.stat().st_size,
        }

    src_dur = duration_seconds(src)
    clip_dur = duration_seconds(clip)
    out_tmp = podcast_dir / f".{type_}_{date}.with_host_tmp.mp3"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-i",
            str(clip),
            "-filter_complex",
            "[0:a][1:a]concat=n=2:v=0:a=1[aout]",
            "-map",
            "[aout]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "96k",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(out_tmp),
        ],
        check=True,
    )

    final_dur = duration_seconds(out_tmp)
    expect = src_dur + clip_dur
    if abs(final_dur - expect) > 3.0:
        raise RuntimeError(
            f"{type_} 拼接后时长异常: {final_dur:.1f}s vs 期望 {expect:.1f}s"
        )

    out_tmp.replace(src)
    marker.write_text(json.dumps({"type": type_, "date": date}, ensure_ascii=False))
    return {
        "type": type_,
        "status": "appended",
        "original_duration_seconds": round(src_dur, 2),
        "clip_duration_seconds": round(clip_dur, 2),
        "final_duration_seconds": round(final_dur, 2),
        "size_bytes": src.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="拼接真人或栏目音频到播客结尾")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--clip",
        default=str(DEFAULT_CLIP),
        help="插播音频路径",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["industry_trends"],
        help="要拼接音频的播客类型",
    )
    parser.add_argument("--podcast-dir", help="播客产物目录（默认按日期推导）")
    args = parser.parse_args()

    clip = Path(args.clip).expanduser()
    if not clip.exists():
        sys.exit(f"插播音频不存在: {clip}")

    podcast_dir = (
        Path(args.podcast_dir).expanduser()
        if args.podcast_dir
        else NEWS_BASE / args.date / "industry_podcast"
    )
    if not podcast_dir.exists():
        sys.exit(f"播客目录不存在: {podcast_dir}")

    results = []
    for type_ in args.types:
        results.append(append_clip(podcast_dir, type_, args.date, clip))

    appended = [r for r in results if r["status"] == "appended"]
    if appended:
        print("✅ 播客音频拼接完成，结果：")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        print("下一步：用 ffprobe 实际时长回填 config.json 的 duration 字段。")
    else:
        print("SKIP: 所有类型均已拼接或无需处理。")


if __name__ == "__main__":
    main()
