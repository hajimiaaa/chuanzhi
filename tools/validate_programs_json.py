#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 培养方案 JSON 自检。

CLAUDE.md 要求"每个 JSON 都要有对应的转换脚本和来源说明"。data/programs/ 下的
样例培养方案没有官方原件可转换，因此补这个**校验脚本**：它复用 app/models.py 里
同一个 from_dict，不引入第二套校验逻辑，从而保持"官方文件 → 结构化数据"这条链
的可复现性。

**只用标准库**：无需安装 fastapi、无需激活 venv 即可运行。

用法:
    py -3.11 tools/validate_programs_json.py
    py -3.11 tools/validate_programs_json.py --dir <目录>

退出码: 0 全部通过 / 1 存在失败
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.constraints import find_prerequisite_cycles  # noqa: E402
from app.models import CATEGORIES, DATA_STATUS_OFFICIAL, DATA_STATUS_SAMPLE, Program  # noqa: E402
from app.store import DataError, load_program_by_path, majors_path  # noqa: E402

VALID_STATUS = (DATA_STATUS_SAMPLE, DATA_STATUS_OFFICIAL)


def check_program(program: Program) -> list[str]:
    problems = []
    by_code = program.by_code()

    if not program.id:
        problems.append("id 不能为空")
    if program.data_status not in VALID_STATUS:
        problems.append(f"data_status 必须是 {VALID_STATUS} 之一，收到 {program.data_status!r}")
    if program.total_terms < 1:
        problems.append(f"total_terms 必须 >= 1，收到 {program.total_terms}")
    if program.max_credits_per_term < 0:
        problems.append("max_credits_per_term 不能为负")
    if not program.courses:
        problems.append("courses 不能为空")

    for course in program.courses:
        if course.credits <= 0:
            problems.append(f"课程 {course.code} 的学分必须 > 0，收到 {course.credits}")
        if course.category not in CATEGORIES:
            problems.append(f"课程 {course.code} 的类别 {course.category!r} 不在 {CATEGORIES} 中")
        for prereq in course.prerequisites:
            if prereq not in by_code:
                problems.append(f"课程 {course.code} 的先修课 {prereq} 不存在")
        for term in course.terms:
            if not 1 <= term <= program.total_terms:
                problems.append(
                    f"课程 {course.code} 的开课学期 {term} 超出 1..{program.total_terms}"
                )

    for rule in program.credit_rules:
        if rule.category not in CATEGORIES:
            problems.append(f"学分要求 {rule.category!r} 不在 {CATEGORIES} 中")
        if rule.min_credits < 0:
            problems.append(f"学分要求 {rule.category} 不能为负")

    if program.credit_rules:
        floor = sum(r.min_credits for r in program.credit_rules)
        if round(floor, 1) > round(program.total_min_credits, 1):
            problems.append(
                f"各类别最低学分之和 {floor} 超过总学分要求 {program.total_min_credits}"
            )

    for rule in program.credit_rules:
        offered = round(sum(c.credits for c in program.courses if c.category == rule.category), 1)
        if offered < round(rule.min_credits, 1):
            problems.append(
                f"类别「{rule.category}」开出的总学分 {offered} 低于最低要求 {rule.min_credits}，永远无法满足"
            )

    cycles, _ = find_prerequisite_cycles(program)
    for cycle in cycles:
        problems.append(f"存在循环先修: {' → '.join(cycle)} → {cycle[0]}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 data/programs/ 下的培养方案 JSON")
    parser.add_argument("--dir", default=str(REPO_ROOT / "data" / "programs"), help="培养方案目录")
    args = parser.parse_args()

    target = Path(args.dir)
    print(f"[..] 培养方案目录: {target}")

    try:
        print(f"[..] 专业目录: {majors_path().name}")
    except DataError as exc:
        print(f"[×] {exc}")
        return 1

    if not target.is_dir():
        print(f"[×] 目录不存在: {target}")
        return 1

    files = sorted(p for p in target.glob("*.json"))
    if not files:
        print("[×] 目录下没有 JSON 文件")
        return 1

    failed = 0
    ids = {}
    for path in files:
        try:
            program = load_program_by_path(path)
        except DataError as exc:
            print(f"[×] {exc}")
            failed += 1
            continue

        problems = check_program(program)
        if program.id in ids:
            problems.append(f"id 与其他文件重复: {program.id}（另见 {ids[program.id]}）")
        ids[program.id] = path.name

        if problems:
            failed += 1
            print(f"[×] {path.name}（{program.id}）发现 {len(problems)} 个问题:")
            for p in problems:
                print(f"      - {p}")
        else:
            print(
                f"[OK] {path.name}（{program.id}）"
                f" {len(program.courses)} 门课 / {len(program.credit_rules)} 类学分要求"
                f" / data_status={program.data_status}"
            )

    if failed:
        print(f"[×] {failed}/{len(files)} 个文件未通过")
        return 1

    print(f"[√] {len(files)} 个培养方案全部通过校验")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
