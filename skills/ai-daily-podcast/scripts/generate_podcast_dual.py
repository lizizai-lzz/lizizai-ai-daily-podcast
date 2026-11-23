#!/usr/bin/env python3
"""
Dual-host podcast TTS generator — converts A/B dialogue scripts to podcast audio.

Parses markdown scripts with `A:` / `B:` speaker labels into nlp_texts format,
then calls Volcengine Podcast TTS WebSocket API (action=3) directly.

Fallback chain:
  1. Strict A/B parsing
  2. Loose parsing (handles bold markers, Chinese colons, indentation)
  3. If parsing yields too few lines → fallback to action=0 (let API auto-generate)

Usage:
  python3 generate_podcast_dual.py \
    --content-file script_daily_brief_2026-05-20.md \
    --output-file daily_brief_2026-05-20.mp3 \
    --transcript-file transcript_daily_brief_2026-05-20.md
"""

import argparse
import json
import os
import re
import sys

# Minimum dialogue lines to consider parsing successful
MIN_DIALOGUE_LINES = 10


def clean_text(text: str) -> str:
    """Clean markdown formatting from text."""
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"`{1,3}", "", text)
    return text.strip()


def parse_strict(content: str) -> list:
    """Strict parser: expects exact 'A: text' or 'B: text' format.

    Each dialogue line must start with 'A: ' or 'B: ' (uppercase, English colon, space).
    Continuation lines (no speaker prefix) are appended to current speaker.
    """
    lines = content.strip().split("\n")
    dialogue = []
    current_speaker = None
    current_text = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = re.match(r"^([AB])\s*:\s+(.*)", stripped)

        if match:
            if current_speaker and current_text:
                text = " ".join(current_text).strip()
                if text:
                    dialogue.append({"speaker": current_speaker, "paragraph": text})
            current_speaker = match.group(1)
            current_text = [clean_text(match.group(2))]
        elif current_speaker:
            cleaned = clean_text(stripped)
            if cleaned and not cleaned.startswith(("[", "#", "---", "```")):
                current_text.append(cleaned)

    if current_speaker and current_text:
        text = " ".join(current_text).strip()
        if text:
            dialogue.append({"speaker": current_speaker, "paragraph": text})

    return dialogue


def parse_loose(content: str) -> list:
    """Loose parser: handles common format variations.

    Accepts:
      - A: / B: (standard)
      - **A:** / **B:** (bold markers)
      - A：/ B： (Chinese colon)
      - Leading whitespace
      - Mixed case (a: / b:)
    """
    lines = content.strip().split("\n")
    dialogue = []
    current_speaker = None
    current_text = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Match various A/B formats with optional bold and Chinese/English colon
        match = re.match(
            r"^\*{0,2}\s*([AaBb])\s*\*{0,2}\s*[:：]\s*(.*)",
            stripped,
        )

        if match:
            if current_speaker and current_text:
                text = " ".join(current_text).strip()
                if text:
                    dialogue.append({"speaker": current_speaker.upper(), "paragraph": text})
            current_speaker = match.group(1).upper()
            current_text = [clean_text(match.group(2))]
        elif current_speaker:
            cleaned = clean_text(stripped)
            if cleaned and not cleaned.startswith(("[", "#", "---", "```", "|", "-")):
                current_text.append(cleaned)

    if current_speaker and current_text:
        text = " ".join(current_text).strip()
        if text:
            dialogue.append({"speaker": current_speaker.upper(), "paragraph": text})

    return dialogue


def parse_dialogue(content: str) -> tuple:
    """Try parsing with increasing looseness. Returns (dialogue, method_used)."""
    # Try strict first
    dialogue = parse_strict(content)
    if len(dialogue) >= MIN_DIALOGUE_LINES:
        return dialogue, "strict"

    # Try loose
    dialogue = parse_loose(content)
    if len(dialogue) >= MIN_DIALOGUE_LINES:
        return dialogue, "loose"

    # Return whatever we got (might be empty or too few)
    return dialogue, "loose"


