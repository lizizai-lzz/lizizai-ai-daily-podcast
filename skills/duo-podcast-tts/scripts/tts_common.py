#!/usr/bin/env python3
"""双人对话 TTS 公共逻辑：读对话 JSON、按角色分段合成、带停顿拼接。

对话 JSON 格式:
  [{"speaker": "host", "text": "...", "emotion": "开心|平静|惊讶|..."}]

speaker 到音色的映射由调用方通过 voice_map 传入。
emotion 为可选字段，传给各家引擎的情感控制（MiniMax: voice_setting.emotion + 语气词标签；
阿里云 Qwen-Audio-TTS: instruction 指令）。
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def load_dialogue(path: str) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("对话 JSON 必须是数组：[{\"speaker\":..., \"text\":..., \"emotion\":...}]")
    lines = []
    for item in data:
        speaker = item.get("speaker", "host")
        text = (item.get("text") or "").strip()
        emotion = item.get("emotion") or None
        if text:
            lines.append((speaker, text, emotion))
    return lines


def load_api_keys(*names: str) -> dict:
    """读取 API Key：优先环境变量，缺失时回退解析 ~/.zshrc 的 export 行。
    绝不打印 key 值。返回 {name: value}。"""
    zshrc = os.path.expanduser("~/.zshrc")
    try:
        text = open(zshrc, encoding="utf-8", errors="replace").read()
    except Exception:
        text = ""
    keys = {}
    for name in names:
        val = os.environ.get(name, "")
        if not val:
            m = re.search(rf"^\s*export\s+{re.escape(name)}\s*=\s*[\"']?([^\"'\n]+)", text, re.M)
            if m:
                val = m.group(1).strip()
        keys[name] = val
    return keys


def concat_with_pauses(paths, out_path, pause=0.35):
    """把多段 mp3 按顺序拼接，段间插入 pause 秒静音。"""
    if not paths:
        raise ValueError("没有可拼接的音频")
    if len(paths) == 1:
        subprocess.run(["cp", paths[0], out_path], check=True)
        return
    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd += ["-i", p]
    parts = []
    for i in range(len(paths)):
        parts.append(
            f"[{i}:a]apad=pad_dur={pause},aformat=sample_fmts=fltp:"
            f"channel_layouts=stereo:sample_rates=44100[a{i}]"
        )
    chain = ";".join(parts)
    concat_in = "".join(f"[a{i}]" for i in range(len(paths)))
    chain += f";{concat_in}concat=n={len(paths)}:v=0:a=1[out]"
    cmd += ["-filter_complex", chain, "-map", "[out]", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 拼接失败: {proc.stderr[-800:]}")


def render_dialogue(lines, synthesize_fn, out_path, pause=0.35):
    """通用渲染器：逐行合成到临时目录，再拼接。
    synthesize_fn(speaker, text, emotion) -> bytes（mp3 内容）
    """
    paths = []
    with tempfile.TemporaryDirectory(prefix="tts_seg_") as td:
        for i, (speaker, text, emotion) in enumerate(lines):
            audio = synthesize_fn(speaker, text, emotion)
            seg = f"{td}/seg_{i:03d}.mp3"
            Path(seg).write_bytes(audio)
            paths.append(seg)
        concat_with_pauses(paths, out_path, pause=pause)
