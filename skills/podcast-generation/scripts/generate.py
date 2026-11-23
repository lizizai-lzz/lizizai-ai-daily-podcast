#!/usr/bin/env python3
"""
Podcast Generation Script (WebSocket v3)
=========================================
Uses Volcengine Podcast TTS WebSocket API to generate dual-host podcast audio.

Supports 3 action modes:
  - action=0: Summarize input text/URL → generate podcast (end-to-end)
  - action=3: Generate podcast from pre-written dialogue lines (nlp_texts)
  - action=4: Generate podcast from a prompt topic (with web search)

Usage:
    python3 generate.py \
        --content "source text" \
        --output-file output.mp3

Environment Variables Required:
    VOLCENGINE_TTS_APPID       - Volcengine TTS app ID
    VOLCENGINE_TTS_ACCESS_TOKEN - Volcengine TTS access token

Optional:
    DOUBAO_API_KEY       - Doubao API key (only needed for action=3 mode)
    DOUBAO_ENDPOINT_ID   - Doubao model endpoint ID (only needed for action=3 mode)
"""

import argparse
import gzip
import json
import logging
import os
import struct
import sys
import threading
import time
import uuid
from typing import Optional

import requests
import websocket

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PODCAST_WS_URL = "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# Default podcast speaker voices
DEFAULT_SPEAKER_MALE = "zh_male_dayixiansheng_v2_saturn_bigtts"
DEFAULT_SPEAKER_FEMALE = "zh_female_mizaitongxue_v2_saturn_bigtts"

# Style to speaker mapping (can be customized)
STYLE_PROMPTS = {
    "tech": "你是一位科技播客主持人，擅长将复杂的技术概念用通俗易懂的方式讲解。",
    "news": "你是一位新闻播客主持人，擅长梳理新闻要点，分析背后的趋势和影响。",
    "knowledge": "你是一位知识科普播客主持人，擅长深入浅出地讲解知识，让听众轻松理解。",
    "casual": "你是一位轻松聊天播客主持人，擅长用幽默风趣的方式聊各种话题。",
}

# WebSocket binary protocol constants
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001  # 4 bytes (4 * 1)

# Message types (left 4-bit of byte 1)
MSG_TYPE_FULL_CLIENT = 0b0001   # Full client request
MSG_TYPE_FULL_SERVER = 0b1001   # Full server response (with optional+payload)
MSG_TYPE_AUDIO_ONLY = 0b1011    # Audio-only response
MSG_TYPE_ERROR = 0b1111         # Error response

# Message type specific flags (right 4-bit of byte 1)
FLAG_NO_SEQ = 0b0000            # No sequence number
FLAG_POS_SEQ = 0b0001           # With positive sequence number
FLAG_LAST_NO_SEQ = 0b0010       # Last packet, no sequence
FLAG_NEG_SEQ = 0b0011           # Last packet, with negative sequence (error)
FLAG_WITH_EVENT = 0b0100        # Optional section includes event code

# Serialization
SER_JSON = 0b0001
SER_RAW = 0b0000

# Compression
COMP_NONE = 0b0000
COMP_GZIP = 0b0001

# Client event codes (upstream)
EVENT_START_CONNECTION = 1      # Client: establish connection
EVENT_FINISH_CONNECTION = 2     # Client: close connection
EVENT_START_SESSION = 100       # Client: start session
EVENT_FINISH_SESSION = 102      # Client: finish session
EVENT_TASK_REQUEST = 200        # Client: send business request

# Server event codes (downstream)
EVENT_CONNECTION_STARTED = 50   # Server: connection established
EVENT_CONNECTION_FAILED = 51    # Server: connection failed
EVENT_CONNECTION_FINISHED = 52  # Server: connection closed
EVENT_SESSION_STARTED = 150     # Server: session started
EVENT_SESSION_FINISHED = 152    # Server: session finished
EVENT_SESSION_FAILED = 153      # Server: session failed
EVENT_PODCAST_ROUND_START = 360 # Server: podcast round started
EVENT_PODCAST_ROUND_RESPONSE = 361  # Server: podcast audio data
EVENT_PODCAST_ROUND_END = 362   # Server: podcast round ended
EVENT_PODCAST_END = 363         # Server: podcast ended
EVENT_USAGE_RESPONSE = 154      # Server: usage info


# ---------------------------------------------------------------------------
# WebSocket Binary Protocol Helpers
# ---------------------------------------------------------------------------

def _build_header(
    message_type: int,
    message_type_flags: int,
    serialization: int = SER_JSON,
    compression: int = COMP_NONE,
) -> bytes:
    """Build 4-byte protocol header."""
    byte0 = (PROTOCOL_VERSION << 4) | DEFAULT_HEADER_SIZE
    byte1 = (message_type << 4) | message_type_flags
    byte2 = (serialization << 4) | compression
    byte3 = 0b00000000  # reserved
    return bytes([byte0, byte1, byte2, byte3])


