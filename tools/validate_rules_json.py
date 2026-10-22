#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 转专业规则 JSON 自检。

CLAUDE.md 要求"每个 JSON 都要有对应的转换脚本和来源说明"。本脚本是那根链的**独立
第二只眼睛**：它复用 app/models.py 里同一个 from_dict，不引入第二套校验逻辑，
但**不 import build_rules_json.py**——生成方与校验方共用代码，校验就失去了意义。

它回答的是本项目最要紧的一个问题：**这些条款是不是真的从官方文件里来的？**

  1. 结构  —— 每份文件经 RuleDoc.from_dict，枚举值、必填字段、id 唯一
  2. 引用回溯 —— 每条 quote 与每个 factors 条目，抹掉空白后必须能在
     source.raw_file 指向的原文里逐字找到；条号也必须在原文里出现
  3. 负向断言 —— 缺口声明的 absent_keywords 必须真的不在原文里
     （"通知没规定分数门槛"这句话，是可以被机器复核的）
  4. 类别完备 —— 8 个类别每一个都必须有条款或缺口，不允许有类别悄悄消失
  5. 形状恒等 —— 文件必须逐键等于 RuleDoc.to_dict()，即接口实际返回的形状。
     手工往里塞字段、或改了模型却忘了重新生成，都会在这里现形

**只用标准库**：无需安装 fastapi、无需激活 venv 即可运行。

用法:
    py -3.11 tools/validate_rules_json.py
    py -3.11 tools/validate_rules_json.py --dir <目录>

退出码: 0 全部通过 / 1 存在失败
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models import RULE_CATEGORIES, RuleDoc  # noqa: E402
from app.store import DataError, load_rule_by_path  # noqa: E402

CLAUSE_TOKEN = re.compile(r"[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|（\d+）|\d+\.")
WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """刻意与 build_rules_json.py 各写一份：生成方与校验方不能共用这段逻辑，
    否则同一处错误会在两边同时成立，校验就成了自我确认。"""
    return WHITESPACE.sub("", text)


def read_source(doc: RuleDoc) -> tuple[str, list[str]]:
    """读取原文并规范化。"""
    path = REPO_ROOT / doc.source.raw_file
    if not path.is_file():
        return "", [f"raw_file 指向的原文不存在: {doc.source.raw_file}"]
    return normalize(path.read_text(encoding="utf-8")), []


def check_shape(path: Path, doc: RuleDoc) -> list[str]:
    """文件必须逐键等于模型的规范序列化结果。

    只比形状不比内容——内容真伪由引用回溯负责。这一条盯的是另外两种事故：
    有人手工往文件里加了字段，以及改了模型却忘了重新生成脚本产物。
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"读取失败: {exc}"]
    if raw != doc.to_dict():
        return ["文件与 RuleDoc.to_dict() 不一致 —— 被手工改过，或模型改了但没重新生成"]
    return []


def check_doc(doc: RuleDoc) -> list[str]:
    problems = []

    if doc.source.generator != "tools/build_rules_json.py":
        problems.append(f"source.generator 不是本项目的转换脚本: {doc.source.generator!r}")

    flat, read_problems = read_source(doc)
    problems.extend(read_problems)
    if read_problems:
        return problems

    for provision in doc.provisions:
        if normalize(provision.quote) not in flat:
            problems.append(f"条款 {provision.id}: quote 在原文里找不到 —— {provision.quote}")
        for factor in provision.factors:
            if normalize(factor) not in flat:
                problems.append(f"条款 {provision.id}: factors 条目「{factor}」在原文里找不到")
        for token in CLAUSE_TOKEN.findall(provision.clause):
            if token not in flat:
                problems.append(f"条款 {provision.id}: 条号「{token}」在原文里找不到")

    for step in doc.timeline:
        if normalize(step.quote) not in flat:
            problems.append(f"时间线 {step.id}: quote 在原文里找不到 —— {step.quote}")
        for token in CLAUSE_TOKEN.findall(step.clause):
            if token not in flat:
                problems.append(f"时间线 {step.id}: 条号「{token}」在原文里找不到")

    for gap in doc.gaps:
        for token in CLAUSE_TOKEN.findall(gap.evidence_clause):
            if token not in flat:
                problems.append(f"缺口 {gap.category}: 条号「{token}」在原文里找不到")
        for word in gap.absent_keywords:
            if normalize(word) in flat:
                problems.append(
                    f"缺口 {gap.category}: 声明「{word}」不存在，但原文里有 —— 缺口不成立"
                )
        if gap.status == "not_available" and not gap.absent_keywords:
            problems.append(
                f"缺口 {gap.category}: 声明 not_available 却没给 absent_keywords，"
                "无法复核这个「没有」是真的没有"
            )

    answered = {p.category for p in doc.provisions} | {g.category for g in doc.gaps}
    for category in RULE_CATEGORIES:
        if category not in answered:
            problems.append(f"类别「{category}」既没有条款也没有缺口 —— 不允许悄悄消失")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 data/rules/ 下的转专业规则 JSON")
    parser.add_argument("--dir", default=str(REPO_ROOT / "data" / "rules"), help="规则目录")
    args = parser.parse_args()

    target = Path(args.dir)
    print(f"[..] 规则目录: {target}")

    if not target.is_dir():
        print(f"[×] 目录不存在: {target}")
        return 1

    files = sorted(target.glob("*.json"))
    if not files:
        print("[×] 目录下没有 JSON 文件")
        return 1

    failed = 0
    ids = {}
    for path in files:
        try:
            doc = load_rule_by_path(path)
        except DataError as exc:
            print(f"[×] {exc}")
            failed += 1
            continue

        problems = check_shape(path, doc) + check_doc(doc)
        if doc.id in ids:
            problems.append(f"id 与其他文件重复: {doc.id}（另见 {ids[doc.id]}）")
        ids[doc.id] = path.name

        if problems:
            failed += 1
            print(f"[×] {path.name}（{doc.id}）发现 {len(problems)} 个问题:")
            for p in problems:
                print(f"      - {p}")
        else:
            print(
                f"[OK] {path.name}（{doc.id}）"
                f" {len(doc.provisions)} 条条款 / {len(doc.timeline)} 个时间节点"
                f" / {len(doc.gaps)} 处缺口"
                f" / data_status={doc.data_status}"
            )

    if failed:
        print(f"[×] {failed}/{len(files)} 个文件未通过")
        return 1

    print(f"[√] {len(files)} 份规则全部通过校验（引用与缺口断言均已回原文复核）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
