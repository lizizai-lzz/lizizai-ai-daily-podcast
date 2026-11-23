#!/usr/bin/env python3
"""阿里云百炼 DashScope CosyVoice 语音合成（含双人对话模式）。

环境变量（必填）:
  DASHSCOPE_API_KEY   百炼控制台 -> API-KEY 管理 创建的 key（形如 sk-...）

单条合成:
  python3 aliyun_cosyvoice_tts.py --text "你好" --voice longxiaochun --output a.mp3

双人对话:
  python3 aliyun_cosyvoice_tts.py --dialogue dialogue.json --output show.mp3

默认音色: host=longxiaohu(青年男声), guest=longxiaochun(温柔姐姐)
--model cosyvoice-v2 时音色名用 _v2 后缀，如 longxiaohu_v2 / longxiaochun_v2。

情感控制:
  - dialogue 每行可带 "emotion" 字段；仅 Qwen-Audio-TTS 系列(qwen-audio-3.0-tts-plus/flash)
    支持 instruction 指令控制情感（CosyVoice v2/v3 系统音色不支持自由指令）。
  - 情感版建议: --model qwen-audio-3.0-tts-plus --voice-host longanlufeng --voice-guest longanlingxin
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_common import load_api_keys, load_dialogue, render_dialogue

ENDPOINT_TTS = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
ENDPOINT_MM = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DEFAULT_HOST_VOICE = "longshuo_v2"
DEFAULT_GUEST_VOICE = "longxiaochun_v2"

INSTRUCTION_MAP = {
    "开心": "请用开心、带笑意的语气，像和朋友聊天一样自然地说这段话。",
    "高兴": "请用开心、带笑意的语气，像和朋友聊天一样自然地说这段话。",
    "平静": "请用平静、沉稳的语气，娓娓道来，像在认真讲述一个故事。",
    "认真": "请用认真、专注的语气，像在郑重地给朋友讲一件重要的事。",
    "惊讶": "请用惊讶、好奇的语气，声音微微上扬，像刚发现一件意外的事。",
    "好奇": "请用好奇、感兴趣的语气，声音微微上扬，像在追问一个有趣的问题。",
    "悲伤": "请用低沉、难过的语气，语速稍慢，像在回忆一件遗憾的事。",
    "神秘": "请用神秘、压低声音的语气，像在透露一个秘密。",
    "坚定": "请用坚定、有力量感的语气，字字清楚，像在给出一个结论。",
}


class CosyVoice:
    def __init__(self, api_key, model="cosyvoice-v2", voice_host=DEFAULT_HOST_VOICE,
                 voice_guest=DEFAULT_GUEST_VOICE, sample_rate=24000):
        self.api_key = api_key
        self.model = model
        self.voice_map = {"host": voice_host, "guest": voice_guest}
        self.sample_rate = sample_rate

    def synthesize(self, text, voice, emotion=None):
        if self.model.startswith("qwen3-tts"):
            # Qwen-TTS 系列（qwen3-tts-flash 等）走 multimodal-generation 接口
            inp = {"text": text, "voice": voice, "language_type": "Chinese"}
            if "instruct" in self.model and emotion:
                instruction = INSTRUCTION_MAP.get(emotion.strip())
                if instruction:
                    inp["instructions"] = instruction
                    inp["optimize_instructions"] = True
            endpoint = ENDPOINT_MM
        else:
            # CosyVoice / Qwen-Audio-TTS 走 SpeechSynthesizer 接口
            inp = {
                "text": text,
                "voice": voice,
                "format": "mp3",
                "sample_rate": self.sample_rate,
            }
            if emotion and self.model.startswith("qwen-audio"):
                instruction = INSTRUCTION_MAP.get(emotion.strip())
                if instruction:
                    inp["instruction"] = instruction
            endpoint = ENDPOINT_TTS
        body = json.dumps({"model": self.model, "input": inp}).encode("utf-8")
        req = urllib.request.Request(endpoint, data=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"CosyVoice HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]} | text={text[:40]} voice={voice}")
        audio = (resp.get("output") or {}).get("audio") or {}
        audio_url = audio.get("url")
        audio_b64 = audio.get("data")
        if audio_url:
            req = urllib.request.Request(audio_url, headers={"User-Agent": "codex-tts"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        if audio_b64:
            return base64.b64decode(audio_b64)
        raise RuntimeError(f"CosyVoice 未返回音频: {str(resp)[:400]}")

    def line_fn(self, speaker, text, emotion=None):
        voice = self.voice_map.get(speaker, self.voice_map["guest"])
        return self.synthesize(text, voice, emotion)


def main():
    ap = argparse.ArgumentParser(description="阿里云百炼 CosyVoice 语音合成（含双人对话）")
    ap.add_argument("--text", help="单条合成文本")
    ap.add_argument("--voice", help="单条合成音色")
    ap.add_argument("--dialogue", help="对话 JSON 路径")
    ap.add_argument("--output", required=True, help="输出 mp3 路径")
    ap.add_argument("--model", default="cosyvoice-v2",
                    help="cosyvoice-v2 / cosyvoice-v3-plus / cosyvoice-v3.5-plus / qwen-audio-3.0-tts-flash")
    ap.add_argument("--voice-host", default=DEFAULT_HOST_VOICE)
    ap.add_argument("--voice-guest", default=DEFAULT_GUEST_VOICE)
    ap.add_argument("--sample-rate", type=int, default=24000)
    ap.add_argument("--pause", type=float, default=0.35, help="对话段间静音秒数")
    args = ap.parse_args()

    keys = load_api_keys("DASHSCOPE_API_KEY")
    api_key = keys["DASHSCOPE_API_KEY"]
    if not api_key:
        sys.exit("缺少 DASHSCOPE_API_KEY。请在阿里云百炼控制台(百炼 -> API-KEY 管理)创建后设置环境变量。")

    tts = CosyVoice(api_key, model=args.model, voice_host=args.voice_host,
                    voice_guest=args.voice_guest, sample_rate=args.sample_rate)

    if args.text:
        audio = tts.synthesize(args.text, args.voice or DEFAULT_HOST_VOICE)
        open(args.output, "wb").write(audio)
        print(f"已生成 -> {args.output}")
        return
    if args.dialogue:
        lines = load_dialogue(args.dialogue)
        render_dialogue(lines, tts.line_fn, args.output, pause=args.pause)
        print(f"已生成双人对话 -> {args.output}")
        return
    sys.exit("请提供 --text 或 --dialogue")


if __name__ == "__main__":
    main()
