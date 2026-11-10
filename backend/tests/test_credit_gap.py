#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补修/重修清单（analyze_credits）与接口的单测。

这一块的性质要说清楚：**它是「学分折抵」里不需要认定办法的那一半。**
课程号对得上的部分可以算；对不上的（原专业课程）只能进 `pending`。
下面专门有测试锁住"不臆测折抵"这条边界。
"""

import random

import pytest
from conftest import completed
from fastapi.testclient import TestClient

from app.main import app
from app.planner import analyze_credits

SAMPLE = "computer-science-2024-sample"


def codes(cases):
    return [c.course_code for c in cases]


# ---------- 分类 ----------


def test_classifies_four_buckets(program):
    analysis = analyze_credits(
        program,
        completed=[
            completed("CS101", credits=5, grade=90),   # 在方案里、通过
            completed("CS102", credits=4, grade=50),   # 在方案里、未通过
            completed("CE101", credits=3, grade=88),   # 不在方案里
        ],
    )

    assert codes(analysis.recognized) == ["CS101"]
    assert codes(analysis.retake) == ["CS102"]
    assert codes(analysis.pending) == ["CE101"]
    assert codes(analysis.remedial) == ["GE101", "EL101", "CS103", "PR101"]


def test_remedial_is_sorted_by_first_term_then_code(program):
    analysis = analyze_credits(program, completed=[])

    # 按「首个开课学期, 课号」排序：第1学期 CS101/GE101，第2学期 CS102/EL101，
    # 第3学期 CS103，第4学期 PR101
    assert codes(analysis.remedial) == ["CS101", "GE101", "CS102", "EL101", "CS103", "PR101"]


def test_empty_transcript_means_everything_is_remedial(program):
    analysis = analyze_credits(program, completed=[])

    assert analysis.recognized == ()
    assert analysis.retake == ()
    assert analysis.pending == ()
    assert len(analysis.remedial) == len(program.courses)


def test_failed_course_is_retake_not_remedial(program):
    analysis = analyze_credits(program, completed=[completed("CS103", grade=40)])

    assert codes(analysis.retake) == ["CS103"]
    assert "CS103" not in codes(analysis.remedial)


def test_pending_carries_no_invented_name(program):
    """原专业课程不在方案里，我们不知道它叫什么 —— 不许编一个名字出来。"""
    analysis = analyze_credits(program, completed=[completed("CE101", credits=3, grade=88)])

    [case] = analysis.pending
    assert case.name == ""
    assert case.credits == 3


def test_duplicate_codes_merge_and_passed_wins(program):
    analysis = analyze_credits(
        program,
        completed=[
            completed("CS102", credits=4, grade=45),
            completed("CS102", credits=4, grade=75),  # 重修通过
        ],
    )

    assert codes(analysis.recognized) == ["CS102"]
    assert analysis.retake == ()
    assert any("重复" in note for note in analysis.notes)


def test_notes_explain_each_bucket(program):
    analysis = analyze_credits(
        program,
        completed=[
            completed("CS101", grade=90),
            completed("CS102", grade=50),
            completed("CE101", grade=88),
        ],
    )

    joined = " ".join(analysis.notes)
    assert "补修" in joined
    assert "重修" in joined
    assert "待认定" in joined


# ---------- 建议顺序 ----------


def test_suggested_order_skips_passed_courses(program):
    analysis = analyze_credits(program, completed=[completed("CS101", grade=90)])

    suggested = {item.course_code for item in analysis.suggested.items}
    assert "CS101" not in suggested
    assert "CS102" in suggested


def test_suggested_order_includes_failed_course(program):
    analysis = analyze_credits(program, completed=[completed("CS102", grade=40)])

    assert "CS102" in {item.course_code for item in analysis.suggested.items}


def test_unscheduled_is_still_exposed(program):
    """排不下的课不能被静默丢掉 —— 这是 PlanSuggestion 存在的理由，这里要沿用。"""
    analysis = analyze_credits(program, completed=[])
    payload = analysis.to_dict()

    assert "unscheduled" in payload["suggested"]
    assert "notes" in payload["suggested"]


# ---------- 确定性 ----------


def test_deterministic_under_shuffle(program):
    items = [
        completed("CS101", grade=90),
        completed("CS102", grade=50),
        completed("CE101", grade=88),
        completed("GE101", grade=70),
    ]
    expected = analyze_credits(program, completed=items).to_dict()

    rng = random.Random(7)
    for _ in range(5):
        shuffled = items[:]
        rng.shuffle(shuffled)
        assert analyze_credits(program, completed=shuffled).to_dict() == expected


# ---------- 汇总 ----------


def test_summary_counts_and_credits(program):
    summary = analyze_credits(
        program,
        completed=[completed("CS101", grade=90), completed("CS102", grade=50)],
    ).summary()

    assert summary["recognized"] == 1
    assert summary["retake"] == 1
    assert summary["possible_overlap"] == 0
    assert summary["recognized_credits"] == 5.0
    assert summary["retake_credits"] == 4.0
    assert summary["possible_overlap_credits"] == 0.0
    assert summary["program_credits"] == 18.0
    assert summary["total_min_credits"] == 18.0


# ---------- 同名不同课号：可能可折抵 ----------


def test_same_name_same_credits_different_code_is_overlap(program):
    """跨专业公共课：课号不同、课名与学分相同 → 单独成类，不并进补修。"""
    analysis = analyze_credits(
        program,
        completed=[completed("OLD-MA101", credits=5, grade=88, name="高等数学")],
    )

    assert codes(analysis.possible_overlap) == ["CS101"]
    assert "CS101" not in codes(analysis.remedial)
    assert analysis.pending == ()


def test_same_name_different_credits_stays_pending(program):
    """学分对不上就不算「可能可折抵」——宁可保守，也不把 4 学分说成 5 学分。"""
    analysis = analyze_credits(
        program,
        completed=[completed("OLD-MA101", credits=4, grade=88, name="高等数学")],
    )

    assert analysis.possible_overlap == ()
    assert codes(analysis.pending) == ["OLD-MA101"]
    assert "CS101" in codes(analysis.remedial)


def test_name_matching_is_normalized(program):
    """全角/半角括号、空格差异不该影响匹配。"""
    analysis = analyze_credits(
        program,
        completed=[completed("OLD-1", credits=2, grade=80, name=" 通识 A ")],
    )

    assert codes(analysis.possible_overlap) == ["GE101"]


def test_overlap_does_not_double_count(program):
    """同一门方案课不能被两条成绩单同时占用。"""
    analysis = analyze_credits(
        program,
        completed=[
            completed("OLD-1", credits=3, grade=80, name="算法设计"),
            completed("OLD-2", credits=3, grade=70, name="算法设计"),
        ],
    )

    overlap_codes = codes(analysis.possible_overlap)
    assert overlap_codes == ["CS103"]
    assert "CS103" not in codes(analysis.remedial)


def test_credit_conservation_across_buckets(program):
    """学分守恒：四类（不含 pending）的学分之和 == 培养方案总学分。"""
    analysis = analyze_credits(
        program,
        completed=[
            completed("CS101", grade=90),
            completed("CS102", grade=50),
            completed("OLD-1", credits=3, grade=80, name="算法设计"),
            completed("X1", credits=2, grade=70, name="原专业独有课"),
        ],
    )

    counted = (
        analysis.recognized
        + analysis.retake
        + analysis.possible_overlap
        + analysis.remedial
    )
    assert round(sum(c.credits for c in counted), 1) == round(
        sum(c.credits for c in program.courses), 1
    )
    # pending 不参与守恒，单独统计
    assert codes(analysis.pending) == ["X1"]


def test_every_program_course_lands_in_exactly_one_bucket(program):
    analysis = analyze_credits(
        program,
        completed=[
            completed("CS101", grade=90),
            completed("OLD-1", credits=4, grade=80, name="数据结构"),
            completed("X1", credits=2, grade=70, name="原专业独有课"),
        ],
    )

    counted = (
        analysis.recognized
        + analysis.retake
        + analysis.possible_overlap
        + analysis.remedial
    )
    landed = [c.course_code for c in counted]
    assert len(landed) == len(set(landed)) == len(program.courses)
    assert set(landed) == set(program.by_code())


# ---------- HTTP 层 ----------


@pytest.fixture
def client():
    return TestClient(app)


def test_endpoint_shape_is_stable(client):
    body = client.post(
        "/api/plan/credit-gap",
        json={
            "program_id": SAMPLE,
            "completed": [{"course_code": "CS105", "credits": 4, "grade": 90}],
        },
    ).json()

    assert set(body) == {
        "program_id",
        "data_status",
        "summary",
        "recognized",
        "retake",
        "possible_overlap",
        "remedial",
        "pending",
        "suggested",
        "notes",
    }
    assert set(body["summary"]) == {
        "recognized",
        "retake",
        "possible_overlap",
        "remedial",
        "pending",
        "recognized_credits",
        "retake_credits",
        "possible_overlap_credits",
        "remedial_credits",
        "pending_credits",
        "program_credits",
        "total_min_credits",
    }
    assert "CS105" in [c["course_code"] for c in body["recognized"]]
    for case in body["recognized"]:
        assert set(case) == {
            "course_code",
            "name",
            "credits",
            "category",
            "grade",
            "terms",
            "prerequisites",
        }


def test_endpoint_accepts_empty_transcript(client):
    body = client.post(
        "/api/plan/credit-gap", json={"program_id": SAMPLE, "completed": []}
    ).json()

    assert body["recognized"] == []
    assert body["remedial"]


def test_endpoint_rejects_unknown_program(client):
    response = client.post(
        "/api/plan/credit-gap", json={"program_id": "nope", "completed": []}
    )
    assert response.status_code == 404


def test_endpoint_rejects_unknown_fields(client):
    response = client.post(
        "/api/plan/credit-gap",
        json={"program_id": SAMPLE, "completed": [{"courseCode": "CS105"}]},
    )
    assert response.status_code == 422


# ---------- 核对单 ----------


def test_audit_sheet_shape_and_self_check(client):
    body = client.post(
        "/api/plan/audit-sheet",
        json={
            "program_id": SAMPLE,
            "completed": [
                {"course_code": "CS105", "name": "程序设计基础", "credits": 4, "grade": 90},
                {"course_code": "SE102", "name": "高等数学A(二)", "credits": 5, "grade": 84},
                {"course_code": "SE001", "name": "软件工程导论", "credits": 3, "grade": 80},
            ],
        },
    ).json()

    assert set(body) == {
        "program",
        "generated_at",
        "engine_version",
        "summary",
        "sections",
        "self_check",
        "disclaimer",
        "next_actions",
        "printable",
    }
    assert [s["key"] for s in body["sections"]] == [
        "recognized",
        "retake",
        "possible_overlap",
        "remedial",
        "pending",
    ]
    for section in body["sections"]:
        assert set(section) == {"key", "title", "confidence", "action", "cases"}

    checks = {c["name"]: c for c in body["self_check"]}
    assert checks["课程无遗漏"]["passed"] is True
    assert checks["学分守恒"]["passed"] is True


def test_audit_sheet_is_not_printable_for_sample_data(client):
    """样例数据不能生成一张"看起来能签字"的单子。"""
    body = client.post(
        "/api/plan/audit-sheet", json={"program_id": SAMPLE, "completed": []}
    ).json()

    assert body["printable"] is False
    assert "样例数据" in body["disclaimer"]
    assert body["next_actions"]


def test_audit_sheet_rejects_unknown_program(client):
    response = client.post(
        "/api/plan/audit-sheet", json={"program_id": "nope", "completed": []}
    )
    assert response.status_code == 404