def _build_optional(
    event: int = 0,
    session_id: str = None,
    sequence: int = None,
) -> bytes:
    """Build the Optional section of a binary frame.
    
    Format:
      - Event (4 bytes, big-endian) if event != 0
      - SessionId: [4-byte length][UTF-8 bytes] if session_id is not None
      - Sequence (4 bytes, big-endian) if sequence is not None
    """
    optional = bytearray()
    if event:
        optional.extend(struct.pack(">i", event))
    if session_id is not None:
        sid_bytes = session_id.encode("utf-8")
        optional.extend(struct.pack(">i", len(sid_bytes)))
        optional.extend(sid_bytes)
    if sequence is not None:
        optional.extend(struct.pack(">i", sequence))
    return bytes(optional)


def _parse_response_header(data: bytes) -> dict:
    """Parse response header to extract message info."""
    if len(data) < 4:
        return {"error": "header too short"}

    byte0, byte1, byte2, byte3 = data[0], data[1], data[2], data[3]
    protocol_version = (byte0 >> 4) & 0x0F
    header_size = (byte0 & 0x0F) * 4  # header_size field is (actual_size / 4)
    message_type = (byte1 >> 4) & 0x0F
    message_type_flags = byte1 & 0x0F
    serialization = (byte2 >> 4) & 0x0F
    compression = byte2 & 0x0F

    result = {
        "protocol_version": protocol_version,
        "header_size": header_size,
        "message_type": message_type,
        "message_type_flags": message_type_flags,
        "serialization": serialization,
        "compression": compression,
    }

    # Parse Optional section after header
    # Optional contains: event (4B if flags & 0x4), session_id (4B len + N bytes), sequence (4B)
    offset = header_size
    has_event = bool(message_type_flags & 0x4)
    has_sequence = bool(message_type_flags & 0x3)

    if has_event and offset + 4 <= len(data):
        event_code = struct.unpack(">i", data[offset:offset + 4])[0]
        result["event_code"] = event_code
        offset += 4

    # Session ID: [4B length][N bytes]
    if offset + 4 <= len(data):
        session_id_len = struct.unpack(">i", data[offset:offset + 4])[0]
        offset += 4
        if session_id_len > 0 and offset + session_id_len <= len(data):
            result["session_id"] = data[offset:offset + session_id_len].decode("utf-8", errors="replace")
            offset += session_id_len

    # Sequence number if present
    if has_sequence and offset + 4 <= len(data):
        seq = struct.unpack(">i", data[offset:offset + 4])[0]
        result["sequence"] = seq
        offset += 4

    # Store the offset where payload_size starts
    result["payload_offset"] = offset

    return result


def _extract_payload(data: bytes, header_size: int, serialization: int, compression: int, payload_offset: int = 0) -> bytes:
    """Extract and decompress payload from a WebSocket frame.
    
    payload_offset: byte offset where the payload_size field starts
    (after header + optional section with event/session_id/sequence)
    """
    if not payload_offset:
        # Fallback: compute from header
        offset = header_size
        if len(data) > header_size:
            byte1 = data[1]
            flags = byte1 & 0x0F
            if flags & 0x4 and offset + 4 <= len(data):  # event
                offset += 4
            if offset + 4 <= len(data):
                session_id_len = struct.unpack(">i", data[offset:offset + 4])[0]
                offset += 4 + session_id_len
            if flags & 0x3 and offset + 4 <= len(data):  # sequence
                offset += 4
        payload_offset = offset

    offset = payload_offset
    # Payload size: 4 bytes
    if offset + 4 > len(data):
        return b""
    payload_size = struct.unpack(">I", data[offset:offset + 4])[0]
    offset += 4

    payload = data[offset:offset + payload_size]

    if compression == COMP_GZIP:
        payload = gzip.decompress(payload)

    return payload


def _extract_json_payload(data: bytes, header_size: int, serialization: int, compression: int, payload_offset: int = 0) -> dict:
    """Extract and parse JSON payload from a WebSocket frame."""
    payload = _extract_payload(data, header_size, serialization, compression, payload_offset)
    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to parse JSON payload: {e}")
        return {}


# ---------------------------------------------------------------------------
# Doubao API - Generate Podcast Dialogue (for action=3 mode)
# ---------------------------------------------------------------------------