def build_nlp_texts(dialogue: list, speaker_male_id: str, speaker_female_id: str) -> list:
    """Convert dialogue list to nlp_texts format for action=3."""
    nlp_texts = []
    for entry in dialogue:
        speaker = entry["speaker"]
        text = entry["paragraph"]
        if not text:
            continue

        speaker_id = speaker_male_id if speaker == "A" else speaker_female_id
        chunks = split_to_chunks(text, 290)
        for chunk in chunks:
            nlp_texts.append({"speaker": speaker_id, "text": chunk})
    return nlp_texts


def split_to_chunks(text: str, max_len: int = 290) -> list:
    """Split text into chunks at sentence boundaries, respecting max_len."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    sentences = re.split(r"([。！？；…])", text)
    current = ""

    i = 0
    while i < len(sentences):
        part = sentences[i]
        if i + 1 < len(sentences) and re.match(r"[。！？；…]", sentences[i + 1]):
            part += sentences[i + 1]
            i += 2
        else:
            i += 1

        if len(current) + len(part) > max_len:
            if current:
                chunks.append(current.strip())
            # If single part exceeds max_len, hard split
            if len(part) > max_len:
                for j in range(0, len(part), max_len):
                    chunks.append(part[j:j + max_len].strip())
                current = ""
            else:
                current = part
        else:
            current += part

    if current.strip():
        chunks.append(current.strip())

    return chunks


def generate_fallback_action0(content: str, output_file: str, transcript_file: str = "") -> bool:
    """Fallback: use action=0 to let the podcast API auto-generate from raw content."""
    print(f"[FALLBACK] Parsing failed, using action=0 (API auto-generate)")

    import _paths
    _pg = _paths.skill_dir("podcast-generation")
    skill_dir = str(_pg / "scripts") if _pg else os.path.expanduser(
        "~/.codex/skills/podcast-generation/scripts")
    if os.path.isdir(skill_dir):
        sys.path.insert(0, skill_dir)
    else:
        print(f"[ERR] podcast-generation skill not found at {skill_dir}")
        return False

    from generate import PodcastGenerator, _download_audio_with_retry

    appid = os.environ.get("VOLCENGINE_TTS_APPID")
    access_token = os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")

    generator = PodcastGenerator(
        appid=appid,
        access_token=access_token,
        audio_format="mp3",
        sample_rate=24000,
        use_head_music=False,
        return_audio_url=True,
    )

    result = generator.generate(action=0, input_text=content, timeout=600)

    saved = False
    if result.get("audio_url"):
        saved = _download_audio_with_retry(
            result["audio_url"], output_file, max_retries=3, timeout=120,
        )
    if not saved and result.get("audio_chunks"):
        audio_data = b"".join(result["audio_chunks"])
        with open(output_file, "wb") as f:
            f.write(audio_data)
        saved = True

    if saved:
        size_kb = os.path.getsize(output_file) / 1024
        print(f"[FALLBACK] action=0 succeeded: {size_kb:.0f}KB → {output_file}")

    return saved


def generate_transcript_md(dialogue: list, title: str = "") -> str:
    """Generate readable markdown transcript from dialogue."""
    lines = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    for entry in dialogue:
        speaker_name = "男主持" if entry["speaker"] == "A" else "女主持"
        lines.append(f"**{speaker_name}**: {entry['paragraph']}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate dual-host podcast from A/B dialogue script"
    )
    parser.add_argument("--content-file", required=True, help="Input script (.md with A:/B: format)")
    parser.add_argument("--output-file", required=True, help="Output MP3 path")
    parser.add_argument("--transcript-file", default="", help="Output transcript markdown path")
    parser.add_argument("--speaker-male", default="zh_male_dayixiansheng_v2_saturn_bigtts")
    parser.add_argument("--speaker-female", default="zh_female_mizaitongxue_v2_saturn_bigtts")
    args = parser.parse_args()

    appid = os.environ.get("VOLCENGINE_TTS_APPID")
    access_token = os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")

    if not appid or not access_token:
        print("[ERR] VOLCENGINE_TTS_APPID and VOLCENGINE_TTS_ACCESS_TOKEN are required")
        sys.exit(1)

    with open(args.content_file, "r", encoding="utf-8") as f:
        content = f.read()

    # ── Parse dialogue with fallback chain ──
    dialogue, method = parse_dialogue(content)
    print(f"Parsed {len(dialogue)} dialogue lines (method: {method})")

    # Check if parsing was successful enough
    if len(dialogue) < MIN_DIALOGUE_LINES:
        print(f"[WARN] Only {len(dialogue)} lines parsed (minimum: {MIN_DIALOGUE_LINES})")
        success = generate_fallback_action0(content, args.output_file, args.transcript_file)
        sys.exit(0 if success else 1)

    # Validate speaker balance: both A and B should have lines
    speakers = set(d["speaker"] for d in dialogue)
    if len(speakers) < 2:
        print(f"[WARN] Only speaker(s) {speakers} found, expected both A and B")
        success = generate_fallback_action0(content, args.output_file, args.transcript_file)
        sys.exit(0 if success else 1)

    # ── Save transcript ──
    if args.transcript_file:
        transcript_dir = os.path.dirname(args.transcript_file)
        if transcript_dir:
            os.makedirs(transcript_dir, exist_ok=True)
        title = os.path.splitext(os.path.basename(args.content_file))[0]
        md = generate_transcript_md(dialogue, title)
        with open(args.transcript_file, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Transcript saved to {args.transcript_file}")

    # ── Build nlp_texts and generate audio ──
    nlp_texts = build_nlp_texts(dialogue, args.speaker_male, args.speaker_female)
    print(f"Built {len(nlp_texts)} nlp_texts rounds")

    import _paths
    _pg = _paths.skill_dir("podcast-generation")
    skill_dir = str(_pg / "scripts") if _pg else os.path.expanduser(
        "~/.codex/skills/podcast-generation/scripts")
    if os.path.isdir(skill_dir):
        sys.path.insert(0, skill_dir)
    else:
        print(f"[ERR] podcast-generation skill not found at {skill_dir}")
        sys.exit(1)

    from generate import PodcastGenerator, _download_audio_with_retry

    output_dir = os.path.dirname(os.path.abspath(args.output_file))
    os.makedirs(output_dir, exist_ok=True)

    generator = PodcastGenerator(
        appid=appid,
        access_token=access_token,
        speaker_male=args.speaker_male,
        speaker_female=args.speaker_female,
        audio_format="mp3",
        sample_rate=24000,
        use_head_music=False,
        return_audio_url=True,
    )

    try:
        result = generator.generate(action=3, nlp_texts=nlp_texts, timeout=600)
    except Exception as e:
        print(f"[ERR] action=3 failed: {e}")
        print("[FALLBACK] Trying action=0...")
        success = generate_fallback_action0(content, args.output_file, args.transcript_file)
        sys.exit(0 if success else 1)

    # Save audio
    saved = False
    if result.get("audio_url"):
        saved = _download_audio_with_retry(
            result["audio_url"], args.output_file, max_retries=3, timeout=120,
        )

    if not saved and result.get("audio_chunks"):
        audio_data = b"".join(result["audio_chunks"])
        with open(args.output_file, "wb") as f:
            f.write(audio_data)
        saved = True
        print(f"Saved from WebSocket chunks: {len(audio_data)} bytes")

    if saved:
        size_kb = os.path.getsize(args.output_file) / 1024
        print(f"\nDone: {size_kb:.0f}KB → {args.output_file}")
    else:
        print("[ERR] Failed to save audio")
        sys.exit(1)


if __name__ == "__main__":
    main()
