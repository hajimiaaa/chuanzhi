#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 数据访问层。

**全项目唯一的文件 I/O 层。** models.py 只吃 dict 吐 dict，读写文件都在这里。

刻意不做缓存：data/ 下的 JSON 只有几百行，每请求重读的开销可忽略；
而 lru_cache + uvicorn --reload（它不监视 .json）会造成"改了数据、接口纹丝不动"
的现场事故，演示时是灾难。要新鲜，不要缓存。

用法:
    from app.store import load_program, list_programs
    program = load_program("computer-science-2024-sample")

依赖: 仅标准库 + app.models
"""

import json
from pathlib import Path

from app.config import DATA_DIR, PROGRAMS_DIR
from app.models import ModelError, Program

MAJORS_GLOB = "majors-*.json"


class DataError(Exception):
    """数据文件缺失或损坏。"""


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise DataError(f"数据文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"JSON 解析失败 {path.name}: {exc}")
    except OSError as exc:
        raise DataError(f"读取失败 {path.name}: {exc}")


def majors_path() -> Path:
    matches = sorted(DATA_DIR.glob(MAJORS_GLOB))
    if not matches:
        raise DataError(f"在 {DATA_DIR} 下找不到 {MAJORS_GLOB}")
    return matches[0]


def load_majors() -> dict:
    """原样返回专业目录（含 source 溯源块），不建 dataclass。"""
    return _read_json(majors_path())


def program_paths() -> list[Path]:
    if not PROGRAMS_DIR.is_dir():
        return []
    return sorted(PROGRAMS_DIR.glob("*.json"))


def load_program_by_path(path: Path) -> Program:
    try:
        return Program.from_dict(_read_json(path), where=path.name)
    except ModelError as exc:
        raise DataError(f"{path.name} 不符合培养方案模型: {exc}")


def load_programs() -> list[Program]:
    return [load_program_by_path(p) for p in program_paths()]


def load_program(program_id: str) -> Program:
    for program in load_programs():
        if program.id == program_id:
            return program
    raise DataError(f"找不到培养方案: {program_id}")


def list_programs() -> list[dict]:
    return [p.summary() for p in load_programs()]