def _build_system_prompt(locale: str, style: str) -> str:
    """Build the system prompt for Doubao API to generate podcast dialogue."""
    style_intro = STYLE_PROMPTS.get(style, "你是一位专业播客主持人，擅长将各种内容转化为生动有趣的对话。")

    if locale == "zh":
        return f"""{style_intro}

你正在制作一档双人对话播客节目，由一位男主持和一位女主持共同主持。

## 你的任务
根据用户提供的源内容，生成一段结构化的双人对话播客脚本。

## 输出格式
你必须输出一个JSON对象，格式如下：
```json
{{
  "title": "播客标题",
  "locale": "zh",
  "lines": [
    {{"speaker": "male", "paragraph": "对话内容"}},
    {{"speaker": "female", "paragraph": "对话内容"}}
  ]
}}
```

## 对话编写规则
1. 只有两位主持人：男主持(male)和女主持(female)，自然交替发言
2. 目标时长约10分钟，约40-60行对话
3. 以男主持的问候开场，包含"大家好，欢迎收听本期节目"
4. 对话风格自然、口语化，像朋友聊天一样
5. 使用口语化表达和过渡语
6. 避免过于正式或学术化的语言
7. 包含反应、追问和自然的感叹
8. 句子简短，便于口语表达
9. 只输出纯文本，不要使用markdown格式、数学公式、代码或复杂符号
10. 将技术概念转化为通俗易懂的语言
11. 不要包含日期、作者名等元信息
12. 对话内容应基于源内容，但要重新组织和口语化

## 重要
- 只输出JSON，不要输出任何其他文字或说明"""

    else:
        return f"""{style_intro}

You are producing a two-host conversational podcast with one male host and one female host.

## Output Format
Output a JSON object:
```json
{{
  "title": "Podcast Title",
  "locale": "en",
  "lines": [
    {{"speaker": "male", "paragraph": "dialogue text"}},
    {{"speaker": "female", "paragraph": "dialogue text"}}
  ]
}}
```

## Dialogue Writing Rules
1. Only two hosts: male and female, alternating naturally
2. Target ~10 minutes, around 40-60 lines
3. Natural, conversational style
4. Include reactions and follow-ups
5. Keep sentences short for spoken delivery
6. Plain text only

## IMPORTANT - Output ONLY the JSON, no other text."""


