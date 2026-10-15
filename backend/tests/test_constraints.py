#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""约束引擎单测。这是"演示时冲突检测结果可预测"的实证。"""

import random

from app.constraints import (
    KIND_ORDER,
    check_all,
    check_credit_rules,
    check_plan_integrity,
    check_prerequisites,
    check_term_availability,
    check_term_load,
    check_time_conflicts,
    summarize,
)
from app.models import Conflict, CreditRule
from conftest import (
    STD_COURSES,
    STD_ITEMS,
    STD_RULES,
    completed,
    course,
    find,
    kinds,
    make_plan,
    make_program,
    slot,
)

# ---------- 基线 ----------


def test_clean_plan_has_no_conflicts(program, clean_plan):
    assert check_all(clean_plan, program) == []


def test_conflict_to_dict_keys():
    keys = set(Conflict(kind="k", severity="error", message="m").to_dict())
    assert keys == {"kind", "severity", "message", "course_codes", "term", "expected", "actual"}


def test_check_all_is_deterministic_under_shuffle(program):
    items = list(STD_ITEMS) + [("CS103", 2), ("ZZZ", 9)]
    done = [completed("CS101"), completed("OLD1", credits=2), completed("CS102", grade="不及格")]

    baseline = None
    for seed in range(5):
        rng = random.Random(seed)
        shuffled_items = items[:]
        shuffled_done = done[:]
        rng.shuffle(shuffled_items)
        rng.shuffle(shuffled_done)
        result = check_all(make_plan(shuffled_items, shuffled_done), program)
        if baseline is None:
            baseline = result
        else:
            assert result == baseline


def test_check_all_ordering_is_stable(program):
    plan = make_plan(list(STD_ITEMS) + [("ZZZ", 9)], [completed("OLD1", credits=2)])
    ranks = [KIND_ORDER.index(c.kind) for c in check_all(plan, program)]
    assert ranks == sorted(ranks)


def test_summarize_counts_by_severity(program, clean_plan):
    assert summarize(check_all(clean_plan, program)) == {
        "error": 0,
        "warning": 0,
        "info": 0,
        "total": 0,
    }


# ---------- 结构校验 ----------


def test_program_mismatch_reported_and_checks_continue(program, clean_plan):
    plan = make_plan(STD_ITEMS, program_id="someone-else")
    out = check_all(plan, program)
    assert kinds(out) == ["program_mismatch"]


def test_unknown_course_in_plan_is_error(program):
    out = check_plan_integrity(make_plan([("ZZZ", 1)]), program)
    assert [c.severity for c in find(out, "unknown_course")] == ["error"]


def test_unknown_completed_course_is_info_not_error(program):
    """转专业学生的成绩单本来就含原专业课程，不在目标方案里是常态。"""
    out = check_plan_integrity(make_plan([], [completed("MATH999", credits=3)]), program)
    hits = find(out, "unknown_completed_course")
    assert len(hits) == 1
    assert hits[0].severity == "info"


def test_unknown_term(program):
    out = check_plan_integrity(make_plan([("CS101", 99)]), program)
    assert len(find(out, "unknown_term")) == 1


def test_duplicate_course_in_items(program):
    out = check_plan_integrity(make_plan([("CS101", 1), ("CS101", 3)]), program)
    assert [c.severity for c in find(out, "duplicate_course")] == ["warning"]


def test_duplicate_course_already_passed(program):
    out = check_plan_integrity(make_plan([("CS101", 1)], [completed("CS101")]), program)
    assert [c.severity for c in find(out, "duplicate_course")] == ["warning"]


def test_grade_unlabeled_is_info(program):
    out = check_plan_integrity(make_plan([], [completed("CS101", grade=None)]), program)
    assert [c.severity for c in find(out, "grade_unlabeled")] == ["info"]


def test_semantic_checks_skip_unknown_courses(program):
    """结构缺陷只由 integrity 报告，其余检查不得重复刷屏。"""
    plan = make_plan([("ZZZ", 1), ("ZZZ", 2)])
    for fn in (check_credit_rules, check_prerequisites, check_term_availability, check_term_load):
        assert [c for c in fn(plan, program) if "ZZZ" in c.course_codes] == []


