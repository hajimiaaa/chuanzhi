#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 层测试。端到端验证"评委照 README 走一遍"时能拿到什么。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLE = "computer-science-2024-sample"


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
