#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大模型适配层测试。全部在 mock 模式下进行，**不触网**。"""

import pytest

from app import config, llm


@pytest.fixture
def clean_env(monkeypatch):
    """屏蔽 .env 加载与真实环境变量，确保测试不受开发机配置影响。"""
    monkeypatch.setattr(config, "_env_loaded", True)
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_no_key_falls_back_to_mock(clean_env):
    assert llm.get_provider().name == "mock"


def test_partial_config_falls_back_to_mock(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-not-a-real-key")
    assert llm.get_provider().name == "mock"


def test_full_config_selects_live_provider(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    assert llm.get_provider().name == "openai-compat"


def test_mock_provider_is_deterministic():
    provider = llm.MockProvider()
    assert provider.complete("prerequisite_order 冲突") == provider.complete(
        "prerequisite_order 冲突"
    )


def test_mock_provider_matches_known_kinds():
    text = llm.MockProvider().complete("term_overload course_not_offered")
    assert "学期负荷超标" in text
    assert "开课学期不匹配" in text


def test_mock_provider_fallback_on_unknown_prompt():
    text = llm.MockProvider().complete("完全无关的内容")
    assert llm.MOCK_FALLBACK in text


def test_explain_conflicts_uses_mock():
    from app.constraints import check_all
    from app.models import Plan
    from app.store import load_program

    program = load_program("computer-science-2024-sample")
    plan = Plan.from_dict({"program_id": program.id, "items": [{"course_code": "CS201", "term": 1}]})
    result = llm.explain_conflicts(program, check_all(plan, program))
    assert result["provider"] == "mock"
    assert result["text"]
    assert result["error"] == ""
