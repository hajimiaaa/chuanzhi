#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 约束校验引擎。

契约：`check_all(plan, program) -> list[Conflict]`

无 I/O、无全局状态、**输出确定性排序**。同样的输入必然得到逐字段相同的输出，
这是"演示时冲突检测的结果可预测"的技术兑现，也是本模块可以被单独单测的前提。

--------------------------------------------------------------------
总原则：一条缺陷只由一个检查负责报告。

结构类缺陷（培养方案不匹配 / 未知课程 / 学期越界 / 重复项）统一由
`check_plan_integrity` 报出；其余五个语义检查遇到这些情况一律跳过，不重复报告。
否则同一处笔误会在三个检查里各报一次，冲突列表就从"可预测"变成"靠猜"。
--------------------------------------------------------------------

依赖: 仅标准库 + app.models
"""

from app.models import (
    CATEGORIES,
    OVERLAP_DEFINITE,
    OVERLAP_POSSIBLE,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    Conflict,
    Plan,
    Program,
)

KIND_ORDER = (
    "program_mismatch",
    "unknown_course",
    "duplicate_course",
    "unknown_term",
    "unknown_completed_course",
    "grade_unlabeled",
    "unknown_category",
    "prerequisite_cycle",
    "prerequisite_missing",
    "prerequisite_order",
    "prerequisite_failed",
    "course_not_offered",
    "term_overload",
    "time_overlap",
    "time_data_missing",
    "credit_below_minimum",
)

SEVERITY_RANK = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

# ---------- 内部小工具 ----------


def _credits(values) -> float:
    """学分求和。培养方案里有 2.5 / 1.5 / 0.5 这类值，统一四舍五入到一位小数，
    避免 39.999999999999996 < 40 这种边界翻转。"""
    return round(sum(float(v) for v in values), 1)


def _passed_by_code(plan: Plan) -> dict:
    """已通过考核的课程 -> CompletedCourse。转专业准入的硬条件就是「全部合格」。"""
    return {c.course_code: c for c in plan.completed if c.passed}


def _scheduled_terms(plan: Plan) -> dict:
    """课程代码 -> 最早被安排的学期。"""
    out = {}
    for item in plan.items:
        if item.course_code not in out or item.term < out[item.course_code]:
            out[item.course_code] = item.term
    return out


def find_prerequisite_cycles(program: Program):
    """显式栈 DFS，返回 (环列表, 环内边集合)。

    绝不使用递归：A ↔ B 互指时会直接 RecursionError → 500 → 演示当场挂掉。
    每个环只返回一次（旋转到字典序最小的课程打头）。
    边以 (课程, 先修课) 表示。
    """
    by_code = program.by_code()
    color = {}
    cycles, cycle_edges = [], set()

    for start in sorted(by_code):
        if color.get(start):
            continue
        path, on_path = [], set()
        stack = [(start, iter(sorted(by_code[start].prerequisites)))]
        color[start] = 1
        path.append(start)
        on_path.add(start)

        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in by_code:
                    continue
                if color.get(nxt) == 1 and nxt in on_path:
                    idx = path.index(nxt)
                    cycle = path[idx:]
                    key = min(range(len(cycle)), key=lambda i: cycle[i])
                    cycle = cycle[key:] + cycle[:key]
                    if cycle not in cycles:
                        cycles.append(cycle)
                        for i, cur in enumerate(cycle):
                            cycle_edges.add((cur, cycle[(i + 1) % len(cycle)]))
                elif not color.get(nxt):
                    color[nxt] = 1
                    path.append(nxt)
                    on_path.add(nxt)
                    stack.append((nxt, iter(sorted(by_code[nxt].prerequisites))))
                    advanced = True
                    break
            if not advanced:
                stack.pop()
                done = path.pop()
                on_path.discard(done)
                color[done] = 2

    return cycles, cycle_edges


def _sort_key(conflict: Conflict):
    rank = KIND_ORDER.index(conflict.kind) if conflict.kind in KIND_ORDER else len(KIND_ORDER)
    return (
        rank,
        SEVERITY_RANK.get(conflict.severity, 9),
        conflict.term,
        conflict.course_codes,
        conflict.message,
    )


def _sorted_conflicts(conflicts) -> list:
    return sorted(conflicts, key=_sort_key)


# ---------- 结构校验 ----------


def check_plan_integrity(plan: Plan, program: Program) -> list:
    """结构类缺陷的唯一出口。其余检查依赖它先行排雷，自身不再重复报告。"""
    out = []
    by_code = program.by_code()

    if plan.program_id != program.id:
        out.append(
            Conflict(
                kind="program_mismatch",
                severity=SEVERITY_ERROR,
                message=f"规划的 program_id 是「{plan.program_id}」，与培养方案「{program.id}」不一致",
            )
        )

    seen = {}
    for item in sorted(plan.items, key=lambda i: (i.course_code, i.term)):
        if item.course_code not in by_code:
            out.append(
                Conflict(
                    kind="unknown_course",
                    severity=SEVERITY_ERROR,
                    message=f"课程代码「{item.course_code}」不在本培养方案的课程库中",
                    course_codes=(item.course_code,),
                    term=item.term,
                )
            )
            continue

        if not 1 <= item.term <= program.total_terms:
            out.append(
                Conflict(
                    kind="unknown_term",
                    severity=SEVERITY_ERROR,
                    message=f"课程「{item.course_code}」被排在第 {item.term} 学期，超出 1–{program.total_terms} 的范围",
                    course_codes=(item.course_code,),
                    term=item.term,
                )
            )
            continue

        if item.course_code in seen:
            out.append(
                Conflict(
                    kind="duplicate_course",
                    severity=SEVERITY_WARNING,
                    message=f"课程「{item.course_code}」被重复安排在第 {seen[item.course_code]} 与第 {item.term} 学期",
                    course_codes=(item.course_code,),
                    term=item.term,
                )
            )
        else:
            seen[item.course_code] = item.term

    passed = _passed_by_code(plan)
    for code in sorted(set(seen) & set(passed)):
        out.append(
            Conflict(
                kind="duplicate_course",
                severity=SEVERITY_WARNING,
                message=f"课程「{code}」已修读通过，无需再排入规划",
                course_codes=(code,),
                term=seen[code],
            )
        )

    for completed in sorted(plan.completed, key=lambda c: c.course_code):
        if completed.course_code not in by_code:
            # 转专业学生的成绩单本来就含原专业课程，不在目标方案里是常态，不是错误。
            # 学分折抵依赖尚未获取的《学分认定管理办法》，此处如实标注，不做折算。
            out.append(
                Conflict(
                    kind="unknown_completed_course",
                    severity=SEVERITY_INFO,
                    message=(
                        f"已修课程「{completed.course_code}」不在本培养方案课程库中，"
                        "暂不计入学分统计；如需折抵，待接入学分认定办法后处理"
                    ),
                    course_codes=(completed.course_code,),
                    actual=completed.credits,
                )
            )
        if completed.grade is None or str(completed.grade).strip() == "":
            out.append(
                Conflict(
                    kind="grade_unlabeled",
                    severity=SEVERITY_INFO,
                    message=f"已修课程「{completed.course_code}」未标注成绩，按通过处理",
                    course_codes=(completed.course_code,),
                )
            )

    return out


# ---------- 语义校验 ----------


def check_credit_rules(plan: Plan, program: Program) -> list:
    out = []
    by_code = program.by_code()

    bad_categories = sorted({c.category for c in program.courses if c.category not in CATEGORIES})
    for category in bad_categories:
        out.append(
            Conflict(
                kind="unknown_category",
                severity=SEVERITY_WARNING,
                message=f"培养方案中存在不属于既定类别的课程类别「{category}」，该类学分不计入任何类别要求",
            )
        )
    if bad_categories:
        return out

    if not program.credit_rules:
        return out

    passed = _passed_by_code(plan)
    counted = {}
    for code, completed in passed.items():
        course = by_code.get(code)
        if course is not None:
            counted.setdefault(course.category, {})[code] = course.credits
    for item in plan.items:
        course = by_code.get(item.course_code)
        if course is not None:
            counted.setdefault(course.category, {}).setdefault(course.code, course.credits)

    total = _credits(v for group in counted.values() for v in group.values())

    for rule in program.credit_rules:
        have = _credits(counted.get(rule.category, {}).values())
        if have < round(rule.min_credits, 1):
            out.append(
                Conflict(
                    kind="credit_below_minimum",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"「{rule.category}」已修 {have} 学分，"
                        f"距最低要求 {rule.min_credits} 学分还差 {_credits([rule.min_credits - have])} 学分"
                    ),
                    expected=rule.min_credits,
                    actual=have,
                )
            )

    if total < round(program.total_min_credits, 1):
        out.append(
            Conflict(
                kind="credit_below_minimum",
                severity=SEVERITY_ERROR,
                message=(
                    f"总学分 {total}，距毕业要求的 {program.total_min_credits} 学分"
                    f"还差 {_credits([program.total_min_credits - total])} 学分"
                ),
                expected=program.total_min_credits,
                actual=total,
            )
        )

    return out


def check_prerequisites(plan: Plan, program: Program) -> list:
    out = []
    by_code = program.by_code()

    cycles, cycle_edges = find_prerequisite_cycles(program)
    for cycle in cycles:
        out.append(
            Conflict(
                kind="prerequisite_cycle",
                severity=SEVERITY_ERROR,
                message=f"培养方案存在循环先修: {' → '.join(cycle)} → {cycle[0]}",
                course_codes=tuple(cycle),
            )
        )

    passed = _passed_by_code(plan)
    failed = {c.course_code: c for c in plan.completed if not c.passed}
    scheduled = _scheduled_terms(plan)

    for item in sorted(plan.items, key=lambda i: (i.course_code, i.term)):
        course = by_code.get(item.course_code)
        # 未知课程 / 学期越界已由 integrity 报告，这里跳过
        if course is None or not 1 <= item.term <= program.total_terms:
            continue

        for prereq in course.prerequisites:
            # 环内的边不再重复报告缺先修 —— 环本身已是 error，逐边报告只会刷屏
            if (course.code, prereq) in cycle_edges:
                continue

            if prereq in passed:
                continue
            if prereq in failed:
                out.append(
                    Conflict(
                        kind="prerequisite_failed",
                        severity=SEVERITY_ERROR,
                        message=f"课程「{course.code}」的先修课「{prereq}」考核未通过",
                        course_codes=(prereq, course.code),
                        term=item.term,
                    )
                )
                continue
            if prereq in scheduled:
                if scheduled[prereq] >= item.term:
                    out.append(
                        Conflict(
                            kind="prerequisite_order",
                            severity=SEVERITY_ERROR,
                            message=(
                                f"课程「{course.code}」排在第 {item.term} 学期，"
                                f"但其先修课「{prereq}」排在第 {scheduled[prereq]} 学期，先修必须先修完"
                            ),
                            course_codes=(prereq, course.code),
                            term=item.term,
                        )
                    )
                continue

            known = prereq in by_code
            out.append(
                Conflict(
                    kind="prerequisite_missing",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"课程「{course.code}」的先修课「{prereq}」"
                        + ("未出现在本培养方案课程库中" if not known else "既未修读，也未排入规划")
                    ),
                    course_codes=(prereq, course.code),
                    term=item.term,
                )
            )

    return out


def check_term_availability(plan: Plan, program: Program) -> list:
    out = []
    by_code = program.by_code()

    for item in sorted(plan.items, key=lambda i: (i.course_code, i.term)):
        course = by_code.get(item.course_code)
        if course is None or not 1 <= item.term <= program.total_terms:
            continue
        # terms 为空 = 未标注，视为每学期均可开课
        if not course.terms:
            continue
        if item.term not in course.terms:
            offered = "、".join(f"第 {t} 学期" for t in course.terms)
            out.append(
                Conflict(
                    kind="course_not_offered",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"课程「{course.code} {course.name}」被排在第 {item.term} 学期，"
                        f"但该课只在{offered}开课"
                    ),
                    course_codes=(course.code,),
                    term=item.term,
                )
            )

    return out


def check_term_load(plan: Plan, program: Program) -> list:
    out = []
    cap = round(program.max_credits_per_term or 0, 1)
    # 0 表示未设上限
    if cap <= 0:
        return out

    by_code = program.by_code()
    per_term = {}
    for item in plan.items:
        course = by_code.get(item.course_code)
        if course is None or not 1 <= item.term <= program.total_terms:
            continue
        per_term.setdefault(item.term, {})[course.code] = course.credits

    for term in sorted(per_term):
        load = _credits(per_term[term].values())
        if load > cap:
            out.append(
                Conflict(
                    kind="term_overload",
                    severity=SEVERITY_ERROR,
                    message=f"第 {term} 学期安排了 {load} 学分，超过每学期上限 {cap} 学分",
                    course_codes=tuple(sorted(per_term[term])),
                    term=term,
                    expected=cap,
                    actual=load,
                )
            )

    return out


def check_time_conflicts(plan: Plan, program: Program) -> list:
    out = []
    by_code = program.by_code()

    per_term = {}
    for item in plan.items:
        course = by_code.get(item.course_code)
        if course is None or not 1 <= item.term <= program.total_terms:
            continue
        if course.slots:
            per_term.setdefault(item.term, {})[course.code] = course

    if not per_term:
        if not plan.items:
            return out
        # 「检测了但没有数据」必须与「检测了且无冲突」区分开，否则又是一次静默假阴性
        return [
            Conflict(
                kind="time_data_missing",
                severity=SEVERITY_INFO,
                message=(
                    "时间冲突检测已就绪，但当前培养方案未接入排课时段数据"
                    f"（schedule_status={program.schedule_status}），本次跳过检测"
                ),
            )
        ]

    for term in sorted(per_term):
        courses = per_term[term]
        codes = sorted(courses)
        for i, left in enumerate(codes):
            for right in codes[i + 1:]:
                for slot_a in courses[left].slots:
                    for slot_b in courses[right].slots:
                        level = slot_a.overlap_level(slot_b)
                        if level == OVERLAP_DEFINITE:
                            out.append(
                                Conflict(
                                    kind="time_overlap",
                                    severity=SEVERITY_ERROR,
                                    message=(
                                        f"第 {term} 学期「{left}」与「{right}」的上课时段重叠"
                                        f"（周{'一二三四五六日'[slot_a.day - 1]} 第 "
                                        f"{slot_a.start_period}-{slot_a.end_period} 节）"
                                    ),
                                    course_codes=(left, right),
                                    term=term,
                                )
                            )
                        elif level == OVERLAP_POSSIBLE:
                            out.append(
                                Conflict(
                                    kind="time_overlap",
                                    severity=SEVERITY_WARNING,
                                    message=(
                                        f"第 {term} 学期「{left}」与「{right}」的上课时段可能重叠"
                                        "（周次未标注，无法判定）"
                                    ),
                                    course_codes=(left, right),
                                    term=term,
                                )
                            )

    return out


CHECKS = (
    ("integrity", check_plan_integrity),
    ("credit", check_credit_rules),
    ("prerequisite", check_prerequisites),
    ("availability", check_term_availability),
    ("load", check_term_load),
    ("time", check_time_conflicts),
)


def check_all(plan: Plan, program: Program) -> list:
    """跑完全部检查并排序。引擎永不抛异常——演示时崩溃比报错更致命。"""
    out = []
    for _, fn in CHECKS:
        out.extend(fn(plan, program))
    return _sorted_conflicts(out)


def summarize(conflicts) -> dict:
    counts = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 0, SEVERITY_INFO: 0}
    for conflict in conflicts:
        counts[conflict.severity] = counts.get(conflict.severity, 0) + 1
    return {
        "error": counts[SEVERITY_ERROR],
        "warning": counts[SEVERITY_WARNING],
        "info": counts[SEVERITY_INFO],
        "total": len(conflicts),
    }
