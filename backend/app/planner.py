#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 路径规划。

`plan_completion_order`：对尚未修读的课程做拓扑排序，再按开课学期与学期负荷上限
贪心分配到各学期，生成一份**可行**的补修顺序。

刻意不返回 `list[PlanItem]`：先修成环、或学期内排不下时，纯列表会把排不下的课
静默丢掉，前端看到一份"完整计划"却缺课 —— 又是一次静默假阴性。因此返回
`PlanSuggestion`，用 `unscheduled` 把失败显式暴露出来。

本轮不做最优化（不加"最少学期数"之类的目标函数），留待后续迭代。

用法:
    suggestion = plan_completion_order(program, completed=())

依赖: 仅标准库 + app.models
"""

from dataclasses import dataclass

from app.models import PlanItem, Program


@dataclass(frozen=True)
class PlanSuggestion:
    items: tuple = ()
    unscheduled: tuple = ()
    notes: tuple = ()

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "unscheduled": list(self.unscheduled),
            "notes": list(self.notes),
        }


def _topological_order(active: dict, available: set):
    """Kahn 拓扑排序。返回 (有序代码列表, 环内代码列表)。不递归，环不会导致爆栈。"""
    indegree = {}
    dependents = {}
    for code, course in active.items():
        pending = [p for p in course.prerequisites if p not in available and p in active]
        indegree[code] = len(pending)
        for p in pending:
            dependents.setdefault(p, []).append(code)

    queue = sorted(code for code, deg in indegree.items() if deg == 0)
    order = []
    while queue:
        code = queue.pop(0)
        order.append(code)
        newly = []
        for dep in dependents.get(code, []):
            indegree[dep] -= 1
            if indegree[dep] == 0:
                newly.append(dep)
        if newly:
            queue = sorted(queue + newly)

    stuck = sorted(set(active) - set(order))
    return order, stuck


def plan_completion_order(program: Program, completed=(), max_credits_per_term=None) -> PlanSuggestion:
    by_code = program.by_code()
    done = {c.course_code for c in completed if c.passed}
    cap = max_credits_per_term if max_credits_per_term is not None else program.max_credits_per_term
    cap = round(cap or 0, 1)

    notes = []
    unscheduled = []
    blocked = {}

    for code, course in sorted(by_code.items()):
        if code in done:
            continue
        for prereq in course.prerequisites:
            if prereq not in done and prereq not in by_code:
                blocked[code] = f"先修课「{prereq}」不在课程库中且未修读"
                break

    active = {c: by_code[c] for c in sorted(by_code) if c not in done and c not in blocked}
    for code, reason in sorted(blocked.items()):
        unscheduled.append(code)
        notes.append(f"课程「{code}」无法排课：{reason}")

    order, stuck = _topological_order(active, done)
    for code in stuck:
        unscheduled.append(code)
        notes.append(f"课程「{code}」位于循环先修链中，无法确定修读顺序")

    assigned = {}
    term_credits = {}

    for code in order:
        course = by_code[code]

        prereq_terms = []
        unplaced_prereq = False
        for prereq in course.prerequisites:
            if prereq in done:
                continue
            if prereq in assigned:
                prereq_terms.append(assigned[prereq])
            else:
                unplaced_prereq = True
        if unplaced_prereq:
            unscheduled.append(code)
            notes.append(f"课程「{code}」无法排课：其先修课未能排入任何学期")
            continue

        earliest = max(prereq_terms) + 1 if prereq_terms else 1
        allowed = course.terms or tuple(range(1, program.total_terms + 1))

        placed = None
        blocked_by_cap = False
        for term in allowed:
            if term < earliest or term > program.total_terms:
                continue
            if cap > 0 and round(term_credits.get(term, 0.0) + course.credits, 1) > cap:
                blocked_by_cap = True
                continue
            placed = term
            break

        if placed is None:
            unscheduled.append(code)
            if earliest > program.total_terms:
                notes.append(
                    f"课程「{code}」无法排课：先修课最早在第 {earliest - 1} 学期完成，"
                    f"之后修读本课会超出 {program.total_terms} 个学期的学制"
                )
            elif blocked_by_cap:
                notes.append(f"课程「{code}」无法排课：受每学期 {cap} 学分上限限制排不下")
            else:
                offered = "、".join(str(t) for t in course.terms) if course.terms else "任意"
                notes.append(
                    f"课程「{code}」无法排课：其开课学期（{offered}）晚于先修课可完成的时间"
                )
            continue

        assigned[code] = placed
        term_credits[placed] = round(term_credits.get(placed, 0.0) + course.credits, 1)

    items = tuple(
        sorted(
            (PlanItem(course_code=code, term=term) for code, term in assigned.items()),
            key=lambda i: (i.term, i.course_code),
        )
    )

    if not notes:
        notes.append(
            f"已排出 {len(items)} 门课，分布在 {len(term_credits)} 个学期；"
            f"每学期学分不超过 {cap if cap > 0 else '未设上限'}"
        )

    return PlanSuggestion(
        items=items,
        unscheduled=tuple(sorted(set(unscheduled))),
        notes=tuple(notes),
    )
