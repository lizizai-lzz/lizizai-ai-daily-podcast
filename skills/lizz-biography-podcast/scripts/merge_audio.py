#!/usr/bin/env python3
"""
「李自在AI人物志」三段音频合并器

用 ffmpeg 把 片头 + 正片 + 片尾 拼成最终 episode.mp3。
统一重采样到 24000Hz mono，避免三段采样率/声道不一致造成的 glitch。

用法：
    python3 merge_audio.py --episode-dir E01.山姆奥特曼
    python3 merge_audio.py --episode-dir E01.山姆奥特曼 --main-audio custom.mp3
    python3 merge_audio.py --episode-dir E01.山姆奥特曼 --output final.mp3

合并顺序固定为：intro.mp3 → 正片 → outro.mp3
"""

import argparse
import os
import subprocess
import sys
import json
import re


def get_audio_meta(filepath):
    """用 ffprobe 获取音频时长（秒）和比特率。"""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", filepath],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        return None
    try:
        data = json.loads(probe.stdout)
        fmt = data.get("format", {})
        return {
            "duration": float(fmt.get("duration", 0)),
            "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
            "size_bytes": int(fmt.get("size", 0)) if fmt.get("size") else None,
        }
    except (json.JSONDecodeError, ValueError):
        return None


def format_duration(seconds):
    """把秒数转成 M:SS 格式。"""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def detect_main_audio(episode_dir):
    """自动探测集数目录里的正片音频。

    优先级：
    1. episode.mp3（本 skill 已合并过的产物）
    2. 60_podcast.mp3（biography-writer 阶段 6 新命名）
    3. podcast_*.mp3（biography-writer E01 旧命名）
    4. *.mp3 中文件最大的（兜底）
    """
    # 显式产物
    for candidate in ("episode.mp3", "60_podcast.mp3"):
        p = os.path.join(episode_dir, candidate)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p

    # 旧命名 podcast_xxx.mp3
    for name in os.listdir(episode_dir):
        if name.startswith("podcast_") and name.endswith(".mp3"):
            p = os.path.join(episode_dir, name)
            if os.path.getsize(p) > 0:
                return p

    # 兜底：最大的 mp3（排除 intro/outro）
    candidates = []
    for name in os.listdir(episode_dir):
        if name.endswith(".mp3") and not name.startswith(("intro", "outro", "episode")):
            p = os.path.join(episode_dir, name)
            if os.path.getsize(p) > 0:
                candidates.append((p, os.path.getsize(p)))
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    return None


def main():
    parser = argparse.ArgumentParser(description="「李自在AI人物志」三段音频合并")
    parser.add_argument("--episode-dir", required=True,
                        help="集数目录（绝对或相对路径）")
    parser.add_argument("--main-audio", default=None,
                        help="正片音频文件名（默认自动探测）")
    parser.add_argument("--output", default="episode.mp3",
                        help="输出文件名（默认 episode.mp3）")
    parser.add_argument("--sample-rate", type=int, default=24000,
                        help="统一采样率（默认 24000Hz，与 TTS 输出一致）")
    parser.add_argument("--bitrate", default="96k",
                        help="输出比特率（默认 96k，与 ai-daily-podcast 一致）")
    args = parser.parse_args()

    episode_dir = os.path.abspath(args.episode_dir)
    if not os.path.isdir(episode_dir):
        print(f"[ERR] 集数目录不存在: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    intro_path = os.path.join(episode_dir, "intro.mp3")
    outro_path = os.path.join(episode_dir, "outro.mp3")

    # 探测或使用指定的正片音频
    if args.main_audio:
        # 允许传相对路径（相对 episode_dir）或绝对路径
        main_path = args.main_audio if os.path.isabs(args.main_audio) \
            else os.path.join(episode_dir, args.main_audio)
    else:
        main_path = detect_main_audio(episode_dir)

    if not main_path or not os.path.isfile(main_path):
        print(f"[ERR] 找不到正片音频。请用 --main-audio 指定，或确保目录下有 60_podcast.mp3 / podcast_*.mp3",
              file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(intro_path):
        print(f"[ERR] 片头不存在: {intro_path}（请先运行 generate_brand_audio.py）", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(outro_path):
        print(f"[ERR] 片尾不存在: {outro_path}（请先运行 generate_brand_audio.py）", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.join(episode_dir, args.output)

    print(f"集数目录: {episode_dir}")
    print(f"片头: {intro_path}")
    print(f"正片: {main_path}")
    print(f"片尾: {outro_path}")
    print(f"输出: {output_path}")
    print(f"采样率: {args.sample_rate}Hz | 比特率: {args.bitrate}")
    print()

    # 三段元数据
    segments = [("intro", intro_path), ("main", main_path), ("outro", outro_path)]
    meta = {}
    total_duration = 0
    for name, path in segments:
        m = get_audio_meta(path)
        if m is None:
            print(f"[ERR] 无法读取 {name} 元数据: {path}", file=sys.stderr)
            sys.exit(1)
        meta[name] = m
        total_duration += m["duration"]
        print(f"  {name}: {format_duration(m['duration'])} | {os.path.basename(path)}")
    print(f"  合计: {format_duration(total_duration)}")
    print()

    # 用 ffmpeg concat filter 合并：统一重采样 + 转 mono + 同编码
    # 用 filter_complex 而不是 concat demuxer，避免不同编码/采样率导致的问题
    cmd = [
        "ffmpeg", "-y",
        "-i", intro_path,
        "-i", main_path,
        "-i", outro_path,
        "-filter_complex",
        f"[0:a]aresample={args.sample_rate},aformat=sample_fmts=fltp:channel_layouts=mono[a0];"
        f"[1:a]aresample={args.sample_rate},aformat=sample_fmts=fltp:channel_layouts=mono[a1];"
        f"[2:a]aresample={args.sample_rate},aformat=sample_fmts=fltp:channel_layouts=mono[a2];"
        f"[a0][a1][a2]concat=n=3:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-b:a", args.bitrate,
        output_path,
    ]
    print("[ffmpeg] 合并中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERR] ffmpeg 合并失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # 验证输出
    out_meta = get_audio_meta(output_path)
    if out_meta is None or out_meta["duration"] < total_duration - 5:
        print(f"[ERR] 输出文件异常，时长 {format_duration(out_meta['duration'] if out_meta else 0)} "
              f"< 预期 {format_duration(total_duration)}", file=sys.stderr)
        sys.exit(1)

    size_mb = out_meta["size_bytes"] / (1024 * 1024) if out_meta["size_bytes"] else 0
    print(f"\n✅ 合并成功")
    print(f"  时长: {format_duration(out_meta['duration'])}")
    print(f"  大小: {size_mb:.1f}MB")
    print(f"  输出: {output_path}")

    # 输出元数据 JSON 供 generate_config.py 消费
    meta_path = os.path.join(episode_dir, "episode_meta.json")
    meta_out = {
        "output_path": output_path,
        "duration_seconds": out_meta["duration"],
        "duration_human": format_duration(out_meta["duration"]),
        "size_bytes": out_meta["size_bytes"],
        "size_mb": round(size_mb, 2),
        "bitrate": args.bitrate,
        "sample_rate": args.sample_rate,
        "segments": {
            name: {
                "path": path,
                "duration": m["duration"],
                "duration_human": format_duration(m["duration"]),
            }
            for name, (_, path), (_, m) in zip(
                [s[0] for s in segments],
                segments,
                [(k, meta[k]) for k in [s[0] for s in segments]],
            )
        },
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=2)
    print(f"  元数据: {meta_path}")


if __name__ == "__main__":
    main()
