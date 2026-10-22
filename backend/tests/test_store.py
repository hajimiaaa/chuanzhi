#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层测试。这是唯一读磁盘的测试文件。"""

import re

import pytest

from app import store
from app.config import REPO_ROOT
from app.models import RULE_CATEGORIES

RULE_ID = "transfer-notice-2024"
WHITESPACE = re.compile(r"\s+")


def normalize(text):
    """与 tools/build_rules_json.py 同一套空白规范化。

    必须各写一份、不能共用：生成方和校验方共用一段逻辑，同一处错误会在两边
    同时成立，校验就成了自我确认。这里的复制是刻意的。
    """
    return WHITESPACE.sub("", text)


def test_programs_dir_resolves_to_repo_data():
    """守 parents[2]。

    config.py 到仓库根是三层（config.py → app → backend → 仓库根）。
    写成 parents[1] 会静默指向 backend/，表现为"接口 200、列表为空"，极难排查。
    这个断言把那种错误从"看起来正常"变成"红"。
    """
    assert store.PROGRAMS_DIR.is_dir()
    assert store.PROGRAMS_DIR.name == "programs"
    assert (store.PROGRAMS_DIR.parent / "majors-枣庄学院-2024级.json").is_file()


def test_program_paths_not_empty():
    assert store.program_paths()


def test_load_majors_keeps_provenance():
    majors = store.load_majors()
    assert majors["stats"]["majors"] > 0
    assert majors["source"]["generator"] == "tools/build_majors_json.py"


def test_load_program_reads_sample():
    program = store.load_program("computer-science-2024-sample")
    assert program.name == "计算机科学与技术"
    assert program.data_status == "sample"
    assert program.courses
    assert program.schedule_status == "not_available"


def test_unknown_program_raises():
    with pytest.raises(store.DataError):
        store.load_program("does-not-exist")


def test_rules_dir_resolves_to_repo_data():
    assert store.RULES_DIR.is_dir()
    assert store.RULES_DIR.name == "rules"


def test_rules_paths_not_empty():
    assert store.rules_paths()


def test_load_rule_keeps_provenance():
    rule = store.load_rule(RULE_ID)
    assert rule.data_status == "official"
    assert rule.source.generator == "tools/build_rules_json.py"
    assert rule.source.raw_file.endswith(".txt")
    assert rule.provisions
    assert rule.timeline
    assert rule.gaps


def test_unknown_rule_raises():
    with pytest.raises(store.DataError):
        store.load_rule("does-not-exist")


def test_list_rules_summarizes():
    items = store.list_rules()
    assert any(r["id"] == RULE_ID for r in items)
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


def test_every_quote_is_grounded_in_the_official_source():
    """**这个模块最重要的一条测试。**

    每条条款、每个 factors 条目、每个时间节点的引用，抹掉空白后都必须能在
    source.raw_file 指向的官方原文里逐字找到。它把「不伪造校方数据」从一句承诺
    变成一条会变红的断言——谁往条款里塞了原文没有的话，这里立刻失败。
    """
    rule = store.load_rule(RULE_ID)
    source = normalize((REPO_ROOT / rule.source.raw_file).read_text(encoding="utf-8"))

    for provision in rule.provisions:
        assert normalize(provision.quote) in source, provision.id
        for factor in provision.factors:
            assert normalize(factor) in source, f"{provision.id} / {factor}"

    for step in rule.timeline:
        assert normalize(step.quote) in source, step.id


def test_gap_absence_claims_hold():
    """缺口是负向断言：「通知没写分数线」这句话本身也要能被复核。"""
    rule = store.load_rule(RULE_ID)
    source = normalize((REPO_ROOT / rule.source.raw_file).read_text(encoding="utf-8"))

    for gap in rule.gaps:
        assert gap.absent_keywords, gap.category
        for word in gap.absent_keywords:
            assert normalize(word) not in source, f"{gap.category} / {word}"


def test_every_category_is_answered_or_declared_gap():
    """8 个类别必须条条有交代：要么给条款，要么明说"通知里没有"。

    这条挡的是最隐蔽的失败——某个类别被整段忘掉，接口返回空列表，
    看起来像"这个学校不限制"，实际是我们没做。
    """
    rule = store.load_rule(RULE_ID)
    answered = {p.category for p in rule.provisions} | {g.category for g in rule.gaps}
    assert answered == set(RULE_CATEGORIES)


def test_notice_cannot_answer_score_threshold_and_campus():
    """把本轮最关键的结论钉在测试里：这两类校级通知回答不了。"""
    gaps = {g.category: g for g in store.load_rule(RULE_ID).gaps}
    assert gaps["score_threshold"].status == "not_available"
    assert gaps["campus_restriction"].status == "not_available"
    assert "学院" in gaps["score_threshold"].where_to_find


def test_sample_program_matches_official_catalog():
    """样例培养方案的学院/校区/专业名取自官方专业目录，必须是真实存在的。"""
    program = store.load_program("computer-science-2024-sample")
    majors = store.load_majors()
    names = {
        (college["name"], major["name"])
        for college in majors["colleges"]
        for major in college["majors"]
    }
    assert (program.college, program.name) in names
