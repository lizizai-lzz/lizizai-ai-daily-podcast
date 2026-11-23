#!/usr/bin/env python3
"""检查逐字稿的"口播声纹"密度是否达标。

真实中文播客（9 档 / 12 段开头实测，见 references/voice-samples.md）：
句尾语气词 13.5/千字、人称词 34.0/千字、问句 5.5/千字。
2026-09-28 的稿子是 0 / 4.1 / 0，所以听起来像念稿而不是说话。

2026-10-13 起（每日精选 / TTS 干净稿）：
- 人称、问句、书面连接词、平均句长仍是硬 FAIL
- 句尾语气词改为软建议（约 2–5/千字，宁少勿滥）：不足或 >8 只 WARN，不再因语气词不足 FAIL
- TTS 禁区：专有名词后、数字/评分后、纯事实陈述句尾，禁止加 啊/呢/吧/嘛/呀
  （启发式命中 → 硬 FAIL，详见模块「TTS 语气词禁区」）

用法:
  python3 check_oral_voice.py --type daily_brief ~/.daily-ai-news/.../script_daily_brief_{date}.md
  python3 check_oral_voice.py --type opensource  ~/.daily-ai-news/.../script_opensource_{date}.md

退出码 0 = 无硬 FAIL（语气词密度 WARN 可保留）；1 = 有硬 FAIL（含 TTS 禁区命中）。
"""

import argparse
import re
import sys

PARTICLES = "啊呢吧嘛哎哦呀啦哈嗯"
PERSON = re.compile(r"我们|我|你|大家|咱们")
WRITTEN = re.compile(
    r"因此|然而|此外|综上|其次|首先|总之|值得注意|意味着|换句话说|由此可见|与此同时"
)
TAG = re.compile(r"\[[^\]]{1,12}\]")
SPEAKER = re.compile(r"^\s*\*{0,2}\s*[AB]\s*\*{0,2}\s*[:：]")
SPLIT = re.compile(r"[，。？！；、,]")

# 硬线（每千汉字）。语气词已从硬线移出，见 SOFT_*。
THRESHOLDS = {
    "daily_brief": {"person": 20.0, "questions": 2.5},
    "opensource": {"person": 25.0, "questions": 2.5},
    "industry": {"person": 25.0, "questions": 2.5},
}
MAX_WRITTEN = 2.0
CLAUSE_RANGE = (8.0, 18.0)

# 语气词软建议（每千汉字）：约 2–5，宁少勿滥；不足或偏多只 WARN
SOFT_PARTICLE_MIN = 2.0
SOFT_PARTICLE_TARGET_MAX = 5.0
SOFT_PARTICLE_WARN_HIGH = 8.0  # >8 WARN（可能在硬凑）

# TTS 禁区启发式：分句末尾是语气词，且末尾前像专名/数字/纯事实尾巴
# 专名片段：连续拉丁词、或常见中文专名后缀前的短词+语气词
FORBIDDEN_BEFORE_PARTICLE = re.compile(
    r"(?:"
    r"[A-Za-z][A-Za-z0-9\.\-]*(?:\s+[A-Za-z][A-Za-z0-9\.\-]*){0,3}"  # Muse Wonder Full
    r"|[零一二三四五六七八九十百千万亿两点\d]+(?:分|星|亿|万|元)?"  # 数字/评分
    r"|成果|达成|谈崩了|都高|颗星|文档|位置|共性|架构"
    r")"
    r"[啊呢吧嘛呀]$"
)


def plain_text(path: str) -> str:
    """去掉情感标签、A:/B: 前缀、标题和分隔符，只留要读出口的字。"""
    out = []
    for line in open(path, encoding="utf-8").read().splitlines():
        line = SPEAKER.sub("", line.strip())
        if not line or line.startswith("#") or line.startswith("==="):
            continue
        out.append(TAG.sub("", line))
    return "".join(out)


def measure(text: str) -> dict:
    han = len(re.findall(r"[\u4e00-\u9fff]", text)) or 1
    clauses = [c for c in SPLIT.split(text) if c.strip()]
    return {
        "han": han,
        "clauses": len(clauses),
        "clause_len": sum(len(c) for c in clauses) / max(len(clauses), 1),
        "particles": sum(1 for c in clauses if c[-1] in PARTICLES) / han * 1000,
        "person": len(PERSON.findall(text)) / han * 1000,
        "questions": len(re.findall(r"[？?]", text)) / han * 1000,
        "written": len(WRITTEN.findall(text)) / han * 1000,
        "clause_list": clauses,
    }


