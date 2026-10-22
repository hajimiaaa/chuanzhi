#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 路径规划。

`plan_completion_order`：对尚未修读的课程做拓扑排序，再按开课学期与学期负荷上限
贪心分配到各学期，生成一份**可行**的补修顺序。

刻意不返回 `list[PlanItem]`：先修成环、或学期内排不下时，纯列表会把排不下的课
静默丢掉，前端看到一份"完整计划"却缺课 —— 又是一次静默假阴性。因此返回
`PlanSuggestion`，用 `unscheduled` 把失败显式暴露出来。

`analyze_credits`：把「已修成绩单 + 目标培养方案」分成四类——
已认定 / 需重修 / 需补修 / 待认定。**这是 MVP「学分折抵核算」里不需要
《学分认定管理办法》的那一半**：课程号能对上的，算得出来；对不上的（原专业课程），
只能标成「待认定」，等学校那份认定办法。

本轮不做最优化（不加"最少学期数"之类的目标函数），留待后续迭代。

用法:
    suggestion = plan_completion_order(program, completed=())
    analysis = analyze_credits(program, completed)

依赖: 仅标准库 + app.models
"""

from dataclasses import dataclass
from typing import Any

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


# ---------- 学分认定：补修 / 重修清单 ----------


@dataclass(frozen=True, slots=True)
class CreditCase:
    """清单里的一门课。`name` 为空表示这门课不在目标培养方案的课程库里。"""

    course_code: str
    name: str
    credits: float
    category: str = ""
    grade: Any = None
    terms: tuple[int, ...] = ()
    prerequisites: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "course_code": self.course_code,
            "name": self.name,
            "credits": self.credits,
            "category": self.category,
            "grade": self.grade,
            "terms": list(self.terms),
            "prerequisites": list(self.prerequisites),
        }


@dataclass(frozen=True)
class CreditAnalysis:
    """四类清单 + 补修顺序。

    刻意把四类分开返回，而不是合成一个"还需要修 N 门"的数字：
    四类对学生意味着四种不同的动作（不用管 / 重修 / 补修 / 去问教务处），
    合并掉任何一类都会变成误导。
    """

    recognized: tuple[CreditCase, ...] = ()   # 在目标方案中且已通过
    retake: tuple[CreditCase, ...] = ()       # 在目标方案中但未通过
    remedial: tuple[CreditCase, ...] = ()     # 目标方案要求但未修读
    pending: tuple[CreditCase, ...] = ()      # 已修但不在目标方案课程库 —— 需认定办法
    suggested: PlanSuggestion = PlanSuggestion()
    notes: tuple[str, ...] = ()
    program_credits: float = 0.0
    total_min_credits: float = 0.0

    def summary(self) -> dict:
        return {
            "recognized": len(self.recognized),
            "retake": len(self.retake),
            "remedial": len(self.remedial),
            "pending": len(self.pending),
            "recognized_credits": round(sum(c.credits for c in self.recognized), 1),
            "retake_credits": round(sum(c.credits for c in self.retake), 1),
            "remedial_credits": round(sum(c.credits for c in self.remedial), 1),
            "pending_credits": round(sum(c.credits for c in self.pending), 1),
            "program_credits": round(self.program_credits, 1),
            "total_min_credits": round(self.total_min_credits, 1),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "recognized": [c.to_dict() for c in self.recognized],
            "retake": [c.to_dict() for c in self.retake],
            "remedial": [c.to_dict() for c in self.remedial],
            "pending": [c.to_dict() for c in self.pending],
            "suggested": self.suggested.to_dict(),
            "notes": list(self.notes),
        }


def analyze_credits(program: Program, completed=()) -> CreditAnalysis:
    """把成绩单与目标培养方案对照，分成四类。

    **不做的判断**：原专业的某门课能不能顶替目标专业的某门课。
    那需要《学分认定管理办法》，各校标准完全不同（有的给换算式，有的要求
    「课程目标对毕业要求的支撑等效」），我们不臆测——统一归入 `pending`。
    """
    by_code = program.by_code()

    # 同一课号在成绩单里出现多次时，任一条通过即视为通过（重修过的学生就是这样）
    best = {}
    duplicates = set()
    for item in completed:
        code = item.course_code
        if code not in best:
            best[code] = item
            continue
        duplicates.add(code)
        if item.passed and not best[code].passed:
            best[code] = item

    recognized, retake, pending = [], [], []
    for code in sorted(best):
        item = best[code]
        course = by_code.get(code)
        if course is None:
            # 只在成绩单里出现、目标方案没有：原专业课程，只能待认定
            pending.append(
                CreditCase(
                    course_code=code,
                    name="",
                    credits=item.credits,
                    grade=item.grade,
                )
            )
            continue
        case = CreditCase(
            course_code=code,
            name=course.name,
            credits=course.credits,
            category=course.category,
            grade=item.grade,
            terms=course.terms,
            prerequisites=course.prerequisites,
        )
        (recognized if item.passed else retake).append(case)

    remedial = [
        CreditCase(
            course_code=course.code,
            name=course.name,
            credits=course.credits,
            category=course.category,
            terms=course.terms,
            prerequisites=course.prerequisites,
        )
        for course in sorted(
            (c for code, c in by_code.items() if code not in best),
            key=lambda c: (c.terms[0] if c.terms else 99, c.code),
        )
    ]

    notes = []
    if duplicates:
        notes.append(
            f"成绩单里有 {len(duplicates)} 门课程重复出现，已按「任一条通过即视为通过」合并"
        )
    if remedial:
        notes.append(f"{len(remedial)} 门课程尚未修读，需要补修")
    if retake:
        notes.append(f"{len(retake)} 门课程已修未通过，需要重修")
    if pending:
        notes.append(
            f"{len(pending)} 门已修课程不在本培养方案课程库中，能否折抵需《学分认定管理办法》，"
            "当前记为「待认定」"
        )

    return CreditAnalysis(
        recognized=tuple(recognized),
        retake=tuple(retake),
        remedial=tuple(remedial),
        pending=tuple(pending),
        suggested=plan_completion_order(program, completed=tuple(best.values())),
        notes=tuple(notes),
        program_credits=sum(c.credits for c in program.courses),
        total_min_credits=program.total_min_credits,
    )


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
