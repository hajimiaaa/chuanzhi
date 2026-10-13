#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
留痕工具：把 Claude Code 的会话记录导出成人类可读的 Prompt 链报告。

比赛要求：「须包含至少 3 个核心功能迭代时与 AI 交互的完整 Prompt 链
（包含你的 Prompt 提问、AI 的修改建议、以及你如何引导 AI 修复 Bug 的过程）」

Claude Code 会把每次会话完整存在 ~/.claude/projects/<项目>/<会话id>.jsonl，
本脚本读取它、按「一问一答」整理成 Markdown，并自动抹掉疑似密钥。

用法：
    python tools/export_prompts.py --label "第一版：数据模型"
    python tools/export_prompts.py                 # 不写标签也行
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------- 配置 ----------

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "prompts"

# 疑似密钥的抹除规则
SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{12,}"), "sk-***REDACTED***"),
    (re.compile(r"(?i)\b(ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|OPENAI_API_KEY|"
                r"DEEPSEEK_API_KEY|API_KEY|APIKEY|ACCESS_TOKEN|SECRET_KEY|PASSWORD)"
                r"(\s*[=:]\s*)(\S+)"), r"\1\2***REDACTED***"),
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._\-]{20,}"), r"\1***REDACTED***"),
]

# 工具调用里值得记录的关键参数
TOOL_DETAIL_KEYS = ("file_path", "path", "pattern", "command", "query", "url")


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def norm_path(p) -> str:
    return str(p).replace("\\", "/").rstrip("/").lower()


def load_entries(path: Path):
    """读取一个 jsonl 会话文件，返回有效条目列表。"""
    entries = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") not in ("user", "assistant"):
                continue
            entries.append(obj)
    return entries


def extract_prompt(obj):
    """从 user 条目里取出真实提问；工具返回结果返回 None。"""
    content = (obj.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if not isinstance(content, list):
        return None
    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    joined = "\n".join(t for t in texts if t).strip()
    return joined or None


def extract_response(obj):
    """从 assistant 条目里取出正文与工具调用。"""
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return "", []
    texts, tools = [], []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            if block.get("text"):
                texts.append(block["text"])
        elif btype == "tool_use":
            name = block.get("name", "?")
            args = block.get("input") or {}
            detail = ""
            for key in TOOL_DETAIL_KEYS:
                if key in args and isinstance(args[key], str):
                    detail = args[key]
                    break
            if detail:
                detail = detail.replace("\n", " ")[:110]
            tools.append(f"{name} → {detail}" if detail else name)
    return "\n\n".join(texts).strip(), tools


def build_turns(entries):
    """把条目按会话分组，会话内按「提问 → 回应」组织成轮次。"""
    sessions = {}
    for obj in entries:
        sid = obj.get("sessionId") or "unknown"
        sessions.setdefault(sid, []).append(obj)

    result = []
    for sid, items in sessions.items():
        items.sort(key=lambda o: o.get("timestamp") or "")
        turns, current = [], None
        for obj in items:
            if obj.get("type") == "user":
                prompt = extract_prompt(obj)
                if prompt:
                    current = {"prompt": prompt, "time": obj.get("timestamp"),
                               "texts": [], "tools": []}
                    turns.append(current)
            elif obj.get("type") == "assistant" and current is not None:
                text, tools = extract_response(obj)
                if text:
                    current["texts"].append(text)
                current["tools"].extend(tools)
        if turns:
            result.append((sid, turns))
    return result


def fmt_time(ts):
    if not ts:
        return "--:--:--"
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return "--:--:--"


def render(label, sessions):
    now = datetime.now()
    lines = [
        f"# Prompt 链路记录 — {now:%Y-%m-%d}",
        "",
        f"> 迭代标签：**{label}**" if label else "> 迭代标签：（未填写）",
        ">",
        f"> 导出时间：{now:%Y-%m-%d %H:%M:%S}",
        ">",
        "> 本文件由 `tools/export_prompts.py` 自动生成，密钥已自动抹除。",
        "",
        "---",
        "",
    ]
    turn_no = 0
    for sid, turns in sessions:
        lines.append(f"## 会话 `{sid[:8]}`　共 {len(turns)} 轮")
        lines.append("")
        for turn in turns:
            turn_no += 1
            lines.append(f"### 第 {turn_no} 轮 · {fmt_time(turn['time'])}")
            lines.append("")
            lines.append("**👤 我的提问**")
            lines.append("")
            lines.append("> " + turn["prompt"].replace("\n", "\n> "))
            lines.append("")
            answer = "\n\n".join(turn["texts"]).strip()
            lines.append("**🤖 AI 的回应**")
            lines.append("")
            lines.append(answer if answer else "_（本轮 AI 未返回正文，仅执行了工具调用）_")
            lines.append("")
            if turn["tools"]:
                lines.append("<details><summary>本轮工具调用（{} 次）</summary>".format(len(turn["tools"])))
                lines.append("")
                for tool in turn["tools"]:
                    lines.append(f"- `{tool}`")
                lines.append("")
                lines.append("</details>")
                lines.append("")
            lines.append("---")
            lines.append("")
    return redact("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="导出 Claude Code 会话为 Prompt 链报告")
    parser.add_argument("--label", default="", help="本次迭代的名称，如「第一版：数据模型」")
    parser.add_argument("--project", default=str(REPO_ROOT), help="项目根目录，默认取本仓库")
    parser.add_argument("--skip-first", type=int, default=0, metavar="N",
                        help="跳过会话开头的前 N 轮（用于剔除与本项目无关的早期内容）")
    args = parser.parse_args()

    if not CLAUDE_PROJECTS.is_dir():
        print(f"[×] 找不到 Claude Code 记录目录：{CLAUDE_PROJECTS}")
        return 1

    target = norm_path(args.project)
    entries = []
    scanned = 0
    for session_file in CLAUDE_PROJECTS.glob("*/*.jsonl"):
        scanned += 1
        for obj in load_entries(session_file):
            cwd = obj.get("cwd")
            if cwd and norm_path(cwd) == target:
                entries.append(obj)

    if not entries:
        print(f"[!] 在 {args.project} 下没有找到会话记录。")
        print(f"    已扫描 {scanned} 个会话文件。")
        print("    请确认：① 你是在这个目录下启动的 Claude Code；② 至少进行过一次对话。")
        return 1

    sessions = build_turns(entries)

    if args.skip_first:
        sessions = [(sid, turns[args.skip_first:]) for sid, turns in sessions]
        sessions = [(sid, turns) for sid, turns in sessions if turns]

    total_turns = sum(len(t) for _, t in sessions)

    if not sessions:
        print(f"[!] 跳过前 {args.skip_first} 轮后没有剩余内容。")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_label = re.sub(r'[\\/:*?"<>|]', "_", args.label).strip() or "未命名"
    out_file = OUT_DIR / f"{stamp}_{safe_label}.md"
    out_file.write_text(render(args.label, sessions), encoding="utf-8")

    print(f"[√] 已导出 {len(sessions)} 个会话、{total_turns} 轮对话")
    print(f"    {out_file}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
