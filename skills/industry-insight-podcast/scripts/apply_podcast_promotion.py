#!/usr/bin/env python3
"""Apply an active promotion clip to the podcast MP3s in this run.

Prefers assets/promotions/YYYY-MM-DD.json, then falls back to default.json.
The append operation is delegated to append_host_clip.py.

A promotion may target all three regular shows, but a run can contain only one
or two shows (for example, a standalone industry insight). In that case, apply
the clip only to podcast types present in config.json.
"""

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from append_host_clip import NEWS_BASE, append_clip  # noqa: E402

DEFAULT_PROMOTIONS_DIR = SCRIPT_DIR.parent / "assets" / "promotions"


def load_promotion(date: str, promotions_dir: Path) -> tuple[Path, dict]:
    dated_config = promotions_dir / f"{date}.json"
    config_path = dated_config if dated_config.exists() else promotions_dir / "default.json"
    if not config_path.exists():
        raise FileNotFoundError(f"缺少推广配置: {dated_config} 或 default.json")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    active_from = config.get("active_from")
    active_until = config.get("active_until")
    if active_from and date < active_from:
        raise ValueError(f"推广尚未生效: {date} < {active_from}")
    if active_until and date > active_until:
        raise ValueError(f"推广已经结束: {date} > {active_until}")

    clip_value = config.get("clip")
    types = config.get("types")
    if not clip_value:
        raise ValueError(f"推广配置缺少 clip: {config_path}")
    if not isinstance(types, list) or not types:
        raise ValueError(f"推广配置 types 必须是非空数组: {config_path}")

    clip = Path(clip_value).expanduser()
    if not clip.is_absolute():
        clip = config_path.parent / clip
    return clip.resolve(), config


def main() -> None:
    parser = argparse.ArgumentParser(description="给播客拼接当期推广音频")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--promotions-dir",
        default=str(DEFAULT_PROMOTIONS_DIR),
        help="推广配置目录",
    )
    parser.add_argument("--podcast-dir", help="播客产物目录")
    args = parser.parse_args()

    try:
        clip, config = load_promotion(args.date, Path(args.promotions_dir))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        sys.exit(str(exc))
    if not clip.exists():
        sys.exit(f"推广音频不存在: {clip}")

    podcast_dir = (
        Path(args.podcast_dir).expanduser()
        if args.podcast_dir
        else NEWS_BASE / "data" / args.date / "podcast"
    )
    if not podcast_dir.exists():
        sys.exit(f"播客目录不存在: {podcast_dir}")

    config_path = podcast_dir / "config.json"
    if not config_path.is_file():
        sys.exit(f"config.json 不存在: {config_path}")
    try:
        podcast_config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"config.json 解析失败: {exc}")

    configured_types = {
        entry.get("type")
        for entry in podcast_config.get("podcasts", [])
        if entry.get("type")
    }
    target_types = [
        type_ for type_ in config["types"] if type_ in configured_types
    ]
    if not target_types:
        print(
            json.dumps(
                {
                    "date": args.date,
                    "promo_id": config.get("promo_id"),
                    "status": "skipped",
                    "reason": "本轮栏目不在推广配置覆盖范围内",
                    "configured_types": sorted(configured_types),
                    "promotion_types": config["types"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    missing = [
        type_
        for type_ in target_types
        if not (podcast_dir / f"{type_}_{args.date}.mp3").exists()
    ]
    if missing:
        sys.exit(f"缺少播客文件: {', '.join(missing)}")

    with contextlib.redirect_stdout(io.StringIO()):
        results = [
            append_clip(podcast_dir, type_, args.date, clip)
            for type_ in target_types
        ]
    print(
        json.dumps(
            {
                "date": args.date,
                "promo_id": config.get("promo_id"),
                "label": config.get("label"),
                "clip": str(clip),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