def generate_podcast_script_via_doubao(
    content: str,
    locale: str = "zh",
    style: str = "",
    max_lines: int = 60,
) -> dict:
    """Call Doubao API to generate podcast dialogue script."""
    api_key = os.getenv("DOUBAO_API_KEY")
    endpoint_id = os.getenv("DOUBAO_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise ValueError(
            "Missing DOUBAO_API_KEY and DOUBAO_ENDPOINT_ID (required for action=3 mode). "
            "Set them or use action=0/4 mode instead."
        )

    system_prompt = _build_system_prompt(locale, style)
    user_message = f"请根据以下内容生成播客对话脚本：\n\n---\n{content}\n---\n\n要求：对话行数不超过{max_lines}行，只输出JSON格式"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": endpoint_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    logger.info("Calling Doubao API to generate podcast script...")
    response = requests.post(DOUBAO_API_URL, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise Exception(f"Doubao API error: {response.status_code} - {response.text}")

    result = response.json()
    content_text = result["choices"][0]["message"]["content"]

    # Extract JSON
    import re
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content_text, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
    else:
        json_match = re.search(r"\{[\s\S]*\}", content_text)
        json_str = json_match.group(0) if json_match else content_text.strip()

    # Fix trailing commas
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    script_json = json.loads(json_str)
    if len(script_json.get("lines", [])) > max_lines:
        script_json["lines"] = script_json["lines"][:max_lines]

    logger.info(f"Generated podcast script with {len(script_json.get('lines', []))} lines")
    return script_json


# ---------------------------------------------------------------------------
# WebSocket Podcast TTS API
# ---------------------------------------------------------------------------

class PodcastGenerator:
    """Generate podcast audio using Volcengine Podcast TTS WebSocket API."""

    def __init__(
        self,
        appid: str,
        access_token: str,
        speaker_male: str = DEFAULT_SPEAKER_MALE,
        speaker_female: str = DEFAULT_SPEAKER_FEMALE,
        audio_format: str = "mp3",
        sample_rate: int = 24000,
        speech_rate: int = 0,
        use_head_music: bool = False,
        return_audio_url: bool = True,
    ):
        self.appid = appid
        self.access_token = access_token
        self.speaker_male = speaker_male
        self.speaker_female = speaker_female
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.speech_rate = speech_rate
        self.use_head_music = use_head_music
        self.return_audio_url = return_audio_url

        self.audio_chunks = []
        self.session_id = ""
        self.audio_url = ""
        self.nlp_texts_result = []
        self.podcast_meta = {}
        self.usage = {}

    def _build_ws_headers(self) -> dict:
        """Build WebSocket connection headers."""
        return {
            "X-Api-App-Id": self.appid,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": "volc.service_type.10050",
            "X-Api-App-Key": "aGjiRDfUWi",
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

    def _build_start_request(self, action: int, **kwargs) -> bytes:
        """Build the start session request frame.

        Frame format (V1 protocol):
        [Header 4B] [Optional: event 4B + session_id 4B+NB] [PayloadSize 4B] [Payload NB]
        """
        request_payload = {
            "action": action,
            "use_head_music": self.use_head_music,
            "audio_config": {
                "format": self.audio_format,
                "sample_rate": self.sample_rate,
                "speech_rate": self.speech_rate,
            },
        }

        # Add optional fields
        input_id = kwargs.get("input_id", str(uuid.uuid4())[:8])
        request_payload["input_id"] = input_id

        if action == 0:
            # Long text or URL mode
            if "input_text" in kwargs and kwargs["input_text"]:
                request_payload["input_text"] = kwargs["input_text"]
            if "input_info" in kwargs:
                request_payload["input_info"] = kwargs["input_info"]
        elif action == 3:
            # NLP texts mode
            if "nlp_texts" in kwargs:
                request_payload["nlp_texts"] = kwargs["nlp_texts"]
        elif action == 4:
            # Prompt mode (with web search)
            if "prompt_text" in kwargs:
                request_payload["prompt_text"] = kwargs["prompt_text"]

        # Add input_info for action=0
        if action == 0 and "input_info" not in request_payload:
            input_info = {}
            if self.return_audio_url:
                input_info["return_audio_url"] = True
            if input_info:
                request_payload["input_info"] = input_info
        elif action == 0 and "input_info" in request_payload:
            if self.return_audio_url:
                request_payload["input_info"]["return_audio_url"] = True

        # Add speaker info
        request_payload["speaker_info"] = {
            "random_order": True,
            "speakers": [self.speaker_male, self.speaker_female],
        }

        # Serialize payload
        payload_json = json.dumps(request_payload, ensure_ascii=False)
        payload_bytes = payload_json.encode("utf-8")

        # Generate session_id (UUID without dashes, per working reference impl)
        session_id = str(uuid.uuid4()).replace("-", "")

        # Build binary frame per V1 protocol:
        # [Header 4B] [Optional: event 4B + session_id_len 4B + session_id NB]
        # [PayloadSize 4B] [Payload NB]
        header = _build_header(
            message_type=MSG_TYPE_FULL_CLIENT,
            message_type_flags=FLAG_WITH_EVENT,
            serialization=SER_JSON,
            compression=COMP_NONE,
        )
        # Optional: event code (StartSession=100) + session_id
        optional = _build_optional(event=EVENT_START_SESSION, session_id=session_id)
        # Payload with size prefix
        frame = header + optional + struct.pack(">I", len(payload_bytes)) + payload_bytes

        return frame

    def _build_nlp_texts(self, script_lines: list, locale: str = "zh") -> list:
        """Convert script lines to nlp_texts format for action=3."""
        nlp_texts = []
        for line in script_lines:
            speaker = line.get("speaker", "male")
            text = line.get("paragraph", "")
            if not text:
                continue
            speaker_id = self.speaker_male if speaker == "male" else self.speaker_female
            nlp_texts.append({
                "speaker": speaker_id,
                "text": text[:300],  # max 300 chars per round
            })
        return nlp_texts

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        self._last_activity_time = time.time()
        if isinstance(message, bytes):
            self._handle_binary_message(message)
        else:
            logger.debug(f"Text message: {message}")

    def _handle_binary_message(self, data: bytes):
        """Parse and handle a binary protocol message."""
        header_info = _parse_response_header(data)
        msg_type = header_info.get("message_type", 0)
        msg_flags = header_info.get("message_type_flags", 0)
        serialization = header_info.get("serialization", SER_RAW)
        compression = header_info.get("compression", COMP_NONE)
        header_size = header_info.get("header_size", 4)
        event_code = header_info.get("event_code", 0)
        payload_offset = header_info.get("payload_offset", 0)

        # Check for errors
        if msg_type == MSG_TYPE_ERROR:
            error_json = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            logger.error(f"Error frame received: {error_json}")
            return

        if event_code == EVENT_SESSION_STARTED:
            # Session started - extract session_id
            self.session_id = header_info.get("session_id", "")
            logger.info(f"Session started: {self.session_id}")

        elif event_code == EVENT_SESSION_FAILED:
            error_json = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            logger.error(f"Session failed: {error_json}")

        elif event_code == EVENT_CONNECTION_STARTED:
            logger.info("Connection established")

        elif event_code == EVENT_CONNECTION_FAILED:
            error_json = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            logger.error(f"Connection failed: {error_json}")

        elif event_code == EVENT_PODCAST_ROUND_START:
            payload = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            round_idx = payload.get("round_idx", "?")
            speaker = payload.get("speaker", "?")
            logger.info(f"Round {round_idx} started (speaker: {speaker})")

        elif event_code == EVENT_PODCAST_ROUND_RESPONSE:
            # Audio data - extract raw payload
            offset = payload_offset
            if offset + 4 <= len(data):
                payload_size = struct.unpack(">I", data[offset:offset + 4])[0]
                offset += 4
                audio_data = data[offset:offset + payload_size]
                if audio_data:
                    self.audio_chunks.append(audio_data)

        elif event_code == EVENT_PODCAST_ROUND_END:
            self._round_count += 1
            payload = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            duration = payload.get("audio_duration", 0)
            start = payload.get("start_time", 0)
            end = payload.get("end_time", 0)
            logger.info(f"Round {self._round_count} ended: duration={duration:.1f}s, start={start:.1f}s, end={end:.1f}s")

        elif event_code == EVENT_PODCAST_END:
            payload = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            self.podcast_meta = payload
            if "meta_info" in payload and "audio_url" in payload["meta_info"]:
                self.audio_url = payload["meta_info"]["audio_url"]
                logger.info(f"Podcast audio URL received (expires in 1h)")
                logger.info(f"FULL_AUDIO_URL: {self.audio_url}")
            logger.info(f"Podcast ended. Meta: {json.dumps(payload, ensure_ascii=False)[:500]}")
            # Signal generation complete
            if hasattr(self, '_generation_complete'):
                self._generation_complete.set()

        elif event_code == EVENT_SESSION_FINISHED:
            payload = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            status_code = payload.get("status_code", 0)
            msg = payload.get("message", "")
            if status_code == 20000000:
                logger.info("Session finished successfully")
            else:
                logger.error(f"Session finished with error: status={status_code}, message={msg}")
            # Signal generation complete (in case PODCAST_END wasn't received)
            if hasattr(self, '_generation_complete') and not self._generation_complete.is_set():
                self._generation_complete.set()

        elif event_code == EVENT_USAGE_RESPONSE:
            payload = _extract_json_payload(data, header_size, serialization, compression, payload_offset)
            self.usage = payload.get("usage", {})
            logger.info(f"Usage: input_tokens={self.usage.get('input_text_tokens', 0)}, output_tokens={self.usage.get('output_audio_tokens', 0)}")

        elif event_code == EVENT_CONNECTION_FINISHED:
            logger.info("Connection finished")

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed: code={close_status_code}, msg={close_msg}")

    def _on_open(self, ws):
        """Send the start request when connection opens."""
        request_frame = self._build_start_request(
            action=self._action,
            **self._request_kwargs,
        )
        ws.send(request_frame, opcode=0x2)  # binary frame
        logger.info("Start request sent")

    def _send_finish_connection(self, ws):
        """Send finish connection frame."""
        header = _build_header(
            message_type=MSG_TYPE_FULL_CLIENT,
            message_type_flags=FLAG_WITH_EVENT,
            serialization=SER_JSON,
            compression=COMP_NONE,
        )
        # Optional section: event code for finish connection
        optional = _build_optional(event=EVENT_FINISH_CONNECTION)
        # Empty payload
        payload = b"{}"
        frame = header + optional + struct.pack(">I", len(payload)) + payload
        ws.send(frame, opcode=0x2)
        logger.info("Finish connection sent")

    def generate(
        self,
        action: int,
        timeout: int = 600,
        **kwargs,
    ) -> dict:
        """
        Generate podcast audio.

        Args:
            action: 0 (text/URL summary), 3 (nlp_texts), 4 (prompt with search)
            timeout: Max wait time in seconds (default 600 = 10 min)
            **kwargs: Additional parameters depending on action mode

        Returns:
            dict with keys: audio_file, audio_url, usage, meta_info
        """
        self._action = action
        self._request_kwargs = kwargs
        self.audio_chunks = []
        self.session_id = ""
        self.audio_url = ""
        self.podcast_meta = {}
        self.usage = {}
        self._generation_complete = threading.Event()
        self._last_activity_time = time.time()
        self._round_count = 0
        self._expected_rounds = None
        # For action=3, calculate expected round count from nlp_texts
        if action == 3 and "nlp_texts" in kwargs:
            self._expected_rounds = len(kwargs["nlp_texts"])

        headers = self._build_ws_headers()

        logger.info(f"Connecting to Podcast TTS WebSocket (action={action}, timeout={timeout}s)...")
        ws = websocket.WebSocketApp(
            PODCAST_WS_URL,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # Run WebSocket in a thread so we can enforce timeout
        ws_thread = threading.Thread(
            target=ws.run_forever,
            kwargs={"ping_interval": 10, "ping_timeout": 5},
            daemon=True,
        )
        ws_thread.start()

        # Wait for generation to complete or timeout
        start_time = time.time()
        last_progress_log = start_time
        progress_interval = 30  # Log progress every 30 seconds

        while not self._generation_complete.is_set():
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Generation timed out after {timeout}s")
                try:
                    ws.close()
                except Exception:
                    pass
                raise TimeoutError(f"Podcast generation timed out after {timeout}s")

            # Log periodic progress
            now = time.time()
            if now - last_progress_log >= progress_interval:
                idle = now - self._last_activity_time
                logger.info(
                    f"Progress: {elapsed:.0f}s elapsed, {self._round_count} rounds completed, "
                    f"{len(self.audio_chunks)} audio chunks, idle {idle:.0f}s"
                )
                last_progress_log = now

            # For action=3: detect when all nlp_texts rounds have been processed
            # The server sometimes stops sending events after all rounds complete
            # without sending PodcastEnd/SessionFinished
            if (self._expected_rounds is not None
                    and self._round_count >= self._expected_rounds
                    and (self.audio_chunks or self.audio_url)
                    and not self._generation_complete.is_set()):
                idle = now - self._last_activity_time
                if idle > 30:
                    logger.warning(
                        f"All {self._expected_rounds} rounds completed with audio data, "
                        f"but no PodcastEnd received (idle {idle:.0f}s). Treating as complete."
                    )
                    self._generation_complete.set()

            # Check if WebSocket thread has exited without setting the event
            if not ws_thread.is_alive() and not self._generation_complete.is_set():
                # Thread exited — check if we got podcast_end
                if self.audio_chunks or self.audio_url:
                    logger.warning("WebSocket thread exited without PODCAST_END event, but audio data was received")
                    self._generation_complete.set()
                else:
                    logger.error("WebSocket thread exited unexpectedly without audio data")
                    raise ConnectionError("WebSocket connection closed unexpectedly before podcast generation completed")

            self._generation_complete.wait(timeout=2)

        total_elapsed = time.time() - start_time
        logger.info(f"Generation completed in {total_elapsed:.1f}s ({self._round_count} rounds, {len(self.audio_chunks)} chunks)")

        return {
            "audio_chunks": self.audio_chunks,
            "audio_url": self.audio_url,
            "usage": self.usage,
            "meta_info": self.podcast_meta,
            "total_audio_bytes": sum(len(c) for c in self.audio_chunks),
            "elapsed_seconds": total_elapsed,
            "round_count": self._round_count,
        }


# ---------------------------------------------------------------------------
# Transcript Generation
# ---------------------------------------------------------------------------

def generate_markdown_from_nlp(nlp_texts: list, title: str = "播客文字稿") -> str:
    """Generate markdown transcript from nlp_texts."""
    lines = [f"# {title}", ""]
    for item in nlp_texts:
        speaker = item.get("speaker", "")
        text = item.get("text", "")
        # Map speaker IDs to friendly names
        if "male" in speaker.lower():
            speaker_name = "**男主持**"
        elif "female" in speaker.lower():
            speaker_name = "**女主持**"
        else:
            speaker_name = f"**{speaker}**"
        lines.append(f"{speaker_name}: {text}")
        lines.append("")
    return "\n".join(lines)


def generate_markdown_from_script(script_json: dict) -> str:
    """Generate markdown transcript from script JSON."""
    title = script_json.get("title", "播客文字稿")
    lines_md = [f"# {title}", ""]
    for line in script_json.get("lines", []):
        speaker = line.get("speaker", "male")
        paragraph = line.get("paragraph", "")
        speaker_name = "**男主持**" if speaker == "male" else "**女主持**"
        lines_md.append(f"{speaker_name}: {paragraph}")
        lines_md.append("")
    return "\n".join(lines_md)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def _download_audio_with_retry(url: str, output_file: str, max_retries: int = 3, timeout: int = 120) -> bool:
    """Download audio from URL with retry logic.

    Args:
        url: Audio download URL
        output_file: Path to save the downloaded file
        max_retries: Maximum number of download attempts
        timeout: Download timeout in seconds per attempt

    Returns:
        True if download succeeded, False otherwise
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Downloading audio from URL (attempt {attempt}/{max_retries})...")
            audio_response = requests.get(url, timeout=timeout, stream=True)
            if audio_response.status_code == 200:
                total_size = int(audio_response.headers.get('content-length', 0))
                downloaded = 0
                with open(output_file, "wb") as f:
                    for chunk in audio_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                if total_size > 0:
                    logger.info(f"Downloaded audio from URL: {downloaded}/{total_size} bytes ({downloaded/total_size*100:.1f}%)")
                else:
                    logger.info(f"Downloaded audio from URL: {downloaded} bytes")
                return True
            else:
                logger.warning(f"Download attempt {attempt} failed: HTTP {audio_response.status_code}")
        except requests.exceptions.Timeout:
            logger.warning(f"Download attempt {attempt} timed out ({timeout}s)")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Download attempt {attempt} connection error: {e}")
        except Exception as e:
            logger.warning(f"Download attempt {attempt} failed: {e}")

        if attempt < max_retries:
            wait_time = 5 * attempt
            logger.info(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)

    return False


def generate_podcast(
    content: str = "",
    content_file: str = "",
    output_file: str = "",
    script_file: str = "",
    transcript_file: str = "",
    locale: str = "zh",
    style: str = "",
    max_lines: int = 60,
    action: int = 0,
    input_url: str = "",
    prompt_text: str = "",
) -> str:
    """Full pipeline to generate podcast."""

    appid = os.getenv("VOLCENGINE_TTS_APPID")
    access_token = os.getenv("VOLCENGINE_TTS_ACCESS_TOKEN")

    if not appid or not access_token:
        raise ValueError(
            "Missing VOLCENGINE_TTS_APPID and VOLCENGINE_TTS_ACCESS_TOKEN. "
            "Get them from https://console.volcengine.com/speech/service"
        )

    # Read content from file if specified
    if content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Read content from {content_file} ({len(content)} chars)")

    generator = PodcastGenerator(
        appid=appid,
        access_token=access_token,
        audio_format="mp3",
        sample_rate=24000,
        use_head_music=False,
        return_audio_url=True,
    )

    # Determine action mode
    if action == 0 and input_url:
        # URL mode
        logger.info("=" * 60)
        logger.info("Mode: URL/Text Summary → Podcast (action=0)")
        logger.info("=" * 60)
        input_info = {"input_url": input_url}
        if content:
            input_info["input_text_max_length"] = 12000

        result = generator.generate(
            action=0,
            input_text=content if content else "",
            input_info=input_info,
        )

    elif action == 0:
        # Text summary mode
        logger.info("=" * 60)
        logger.info("Mode: Text Summary → Podcast (action=0)")
        logger.info("=" * 60)
        result = generator.generate(
            action=0,
            input_text=content,
        )

    elif action == 3:
        # NLP texts mode - first generate script via Doubao, then synthesize
        logger.info("=" * 60)
        logger.info("Mode: Doubao Script → NLP Texts → Podcast (action=3)")
        logger.info("=" * 60)

        script_json = generate_podcast_script_via_doubao(
            content=content,
            locale=locale,
            style=style,
            max_lines=max_lines,
        )

        # Save script
        if script_file:
            script_dir = os.path.dirname(script_file)
            if script_dir:
                os.makedirs(script_dir, exist_ok=True)
            with open(script_file, "w", encoding="utf-8") as f:
                json.dump(script_json, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved script to {script_file}")

        # Save transcript from script
        if transcript_file:
            transcript_dir = os.path.dirname(transcript_file)
            if transcript_dir:
                os.makedirs(transcript_dir, exist_ok=True)
            md = generate_markdown_from_script(script_json)
            with open(transcript_file, "w", encoding="utf-8") as f:
                f.write(md)
            logger.info(f"Saved transcript to {transcript_file}")

        nlp_texts = generator._build_nlp_texts(script_json["lines"], locale)
        logger.info(f"Built {len(nlp_texts)} NLP text rounds")

        result = generator.generate(
            action=3,
            nlp_texts=nlp_texts,
        )

    elif action == 4:
        # Prompt mode (with web search)
        logger.info("=" * 60)
        logger.info("Mode: Prompt → Web Search → Podcast (action=4)")
        logger.info("=" * 60)
        prompt = prompt_text or content[:200]
        result = generator.generate(
            action=4,
            prompt_text=prompt,
        )

    else:
        raise ValueError(f"Invalid action: {action}. Must be 0, 3, or 4.")

    # Save audio
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Prefer audio URL download (higher quality, complete)
    saved_via_url = False
    if result.get("audio_url"):
        saved_via_url = _download_audio_with_retry(
            result["audio_url"], output_file,
            max_retries=3, timeout=120,
        )

    if not saved_via_url and result.get("audio_chunks"):
        audio_data = b"".join(result["audio_chunks"])
        with open(output_file, "wb") as f:
            f.write(audio_data)
        logger.info(f"Saved audio from WebSocket chunks: {len(audio_data)} bytes")

    # Build result message
    msg = f"Podcast generated successfully!"
    msg += f"\n  Audio: {output_file}"
    if result.get("audio_url"):
        msg += f"\n  Audio URL: {result['audio_url']} (expires in 1h)"
    if script_file:
        msg += f"\n  Script: {script_file}"
    if transcript_file:
        msg += f"\n  Transcript: {transcript_file}"
    if result.get("usage"):
        msg += f"\n  Usage: input_tokens={result['usage'].get('input_text_tokens', 0)}, output_tokens={result['usage'].get('output_audio_tokens', 0)}"
    if result.get("total_audio_bytes"):
        msg += f"\n  Audio size: {result['total_audio_bytes']} bytes"

    return msg


# ---------------------------------------------------------------------------
# Retry Wrapper
# ---------------------------------------------------------------------------

# Errors that are worth retrying (transient network/API issues)
RETRYABLE_ERRORS = (
    TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    websocket.WebSocketTimeoutException,
    websocket.WebSocketConnectionClosedException,
)


def _generate_podcast_with_retry(
    max_retries: int = 3,
    retry_delay: int = 10,
    **kwargs,
) -> str:
    """Wrapper around generate_podcast with retry logic for transient failures.

    Args:
        max_retries: Maximum number of retry attempts (default 3)
        retry_delay: Base delay between retries in seconds, doubles each attempt
        **kwargs: All arguments passed to generate_podcast

    Returns:
        Result message from generate_podcast

    Raises:
        The last exception if all retries are exhausted
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Podcast generation attempt {attempt}/{max_retries}")
            result = generate_podcast(**kwargs)

            # Validate the output file exists and has content
            output_file = kwargs.get("output_file", "")
            if output_file and os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                if file_size < 1024:
                    logger.warning(f"Output file too small ({file_size} bytes), possible generation failure")
                    if attempt < max_retries:
                        wait = retry_delay * (2 ** (attempt - 1))
                        logger.info(f"Retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                else:
                    logger.info(f"Output file validated: {file_size} bytes")
            return result

        except RETRYABLE_ERRORS as e:
            last_error = e
            logger.warning(f"Attempt {attempt} failed with retryable error: {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait = retry_delay * (2 ** (attempt - 1))  # exponential backoff: 10s, 20s, 40s
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"All {max_retries} attempts exhausted")

        except Exception as e:
            # Check if the error message indicates a retryable condition
            error_str = str(e).lower()
            is_retryable = any(keyword in error_str for keyword in [
                "timeout", "connection", "reset", "503", "502", "429", "rate limit",
                "server error", "internal error", "temporarily unavailable",
            ])

            if is_retryable and attempt < max_retries:
                last_error = e
                logger.warning(f"Attempt {attempt} failed with potentially retryable error: {e}")
                wait = retry_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                # Non-retryable or last attempt — raise immediately
                raise

    raise last_error or RuntimeError("All retry attempts exhausted with unknown error")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate podcast using Volcengine Podcast TTS WebSocket API"
    )

    # Content input
    content_group = parser.add_mutually_exclusive_group(required=False)
    content_group.add_argument("--content", help="Source text content")
    content_group.add_argument("--content-file", help="Path to text file with source content")

    # Output files
    parser.add_argument("--output-file", required=True, help="Output MP3 file path")
    parser.add_argument("--script-file", help="Output script JSON path (action=3 only)")
    parser.add_argument("--transcript-file", help="Output transcript markdown path")

    # Mode selection
    parser.add_argument(
        "--action",
        type=int,
        choices=[0, 3, 4],
        default=0,
        help="Generation mode: 0=text/URL summary (default), 3=pre-written dialogue, 4=prompt with search",
    )
    parser.add_argument("--input-url", help="URL for action=0 URL mode")
    parser.add_argument("--prompt-text", help="Prompt text for action=4 mode")

    # Options
    parser.add_argument("--locale", choices=["zh", "en"], default="zh")
    parser.add_argument("--style", choices=["tech", "news", "knowledge", "casual"], default="")
    parser.add_argument("--max-lines", type=int, default=60, help="Max dialogue lines for action=3")
    parser.add_argument("--use-head-music", action="store_true", help="Add intro music")

    args = parser.parse_args()

    # Validate content for action 0 and 3
    if args.action in (0, 3) and not args.content and not args.content_file and not args.input_url:
        parser.error("--content, --content-file, or --input-url is required for action=0/3")

    try:
        result = _generate_podcast_with_retry(
            content=args.content or "",
            content_file=args.content_file or "",
            output_file=args.output_file,
            script_file=args.script_file or "",
            transcript_file=args.transcript_file or "",
            locale=args.locale,
            style=args.style,
            max_lines=args.max_lines,
            action=args.action,
            input_url=args.input_url or "",
            prompt_text=args.prompt_text or "",
            max_retries=3,
        )
        print(result)
    except Exception as e:
        import traceback
        print(f"Error generating podcast: {e}")
        traceback.print_exc()
        sys.exit(1)
