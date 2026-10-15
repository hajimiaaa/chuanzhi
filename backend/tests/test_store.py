#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层测试。这是唯一读磁盘的测试文件。"""

import pytest

from app import store


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
