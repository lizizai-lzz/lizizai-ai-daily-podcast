#!/usr/bin/env python3
"""
Gemini API 调用脚本。

职责：
1. 从环境变量读取 GEMINI_API_KEY（要求用户已在 ~/.zshrc 中 export）。
2. 接收两个输入文件：
   - system_prompt.txt：完整系统提示词
   - user_content.txt：调用 Gemini 时作为上下文 / 用户输入的内容
3. 调用 Gemini `generateContent` 接口（gemini-4-hydrogen）。
4. 把返回的纯文本写入指定的输出路径（markdown）。

用法：
    python3 gemini_call.py \
        --system system_prompt.txt \
        --content user_content.txt \
        --output article.md

可选：
    --model gemini-4-hydrogen    （默认值，可改其它模型名，如 gemini-4-neon / gemini-4-argon）
    --endpoint v1alpha            （默认 v1alpha）
    --raw-json                    （同时把原始 JSON 落盘到 <output>.raw.json）

环境变量：
    GEMINI_API_KEY  必需，从 ~/.zshrc 加载

退出码：
    0  成功
    1  参数错误 / API key 缺失
    2  网络 / HTTP 错误
    3  响应解析错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gemini-4-hydrogen"
DEFAULT_ENDPOINT = "v1alpha"
API_BASE = "https://generativelanguage.googleapis.com"


def die(message: str, code: int) -> None:
    print(f"[gemini-writer] ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def load_api_key() -> str:
    """优先用进程环境变量；若为空，尝试 source ~/.zshrc 再回读。"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    # 回退：从 ~/.zshrc 抽取 export GEMINI_API_KEY=...
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        for line in zshrc.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("export ") and "GEMINI_API_KEY" in stripped:
                # export GEMINI_API_KEY='xxx' / export GEMINI_API_KEY="xxx" / export GEMINI_API_KEY=xxx
                _, _, rhs = stripped.partition("=")
                rhs = rhs.strip().strip(";")
                if len(rhs) >= 2 and rhs[0] in {"'", '"'} and rhs[-1] == rhs[0]:
                    rhs = rhs[1:-1]
                if rhs:
                    return rhs
    die(
        "未找到 GEMINI_API_KEY。请在 ~/.zshrc 中加入：export GEMINI_API_KEY='your_key'",
        1,
    )


def read_text_file(path: Path, label: str) -> str:
    if not path.exists():
        die(f"{label} 文件不存在: {path}", 1)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 兜底用 utf-8 ignore 读取
        return path.read_text(encoding="utf-8", errors="ignore")


def call_gemini(
    api_key: str,
    system_prompt: str,
    user_content: str,
    model: str,
    endpoint: str,
    max_tokens: int = 65536,
) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint}/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_content}]}],
        # 适度抑制过度创造性，保持文章稳定输出
        # maxOutputTokens 默认调高至 65536，避免长文（>2000字）被 MAX_TOKENS 截断
        "generationConfig": {
            "temperature": 0.8,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": max_tokens,
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        snippet = ""
        try:
            snippet = e.read().decode("utf-8", errors="ignore")[:1000]
        except Exception:
            pass
        die(f"Gemini HTTP {e.code}: {e.reason}\n{snippet}", 2)
    except urllib.error.URLError as e:
        die(f"网络错误: {e}", 2)
    except (ConnectionError, TimeoutError) as e:
        # RemoteDisconnected / 连接重置 / 超时不在 URLError 覆盖范围内
        die(f"连接被中断或超时（{type(e).__name__}）: {e}\n可稍后重试；gemini-4-neon 在 v1beta 端点偶发断连，可试 --endpoint v1alpha", 2)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"响应不是合法 JSON: {e}\n原始内容前 1000 字符:\n{raw[:1000]}", 3)


def extract_text(response: dict[str, Any]) -> str:
    """从 generateContent 响应里抽出纯文本。出错则抛出带提示的异常。"""
    try:
        candidates = response["candidates"]
        if not candidates:
            # 看是否有 promptFeedback / safety 问题
            feedback = response.get("promptFeedback")
            die(f"无候选结果，promptFeedback={feedback}", 3)
        parts = candidates[0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as e:
        die(f"响应结构异常，无法抽取文本: {e}\n响应 JSON:\n{json.dumps(response, ensure_ascii=False, indent=2)[:2000]}", 3)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="调用 Gemini 生成文章，输出 markdown 文件。"
    )
    parser.add_argument(
        "--system", required=True, help="系统提示词文本文件路径"
    )
    parser.add_argument(
        "--content", required=True, help="上下文 / 用户输入文本文件路径"
    )
    parser.add_argument(
        "--output", required=True, help="输出 markdown 文件路径"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名，默认 {DEFAULT_MODEL}")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=f"API 版本，默认 {DEFAULT_ENDPOINT}")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=65536,
        help="生成最大 token 数，默认 65536（长文需要更大值，否则会被 MAX_TOKENS 截断）",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="同时把原始 JSON 响应写到 <output>.raw.json",
    )
    args = parser.parse_args()

    api_key = load_api_key()
    system_prompt = read_text_file(Path(args.system), "system prompt")
    user_content = read_text_file(Path(args.content), "user content")

    if not system_prompt.strip():
        die("system prompt 为空", 1)
    if not user_content.strip():
        die("user content 为空", 1)

    response = call_gemini(
        api_key=api_key,
        system_prompt=system_prompt,
        user_content=user_content,
        model=args.model,
        endpoint=args.endpoint,
        max_tokens=args.max_tokens,
    )
    text = extract_text(response)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"[gemini-writer] 已写入: {out_path}")

    if args.raw_json:
        raw_path = out_path.with_suffix(out_path.suffix + ".raw.json")
        raw_path.write_text(
            json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[gemini-writer] 原始响应: {raw_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