# ---------- 学分 ----------


def test_credit_exactly_at_minimum_passes(program, clean_plan):
    assert find(check_credit_rules(clean_plan, program), "credit_below_minimum") == []


def test_credit_below_minimum_per_category(program):
    # 去掉专业选修那门课（3 学分），并把通识也去掉（2 学分）
    plan = make_plan([("CS101", 1), ("CS102", 2), ("CS103", 3), ("PR101", 4)])
    hits = [c for c in check_credit_rules(plan, program) if c.expected == 3]
    assert len(hits) == 1
    assert hits[0].actual == 0.0


def test_total_credit_below_minimum(program):
    plan = make_plan([("CS101", 1)])
    hits = [c for c in check_credit_rules(plan, program) if c.expected == 18.0]
    assert len(hits) == 1
    assert hits[0].actual == 5.0


def test_no_credit_rules_skips_check(program, clean_plan):
    bare = make_program(STD_COURSES, [], total_min=0.0, max_per_term=10.0)
    assert check_credit_rules(clean_plan, bare) == []


def test_completed_courses_count_toward_credits(program):
    plan = make_plan([("CS102", 2)], [completed("CS101", credits=5)])
    assert find(check_credit_rules(plan, program), "credit_below_minimum")


def test_unknown_category_warns():
    p = make_program(
        [course("X1", credits=2, category="神秘类别")],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    out = check_credit_rules(make_plan([("X1", 1)]), p)
    assert kinds(out) == ["unknown_category"]


# ---------- 先修 ----------


def test_prerequisite_missing(program):
    plan = make_plan([("CS102", 2)])
    hits = find(check_prerequisites(plan, program), "prerequisite_missing")
    assert len(hits) == 1
    assert hits[0].course_codes == ("CS101", "CS102")


def test_prerequisite_order(program):
    plan = make_plan([("CS101", 3), ("CS102", 1)])
    assert len(find(check_prerequisites(plan, program), "prerequisite_order")) == 1


def test_prerequisite_same_term_is_order_error(program):
    plan = make_plan([("CS101", 2), ("CS102", 2)])
    assert len(find(check_prerequisites(plan, program), "prerequisite_order")) == 1


def test_prerequisite_failed(program):
    plan = make_plan([("CS102", 2)], [completed("CS101", grade="不及格")])
    hits = find(check_prerequisites(plan, program), "prerequisite_failed")
    assert len(hits) == 1


def test_prerequisite_satisfied_by_completed(program):
    plan = make_plan([("CS102", 2)], [completed("CS101")])
    assert find(check_prerequisites(plan, program), "prerequisite_") == []


def test_cycle_reported_once_and_no_recursion():
    # A 需要 C，C 需要 B，B 需要 A —— 一个三元环。递归实现会在这里爆栈。
    p = make_program(
        [
            course("A", credits=1, prereqs=["C"]),
            course("B", credits=1, prereqs=["A"]),
            course("C", credits=1, prereqs=["B"]),
        ],
        [CreditRule("必修", 3)],
        total_min=3.0,
    )
    out = check_prerequisites(make_plan([("A", 1)]), p)
    assert len(find(out, "prerequisite_cycle")) == 1
    # 环内的边不再逐条报告缺先修，否则会刷屏
    assert find(out, "prerequisite_missing") == []


def test_self_cycle_does_not_hang():
    p = make_program(
        [course("A", credits=1, prereqs=["A"])],
        [CreditRule("必修", 1)],
        total_min=1.0,
    )
    out = check_prerequisites(make_plan([("A", 1)]), p)
    assert len(find(out, "prerequisite_cycle")) == 1
    assert find(out, "prerequisite_missing") == []


def test_cycle_suppression_does_not_hide_unrelated_missing():
    """抑制只针对环内的边——环外缺的先修必须照报。"""
    p = make_program(
        [
            course("A", credits=1, prereqs=["B"]),
            course("B", credits=1, prereqs=["A"]),
            course("D", credits=1, prereqs=["E"]),
            course("E", credits=1),
        ],
        [CreditRule("必修", 4)],
        total_min=4.0,
    )
    out = check_prerequisites(make_plan([("A", 1), ("D", 2)]), p)
    assert len(find(out, "prerequisite_cycle")) == 1
    assert [c.course_codes for c in find(out, "prerequisite_missing")] == [("E", "D")]


# ---------- 开课学期 ----------


def test_course_not_offered(program):
    plan = make_plan([("CS101", 1), ("CS102", 2), ("CS103", 2)])
    hits = find(check_term_availability(plan, program), "course_not_offered")
    assert [c.term for c in hits] == [2]


def test_empty_terms_means_any_term():
    p = make_program([course("X1", credits=1, terms=[])], [CreditRule("必修", 1)], total_min=1.0)
    assert check_term_availability(make_plan([("X1", 5)]), p) == []


# ---------- 学期负荷 ----------


def test_term_exactly_at_cap_passes(program, clean_plan):
    assert check_term_load(clean_plan, program) == []


def test_term_overload(program):
    plan = make_plan([("CS101", 1), ("CS102", 1), ("GE101", 1)])
    hits = find(check_term_load(plan, program), "term_overload")
    assert len(hits) == 1
    assert (hits[0].expected, hits[0].actual) == (10.0, 11.0)


def test_zero_cap_means_no_limit(program):
    unlimited = make_program(STD_COURSES, STD_RULES, total_min=18.0, max_per_term=0.0)
    plan = make_plan([("CS101", 1), ("CS102", 1), ("GE101", 1), ("CS103", 1)])
    assert check_term_load(plan, unlimited) == []


def test_completed_does_not_count_toward_term_load(program):
    plan = make_plan([("CS101", 1)], [completed("CS102", credits=4, grade=90)])
    assert check_term_load(plan, program) == []


# ---------- 时间冲突 ----------


def test_time_data_missing_is_single_info(no_schedule_program):
    plan = make_plan([("CS101", 1), ("GE101", 1)])
    hits = check_time_conflicts(plan, no_schedule_program)
    assert len(hits) == 1
    assert hits[0].kind == "time_data_missing"
    assert hits[0].severity == "info"


def test_empty_plan_produces_no_time_conflict(no_schedule_program):
    assert check_time_conflicts(make_plan([]), no_schedule_program) == []


def test_time_overlap_definite():
    p = make_program(
        [
            course("A", credits=1, slots=[slot(1, 1, 2, range(1, 17))]),
            course("B", credits=1, slots=[slot(1, 2, 3, range(1, 17))]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    hits = check_time_conflicts(make_plan([("A", 1), ("B", 1)]), p)
    assert [c.severity for c in hits] == ["error"]


def test_time_overlap_possible_when_weeks_unlabeled():
    p = make_program(
        [
            course("A", credits=1, slots=[slot(1, 1, 2)]),
            course("B", credits=1, slots=[slot(1, 1, 2)]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    hits = check_time_conflicts(make_plan([("A", 1), ("B", 1)]), p)
    assert [c.severity for c in hits] == ["warning"]


def test_no_overlap_when_weeks_disjoint():
    p = make_program(
        [
            course("A", credits=1, slots=[slot(1, 1, 2, range(1, 9))]),
            course("B", credits=1, slots=[slot(1, 1, 2, range(9, 17))]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    assert check_time_conflicts(make_plan([("A", 1), ("B", 1)]), p) == []


def test_no_overlap_on_different_day():
    p = make_program(
        [
            course("A", credits=1, slots=[slot(1, 1, 2, range(1, 17))]),
            course("B", credits=1, slots=[slot(2, 1, 2, range(1, 17))]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    assert check_time_conflicts(make_plan([("A", 1), ("B", 1)]), p) == []


def test_no_overlap_when_different_terms():
    p = make_program(
        [
            course("A", credits=1, slots=[slot(1, 1, 2, range(1, 17))]),
            course("B", credits=1, slots=[slot(1, 1, 2, range(1, 17))]),
        ],
        [CreditRule("必修", 2)],
        total_min=2.0,
    )
    assert check_time_conflicts(make_plan([("A", 1), ("B", 2)]), p) == []
