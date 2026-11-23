#!/usr/bin/env python3
"""Check the one-host-per-news-item rule in a 每日精选 A:/B: script.

The two hosts take turns by news item: A reads one item end to end, then B
reads the next one. Anything that alternates *inside* an item (A fact, B
comment, A takeaway) is a bug — it makes the episode sound like both hosts
are talking over the same story.

Block 1 is the intro and the last block is the outro; those two may mix A/B
(brand lines). Every block in between is a news item and must be single-host.

Usage:
  python3 check_broadcast_speakers.py ~/.daily-ai-news/data/{date}/podcast/script_daily_brief_{date}.md

Exit code 0 = pass, 1 = at least one news item switches hosts mid-item.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_news_broadcast import parse_items, validate_items  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that each 每日精选 news item is read by one host"
    )
    parser.add_argument("script", help="Path to the A:/B: script (.md)")
    args = parser.parse_args()

    with open(args.script, "r", encoding="utf-8") as handle:
        items = parse_items(handle.read())

    if not items:
        print("FAIL 脚本里没有解析到任何 A:/B: 行"
              "（2026-09-23 起的每日精选必须每行都带 A:/B: 前缀）")
        return 1

    check = validate_items(items)
    print(f"区块 {len(items)} 个 | 新闻 {len(check['leads'])} 条 | "
          f"播报顺序 {' '.join(check['leads']) or '(无)'}")

    if check["mixed"]:
        for item_number, speakers in check["mixed"]:
            print(f"FAIL 第 {item_number} 条新闻中途换人：{' → '.join(speakers)}")
        print("     一条新闻只能由一位主持读完，换人只发生在 === 处")
        return 1

    for left, right in zip(check["leads"], check["leads"][1:]):
        if left == right:
            print(f"WARN 相邻两条新闻都是 {left} 声，交替顺序可能不对")

    print("PASS 每条新闻都由一位主持从头读到尾")
    return 0


if __name__ == "__main__":
    sys.exit(main())
