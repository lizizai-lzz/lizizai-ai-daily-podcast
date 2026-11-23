#!/usr/bin/env python3
"""
News-broadcast TTS generator — two hosts reading alternating news items.

Unlike generate_podcast_dual.py (which asks the podcast API to render a whole
dialogue), this script keeps the two hosts as *separate solo voices* and
synthesizes one MP3 per speaker run. That gives exact segment boundaries, so a
page-turn sound effect can be dropped between news items.

Script format (markdown, plain text):

    A: [平稳地]第一条，……
    A: [郑重地]……

    ===

    B: [平稳地]第二条，……

Speaker A uses --male-voice, speaker B uses --female-voice; emotion tags in
square brackets are passed through to the TTS engine.

Usage:
  python3 generate_news_broadcast.py \
    --content-file script_daily_brief_broadcast_2026-09-22.md \
    --output-file daily_brief_broadcast_2026-09-22.mp3 \
    --female-voice zh_female_vv_uranus_bigtts

Optional intro/outro music:
  defaults to a fixed 5s intro bed and 8s outro tail (see podcast_audio.py);
  --no-music turns it off, --intro-music {file} swaps the track.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from generate_tts_solo import get_duration, synthesize_text  # noqa: E402
from podcast_audio import (  # noqa: E402
    add_music_arguments,
    build_intro_outro,
    concat_mp3,
    make_silence,
)

import _paths

_sfx = _paths.repo_asset("assets/sfx/paper/paper-page-turn.mp3")
if _sfx is None:  # 旧版独立安装布局里去 video-shotcraft 找
    _vsc = _paths.skill_dir("video-shotcraft")
    if _vsc:
        _sfx = _vsc / "assets/audio/sfx/paper/paper-page-turn.mp3"
DEFAULT_SFX = str(_sfx) if _sfx else ""

ITEM_SEPARATOR = re.compile(r"^\s*={3,}\s*$")
SPEAKER_LINE = re.compile(r"^\*{0,2}\s*([AaBb])\s*\*{0,2}\s*[:：]\s*(.*)$")
# 收尾区块靠这句固定的收尾品牌口播辨认，避免把最后一条新闻误当成收尾放行。
CLOSING_MARK = "以上就是今天的全部内容"


def parse_items(content: str) -> list:
    """Parse an A:/B: script into items, each split by === into speaker runs.

    Returns a list of items; each item is a list of {speaker, text} runs, where
    consecutive lines from the same speaker are merged into one run.
    """
    items = []
    runs = []
    speaker = None
    lines = []

    def flush_run():
        nonlocal runs, speaker, lines
        if speaker and lines:
            runs.append({"speaker": speaker, "text": "\n".join(lines).strip()})
        speaker, lines = None, []

    for raw_line in content.split("\n"):
        line = raw_line.strip()

        if ITEM_SEPARATOR.match(line):
            flush_run()
            if runs:
                items.append(runs)
            runs = []
            continue

        if not line or line.startswith("#") or line.startswith("---"):
            continue

        match = SPEAKER_LINE.match(line)
        if match:
            new_speaker = match.group(1).upper()
            text = match.group(2).strip()
            if new_speaker != speaker:
                flush_run()
                speaker = new_speaker
            if text:
                lines.append(text)
        elif speaker:
            lines.append(line)

    flush_run()
    if runs:
        items.append(runs)

    return items


def validate_items(items: list) -> dict:
    """Check the one-host-per-news-item rule.

    Block 1 is the intro; the block carrying the closing brand line is the
    outro. Both may mix A/B (brand lines). Every block in between is a news
    item and must be read end to end by a single host — switching mid-item is
    what makes the two hosts sound like they are trading sentences instead of
    taking turns.

    Returns {"mixed": [(item_number, [speaker, ...]), ...],
             "leads": [speaker, ...]} where ``leads`` is the host who opens
    each news item, in order.
    """
    news = items[1:] if len(items) > 1 else []
    if news and CLOSING_MARK in "\n".join(
        run["text"] for run in news[-1]
    ):
        news = news[:-1]
    mixed = []
    leads = []
    for offset, item in enumerate(news):
        speakers = [run["speaker"] for run in item]
        leads.append(speakers[0])
        if len(set(speakers)) > 1:
            mixed.append((offset + 1, speakers))
    return {"mixed": mixed, "leads": leads}


def prepare_sfx(sfx_path: str, volume_db: float, work_dir: str,
                sample_rate: int) -> str:
    """Normalize the SFX clip to the podcast format and volume."""
    out_path = os.path.join(work_dir, "sfx.mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", sfx_path,
            "-af", f"volume={volume_db}dB",
            "-ar", str(sample_rate), "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "96k",
            out_path,
        ],
        check=True, capture_output=True, text=True,
    )
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a two-host news-broadcast podcast with page-turn SFX"
    )
    parser.add_argument("--content-file", required=True, help="Input A:/B: script (.md)")
    parser.add_argument("--output-file", required=True, help="Output MP3 path")
    parser.add_argument("--male-voice", default="zh_male_wennuanahu_uranus_bigtts")
    parser.add_argument("--female-voice", required=True)
    parser.add_argument("--sfx", default=DEFAULT_SFX, help="Page-turn SFX file")
    parser.add_argument("--sfx-volume", type=float, default=-8.0,
                        help="SFX gain in dB relative to the clip")
    add_music_arguments(parser)
    parser.add_argument("--sfx-gap", type=float, default=0.32,
                        help="Silence before and after the SFX, in seconds")
    parser.add_argument("--run-gap", type=float, default=0.22,
                        help="Silence between speaker runs inside one item")
    parser.add_argument("--allow-multi-speaker-items", action="store_true",
                        help="Skip the one-host-per-news-item check "
                             "(only for legacy scripts, e.g. pre-2026-09-29)")
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--access-key", default=None)
    parser.add_argument("--work-dir", default="",
                        help="Keep intermediate files here (default: temp dir)")
    parser.add_argument("--reuse", action="store_true",
                        help="Reuse cached segments in --work-dir instead of "
                             "re-synthesizing (only for re-tuning SFX/gaps)")
    args = parser.parse_args()

    with open(args.content_file, "r", encoding="utf-8") as handle:
        content = handle.read()

    items = parse_items(content)
    if not items:
        print("[ERR] No A:/B: dialogue lines found in the script")
        sys.exit(1)

    check = validate_items(items)
    if check["leads"]:
        print(f"News items read by: {' '.join(check['leads'])}")
    if check["mixed"]:
        if not args.allow_multi_speaker_items:
            print("[ERR] 每条新闻必须由一位主持从头读到尾，以下条目中途换人了：")
            for item_number, speakers in check["mixed"]:
                print(f"  第 {item_number} 条新闻：{' → '.join(speakers)}")
            print("      (A = 李自在/男声, B = 肖然/女声)"
                  "——换人只应发生在条与条之间的 === 处)")
            print("      改稿后重跑；确需沿用旧版混播脚本可加 --allow-multi-speaker-items")
            sys.exit(1)
        print(f"[WARN] {len(check['mixed'])} 条新闻是双人混播（--allow-multi-speaker-items）")
    for left, right in zip(check["leads"], check["leads"][1:]):
        if left == right:
            print(f"[WARN] 相邻两条新闻都是 {left} 声，交替顺序可能不对")

    app_id = args.app_id or os.environ.get("VOLCENGINE_TTS_APPID")
    access_key = args.access_key or os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")
    if not app_id or not access_key:
        print("[ERR] VOLCENGINE_TTS_APPID / VOLCENGINE_TTS_ACCESS_TOKEN are required")
        sys.exit(1)

    total_runs = sum(len(item) for item in items)
    print(f"Parsed {len(items)} items, {total_runs} speaker runs")

    keep_work = bool(args.work_dir)
    work_dir = args.work_dir or tempfile.mkdtemp(prefix="news_broadcast_")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)

    sfx_path = prepare_sfx(args.sfx, args.sfx_volume, work_dir, args.sample_rate)
    run_gap = make_silence(args.run_gap, os.path.join(work_dir, "gap_run.mp3"),
                           args.sample_rate)
    sfx_gap = make_silence(args.sfx_gap, os.path.join(work_dir, "gap_sfx.mp3"),
                           args.sample_rate)

    intro_music, outro_music, outro_source = build_intro_outro(
        args, work_dir, args.sample_rate
    )

    timeline = []
    run_index = 0
    for item_index, item in enumerate(items):
        if item_index > 0:
            timeline += [sfx_gap, sfx_path, sfx_gap]

        for run_offset, run in enumerate(item):
            if run_offset > 0:
                timeline.append(run_gap)

            voice = args.male_voice if run["speaker"] == "A" else args.female_voice
            digest = hashlib.md5(run["text"].encode("utf-8")).hexdigest()[:8]
            seg_path = os.path.join(
                work_dir, f"run_{run_index:03d}_{run['speaker']}_{digest}.mp3"
            )
            label = "男" if run["speaker"] == "A" else "女"
            print(f"  [{run_index + 1}/{total_runs}] {label}声 "
                  f"item{item_index + 1} {len(run['text'])}字 ...", end=" ", flush=True)

            if args.reuse and os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                print(f"cached {get_duration(seg_path):.1f}s")
                timeline.append(seg_path)
                run_index += 1
                continue

            if not synthesize_text(run["text"], seg_path, voice, app_id, access_key,
                                   "mp3", args.sample_rate, "workbuddy"):
                print("FAILED")
                sys.exit(1)

            print(f"{get_duration(seg_path):.1f}s")
            timeline.append(seg_path)
            run_index += 1

    final_timeline = ([intro_music] if intro_music else []) + timeline
    if outro_music:
        final_timeline.append(outro_music)

    concat_mp3(final_timeline, args.output_file)

    duration = get_duration(args.output_file)
    size_mb = os.path.getsize(args.output_file) / 1024 / 1024
    sfx_count = max(len(items) - 1, 0)
    print(f"\nDone: {duration:.1f}s "
          f"({int(duration) // 60}m{int(duration) % 60:02d}s), "
          f"{size_mb:.1f}MB, {sfx_count} page-turn SFX")
    if intro_music:
        print(f"  intro music: {args.intro_music_duration:.0f}s @ "
              f"{args.intro_music_volume}dB from {args.intro_music}")
    if outro_music:
        print(f"  outro music: {args.outro_music_duration:.0f}s @ "
              f"{args.outro_music_volume}dB from {outro_source}")
    print(f"  → {args.output_file}")

    if not keep_work:
        for name in os.listdir(work_dir):
            os.remove(os.path.join(work_dir, name))
        os.rmdir(work_dir)


if __name__ == "__main__":
    main()
