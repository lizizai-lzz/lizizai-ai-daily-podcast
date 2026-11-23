#!/usr/bin/env python3
"""MiniMax speech 语音合成（含双人对话模式）。

环境变量（必填）:
  国内站(默认): MINIMAX_CN_API_KEY
  国际站(--endpoint intl): MINIMAX_API_KEY

说明: 按官方文档(platform.minimaxi.com/docs/api-reference/speech-t2a-http)，
T2A HTTP 接口仅需 Authorization: Bearer API_KEY，无需 GroupId。

单条合成:
  python3 minimax_speech_tts.py --text "你好" --voice male-qn-qingse --output a.mp3

双人对话:
  python3 minimax_speech_tts.py --dialogue dialogue.json --output show.mp3

默认音色: host=male-qn-qingse(男), guest=female-shaonv(女)
更多音色见 MiniMax 控制台音色列表。

情感控制（speech-2.8 系列）:
  - dialogue 每行可带 "emotion": "开心|平静|惊讶|悲伤|生气|害怕|厌恶|calm|happy|..."
  - 会自动映射到 voice_setting.emotion，并往文本里插入语气词标签:
    (laughs)笑声 / (sighs)叹气 / (gasps)倒吸气 / (breath)换气 等
  - 文本中也可手动写 <#0.4#> 控制停顿（秒）
"""

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_common import load_api_keys, load_dialogue, render_dialogue

ENDPOINTS = {
    "cn": "https://api.minimaxi.com/v1/t2a_v2",
    "intl": "https://api.minimax.io/v1/t2a_v2",
}
DEFAULT_HOST_VOICE = "male-qn-qingse"
DEFAULT_GUEST_VOICE = "female-shaonv"

EMOTION_MAP = {
    "开心": "happy", "高兴": "happy", "快乐": "happy", "愉快": "happy",
    "平静": "calm", "沉稳": "calm", "认真": "calm", "淡定": "calm",
    "惊讶": "surprised", "惊奇": "surprised", "好奇": "surprised", "惊喜": "surprised",
    "悲伤": "sad", "难过": "sad", "失落": "sad",
    "生气": "angry", "愤怒": "angry",
    "害怕": "fearful", "担忧": "fearful", "紧张": "fearful",
    "厌恶": "disgusted",
}
TAG_MAP = {
    "happy": " (laughs)",
    "surprised": " (gasps)",
    "sad": " (sighs)",
    "angry": " (snorts)",
    "fearful": " (breath)",
    "calm": " (breath)",
}


class MiniMaxTTS:
    def __init__(self, api_key, endpoint="cn", model="speech-2.8-hd",
                 voice_host=DEFAULT_HOST_VOICE, voice_guest=DEFAULT_GUEST_VOICE):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.voice_map = {"host": voice_host, "guest": voice_guest}

    def synthesize(self, text, voice, emotion=None):
        url = ENDPOINTS[self.endpoint]
        voice_setting = {"voice_id": voice, "speed": 1.0, "vol": 1.0, "pitch": 0}
        if emotion:
            voice_setting["emotion"] = emotion
        body = json.dumps({
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": voice_setting,
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode("utf-8"))
        br = resp.get("base_resp") or {}
        if br.get("status_code") not in (0, None):
            raise RuntimeError(f"MiniMax 错误 {br.get('status_code')}: {br.get('status_msg')}")
        data = resp.get("data") or {}
        audio_b64 = data.get("audio") or (data.get("audio_utils") or {}).get("audio")
        if not audio_b64:
            raise RuntimeError(f"MiniMax 未返回音频: {str(resp)[:300]}")
        audio_b64 = audio_b64.strip()
        try:
            return bytes.fromhex(audio_b64)
        except Exception:
            try:
                return base64.b64decode(audio_b64)
            except Exception:
                raise RuntimeError("MiniMax 返回的音频既不是 hex 也不是 base64")

    def line_fn(self, speaker, text, emotion=None):
        voice = self.voice_map.get(speaker, self.voice_map["guest"])
        emo_en = None
        if emotion:
            emo_en = EMOTION_MAP.get(emotion.strip(), emotion.strip())
            if emo_en in TAG_MAP and TAG_MAP[emo_en] not in text:
                # 在第一个句末标点后插入语气词标签，让情绪更自然
                for punct in ("。", "！", "？", "！？"):
                    idx = text.find(punct)
                    if idx != -1:
                        text = text[: idx + 1] + TAG_MAP[emo_en] + text[idx + 1:]
                        break
        return self.synthesize(text, voice, emo_en)


def main():
    ap = argparse.ArgumentParser(description="MiniMax speech-02 语音合成（含双人对话）")
    ap.add_argument("--text", help="单条合成文本")
    ap.add_argument("--voice", help="单条合成音色")
    ap.add_argument("--dialogue", help="对话 JSON 路径")
    ap.add_argument("--output", required=True, help="输出 mp3 路径")
    ap.add_argument("--model", default="speech-2.8-hd",
                    help="当前型号 speech-2.8-hd / speech-2.8-turbo；老型号可用 speech-02-hd / speech-02-turbo")
    ap.add_argument("--endpoint", default="cn", choices=["cn", "intl"])
    ap.add_argument("--voice-host", default=DEFAULT_HOST_VOICE)
    ap.add_argument("--voice-guest", default=DEFAULT_GUEST_VOICE)
    ap.add_argument("--pause", type=float, default=0.35)
    args = ap.parse_args()

    if args.endpoint == "cn":
        keys = load_api_keys("MINIMAX_CN_API_KEY")
        api_key = keys["MINIMAX_CN_API_KEY"]
        missing = [n for n, v in keys.items() if not v]
    else:
        keys = load_api_keys("MINIMAX_API_KEY")
        api_key = keys["MINIMAX_API_KEY"]
        missing = [n for n, v in keys.items() if not v]
    if missing:
        sys.exit(f"缺少环境变量: {', '.join(missing)}。请在 MiniMax 开放平台创建后设置。")

    tts = MiniMaxTTS(api_key, endpoint=args.endpoint, model=args.model,
                     voice_host=args.voice_host, voice_guest=args.voice_guest)
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
