#!/usr/bin/env python3
"""阿里云百炼 语音转文字（听悟同源 ASR，含说话人分离）。

把本地音视频文件（或公网 URL）转成带说话人标签和时间戳的 Markdown 文字稿。

用法:
  python transcribe_audio.py <file_or_url> [<file_or_url> ...] [options]

必需环境变量:
  DASHSCOPE_API_KEY  阿里云百炼 API Key（获取: https://help.aliyun.com/zh/model-studio/get-api-key）

本地文件上传依赖 OSS 配置（复用 aliyun-oss-upload skill 的配置）:
  ~/.config/aliyun-oss/config.json
  格式: {"access_key_id":"...","access_key_secret":"...","endpoint":"oss-cn-xxx.aliyuncs.com",
         "bucket":"...","key_prefix":"...","object_acl":"public-read",
         "public_base_url":"https://<bucket>.<endpoint>"}

计费参考（2026-08，按音频时长）:
  paraformer-v2: 0.288 元/小时，每月免费 10 小时（36,000 秒）
  听悟 ASR(百炼): 0.6 元/小时（含说话人分离、自动语种识别）
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid
from datetime import date
from pathlib import Path


API_BASE = os.environ.get("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
OSS_CONFIG_DEFAULT = os.path.expanduser("~/.config/aliyun-oss/config.json")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def http_json(method, url, payload=None, headers=None, timeout=120):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {os.environ['DASHSCOPE_API_KEY']}")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        die(f"HTTP {e.code} from {url}: {body}")


def upload_to_oss(path, key_prefix, config_path):
    if not os.path.exists(config_path):
        die(f"OSS 配置缺失: {config_path}\n请按 SKILL.md 的配置说明创建。")
    try:
        import oss2
    except ImportError:
        die("缺少 oss2，请先安装: pip install oss2（或用技能自带 venv）")
    cfg = json.load(open(config_path))
    auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
    bucket = oss2.Bucket(auth, cfg["endpoint"], cfg["bucket"])
    ext = Path(path).suffix or ".bin"
    key = f"{key_prefix}/{date.today().isoformat()}/{uuid.uuid4().hex[:8]}{ext}"
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    headers = {"Content-Type": content_type} if content_type else None
    bucket.put_object_from_file(key, path, headers=headers)
    base = cfg.get("public_base_url", f"https://{cfg['bucket']}.{cfg['endpoint']}").rstrip("/")
    return f"{base}/{key}"


def submit_task(file_url, model, diarization, speaker_count, language_hints, extra_params):
    parameters = dict(extra_params or {})
    if diarization:
        parameters["diarization_enabled"] = True
        if speaker_count:
            parameters["speaker_count"] = speaker_count
    if language_hints:
        parameters["language_hints"] = language_hints
    payload = {"model": model, "input": {"file_urls": [file_url]}, "parameters": parameters}
    resp = http_json(
        "POST",
        f"{API_BASE}/services/audio/asr/transcription",
        payload,
        headers={"X-DashScope-Async": "enable"},
    )
    task_id = resp.get("output", {}).get("task_id")
    if not task_id:
        die(f"提交失败: {json.dumps(resp, ensure_ascii=False)}")
    return task_id


def poll_task(task_id, timeout_sec=3600, interval=15):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = http_json("GET", f"{API_BASE}/tasks/{task_id}")
        out = resp.get("output", {})
        status = out.get("task_status")
        if status == "SUCCEEDED":
            return out
        if status in ("FAILED", "UNKNOWN"):
            die(f"任务 {task_id} 失败: {out.get('message', status)}")
        time.sleep(interval)
    die(f"任务 {task_id} 超时（{timeout_sec}s）")


def result_json(task_output):
    # paraformer 系列: output.results[0].output.results[0].transcription_url
    # qwen3-asr-flash-filetrans: output.result.transcription_url
    tu = None
    try:
        tu = task_output["results"][0]["output"]["results"][0]["transcription_url"]
    except (KeyError, IndexError, TypeError):
        pass
    if tu is None:
        try:
            tu = task_output["result"]["transcription_url"]
        except (KeyError, TypeError):
            die(f"无法从任务结果中解析 transcription_url: {json.dumps(task_output, ensure_ascii=False)[:800]}")
    with urllib.request.urlopen(tu, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def fmt_ts(ms):
    s = ms / 1000
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def to_markdown(data, title):
    lines = [f"# {title}", ""]
    props = data.get("properties", {})
    dur = props.get("original_duration_in_milliseconds")
    if dur:
        lines.append(f"> 音频时长：{dur / 1000:.0f} 秒")
    transcripts = data.get("transcripts", [])
    if not transcripts:
        return "\n".join(lines) + "\n\n（无转写内容）"
    for ch in transcripts:
        sentences = ch.get("sentences", [])
        speakers = sorted({s.get("speaker_id", 0) for s in sentences})
        lines.append(f"> 声道 {ch.get('channel_id', 0)}：{len(sentences)} 句，{len(speakers)} 个说话人")
    lines.append("")
    for ch in transcripts:
        for s in ch.get("sentences", []):
            sp = s.get("speaker_id", 0)
            lines.append(
                f"[{fmt_ts(s.get('begin_time', 0))}-{fmt_ts(s.get('end_time', 0))}] "
                f"说话人{sp}：{s.get('text', '')}"
            )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="阿里云百炼语音转文字（含说话人分离）")
    ap.add_argument("inputs", nargs="+", help="本地音视频文件路径或公网 URL")
    ap.add_argument("--model", default="paraformer-v2",
                    help="ASR 模型（默认 paraformer-v2；备选 qwen3-asr-flash-filetrans、qwen-audio-3.0-asr-flash-filetrans、paraformer-1）")
    ap.add_argument("--no-diarization", action="store_true", help="关闭说话人分离")
    ap.add_argument("--speaker-count", type=int, default=2, help="预估说话人数（默认 2）")
    ap.add_argument("--language-hints", nargs="*", default=None,
                    help="语种提示，如 --language-hints zh en（qwen 系列支持）")
    ap.add_argument("--output-dir", default=".", help="结果输出目录（默认当前目录）")
    ap.add_argument("--oss-config", default=OSS_CONFIG_DEFAULT, help="OSS 配置文件路径")
    ap.add_argument("--oss-key-prefix", default="transcribe", help="OSS 对象 key 前缀")
    ap.add_argument("--extra-param", action="append", default=[], help="额外参数 JSON，如 '{\"enable_itn\": false}'")
    args = ap.parse_args()

    if not os.environ.get("DASHSCOPE_API_KEY"):
        die("缺少环境变量 DASHSCOPE_API_KEY")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    extra = {}
    for p in args.extra_param:
        extra.update(json.loads(p))

    for inp in args.inputs:
        name = Path(inp).stem if inp.startswith(("http://", "https://")) else Path(inp).stem
        print(f"== 处理: {inp}")
        file_url = inp
        if inp.startswith(("http://", "https://")):
            print("  使用公网 URL")
        else:
            if not os.path.exists(inp):
                die(f"文件不存在: {inp}")
            print("  上传到 OSS ...")
            file_url = upload_to_oss(inp, args.oss_key_prefix, args.oss_config)
            print(f"  OSS URL: {file_url}")

        task_id = submit_task(
            file_url, args.model, not args.no_diarization,
            args.speaker_count, args.language_hints, extra,
        )
        print(f"  任务已提交: {task_id}，轮询中 ...")
        task_out = poll_task(task_id)
        data = result_json(task_out)

        json_path = out_dir / f"{name}.json"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        md = to_markdown(data, name)
        md_path = out_dir / f"{name}.md"
        md_path.write_text(md, encoding="utf-8")
        print(f"  完成: {json_path}")
        print(f"  完成: {md_path}")


if __name__ == "__main__":
    main()
