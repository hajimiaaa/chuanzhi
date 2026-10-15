#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流式增量单测：帧格式、同源性、确定性、降级。全部不触网。"""

import json

import pytest
from fastapi.testclient import TestClient

from app.llm import MOCK_FALLBACK, MockProvider, stream_conflicts, thinking_text
from app.main import app
from app.models import Conflict
from app.sse import sse_event

SAMPLE = "computer-science-2024-sample"
PROMPT = "course_not_offered 与 term_overload"


@pytest.fixture
def client():
    return TestClient(app)


def parse_frames(body: str) -> list:
    """按 \n\n 切帧，取出每帧 data: 后的 JSON。"""
    events = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        assert frame.startswith("data: "), f"帧必须以 data: 开头，收到 {frame[:20]!r}"
        events.append(json.loads(frame[len("data: "):]))
    return events


# ---------- 同源性与确定性 ----------


def test_stream_is_the_same_text_as_complete():
    """流式不是第二份文案 —— 这是整套设计的核心不变量。"""
    provider = MockProvider()
    assert "".join(provider._chunks(PROMPT)) == provider.complete(PROMPT)


def test_stream_chunks_join_to_complete():
    provider = MockProvider(stream_delay=0)
    assert "".join(provider.stream(PROMPT)) == provider.complete(PROMPT)


def test_stream_is_deterministic():
    """节奏与内容解耦：延迟不进断言，同样的输入必得同样的块序列。"""
    first = list(MockProvider(stream_delay=0).stream(PROMPT))
    second = list(MockProvider(stream_delay=0).stream(PROMPT))
    assert first == second


def test_fallback_prompt_uses_fallback_text():
    text = MockProvider().complete("完全无关的内容")
    assert MOCK_FALLBACK in text


def test_chunks_are_not_empty():
    assert all(chunk for chunk in MockProvider()._chunks(PROMPT))


# ---------- 帧格式 ----------


def test_sse_event_shape_and_chinese_not_escaped():
    frame = sse_event({"type": "delta", "text": "学分"})
    assert frame.endswith("\n\n")
    assert frame.startswith("data: ")
    assert "学分" in frame          # ensure_ascii=False
    assert "\\u5b66" not in frame


def test_sse_event_survives_newlines_in_payload():
    frame = sse_event({"type": "delta", "text": "第一行\n第二行"})
    # 正文里的换行被 JSON 转义，帧边界不受影响
    assert frame.count("\n\n") == 1
    assert json.loads(frame[len("data: "):])["text"] == "第一行\n第二行"


# ---------- 思考过程 ----------


def test_thinking_text_reports_real_counts():
    conflicts = [
        Conflict(kind="course_not_offered", severity="error", message="m"),
        Conflict(kind="term_overload", severity="error", message="m"),
        Conflict(kind="time_data_missing", severity="info", message="m"),
    ]
    text = thinking_text(conflicts)
    assert "3 条冲突" in text
    assert "错误 2" in text and "提示 1" in text
    assert "course_not_offered" in text


def test_thinking_text_on_clean_plan():
    assert "未发现冲突" in thinking_text([])


# ---------- 事件序列 ----------


def test_event_sequence_and_counts(client):
    response = client.post(
        "/api/llm/explain/stream",
        json={"program_id": SAMPLE, "items": [{"course_code": "CS101", "term": 3}]},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-coursepath-stream"] == "1"

    events = parse_frames(response.text)
    types = [e["type"] for e in events]

    assert types[0] == "meta"
    assert types[1] == "thinking"
    assert types[-1] == "done"
    assert "delta" in types

    deltas = [e for e in events if e["type"] == "delta"]
    done = events[-1]
    assert done["chunks"] == len(deltas)
    assert done["chars"] == len("".join(e["text"] for e in deltas))
    assert done["error"] == ""
    assert events[0]["provider"] == "mock"


def test_streamed_text_matches_non_streaming_endpoint(client):
    """同一个 plan，流式拼起来必须与非流式端点的 text 完全一致。"""
    payload = {"program_id": SAMPLE, "items": [{"course_code": "CS101", "term": 3}]}

    streamed = "".join(
        e["text"]
        for e in parse_frames(client.post("/api/llm/explain/stream", json=payload).text)
        if e["type"] == "delta"
    )
    plain = client.post("/api/llm/explain", json=payload).json()["text"]
    assert streamed == plain


def test_unknown_program_returns_404_before_stream(client):
    response = client.post(
        "/api/llm/explain/stream",
        json={"program_id": "nope", "items": []},
    )
    assert response.status_code == 404


def test_extra_field_still_422(client):
    response = client.post(
        "/api/llm/explain/stream",
        json={"program_id": SAMPLE, "items": [{"courseCode": "CS101", "term": 1}]},
    )
    assert response.status_code == 422


# ---------- 降级 ----------


class BoomProvider:
    name = "boom"

    def complete(self, prompt, *, system=""):
        raise OSError("upstream down")

    def stream(self, prompt, *, system=""):
        raise OSError("upstream down")
        yield


def test_upstream_failure_degrades_instead_of_breaking():
    from app.store import load_program

    program = load_program(SAMPLE)
    events = list(stream_conflicts(program, [], provider=BoomProvider()))
    types = [e["type"] for e in events]

    assert "error" in types
    assert types[-1] == "done"
    assert events[-1]["error"] == "upstream down"
    # 降级后仍给出内置规则的文案，而不是留空
    assert any(e["type"] == "delta" for e in events)


def test_empty_plan_still_streams(client):
    events = parse_frames(
        client.post("/api/llm/explain/stream", json={"program_id": SAMPLE, "items": []}).text
    )
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "delta" for e in events)
