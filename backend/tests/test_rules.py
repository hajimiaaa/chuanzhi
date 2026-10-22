#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""转专业规则模型测试。全部在内存里构造，**不读磁盘**。

真实文件的加载与"引用是否真的出自原文"在 test_store.py 里测——那是数据层的事。
"""

import pytest

from app.models import RULE_CATEGORIES, ModelError, RuleDoc


def payload(**overrides):
    """一份合法的最小规则文件。每次调用都是全新的嵌套结构，可放心就地改。"""
    base = {
        "id": "r1",
        "doc_type": "school_notice",
        "data_status": "official",
        "title": "测试通知",
        "source": {
            "school": "测试大学",
            "title": "测试通知",
            "origin": "测试用",
            "raw_file": "docs/测试.txt",
            "generator": "tools/build_rules_json.py",
        },
        "applies_to": {"grade": "2024级", "student_types": ["本科在校生"]},
        "provisions": [
            {
                "id": "p1",
                "category": "academic_record",
                "verdict": "require",
                "clause": "一、（一）",
                "quote": "已修读课程考核全部合格",
            }
        ],
        "timeline": [],
        "gaps": [],
        "note": "",
    }
    base.update(overrides)
    return base


# ---------- 结构校验 ----------


def test_minimal_payload_parses():
    doc = RuleDoc.from_dict(payload())
    assert doc.id == "r1"
    assert doc.provisions[0].category == "academic_record"
    assert doc.source.issuer == ""


def test_round_trip_is_stable():
    """文件 -> 模型 -> 文件 必须恒等：否则接口响应和落盘文件会各说各话。"""
    doc = RuleDoc.from_dict(payload())
    assert RuleDoc.from_dict(doc.to_dict()).to_dict() == doc.to_dict()


def test_optional_payload_fields_default_to_empty():
    """登记表里没写的键，模型要补成稳定的空值——前端拿到的键集合不能时有时无。"""
    item = RuleDoc.from_dict(payload()).provisions[0].to_dict()
    assert item["restricted_from"] == []
    assert item["ratio"] is None
    assert item["max_count"] is None
    assert item["defers_to"] == ""
    assert item["discretionary"] is False


@pytest.mark.parametrize("field", ["id", "doc_type", "title", "source", "applies_to"])
def test_missing_required_field_raises(field):
    data = payload()
    del data[field]
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_unknown_doc_type_raises():
    with pytest.raises(ModelError):
        RuleDoc.from_dict(payload(doc_type="随便编的类型"))


def test_bad_data_status_raises():
    with pytest.raises(ModelError):
        RuleDoc.from_dict(payload(data_status="差不多是真的"))


@pytest.mark.parametrize("key", ["school", "title", "origin", "raw_file", "generator"])
def test_source_missing_required_key_raises(key):
    """溯源块缺一个必需键就不许通过——它正是"这条数据从哪来"的唯一凭证。"""
    data = payload()
    del data["source"][key]
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_source_rejects_windows_path():
    """raw_file 必须是仓库相对路径且用正斜杠，否则换台机器就复现不了。"""
    data = payload()
    data["source"]["raw_file"] = "docs\\测试.txt"
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_unknown_category_raises():
    data = payload()
    data["provisions"][0]["category"] = "income"
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_unknown_verdict_raises():
    data = payload()
    data["provisions"][0]["verdict"] = "maybe"
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_provision_requires_quote():
    """没有逐字引用的条款不许存在——那等于无法追溯的自撰规则。"""
    data = payload()
    data["provisions"][0]["quote"] = "   "
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_duplicate_provision_ids_raise():
    data = payload()
    data["provisions"].append(dict(data["provisions"][0]))
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_gap_with_unknown_status_raises():
    data = payload(gaps=[{"category": "campus_restriction", "status": "maybe",
                          "detail": "通知未涉及"}])
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


def test_gap_with_unknown_category_raises():
    data = payload(gaps=[{"category": "食堂", "status": "partial", "detail": "x"}])
    with pytest.raises(ModelError):
        RuleDoc.from_dict(data)


# ---------- 输出形状 ----------


def test_summary_keys_are_stable():
    assert set(RuleDoc.from_dict(payload()).summary()) == {
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


def test_stats_lists_every_category_even_when_zero():
    """计数为 0 本身就是信息：它让"这一类通知里没有"在响应里直接可见。"""
    stats = RuleDoc.from_dict(payload()).stats()
    assert set(stats["by_category"]) == set(RULE_CATEGORIES)
    assert stats["by_category"]["score_threshold"] == 0
    assert stats["by_category"]["academic_record"] == 1
    assert stats["provisions"] == 1


def test_category_counter_counts_all_matches():
    data = payload()
    data["provisions"].append(
        {"id": "p2", "category": "academic_record", "verdict": "require",
         "clause": "一、（一）", "quote": "另一条"}
    )
    assert RuleDoc.from_dict(data).stats()["by_category"]["academic_record"] == 2


def test_by_id_and_in_category(rule_doc):
    assert rule_doc.by_id("p1").id == "p1"
    assert rule_doc.by_id("nope") is None
    assert len(rule_doc.in_category("academic_record")) == 1
    assert rule_doc.in_category("score_threshold") == ()
