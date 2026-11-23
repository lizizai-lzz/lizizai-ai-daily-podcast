#!/usr/bin/env python3
"""Shared audio plumbing for the AI Daily Podcast renderers.

Both renderers assemble an episode the same way:

    [intro bed 5s] + spoken segments + [outro tail 8s]

  * ``generate_news_broadcast.py`` — two-host 每日精选 (A/B runs + page-turn SFX)
  * ``generate_tts_solo.py``       — single-host 开源解读 / 行业洞见

The music defaults live here so all three shows share one sonic identity: same
track, same offset, same lengths. Track is "Inspired" by Kevin MacLeod
(incompetech.com), CC BY 4.0 — the attribution line is appended to every
episode description by ``finalize_podcast.py``.
"""

import argparse
import os
import subprocess

try:
    import _paths
    _bundled_bgm = _paths.repo_asset(
        "assets/bgm/Inspired-Cinematic-KevinMacLeod-CCBY40.mp3")
except ImportError:  # 脚本被单独复制走时
    _bundled_bgm = None
DEFAULT_MUSIC = os.environ.get("PODCAST_BGM") or (str(_bundled_bgm) if _bundled_bgm else "")
# 84s into the track: the busiest passage with no silent gap (selection method
# documented in the BGM library README).
DEFAULT_MUSIC_OFFSET = 84.0


def add_music_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the shared intro/outro BGM flags on ``parser``."""
    parser.add_argument("--intro-music", default=DEFAULT_MUSIC,
                        help="Intro music file (played before the first line)")
    parser.add_argument("--no-music", action="store_true",
                        help="Disable the intro/outro music entirely")
    parser.add_argument("--intro-music-offset", type=float,
                        default=DEFAULT_MUSIC_OFFSET,
                        help="Offset into the intro track, in seconds")
    parser.add_argument("--intro-music-duration", type=float, default=5.0,
                        help="Intro music length in seconds")
    parser.add_argument("--intro-music-volume", type=float, default=-11.0,
                        help="Intro music gain in dB")
    parser.add_argument("--outro-music", default="",
                        help="Outro music file (defaults to --intro-music)")
    parser.add_argument("--outro-music-offset", type=float, default=None,
                        help="Offset into the outro track (defaults to intro offset)")
    parser.add_argument("--outro-music-duration", type=float, default=8.0,
                        help="Outro music length in seconds")
    parser.add_argument("--outro-music-volume", type=float, default=-10.0,
                        help="Outro music gain in dB")


def build_music_segment(music_path: str, offset: float, duration: float,
                        volume_db: float, fade_in: float, fade_out: float,
                        out_path: str, sample_rate: int) -> str:
    """Cut a music segment and apply fade in/out for the intro or outro."""
    fade_out_start = max(duration - fade_out, 0.0)
    filters = (
        f"volume={volume_db}dB,"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fade_out_start:.2f}:d={fade_out}"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(offset), "-t", str(duration), "-i", music_path,
            "-af", filters,
            "-ar", str(sample_rate), "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "96k",
            out_path,
        ],
        check=True, capture_output=True, text=True,
    )
    return out_path


def make_silence(duration: float, out_path: str, sample_rate: int) -> str:
    """Render a silence clip of the given duration."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", f"{duration}",
            "-c:a", "libmp3lame", "-b:a", "96k",
            out_path,
        ],
        check=True, capture_output=True, text=True,
    )
    return out_path


def concat_mp3(parts: list, output_file: str) -> None:
    """Concatenate mp3 parts through the concat demuxer."""
    list_path = output_file + ".concat.txt"
    with open(list_path, "w", encoding="utf-8") as handle:
        for part in parts:
            handle.write(f"file '{os.path.abspath(part)}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:a", "libmp3lame", "-b:a", "96k",
            output_file,
        ],
        check=True, capture_output=True, text=True,
    )
    os.remove(list_path)


def build_intro_outro(args, work_dir: str, sample_rate: int) -> tuple:
    """Render the intro/outro music beds described by ``args``.

    Returns ``(intro_path, outro_path, outro_source)``; paths are empty strings
    when music is disabled, the file is missing, or the outro was turned off.
    """
    if args.no_music:
        args.intro_music = ""
    if args.intro_music and not os.path.exists(args.intro_music):
        print(f"[WARN] Intro music not found, skipping BGM: {args.intro_music}")
        args.intro_music = ""

    intro = ""
    if args.intro_music:
        intro = build_music_segment(
            args.intro_music, args.intro_music_offset, args.intro_music_duration,
            args.intro_music_volume, 0.3, min(1.5, args.intro_music_duration / 3),
            os.path.join(work_dir, "music_intro.mp3"), sample_rate,
        )

    outro_source = args.outro_music or args.intro_music
    outro = ""
    if outro_source:
        outro_offset = (args.outro_music_offset
                        if args.outro_music_offset is not None
                        else args.intro_music_offset)
        outro = build_music_segment(
            outro_source, outro_offset, args.outro_music_duration,
            args.outro_music_volume, 1.5, 3.0,
            os.path.join(work_dir, "music_outro.mp3"), sample_rate,
        )

    return intro, outro, outro_source
