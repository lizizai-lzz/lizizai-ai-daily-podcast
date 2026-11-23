#!/usr/bin/env python3
"""
Single-speaker TTS generator for AI Daily Podcast — 开源解读 / 行业洞见.

Wraps volcengine-tts to generate a single MP3 from a plain-text script file.
Interface matches the podcast-generation script pattern (--content-file / --output-file).
The episode gets the same 5s intro bed and 8s outro tail as the two-host daily
brief (shared defaults in podcast_audio.py); --no-music turns it off.

Usage:
  python3 generate_tts_solo.py \
    --content-file script_industry_trends_2026-05-20.md \
    --output-file industry_trends_2026-05-20.mp3 \
    --speaker zh_male_liufei_uranus_bigtts
"""

import argparse
import os
import sys
import time
import subprocess
import json
import re
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

INDUSTRY_SPEAKER = "zh_male_liufei_uranus_bigtts"

from podcast_audio import add_music_arguments, build_intro_outro, concat_mp3  # noqa: E402


def get_duration(filepath):
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", filepath],
        capture_output=True, text=True,
    )
    return float(json.loads(probe.stdout)["format"]["duration"])


def synthesize_text(text, output_path, speaker_id, app_id, access_key,
                    audio_format="mp3", sample_rate=24000, uid="workbuddy",
                    max_retries=3):
    """Call volcengine_tts synthesize with retry logic."""
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
            print(f"  [TTS ERR] Attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                wait = 3 * (attempt + 1)
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  All {max_retries} attempts failed.")
                return False


def split_into_segments(text, max_chars=2000):
    """Split text into segments at paragraph boundaries, respecting max_chars limit."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    segments = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            segments.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        segments.append(current.strip())

    return segments


def preprocess_script(text: str) -> str:
    """Drop non-spoken content that should never reach TTS.

    Defensive layer. Even if the script generator drifts and emits meta info
    (blockquote specs, horizontal rules, YAML front matter, standalone spec
    lines, heading lines), we must not let it get synthesized as audio.
    """
    # 1) YAML front matter (--- ... ---) at the very top of the file
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)

    # 2) Markdown blockquotes (lines starting with '>'). These are never spoken
    # content in our scripts — they only appear as leaked "播客定位" specs.
    # Drop whole blockquote lines (including multi-line blockquotes).
    text = re.sub(r"^[ \t]*>.*$", "", text, flags=re.MULTILINE)

    # 3) Standalone horizontal rules ('---', '***', '___' on their own line).
    # Must run AFTER YAML front matter removal. A bare '---' line is never
    # spoken content in our scripts.
    text = re.sub(r"^[ \t]*([-*])\1{2,}[ \t]*$", "", text, flags=re.MULTILINE)

    # 4) Line 1 is the episode H1 title — it goes into config.json and the cover,
    # never into the audio (the daily-brief parser skips '#' lines for the same
    # reason). The module spec allows no heading other than that one.
    text = re.sub(r"^[ \t]*#+.*$", "", text, flags=re.MULTILINE)

    # 5) Standalone spec-leak lines — patterns that match the known leaked
    # meta info from 2026-07-09 (and likely future drift):
    #    "时长目标：8-12 分钟（2400-3600 字）"
    #    "单人播报 · 10 条 AI 热点新闻 · 每条带观点点评"
    #    "单人深度分析 · 01fish 观点输出体 · 三层论证（现象→因果→行动）"
    #    "标题：Peter Steinberger:xxx"
    # Match conservatively: only drop a line if it starts with one of these
    # spec markers and contains no emotion tag.
    spec_patterns = [
        r"时长目标",
        r"字数范围",
        r"^单人播报\b",
        r"^单人深度分析\b",
        r"^标题[：:]",
    ]
    lines = text.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped and not re.search(r"^\[.+?\]", stripped):
            # line has no emotion tag — check if it matches any spec pattern
            if any(re.search(p, stripped) for p in spec_patterns):
                continue
        filtered.append(line)
    text = "\n".join(filtered)

    # 6) Strip inline bold markers, keeping the bracket emotion tags
    text = re.sub(r"\*\*", "", text)

    # 7) Collapse 3+ consecutive blank lines down to 2 (TTS segmenter splits on \n\n)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_speaker(explicit_speaker, content_file, env_speaker):
    """Resolve voice_type, with a hard industry default independent of env."""
    if explicit_speaker:
        return explicit_speaker
    if "industry_trends" in os.path.basename(content_file):
        return INDUSTRY_SPEAKER
    return env_speaker


def main():
    parser = argparse.ArgumentParser(description="Single-speaker TTS for podcast scripts")
    parser.add_argument("--content-file", required=True, help="Input script file (.md or .txt)")
    parser.add_argument("--output-file", required=True, help="Output MP3 path")
    parser.add_argument("--speaker", default=None,
                        help="Speaker voice_type; industry_trends content defaults to "
                             f"{INDUSTRY_SPEAKER}, otherwise uses VOLCENGINE_TTS_SPEAKER")
    parser.add_argument("--app-id", default=None,
                        help="App ID (or VOLCENGINE_TTS_APPID env)")
    parser.add_argument("--access-key", default=None,
                        help="Access key (or VOLCENGINE_TTS_ACCESS_TOKEN env)")
    parser.add_argument("--format", default="mp3", choices=["mp3", "wav"])
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--uid", default="workbuddy")
    parser.add_argument("--max-chars", type=int, default=2000,
                        help="Max chars per TTS segment")
    add_music_arguments(parser)
    args = parser.parse_args()

    app_id = args.app_id or os.environ.get("VOLCENGINE_TTS_APPID")
    access_key = args.access_key or os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")
    speaker_id = resolve_speaker(
        args.speaker,
        args.content_file,
        os.environ.get("VOLCENGINE_TTS_SPEAKER"),
    )

    if not app_id:
        print("[ERR] --app-id or VOLCENGINE_TTS_APPID env is required")
        sys.exit(1)
    if not access_key:
        print("[ERR] --access-key or VOLCENGINE_TTS_ACCESS_TOKEN env is required")
        sys.exit(1)
    if not speaker_id:
        print("[ERR] --speaker or VOLCENGINE_TTS_SPEAKER env is required")
        sys.exit(1)

    with open(args.content_file, "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    original_len = len(raw_text)
    text = preprocess_script(raw_text)

    stripped_len = original_len - len(text)
    if stripped_len > 0:
        print(f"[PREPROCESS] Stripped {stripped_len} chars of non-spoken content "
              f"(front matter / blockquotes / rules / spec leak lines / title heading)")

    if not text:
        print("[ERR] Content file is empty after preprocessing")
        sys.exit(1)

    segments = split_into_segments(text, args.max_chars)
    print(f"Content: {len(text)} chars → {len(segments)} segments")
    print(f"Speaker: {speaker_id}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)

    segment_files = []
    for i, seg in enumerate(segments):
        seg_path = args.output_file.replace(".mp3", f"_seg{i:03d}.mp3")
        print(f"  [{i+1}/{len(segments)}] {len(seg)} chars...", end=" ", flush=True)

        if synthesize_text(seg, seg_path, speaker_id, app_id, access_key,
                           args.format, args.sample_rate, args.uid):
            dur = get_duration(seg_path)
            print(f"{dur:.1f}s")
            segment_files.append(seg_path)
        else:
            print("FAILED")
            sys.exit(1)

    # Intro/outro music bed — same fixed track and lengths as the daily brief
    music_dir = tempfile.mkdtemp(prefix="podcast_music_")
    intro_music, outro_music, outro_source = build_intro_outro(
        args, music_dir, args.sample_rate
    )

    # Concatenate [intro, segments..., outro]
    parts = ([intro_music] if intro_music else []) + segment_files
    if outro_music:
        parts.append(outro_music)

    if len(parts) == 1:
        # No music and a single TTS segment — move it into place, no re-encode.
        os.replace(parts[0], args.output_file)
    else:
        concat_mp3(parts, args.output_file)
        for sf in segment_files:
            os.remove(sf)
    for name in os.listdir(music_dir):
        os.remove(os.path.join(music_dir, name))
    os.rmdir(music_dir)

    total_dur = get_duration(args.output_file)
    size_kb = os.path.getsize(args.output_file) / 1024
    print(f"\nDone: {total_dur:.1f}s ({size_kb:.0f}KB) → {args.output_file}")
    if intro_music:
        print(f"  intro music: {args.intro_music_duration:.0f}s @ "
              f"{args.intro_music_volume}dB from {args.intro_music}")
    if outro_music:
        print(f"  outro music: {args.outro_music_duration:.0f}s @ "
              f"{args.outro_music_volume}dB from {outro_source}")


if __name__ == "__main__":
    main()
