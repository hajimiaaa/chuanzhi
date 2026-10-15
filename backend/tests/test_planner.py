#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径规划测试。"""

from app.planner import plan_completion_order
from conftest import completed, course, make_program
from app.models import CreditRule


def test_plans_everything_for_sample_program():
    from app.store import load_program

    program = load_program("computer-science-2024-sample")
    suggestion = plan_completion_order(program)
    assert suggestion.unscheduled == ()
    assert len(suggestion.items) == len(program.courses)


def test_respects_prerequisite_order():
    p = make_program(
        [
            course("A", credits=1, terms=[1]),
            course("B", credits=1, terms=[2], prereqs=["A"]),
            course("C", credits=1, terms=[3], prereqs=["B"]),
        ],
        [CreditRule("必修", 3)],
        total_min=3.0,
    )
    items = {i.course_code: i.term for i in plan_completion_order(p).items}
    assert items["A"] < items["B"] < items["C"]


def test_places_course_in_an_offered_term():
    p = make_program(
        [course("A", credits=1, terms=[3, 5])],
        [CreditRule("必修", 1)],
        total_min=1.0,
    )
    items = {i.course_code: i.term for i in plan_completion_order(p).items}
    assert items["A"] in (3, 5)


def test_cycle_nodes_are_reported_as_unscheduled():
    p = make_program(
        [
            course("A", credits=1, prereqs=["B"]),
            course("B", credits=1, prereqs=["A"]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    suggestion = plan_completion_order(p)
    assert suggestion.unscheduled == ("A", "B")
    assert any("循环先修" in n for n in suggestion.notes)


def test_unreachable_prerequisite_is_visible_not_silently_dropped():
    p = make_program(
        [
            course("A", credits=1, prereqs=["GHOST"]),
            course("B", credits=1),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    suggestion = plan_completion_order(p)
    assert "A" in suggestion.unscheduled
    assert any("GHOST" in n for n in suggestion.notes)
    # B 仍应正常排出 —— 一门课排不下不能拖垮整份规划
    assert [i.course_code for i in suggestion.items] == ["B"]


def test_already_passed_courses_are_skipped():
    p = make_program(
        [
            course("A", credits=1, terms=[1]),
            course("B", credits=1, terms=[2], prereqs=["A"]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    suggestion = plan_completion_order(p, completed=(completed("A"),))
    assert [i.course_code for i in suggestion.items] == ["B"]


def test_credit_cap_is_respected():
    # 不限制开课学期（terms 为空 = 任意学期），三门课应被上限摊到三个学期
    p = make_program(
        [
            course("A", credits=4),
            course("B", credits=4),
            course("C", credits=4),
        ],
        [CreditRule("必修", 12)],
        total_min=12.0,
        max_per_term=8.0,
    )
    suggestion = plan_completion_order(p)
    assert suggestion.unscheduled == ()
    per_term = {}
    for item in suggestion.items:
        per_term[item.term] = per_term.get(item.term, 0) + 4
    # 贪心最早可行：第 1 学期塞满 8 学分后，第三门顺延到第 2 学期
    assert all(load <= 8 for load in per_term.values())
    assert len(per_term) == 2


def test_cap_with_single_offered_term_leaves_overflow_unscheduled():
    """三门课都只在第 1 学期开、上限 8 学分 —— 必然排不下第三门，必须显式暴露。"""
    p = make_program(
        [
            course("A", credits=4, terms=[1]),
            course("B", credits=4, terms=[1]),
            course("C", credits=4, terms=[1]),
        ],
        [CreditRule("必修", 12)],
        total_min=12.0,
        max_per_term=8.0,
    )
    suggestion = plan_completion_order(p)
    assert len(suggestion.items) == 2
    assert suggestion.unscheduled == ("C",)
    assert any("上限" in n for n in suggestion.notes)


def test_course_beyond_study_length_is_unscheduled():
    p = make_program(
        [
            course("A", credits=1, terms=[1]),
            course("B", credits=1, terms=[2], prereqs=["A"]),
            course("C", credits=1, terms=[3], prereqs=["B"]),
            course("D", credits=1, terms=[4], prereqs=["C"]),
        ],
        [CreditRule("必修", 4)],
        total_min=4.0,
        total_terms=3,
    )
    suggestion = plan_completion_order(p)
    assert "D" in suggestion.unscheduled


def test_output_is_deterministic():
    from app.store import load_program

    program = load_program("computer-science-2024-sample")
    first = plan_completion_order(program)
    second = plan_completion_order(program)
    assert first == second
