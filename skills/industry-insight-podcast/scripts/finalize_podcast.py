#!/usr/bin/env python3
"""
Finalize config.json for the podcasts in this run — one idempotent command.

Replaces the manual Phase 3C procedure (ls + ffprobe + hand-editing JSON) and
the manual BGM credit step with deterministic code:

  1. expand ~ in every path (the Xiaoyuzhou uploader does not expand ~)
  2. backfill audio size / duration / bitrate from the real MP3 files
  3. backfill cover size / dimensions from the real PNG files
  4. append the CC BY 4.0 BGM credit to every episode description if missing
  5. fail loudly if any required field is still empty or a file is missing

Usage:
  python3 finalize_podcast.py --date 2026-09-22
  python3 finalize_podcast.py --date 2026-09-22 --podcast-dir /path/to/podcast
"""
import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

NEWS_BASE = Path.home() / ".daily-ai-news"

BGM_CREDIT = 'Music: "Inspired" by Kevin MacLeod (incompetech.com), CC BY 4.0'
# All supported shows carry the same intro/outro BGM (see podcast_audio.py), so
# every generated show owes the attribution line.
MUSIC_PODCAST_TYPES = {"daily_brief", "opensource", "industry_trends"}


def probe_audio(path: Path) -> dict:
    """Return size text, duration seconds, human duration and bitrate."""
    raw = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries",
         "format=duration,bit_rate", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    duration, _, bitrate = raw.partition(",")
    seconds = float(duration)
    size_mb = path.stat().st_size / 1024 / 1024

    bitrate_text = ""
    if bitrate.strip().isdigit():
        bitrate_text = f"{round(int(bitrate) / 1000)}kbps"

    return {
        "size": f"{size_mb:.1f}MB",
        "duration_seconds": round(seconds, 1),
        "duration_human": f"{int(seconds) // 60}:{int(seconds) % 60:02d}",
        "bitrate": bitrate_text,
    }


def png_dimensions(path: Path) -> str:
    """Read PNG width/height straight from the IHDR chunk (no dependencies)."""
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG file: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return f"{width}x{height}"


def finalize_entry(entry: dict, problems: list) -> dict:
    """Backfill one podcast entry, collecting any problems found."""
    kind = entry.get("type", "?")

    for section_name in ("audio", "cover"):
        section = entry.get(section_name) or {}
        raw_path = section.get("path", "")
        if not raw_path:
            problems.append(f"{kind}: missing {section_name}.path")
            continue
        section["path"] = str(Path(os.path.expanduser(raw_path)))
        entry[section_name] = section

    audio = entry.get("audio") or {}
    audio_path = Path(audio.get("path", ""))
    if audio_path.is_file():
        audio.update(probe_audio(audio_path))
    else:
        problems.append(f"{kind}: audio not found → {audio_path}")

    cover = entry.get("cover") or {}
    cover_path = Path(cover.get("path", ""))
    if cover_path.is_file():
        dimensions = png_dimensions(cover_path)
        cover["size"] = f"{cover_path.stat().st_size / 1024 / 1024:.1f}MB"
        cover["dimensions"] = dimensions
        if dimensions != "2048x2048":
            problems.append(f"{kind}: cover is {dimensions}, expected 2048x2048")
    else:
        problems.append(f"{kind}: cover not found → {cover_path}")

    if kind in MUSIC_PODCAST_TYPES:
        description = entry.get("description", "")
        if BGM_CREDIT not in description:
            entry["description"] = f"{description.rstrip()}\n\n{BGM_CREDIT}\n"

    for section, fields in (
        (audio, ["size", "duration_seconds", "duration_human"]),
        (cover, ["size", "dimensions"]),
    ):
        for field in fields:
            if not section.get(field):
                problems.append(f"{kind}: {field} still empty")

    return entry


def main():
    parser = argparse.ArgumentParser(
        description="Backfill and validate podcast config.json"
    )
    parser.add_argument("--date", required=True, help="Episode date, YYYY-MM-DD")
    parser.add_argument("--podcast-dir", default="",
                        help="Podcast dir (default: ~/.daily-ai-news/data/{date}/industry_podcast)")
    args = parser.parse_args()

    podcast_dir = Path(args.podcast_dir) if args.podcast_dir else (
        NEWS_BASE / "data" / args.date / "industry_podcast"
    )
    config_path = podcast_dir / "config.json"
    if not config_path.is_file():
        print(f"[ERR] config.json not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    problems = []
    config["podcasts"] = [
        finalize_entry(entry, problems) for entry in config.get("podcasts", [])
    ]

    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if problems:
        print("[FAILED] 以下问题必须修完再上传：")
        for item in problems:
            print(f"  - {item}")
        sys.exit(1)

    for entry in config["podcasts"]:
        audio, cover = entry["audio"], entry["cover"]
        print(f"  {entry['type']:16s} {audio['duration_human']:>6s}  "
              f"{audio['size']:>7s}  {audio.get('bitrate', ''):>7s}  "
              f"cover {cover['dimensions']} {cover['size']}")

    print(f"\nconfig.json 已回填并校验通过：{config_path}")


if __name__ == "__main__":
    main()
