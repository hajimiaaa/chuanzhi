#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— API 请求模型。

**Pydantic 只出现在这一层和 main.py。** 领域模型（Program / Course / Conflict）
永远只有 dataclass 一份定义，不设 Pydantic 镜像 —— 两套领域模型必然漂移。

全部 `extra="forbid"`：前端把 course_code 写成 courseCode 时应该**响亮地 422**，
而不是被静默丢进默认值。本项目最大的失败模式是"静默的假阴性"，从入口就要堵。

用法:
    body = PlanIn.model_validate(payload)

依赖: pydantic
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.models import RULE_CATEGORIES

# 规则类别的查询参数类型，**从 models 的枚举派生**而不是手抄一份。
# 手抄一定会漂移：models 里加了新类别，接口却继续 422，而且没人会立刻发现。
# 派生之后，FastAPI 自动对非法类别返回 422，错误信息里还会带上全部合法取值。
RuleCategory = Enum("RuleCategory", {c: c for c in RULE_CATEGORIES}, type=str)


class PlanItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_code: str
    term: int


class CompletedCourseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_code: str
    credits: float = 0
    grade: float | str | None = None
    term: str = ""
    passed: bool | None = None


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_id: str
    items: list[PlanItemIn] = []
    completed: list[CompletedCourseIn] = []


class ExplainIn(PlanIn):
    pass


class CreditGapIn(BaseModel):
    """补修/重修清单的请求体：只要目标专业与已修成绩单，不需要排课规划。"""

    model_config = ConfigDict(extra="forbid")

    program_id: str
    completed: list[CompletedCourseIn] = []


class SuggestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_id: str
    max_credits_per_term: float | None = None
