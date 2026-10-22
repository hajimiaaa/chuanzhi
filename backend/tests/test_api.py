#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 层测试。端到端验证"评委照 README 走一遍"时能拿到什么。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLE = "computer-science-2024-sample"
RULE = "transfer-notice-2024"


@pytest.fixture
def client():
    return TestClient(app)


def test_health_reports_mock_mode(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm"]["provider"] == "mock"
    assert body["llm"]["mode"] == "mock"
    assert body["data"]["programs"] >= 1
    assert body["data"]["majors"] > 0


def test_majors_is_passed_through_with_provenance(client):
    body = client.get("/api/majors").json()
    assert body["source"]["generator"] == "tools/build_majors_json.py"
    assert body["source"]["raw_file"].endswith(".xlsx")
    assert body["stats"]["majors"] == len(
        [m for c in body["colleges"] for m in c["majors"]]
    )


def test_programs_list_and_detail(client):
    items = client.get("/api/programs").json()["items"]
    assert any(p["id"] == SAMPLE for p in items)

    detail = client.get(f"/api/programs/{SAMPLE}").json()
    assert detail["name"] == "计算机科学与技术"
    assert detail["data_status"] == "sample"
    assert detail["schedule_status"] == "not_available"
    assert detail["courses"]


def test_unknown_program_returns_404(client):
    assert client.get("/api/programs/nope").status_code == 404


def test_rules_list(client):
    items = client.get("/api/rules").json()["items"]
    assert any(r["id"] == RULE for r in items)
    assert set(items[0]) == {
        "id",
        "doc_type",
        "data_status",
        "title",
        "issued_by",
        "issued_date",
        "raw_file",
        "provision_count",
        "gap_count",
    }


def test_rules_detail_shape_is_stable(client):
    """锁住前端实际收到的 key 集合 —— 比 response_model 更直接。"""
    body = client.get(f"/api/rules/{RULE}").json()
    assert set(body) == {
        "id",
        "doc_type",
        "data_status",
        "title",
        "source",
        "applies_to",
        "stats",
        "provisions",
        "timeline",
        "gaps",
        "note",
        "filter",
    }
    assert body["filter"] is None
    assert body["data_status"] == "official"
    assert body["source"]["raw_file"].endswith(".txt")
    for provision in body["provisions"]:
        assert set(provision) == {
            "id",
            "category",
            "verdict",
            "clause",
            "quote",
            "restricted_from",
            "restricted_to",
            "factors",
            "ratio",
            "max_count",
            "defers_to",
            "discretionary",
        }


def test_rules_detail_reports_gaps_for_what_the_notice_cannot_answer(client):
    """认知入口最该被看到的一屏：查不到的那几类，以及该去哪查。"""
    gaps = {g["category"]: g for g in client.get(f"/api/rules/{RULE}").json()["gaps"]}
    assert gaps["score_threshold"]["status"] == "not_available"
    assert gaps["campus_restriction"]["status"] == "not_available"
    assert gaps["major_restriction"]["status"] == "partial"
    assert gaps["score_threshold"]["where_to_find"]


def test_rules_stats_show_empty_categories(client):
    """计数为 0 的类别要留在响应里 —— 空列表也是一种答案。"""
    by_category = client.get(f"/api/rules/{RULE}").json()["stats"]["by_category"]
    assert by_category["score_threshold"] == 0
    assert by_category["campus_restriction"] == 0
    assert by_category["major_restriction"] > 0


def test_rules_category_filter(client):
    body = client.get(f"/api/rules/{RULE}", params={"category": "major_restriction"}).json()
    assert body["provisions"]
    assert {p["category"] for p in body["provisions"]} == {"major_restriction"}
    assert body["filter"] == {"category": "major_restriction", "matched": len(body["provisions"])}


def test_rules_filter_does_not_shrink_document_stats(client):
    """过滤是视图，stats 描述的是整份文件。两者不一致时由 filter 回显说清楚，
    否则 'provisions 只有 3 条、stats 却说 17 条' 看起来就是个 bug。"""
    body = client.get(f"/api/rules/{RULE}", params={"category": "major_restriction"}).json()
    assert body["stats"]["provisions"] > len(body["provisions"])
    assert body["filter"]["matched"] == len(body["provisions"])


def test_rules_category_filter_keeps_empty_result(client):
    """过滤后为空是合法结果（这一类通知里没有），不能变成 404。"""
    body = client.get(f"/api/rules/{RULE}", params={"category": "score_threshold"}).json()
    assert body["provisions"] == []
    assert body["filter"] == {"category": "score_threshold", "matched": 0}
    assert body["gaps"]


def test_unknown_rule_category_is_rejected_loudly(client):
    """类别写错必须是 422，而不是静默返回全部条款。"""
    response = client.get(f"/api/rules/{RULE}", params={"category": "nope"})
    assert response.status_code == 422


def test_unknown_rule_returns_404(client):
    assert client.get("/api/rules/nope").status_code == 404


def test_sample_plan_endpoint_plans_everything(client):
    body = client.get(f"/api/programs/{SAMPLE}/sample-plan").json()
    assert body["plan"]["unscheduled"] == []
    assert body["plan"]["items"]


def test_validate_detects_prerequisite_order(client):
    body = client.post(
        "/api/plan/validate",
        json={
            "program_id": SAMPLE,
            "items": [
                {"course_code": "CS105", "term": 3},
                {"course_code": "CS201", "term": 1},
            ],
        },
    ).json()
    assert "prerequisite_order" in [c["kind"] for c in body["conflicts"]]


def test_validate_clears_when_order_is_fixed(client):
    body = client.post(
        "/api/plan/validate",
        json={
            "program_id": SAMPLE,
            "items": [
                {"course_code": "CS105", "term": 1},
                {"course_code": "CS201", "term": 3},
            ],
        },
    ).json()
    assert "prerequisite_order" not in [c["kind"] for c in body["conflicts"]]


def test_validate_detects_course_not_offered(client):
    # CS210 只在第 3、5 学期开课
    body = client.post(
        "/api/plan/validate",
        json={"program_id": SAMPLE, "items": [{"course_code": "CS210", "term": 4}]},
    ).json()
    assert "course_not_offered" in [c["kind"] for c in body["conflicts"]]


def test_validate_reports_time_data_missing(client):
    body = client.post(
        "/api/plan/validate",
        json={"program_id": SAMPLE, "items": [{"course_code": "CS105", "term": 1}]},
    ).json()
    infos = [c for c in body["conflicts"] if c["kind"] == "time_data_missing"]
    assert len(infos) == 1
    assert infos[0]["severity"] == "info"


def test_validate_rejects_unknown_fields(client):
    """请求体写错字段名时必须响亮地 422，而不是静默落进默认值。"""
    response = client.post(
        "/api/plan/validate",
        json={"program_id": SAMPLE, "items": [{"courseCode": "CS105", "term": 1}]},
    )
    assert response.status_code == 422


def test_explain_endpoint_proves_mock_is_live(client):
    body = client.post(
        "/api/llm/explain",
        json={"program_id": SAMPLE, "items": [{"course_code": "CS201", "term": 1}]},
    ).json()
    assert body["provider"] == "mock"
    assert body["text"]


def test_conflict_payload_shape_is_stable(client):
    """锁住前端实际收到的 key 集合 —— 比 response_model 更直接。"""
    body = client.post(
        "/api/plan/validate",
        json={"program_id": SAMPLE, "items": [{"course_code": "CS210", "term": 4}]},
    ).json()
    assert body["conflicts"]
    for conflict in body["conflicts"]:
        assert set(conflict) == {
            "kind",
            "severity",
            "message",
            "course_codes",
            "term",
            "expected",
            "actual",
        }
