#!/usr/bin/env python3
"""
「李自在AI人物志」单集 config.json 生成器

读取集数目录下的 episode_meta.json（由 merge_audio.py 输出），
生成符合小宇宙上传要求的 config.json。

description 结构（小宇宙规范 https://post.xiaoyuzhoufm.com/timespot/）：
    1. 一段简短人物介绍（--intro 提供，30-80 字）
    2. 章节时点列表（从 40_final.md 章节自动提取，按字数占比分配时间戳）
    3. 固定页脚「李自在AI人物志」slogan

用法：
    python3 generate_config.py \\
        --episode-dir E01.山姆奥特曼 \\
        --highlight 用OpenAI点燃全球AI浪潮 \\
        --intro "OpenAI 联合创始人兼 CEO，把 ChatGPT 带到全球每个人的桌面。" \\
        --title "山姆奥特曼：ChatGPT 之父"

若不提供 --title，则使用默认格式 `E{NN}.{person}：{highlight}`。
若不提供 --intro，回退到旧的里程碑格式。

config.json 结构见 references/config-schema.md。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta


def parse_publish_at(value):
    """解析 `--publish-at` 传入的 ISO 8601 时间字符串。

    接受：
        2026-07-20T09:00:00+08:00     (推荐，含时区)
        2026-07-20T09:00:00Z          (UTC)
        2026-07-20T09:00:00           (无时区 → 默认 Asia/Shanghai)
        2026-07-20T09:00              (无秒、无时区 → 同上)
        2026-07-20 09:00              (空格分隔 → 同上)

    返回：
        (datetime_aware, iso_normalized) 其中 datetime_aware 必带 tzinfo，
        iso_normalized 为写入 config.json 的格式（保留原时区偏移的秒级精度）。

    失败时抛出 ValueError，调用方负责打印。
    """
    if not value:
        raise ValueError("空字符串")
    s = value.strip()
    # 空格分隔兼容
    s = s.replace(" ", "T", 1)
    # 短格式补全
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", s):
        s = s + ":00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"无法解析为 ISO 8601: {value!r}（{e}）") from e
    if dt.tzinfo is None:
        # 默认按 Asia/Shanghai（UTC+8）解释
        cst = timezone(timedelta(hours=8), name="CST")
        dt = dt.replace(tzinfo=cst)
    if dt <= datetime.now(tz=dt.tzinfo):
        raise ValueError(f"发布时间必须是未来时间：{dt.isoformat()}")
    # 限制 14 天内：与小宇宙创作者后台 picker 的可选范围一致（实测 2026-07）。
    max_delta_days = 14
    if (dt - datetime.now(tz=dt.tzinfo)).days > max_delta_days:
        raise ValueError(
            f"小宇宙定时发布最多提前 {max_delta_days} 天，"
            f"距离当前 {(dt - datetime.now(tz=dt.tzinfo)).days} 天，超出限制。"
        )
    return dt, dt.isoformat(timespec="seconds")


def parse_episode_dir(episode_dir):
    """从目录名解析集数和人物名。

    支持：
        E01.山姆奥特曼 → (1, "山姆奥特曼")
        E03.黄仁勋 → (3, "黄仁勋")
        E12.Midjourney 创始人 David Holz → (12, "Midjourney 创始人 David Holz")
    """
    basename = os.path.basename(os.path.normpath(episode_dir))
    m = re.match(r"^E(\d+)\.(.+)$", basename)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2).strip()


def format_episode_title(episode_num, person, highlight):
    """生成默认小宇宙标题：E[数字].[人物名]：[亮点总结]。

    小宇宙单集标题无硬性字数限制，但建议亮点总结 ≤ 15 字（SKILL.md 约束）。
    """
    return f"E{episode_num:02d}.{person}：{highlight}"


def load_episode_meta(episode_dir):
    """读取 merge_audio.py 输出的 episode_meta.json。"""
    meta_path = os.path.join(episode_dir, "episode_meta.json")
    if not os.path.isfile(meta_path):
        return None
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def find_script_file(episode_dir):
    """探测集数目录里的播客脚本（用于脚本字数统计）。"""
    for candidate in ("50_podcast_script.md", "podcast_script.md"):
        p = os.path.join(episode_dir, candidate)
        if os.path.isfile(p):
            return p
    return None


def find_source_file(episode_dir):
    """探测集数目录里的母文文件（10_source.md），用于提取里程碑（fallback）。"""
    p = os.path.join(episode_dir, "10_source.md")
    return p if os.path.isfile(p) else None


def find_final_file(episode_dir):
    """探测集数目录里的传记终稿（40_final.md），用于提取章节生成时点。"""
    p = os.path.join(episode_dir, "40_final.md")
    return p if os.path.isfile(p) else None


def count_script_chars(script_path):
    """统计脚本纯文本字数（去掉情感标签和 markdown 符号）。"""
    if not script_path:
        return None
    with open(script_path, encoding="utf-8") as f:
        text = f.read()
    # 去掉情感标签 [xxx]
    text = re.sub(r"\[[^\]]+\]", "", text)
    # 去掉 markdown 标记
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def extract_chapters(final_path):
    """从传记终稿 40_final.md 提取章节，用于生成时点。

    传记骨架由 biography-writer 生成，章节格式：
        ## 开篇：xxx
        ## 第一章：xxx
        ## 第二章：xxx
        ## 第七章：xxx
        ## 收束：xxx

    也兼容无「第X章」前缀的章节，如：
        ## 早期：xxx
        ## 巅峰：xxx

    返回 [(章节标题, 章节字数), ...]，按文档顺序。
    章节标题会做精简：去掉 Markdown 标记、去掉「开篇」「第一章」「收束」等前缀中的冗余部分
    （保留语义，便于听众阅读），但「开篇」「收束」会保留作为"序"和"尾声"。
    """
    if not final_path:
        return []
    with open(final_path, encoding="utf-8") as f:
        text = f.read()

    # 匹配所有二级标题（## xxx）
    heading_pattern = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if len(matches) < 2:
        return []

    chapters = []
    for i, match in enumerate(matches):
        raw_title = match.group(1).strip()
        # 找到下一个标题或文档末尾
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_pos:end_pos]
        # 章节字数（去掉空白和标点）
        body_clean = re.sub(r"\s+", "", body)
        body_clean = re.sub(r"[#*\-_>]", "", body_clean)
        char_count = len(body_clean)

        # 精简章节标题
        title = _simplify_chapter_title(raw_title)
        chapters.append((title, char_count))

    return chapters


def _simplify_chapter_title(raw_title):
    """精简章节标题，去掉「——xxx」副标题、Markdown 加粗、书名号包裹的修饰等。

    保留主线，让标题更短更适合 Show Notes 时点列表。
    """
    title = raw_title.strip()
    # 去掉 Markdown 加粗
    title = re.sub(r"\*\*(.+?)\*\*", r"\1", title)
    # 去掉中文双破折号及后面的副标题（保留主标题）
    title = re.sub(r"\s*[——]+\s*.+$", "", title)
    # 去掉末尾的冒号
    title = re.sub(r"[：:]\s*$", "", title)
    return title.strip()


def format_timestamp(seconds):
    """把秒数格式化为小宇宙时点格式。

    小宇宙支持两种格式（https://post.xiaoyuzhoufm.com/timespot/）：
        - HH:MM:SS（小时:分钟:秒）
        - MM:SS（分钟:秒）

    规则：
        - < 1 小时 → MM:SS
        - >= 1 小时 → HH:MM:SS

    60 进制必须正确（01:59:59 合法，01:61:61 非法）。
    """
    total = max(0, int(round(seconds)))
    hours = total // 3600
    remainder = total % 3600
    minutes = remainder // 60
    secs = remainder % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_chapters_with_timestamps(chapters, intro_duration, main_duration):
    """按章节字数占比分配时间戳。

    Args:
        chapters: [(标题, 字数), ...]
        intro_duration: 片头时长（秒）。第一个章节的起始时间戳 = intro_duration。
        main_duration: 正片时长（秒）。各章节按字数占比瓜分 main_duration。

    Returns:
        [(timestamp, title), ...]
    """
    if not chapters:
        return []

    total_chars = sum(c for _, c in chapters)
    if total_chars == 0:
        return []

    # 起始时间 = 片头结束时间
    current = float(intro_duration)
    result = []
    for i, (title, chars) in enumerate(chapters):
        if i == 0:
            # 第一个章节的时点 = 片头结束位置
            ts = format_timestamp(current)
            result.append((ts, title))
            continue
        # 累加前一个章节的时长（按字数占比）
        prev_chars = chapters[i - 1][1]
        prev_duration = (prev_chars / total_chars) * main_duration
        current += prev_duration
        ts = format_timestamp(current)
        result.append((ts, title))

    return result


def build_description_with_timestamps(intro_text, chapters, person,
                                       intro_duration, main_duration,
                                       max_chars=500):
    """生成新的 Show Notes 结构：简短介绍 + 时点列表 + 固定页脚。

    Args:
        intro_text: 人物简短介绍（30-80 字）
        chapters: [(标题, 字数), ...]（从 40_final.md 提取）
        person: 人物名（用于 fallback 文案）
        intro_duration: 片头时长（秒）
        main_duration: 正片时长（秒）

    小宇宙时点格式见 https://post.xiaoyuzhoufm.com/timespot/。
    """
    # 第一部分：简短介绍
    parts = []
    if intro_text:
        parts.append(intro_text.strip())
        parts.append("")  # 空行分隔

    # 第二部分：时点列表
    ts_list = build_chapters_with_timestamps(
        chapters, intro_duration, main_duration)
    if ts_list:
        parts.append("## 时点")
        parts.append("")
        for ts, title in ts_list:
            parts.append(f"{ts} {title}")
        parts.append("")

    # 第三部分：固定页脚
    parts.append("---")
    parts.append("「李自在AI人物志」——在数字的微光里，读懂改变世界的人。")

    desc = "\n".join(parts)

    # 软字数约束：超长时截断时点（保留前 N 个）
    if len(desc) > max_chars and ts_list:
        # 逐步删除末尾时点
        while len(desc) > max_chars and len(ts_list) > 3:
            ts_list.pop()
            parts_inner = []
            if intro_text:
                parts_inner.append(intro_text.strip())
                parts_inner.append("")
            parts_inner.append("## 时点")
            parts_inner.append("")
            for ts, title in ts_list:
                parts_inner.append(f"{ts} {title}")
            parts_inner.append("")
            parts_inner.append("---")
            parts_inner.append("「李自在AI人物志」——在数字的微光里，读懂改变世界的人。")
            desc = "\n".join(parts_inner)

    return desc


def extract_milestones(source_path):
    """从母文 10_source.md 的「## 3. 关键人生节点」章节提取里程碑（fallback 用）。

    母文由 biography-writer 生成，节点标题格式：
        ### 节点 1：圣路易斯的犹太少年与那台 Mac（1985–2003）
        ### 节点 1：童年——比勒陀利亚的孤独天才
        ### 节点 2：1995——硅谷地板上钻洞偷接网线的青年

    返回 [(时间, 标题), ...]，时间为空字符串表示无时间标注。
    """
    if not source_path:
        return []
    with open(source_path, encoding="utf-8") as f:
        text = f.read()

    # 定位 ## 3. 关键人生节点 章节
    m = re.search(r"^## 3\. 关键人生节点.*?\n(.*?)(?=\n## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return []

    section = m.group(1)
    node_pattern = re.compile(r"^###\s+节点\s*\d*[：:]\s*(.+?)\s*$", re.MULTILINE)

    milestones = []
    matches = list(node_pattern.finditer(section))
    for match in matches:
        raw_title = match.group(1).strip()

        # 从标题末尾括号提取时间
        time_range = ""
        paren_m = re.search(r"[（(]([^）)]*)[）)]\s*$", raw_title)
        if paren_m:
            time_range = paren_m.group(1).strip()
            raw_title = raw_title[: paren_m.start()].strip()

        # 标题内含时间前缀：1995——xxx / 2008——xxx（中文双破折号）
        if not time_range:
            prefix_time_m = re.match(r"^(\d{4}[^\s——\-]*)\s*[——\-]+\s*(.+)", raw_title)
            if prefix_time_m:
                time_range = prefix_time_m.group(1).strip()
                raw_title = prefix_time_m.group(2).strip()

        # 清理标题内残留的中文双破折号 —— 替换为冒号
        raw_title = raw_title.replace("——", "：")

        milestones.append((time_range, raw_title))

    return milestones


def build_description(person, highlight, script_chars, source_path=None, max_chars=200):
    """[fallback] 生成旧版 Show Notes 描述。

    优先使用母文 10_source.md 的关键人生节点作为核心展示内容，
    总字数控制在 max_chars 以内。若母文不可用，回退到旧的亮点+脚本规模格式。
    """
    # 尝试从母文提取里程碑
    milestones = extract_milestones(source_path) if source_path else []

    if milestones:
        header = f"## 本期人物\n\n{person}\n\n## 关键里程碑\n\n"
        footer = "\n\n「李自在AI人物志」——在数字的微光里，读懂改变世界的人。"
        budget = max_chars - len(header) - len(footer)

        if budget > 50:
            lines = []
            used = 0
            for time_range, title in milestones:
                line = f"- {time_range} {title}" if time_range else f"- {title}"
                line_len = len(line) + 1  # +1 for newline
                if used + line_len > budget and lines:
                    break
                lines.append(line)
                used += line_len
            return header + "\n".join(lines) + footer

    # 回退：旧的亮点+脚本规模格式（无字数硬限制）
    desc = f"## 本期人物\n\n{person}\n\n"
    desc += f"## 内容亮点\n\n{highlight}\n\n"
    if script_chars:
        desc += f"## 脚本规模\n\n全篇约 {script_chars} 字，娓娓道来约 25-30 分钟。\n\n"
    desc += "---\n\n「李自在AI人物志」——在数字的微光里，读懂改变世界的人。\n"
    desc += "每一期，一个改变技术进程的人物故事。\n"
    return desc


def main():
    parser = argparse.ArgumentParser(description="「李自在AI人物志」config.json 生成器")
    parser.add_argument("--episode-dir", required=True,
                        help="集数目录（绝对或相对路径）")
    parser.add_argument("--episode-num", type=int, default=None,
                        help="集数编号（默认从目录名 E<数字> 解析）")
    parser.add_argument("--person", default=None,
                        help="人物名（默认从目录名解析；可用 --person 覆盖）")
    parser.add_argument("--highlight", required=True,
                        help="亮点总结（≤15 字，会拼到默认标题里）")
    parser.add_argument("--title", default=None,
                        help="小宇宙单集标题（覆盖默认 E{NN}.{person}：{highlight} 格式）。"
                             "注意：传入 --title 后，title 完全使用此值，不再自动拼接。")
    parser.add_argument("--intro", default=None,
                        help="人物简短介绍（30-80 字），用于 description 第一段。"
                             "提供后启用新的「介绍 + 时点 + 页脚」格式。")
    parser.add_argument("--output", default="config.json",
                        help="输出文件名（默认 config.json）")
    parser.add_argument("--publish-at", default=None,
                        help="[可选] 定时发布时间，ISO 8601 格式。\n"
                             "  支持：'2026-07-20T09:00:00+08:00' / '2026-07-20T09:00:00Z' / \n"
                             "        '2026-07-20T09:00:00'（默认 Asia/Shanghai）/ '2026-07-20T09:00'\n"
                             "  写入 config.json 顶层 scheduled_at 字段，upload_episode.py 会读取并执行定时发布。\n"
                             "  不传 = 立即发布（默认行为）。")
    args = parser.parse_args()

    episode_dir = os.path.abspath(args.episode_dir)
    if not os.path.isdir(episode_dir):
        print(f"[ERR] 集数目录不存在: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    # 集数/人物：命令行参数优先，否则从目录名解析
    dir_num, dir_person = parse_episode_dir(episode_dir)
    episode_num = args.episode_num if args.episode_num is not None else dir_num
    person = args.person or dir_person

    if episode_num is None:
        print(f"[ERR] 无法从目录名解析集数，且未提供 --episode-num", file=sys.stderr)
        sys.exit(1)
    if not person:
        print(f"[ERR] 无法从目录名解析人物名，且未提供 --person", file=sys.stderr)
        sys.exit(1)

    # 校验亮点字数（仅用于默认标题拼接）
    if not args.title and len(args.highlight) > 15:
        print(f"[WARN] 亮点总结 {len(args.highlight)} 字 > 15 字建议上限，仍继续",
              file=sys.stderr)

    # 解析并校验 publish-at
    scheduled_at = None
    if args.publish_at:
        try:
            _dt, scheduled_at = parse_publish_at(args.publish_at)
        except ValueError as e:
            print(f"[ERR] --publish-at 不合法: {e}", file=sys.stderr)
            sys.exit(1)

    # 读取音频元数据
    meta = load_episode_meta(episode_dir)
    if meta is None:
        print(f"[ERR] 找不到 episode_meta.json。请先运行 merge_audio.py，"
              f"或确认文件存在于 {episode_dir}", file=sys.stderr)
        sys.exit(1)

    # 脚本字数
    script_path = find_script_file(episode_dir)
    script_chars = count_script_chars(script_path) if script_path else None

    # 母文路径（fallback 用）
    source_path = find_source_file(episode_dir)
    # 终稿路径（新逻辑用，提取章节生成时点）
    final_path = find_final_file(episode_dir)

    # 构建 config
    if args.title:
        title = args.title
        title_source = "user-provided"
    else:
        title = format_episode_title(episode_num, person, args.highlight)
        title_source = "auto"

    # description：优先使用新逻辑（intro + 时点），fallback 到旧里程碑格式
    if args.intro and final_path:
        chapters = extract_chapters(final_path)
        if chapters:
            segments = meta.get("segments", {})
            intro_dur = segments.get("intro", {}).get("duration", 0)
            main_dur = segments.get("main", {}).get("duration", 0)
            description = build_description_with_timestamps(
                args.intro, chapters, person, intro_dur, main_dur)
            desc_mode = "intro+timestamps"
        else:
            # 终稿章节提取失败，fallback
            description = build_description(person, args.highlight, script_chars,
                                            source_path=source_path, max_chars=200)
            desc_mode = "fallback-milestones (no chapters found in 40_final.md)"
    else:
        description = build_description(person, args.highlight, script_chars,
                                        source_path=source_path, max_chars=200)
        desc_mode = "fallback-milestones" if not args.intro else "fallback-milestones (no 40_final.md)"

    config = {
        "version": "1.1",
        "podcast_name": "李自在AI人物志",
        "podcast_id": "6a53643dd01e2a1f16e0f63e",
        "episode_num": episode_num,
        "person": person,
        "highlight": args.highlight,
        "intro": args.intro,
        "title_override": args.title,
        "scheduled_at": scheduled_at,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "episode": {
            "title": title,
            "description": description,
            "description_mode": desc_mode,
            "audio": {
                "path": meta["output_path"],
                "size_mb": meta["size_mb"],
                "format": "mp3",
                "duration_seconds": meta["duration_seconds"],
                "duration_human": meta["duration_human"],
                "bitrate": meta["bitrate"],
                "sample_rate": meta["sample_rate"],
            },
            "script": {
                "path": script_path,
                "chars": script_chars,
            },
            "segments": meta.get("segments", {}),
        },
    }

    # 若已存在 config.json（如已上传过），保留上传相关字段
    output_path = os.path.join(episode_dir, args.output)
    if os.path.isfile(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                old_cfg = json.load(f)
            old_ep = old_cfg.get("episode", {})
            for key in ("xiaoyuzhou_url", "episode_url", "episode_id", "uploaded_at",
                        "upload_status", "upload_verify_source", "scheduled_at_local"):
                if key in old_ep and key not in config["episode"]:
                    config["episode"][key] = old_ep[key]
            # 顶层 scheduled_at 也保留（除非本次显式 --publish-at）
            if not scheduled_at and "scheduled_at" in old_cfg:
                config["scheduled_at"] = old_cfg["scheduled_at"]
        except (json.JSONDecodeError, KeyError):
            pass

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✅ config.json 已生成: {output_path}")
    print(f"  标题: {title}  (来源: {title_source})")
    print(f"  时长: {meta['duration_human']}")
    print(f"  大小: {meta['size_mb']}MB")
    if script_chars:
        print(f"  脚本: {script_chars} 字")
    if args.intro:
        print(f"  人物介绍: {len(args.intro)} 字 → {args.intro[:40]}...")
    if final_path and args.intro:
        chapters = extract_chapters(final_path)
        if chapters:
            print(f"  章节时点: {len(chapters)} 个（从 40_final.md 提取）")
    if scheduled_at:
        print(f"  定时发布: {scheduled_at}")
    else:
        print(f"  发布模式: 立即发布")
    print(f"  description 模式: {desc_mode}")
    print(f"  描述字数: {len(description)}")
    print(f"  音频: {meta['output_path']}")


if __name__ == "__main__":
    main()
