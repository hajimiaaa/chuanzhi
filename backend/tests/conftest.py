#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 测试夹具。

夹具全部在内存里构造，**不读磁盘**。这样约束引擎的单测不依赖 data/ 下的文件，
换数据、改样例都不会让引擎测试变红。

注意：tests/ 目录下不要出现 app.py / json.py / models.py。
pytest 的 prepend 导入模式会把 backend/tests 插到 sys.path[0]，
一个 tests/models.py 会遮蔽 app.models 包。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.models import (  # noqa: E402
    CompletedCourse,
    Course,
    CreditRule,
    Plan,
    PlanItem,
    Program,
    TimeSlot,
)


def slot(day, start, end, weeks=()):
    return TimeSlot(day=day, start_period=start, end_period=end, weeks=tuple(weeks))


def course(code, name=None, credits=3, category="必修", prereqs=(), terms=(), slots=()):
    return Course(
        code=code,
        name=name or code,
        credits=credits,
        category=category,
        prerequisites=tuple(prereqs),
        terms=tuple(terms),
        slots=tuple(slots),
    )


def make_program(courses, rules=(), total_min=0.0, total_terms=8, max_per_term=0.0, pid="p1"):
    return Program(
        id=pid,
        name="测试专业",
        college="测试学院",
        campus="测试校区",
        data_status="sample",
        note="",
        catalog_ref="",
        total_min_credits=total_min,
        credit_rules=tuple(rules),
        total_terms=total_terms,
        max_credits_per_term=max_per_term,
        courses=tuple(courses),
    )


def make_plan(items=(), completed=(), program_id="p1"):
    return Plan(
        program_id=program_id,
        items=tuple(PlanItem(course_code=c, term=t) for c, t in items),
        completed=tuple(completed),
    )


def completed(code, credits=3, grade=90, term="2024-2025-1", passed=None):
    return CompletedCourse(course_code=code, credits=credits, grade=grade, term=term, passed=passed)


# ---------- 基准夹具 ----------
# 学分：必修 5+4+3=12，专业选修 3，通识 2，实践 1，合计 18，
# 与 credit_rules 完全相等 —— 用于验证"恰好等于下限 = 通过"。
# 时段互不重叠，使时间冲突检测被真正激活（而非落入 time_data_missing）。

STD_COURSES = [
    course("CS101", "高等数学", 5, "必修", terms=[1], slots=[slot(1, 1, 2, range(1, 17))]),
    course("CS102", "数据结构", 4, "必修", ["CS101"], terms=[2], slots=[slot(1, 3, 4, range(1, 17))]),
    course("CS103", "算法设计", 3, "必修", ["CS102"], terms=[3], slots=[slot(2, 1, 2, range(1, 17))]),
    course("EL101", "专业选修A", 3, "专业选修", terms=[2], slots=[slot(3, 1, 2, range(1, 17))]),
    course("GE101", "通识A", 2, "通识", terms=[1], slots=[slot(2, 3, 4, range(1, 17))]),
    course("PR101", "实践A", 1, "实践", terms=[4], slots=[slot(5, 1, 4, range(9, 17))]),
]

STD_RULES = [
    CreditRule(category="必修", min_credits=12),
    CreditRule(category="专业选修", min_credits=3),
    CreditRule(category="通识", min_credits=2),
    CreditRule(category="实践", min_credits=1),
]

STD_ITEMS = [
    ("CS101", 1),
    ("GE101", 1),
    ("CS102", 2),
    ("EL101", 2),
    ("CS103", 3),
    ("PR101", 4),
]


@pytest.fixture
def program():
    return make_program(STD_COURSES, STD_RULES, total_min=18.0, max_per_term=10.0)


@pytest.fixture
def clean_plan():
    """一份完全合规的规划：学分刚好达标、先修顺序正确、无超载、无时段冲突。"""
    return make_plan(STD_ITEMS)


@pytest.fixture
def no_schedule_program():
    """同一份培养方案，但课程不带上课时段 —— 用于验证 time_data_missing 提示。"""
    return make_program(
        [
            course("CS101", "高等数学", 5, "必修", terms=[1]),
            course("CS102", "数据结构", 4, "必修", ["CS101"], terms=[2]),
            course("CS103", "算法设计", 3, "必修", ["CS102"], terms=[3]),
            course("EL101", "专业选修A", 3, "专业选修", terms=[2]),
            course("GE101", "通识A", 2, "通识", terms=[1]),
            course("PR101", "实践A", 1, "实践", terms=[4]),
        ],
        STD_RULES,
        total_min=18.0,
        max_per_term=10.0,
    )


def kinds(conflicts):
    return [c.kind for c in conflicts]


def find(conflicts, kind):
    return [c for c in conflicts if c.kind == kind]
