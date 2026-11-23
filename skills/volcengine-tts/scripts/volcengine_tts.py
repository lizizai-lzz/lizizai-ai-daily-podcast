#!/usr/bin/env python3
"""
Volcengine TTS — 火山引擎豆包语音合成 (Seed-TTS 2.0 / Seed-ICL 2.0)

使用 HTTP Chunk (NDJSON) 协议，一次性提交文本，流式接收音频片段，最终输出 MP3/WAV 文件。

用法:
    python volcengine_tts.py --text "你好世界" --output /tmp/out.mp3
    python volcengine_tts.py --text "[开心]你好！[温柔]辛苦了。" --output /tmp/out.mp3
    python volcengine_tts.py --text "<cot text=开心>你好！</cot>" --speaker S_xxx --output /tmp/out.mp3
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────────

API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
DEFAULT_FORMAT = "mp3"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_UID = "workbuddy"

# Stream end code
STREAM_END_CODE = 20000000

# Success code
SUCCESS_CODE = 0


# ─── Model routing ────────────────────────────────────────────────────────────

def get_resource_id(speaker_id: str) -> str:
    """根据 Speaker ID 自动判断使用哪个模型。"""
    if speaker_id.startswith("S_"):
        return "seed-icl-2.0"
    if "_uranus_" in speaker_id or speaker_id.startswith("saturn_"):
        return "seed-tts-2.0"
    return "seed-tts-1.0"


def is_cloned_speaker(speaker_id: str) -> bool:
    """判断是否为克隆音色。"""
    return speaker_id.startswith("S_")


# ─── Voice tag parsing ───────────────────────────────────────────────────────

def has_bracket_tags(text: str) -> bool:
    """检查文本是否包含方括号情感标签 [xxx]。"""
    return bool(re.search(r"\[[^\]]+\]", text))


def has_cot_tags(text: str) -> bool:
    """检查文本是否包含 COT 标签 <cot text=xxx>。</cot>。"""
    return bool(re.search(r"<cot\s+", text))


def parse_bracket_segments(text: str) -> list[dict]:
    """
    解析方括号情感标签格式: [情感]文本
    返回 [{"emotion": "开心", "text": "你好"}, ...]
    无标签的部分 emotion 为 None。
    """
    segments = []
    # Split by [xxx] patterns
    parts = re.split(r"\[([^\]]+)\]", text)
    pending_emotion = None

    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Text part
            chunk = part.strip()
            if chunk:
                segments.append({"emotion": pending_emotion, "text": chunk})
                pending_emotion = None
        else:
            # Emotion tag part
            pending_emotion = part.strip() or None

    # If no tags found, return entire text as one segment
    if not segments:
        segments.append({"emotion": None, "text": text.strip()})

    return segments


def strip_bracket_tags(text: str) -> str:
    """移除方括号情感标签，返回纯文本。"""
    return re.sub(r"\[[^\]]+\]", "", text).strip()


# ─── Core TTS API call ───────────────────────────────────────────────────────

def call_tts(
    text: str,
    speaker_id: str,
    app_id: str,
    access_key: str,
    audio_format: str = DEFAULT_FORMAT,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    uid: str = DEFAULT_UID,
    context_text: str | None = None,
) -> bytes:
    """
    调用火山引擎 TTS API，使用 HTTP Chunk (NDJSON) 协议。
    一次性提交全部文本，流式接收音频片段。
    返回拼接后的完整音频 bytes。
    """
    cloned = is_cloned_speaker(speaker_id)
    resource_id = get_resource_id(speaker_id)

    # Build additions (must be a JSON string, NOT an object)
    additions_dict: dict = {}
    if cloned:
        additions_dict["model_type"] = 4
    if context_text:
        additions_dict["context_texts"] = [context_text]

    body: dict = {
        "user": {"uid": uid},
        "req_params": {
            "text": text,
            "speaker": speaker_id,
            "audio_params": {
                "format": audio_format,
                "sample_rate": sample_rate,
            },
        },
    }

    if additions_dict:
        body["req_params"]["additions"] = json.dumps(additions_dict)

    headers: dict = {
        "Content-Type": "application/json",
        "X-Api-App-Id": app_id,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": resource_id,
    }

    # Make request (read full response for NDJSON parsing)
    response = requests.post(API_URL, headers=headers, json=body, timeout=120)
    response.raise_for_status()

    # Parse NDJSON response
    audio_chunks: list[bytes] = []

    for line in response.text.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Warning: failed to parse NDJSON line: {e}", file=sys.stderr)
            continue

        code = parsed.get("code")

        if code == SUCCESS_CODE and parsed.get("data"):
            audio_chunks.append(base64.b64decode(parsed["data"]))
        elif code == STREAM_END_CODE:
            break
        elif code is not None and code != SUCCESS_CODE:
            message = parsed.get("message", "Unknown error")
            raise RuntimeError(
                f"Doubao TTS API error: code={code}, message={message}"
            )

    if not audio_chunks:
        raise RuntimeError("Doubao TTS returned no audio data")

    return b"".join(audio_chunks)


# ─── High-level synthesis ────────────────────────────────────────────────────

def synthesize(
    text: str,
    speaker_id: str,
    app_id: str,
    access_key: str,
    output_path: str,
    audio_format: str = DEFAULT_FORMAT,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    uid: str = DEFAULT_UID,
    use_ffmpeg: bool = True,
) -> str:
    """
    高级合成函数：自动检测语音标签，选择最优合成策略。
    返回输出文件的绝对路径。
    """
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Determine synthesis strategy
    if has_bracket_tags(text):
        # Strategy 1: Bracket tags → split into segments, call per-segment
        print(f"[volcengine-tts] Detected bracket tags, using per-segment synthesis", file=sys.stderr)
        audio_data = _synthesize_bracket_segments(
            text, speaker_id, app_id, access_key, audio_format, sample_rate, uid
        )
    elif has_cot_tags(text) and is_cloned_speaker(speaker_id):
        # Strategy 2: COT tags with cloned speaker → single call
        print(f"[volcengine-tts] Detected COT tags with cloned speaker, using single-call synthesis", file=sys.stderr)
        audio_data = call_tts(
            text, speaker_id, app_id, access_key,
            audio_format, sample_rate, uid,
        )
    else:
        # Strategy 3: Plain text → single call
        print(f"[volcengine-tts] Plain text, using single-call synthesis", file=sys.stderr)
        audio_data = call_tts(
            text, speaker_id, app_id, access_key,
            audio_format, sample_rate, uid,
        )

    # Write raw audio
    raw_output = output_path
    if use_ffmpeg and has_bracket_tags(text):
        # If multi-segment, write to temp first, then ffmpeg remux
        raw_output = output_path + ".raw.mp3"

    with open(raw_output, "wb") as f:
        f.write(audio_data)
    print(f"[volcengine-tts] Raw audio written to: {raw_output} ({len(audio_data)} bytes)", file=sys.stderr)

    # FFmpeg remux for multi-segment MP3 to avoid glitches
    if use_ffmpeg and raw_output != output_path:
        _ffmpeg_remux(raw_output, output_path)
        try:
            os.remove(raw_output)
        except OSError:
            pass
    elif raw_output != output_path:
        # ffmpeg disabled but we used temp path
        os.rename(raw_output, output_path)

    print(f"[volcengine-tts] Output: {output_path}", file=sys.stderr)
    return output_path


def _synthesize_bracket_segments(
    text: str,
    speaker_id: str,
    app_id: str,
    access_key: str,
    audio_format: str,
    sample_rate: int,
    uid: str,
) -> bytes:
    """方括号标签模式：拆分为多段，每段独立调用 API，最后拼接。"""
    segments = parse_bracket_segments(text)
    buffers: list[bytes] = []

    for i, seg in enumerate(segments):
        emotion = seg["emotion"]
        seg_text = seg["text"]

        if not seg_text:
            continue

        context_text = None
        if emotion:
            # Use emotion description as context_texts for emotional control
            context_text = emotion
            print(f"[volcengine-tts] Segment {i+1}/{len(segments)}: [{emotion}] {seg_text[:50]}...", file=sys.stderr)
        else:
            print(f"[volcengine-tts] Segment {i+1}/{len(segments)}: {seg_text[:50]}...", file=sys.stderr)

        audio = call_tts(
            text=seg_text,
            speaker_id=speaker_id,
            app_id=app_id,
            access_key=access_key,
            audio_format=audio_format,
            sample_rate=sample_rate,
            uid=uid,
            context_text=context_text,
        )
        buffers.append(audio)

    if not buffers:
        raise RuntimeError("No audio segments produced")

    return b"".join(buffers)


def _ffmpeg_remux(input_path: str, output_path: str) -> None:
    """使用 ffmpeg 重封装 MP3，修复多片段拼接兼容性问题。"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"[volcengine-tts] FFmpeg remux successful", file=sys.stderr)
        else:
            print(f"[volcengine-tts] FFmpeg remux failed (exit {result.returncode}), using raw output", file=sys.stderr)
            # Fallback: just copy the raw file
            import shutil
            shutil.copy2(input_path, output_path)
    except FileNotFoundError:
        print("[volcengine-tts] FFmpeg not found, skipping remux", file=sys.stderr)
        import shutil
        shutil.copy2(input_path, output_path)
    except subprocess.TimeoutExpired:
        print("[volcengine-tts] FFmpeg timeout, using raw output", file=sys.stderr)
        import shutil
        shutil.copy2(input_path, output_path)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Volcengine TTS — 火山引擎豆包语音合成 (Seed-TTS 2.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 纯文本合成
  python volcengine_tts.py --text "你好世界" --output /tmp/out.mp3

  # 带情感标签
  python volcengine_tts.py --text "[开心]你好！[温柔]辛苦了。" --output /tmp/out.mp3

  # COT 标签 + 克隆音色
  python volcengine_tts.py --text "<cot text=开心>你好</cot>" --speaker S_xxx --output /tmp/out.mp3

环境变量:
  VOLCENGINE_TTS_APPID        火山引擎应用 ID（纯数字）
  VOLCENGINE_TTS_ACCESS_TOKEN API 访问密钥
  VOLCENGINE_TTS_SPEAKER      默认 Speaker（voice_type）
        """,
    )

    parser.add_argument("--text", required=True, help="要合成的文本（支持语音标签）")
    parser.add_argument("--output", required=True, help="输出音频文件路径")
    parser.add_argument("--speaker", default=None, help="Speaker voice_type（默认读取 VOLCENGINE_TTS_SPEAKER 环境变量）")
    parser.add_argument("--app-id", default=None, help="火山引擎应用 ID（默认读取 VOLCENGINE_TTS_APPID 环境变量）")
    parser.add_argument("--access-key", default=None, help="API 访问密钥（默认读取 VOLCENGINE_TTS_ACCESS_TOKEN 环境变量）")
    parser.add_argument("--format", default=DEFAULT_FORMAT, choices=["mp3", "wav"], help="音频格式（默认 mp3）")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE, help="采样率（默认 24000）")
    parser.add_argument("--uid", default=DEFAULT_UID, help="用户标识（默认 workbuddy）")
    parser.add_argument("--no-ffmpeg", action="store_true", help="跳过 ffmpeg 重封装")

    args = parser.parse_args()

    # Resolve credentials
    app_id = args.app_id or os.environ.get("VOLCENGINE_TTS_APPID")
    access_key = args.access_key or os.environ.get("VOLCENGINE_TTS_ACCESS_TOKEN")
    speaker_id = args.speaker or os.environ.get("VOLCENGINE_TTS_SPEAKER")

    if not app_id:
        print("Error: --app-id or VOLCENGINE_TTS_APPID environment variable is required", file=sys.stderr)
        sys.exit(1)
    if not access_key:
        print("Error: --access-key or VOLCENGINE_TTS_ACCESS_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)
    if not speaker_id:
        print("Error: --speaker or VOLCENGINE_TTS_SPEAKER environment variable is required", file=sys.stderr)
        sys.exit(1)
    if not args.text.strip():
        print("Error: --text cannot be empty", file=sys.stderr)
        sys.exit(1)

    try:
        result_path = synthesize(
            text=args.text,
            speaker_id=speaker_id,
            app_id=app_id,
            access_key=access_key,
            output_path=args.output,
            audio_format=args.format,
            sample_rate=args.sample_rate,
            uid=args.uid,
            use_ffmpeg=not args.no_ffmpeg,
        )
        print(f"OK: {result_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