def scan_tts_forbidden(clauses: list) -> list:
    """简单启发式：疑似禁区语气词，返回若干示例分句。"""
    hits = []
    for c in clauses:
        c = c.strip()
        if not c or c[-1] not in "啊呢吧嘛呀":
            continue
        # 问句语气词允许（整句在问号前已被 SPLIT 切开，问号本身不在分句里）
        # 禁区：专名/数字/事实尾巴 + 语气词
        if FORBIDDEN_BEFORE_PARTICLE.search(c):
            hits.append(c[-24:] if len(c) > 24 else c)
    return hits[:8]


def main() -> int:
    parser = argparse.ArgumentParser(description="检查口播声纹密度")
    parser.add_argument("script", help="逐字稿路径")
    parser.add_argument("--type", default="daily_brief",
                        choices=sorted(THRESHOLDS),
                        help="哪一栏：daily_brief（默认）、opensource、industry")
    args = parser.parse_args()

    th = THRESHOLDS[args.type]
    m = measure(plain_text(args.script))
    print(f"栏目 {args.type}")
    print(f"汉字 {m['han']} | 分句 {m['clauses']} | 平均句长 {m['clause_len']:.1f}")
    print(f"句尾语气词 {m['particles']:.1f} | 人称词 {m['person']:.1f} | "
          f"问句 {m['questions']:.1f} | 书面连接词 {m['written']:.1f}")

    fails = []
    warns = []

    # —— 硬 FAIL：人称 / 问句 / 书面连接词 / 句长 ——
    if m["person"] < th["person"]:
        fails.append(f"人称词 {m['person']:.1f} < {th['person']}")
    if m["questions"] < th["questions"]:
        fails.append(f"问句 {m['questions']:.1f} < {th['questions']}")
    if m["written"] > MAX_WRITTEN:
        fails.append(f"书面连接词 {m['written']:.1f} > {MAX_WRITTEN}")
    if not CLAUSE_RANGE[0] <= m["clause_len"] <= CLAUSE_RANGE[1]:
        fails.append(f"平均句长 {m['clause_len']:.1f} 不在 {CLAUSE_RANGE} 内")

    # —— 语气词：仅 WARN（不足或偏多）——
    if m["particles"] < SOFT_PARTICLE_MIN:
        warns.append(
            f"句尾语气词 {m['particles']:.1f} < {SOFT_PARTICLE_MIN}"
            f"（软建议约 {SOFT_PARTICLE_MIN}–{SOFT_PARTICLE_TARGET_MAX}/千字，宁少勿滥；不足不 FAIL）"
        )
    elif m["particles"] > SOFT_PARTICLE_WARN_HIGH:
        warns.append(
            f"句尾语气词 {m['particles']:.1f} > {SOFT_PARTICLE_WARN_HIGH}"
            f"（可能在硬凑；TTS 稿建议压到约 {SOFT_PARTICLE_TARGET_MAX} 以下，并避开禁区）"
        )
    elif m["particles"] > SOFT_PARTICLE_TARGET_MAX:
        warns.append(
            f"句尾语气词 {m['particles']:.1f} 略高于软建议上限 {SOFT_PARTICLE_TARGET_MAX}"
            f"（可接受，但进火山 TTS 前请清掉专名/数字后的尾音）"
        )

    forbidden = scan_tts_forbidden(m["clause_list"])
    if forbidden:
        fails.append("TTS 语气词禁区（专名/数字/事实句尾）命中，示例：")
        for h in forbidden:
            fails.append(f"    · …{h}")

    if warns:
        print("WARN（不单独阻断，但进录音前建议处理语气词密度）：")
        for w in warns:
            print(f"  - {w}")

    if fails:
        print("FAIL 逐字稿未过检，禁止进 TTS 录音：")
        for f in fails:
            print(f"  - {f}")
        print("  补「人在场」：第三人称判断改成「我/我们/你」开头，加真问句。")
        print("  清掉专名/数字/事实句尾的语气词；问句里的语气词可留。")
        print("  参考模块「口语化生成规范」与 references/voice-samples.md")
        return 1

    if warns:
        print("PASS 硬指标达标（有语气词密度 WARN，见上；禁区已清空）")
    else:
        print("PASS 硬指标达标（人称、问句在线；语气词在软建议内；禁区清空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
