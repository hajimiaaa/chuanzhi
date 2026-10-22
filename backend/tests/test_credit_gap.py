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
    assert summary["recognized_credits"] == 5.0
    assert summary["retake_credits"] == 4.0
    assert summary["program_credits"] == 18.0
    assert summary["total_min_credits"] == 18.0


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
        "remedial",
        "pending",
        "suggested",
        "notes",
    }
    assert set(body["summary"]) == {
        "recognized",
        "retake",
        "remedial",
        "pending",
        "recognized_credits",
        "retake_credits",
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
