#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 领域模型。

纯标准库 dataclass，不含任何 I/O，也不依赖 fastapi / pydantic。

**为什么这一层必须零第三方依赖**：CLAUDE.md 要求"每个 JSON 都要配一个可复现的
转换脚本"、"评委可一键复现"。只要领域层不依赖 web 栈，数据校验脚本就能在
不装 fastapi、不开 venv 的情况下跑通，形成一条独立的复现链。

两条禁令：
  1. 本文件不出现 open() / json.load —— 文件 I/O 全部在 store.py
  2. 不为 Program / Course 定义 Pydantic 镜像 —— 两套领域模型必然漂移

用法:
    program = Program.from_dict(json.loads(text))

依赖: 仅标准库
"""

from dataclasses import dataclass
from typing import Any

# ---------- 常量 ----------

CATEGORIES = ("必修", "专业选修", "通识", "实践")

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

DATA_STATUS_SAMPLE = "sample"
DATA_STATUS_OFFICIAL = "official"

SCHEDULE_AVAILABLE = "available"
SCHEDULE_NOT_AVAILABLE = "not_available"

PASS_MARKS = ("及格", "合格", "通过", "优秀", "良好", "中等", "合格证")
FAIL_MARKS = ("不及格", "不合格", "未通过", "缺考", "违纪", "作弊")

PASS_MARK = 60.0


class ModelError(ValueError):
    """数据不符合领域模型。消息里带上出错位置，便于定位。"""


# ---------- 内部小工具 ----------


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise ModelError(f"{where} 缺少必填字段 `{key}`")
    return d[key]


def _grade_passed(grade) -> bool:
    """成绩 -> 是否通过。转专业准入的硬条件就是「已修读课程考核全部合格」。"""
    if grade is None:
        return True
    if isinstance(grade, bool):
        return grade
    if isinstance(grade, (int, float)):
        return float(grade) >= PASS_MARK
    text = str(grade).strip()
    if not text:
        return True
    if text in PASS_MARKS:
        return True
    if text in FAIL_MARKS:
        return False
    try:
        return float(text) >= PASS_MARK
    except ValueError:
        return True


def _to_float(value, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ModelError(f"{where} 不是数字: {value!r}")


def _sorted_terms(terms, where: str) -> tuple[int, ...]:
    out = []
    for t in terms:
        if not isinstance(t, int) or isinstance(t, bool):
            raise ModelError(f"{where} 的学期必须是整数: {t!r}")
        out.append(t)
    return tuple(sorted(set(out)))


# ---------- 上课时段 ----------

OVERLAP_NONE = "none"
OVERLAP_POSSIBLE = "possible"
OVERLAP_DEFINITE = "definite"


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """一次上课时段。中国高校排课的最小单元是（星期, 起始节, 结束节, 周次）。"""

    day: int
    start_period: int
    end_period: int
    weeks: tuple[int, ...] = ()

    @classmethod
    def from_dict(cls, d: dict, where: str = "slot") -> "TimeSlot":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        day = _req(d, "day", where)
        start = _req(d, "start_period", where)
        end = _req(d, "end_period", where)
        weeks = d.get("weeks") or []
        if start > end:
            raise ModelError(f"{where} 的起始节 {start} 大于结束节 {end}")
        return cls(
            day=int(day),
            start_period=int(start),
            end_period=int(end),
            weeks=tuple(sorted({int(w) for w in weeks})),
        )

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "start_period": self.start_period,
            "end_period": self.end_period,
            "weeks": list(self.weeks),
        }

    def overlap_level(self, other: "TimeSlot") -> str:
        """none / possible / definite。

        周次未标注时保守判为 possible —— 漏报比误报危险，方向刻意选在这一侧。
        """
        if self.day != other.day:
            return OVERLAP_NONE
        if not (self.start_period <= other.end_period and other.start_period <= self.end_period):
            return OVERLAP_NONE
        if not self.weeks or not other.weeks:
            return OVERLAP_POSSIBLE
        return OVERLAP_DEFINITE if set(self.weeks) & set(other.weeks) else OVERLAP_NONE


# ---------- 培养方案 ----------


@dataclass(frozen=True, slots=True)
class Course:
    code: str
    name: str
    credits: float
    category: str
    prerequisites: tuple[str, ...] = ()
    terms: tuple[int, ...] = ()
    slots: tuple[TimeSlot, ...] = ()

    @classmethod
    def from_dict(cls, d: dict, where: str = "course") -> "Course":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        code = str(_req(d, "code", where)).strip()
        if not code:
            raise ModelError(f"{where} 的 code 不能为空")
        where = f"课程 {code}"
        slots = d.get("slots") or []
        return cls(
            code=code,
            name=str(_req(d, "name", where)).strip(),
            credits=_to_float(_req(d, "credits", where), f"{where} 的 credits"),
            category=str(_req(d, "category", where)).strip(),
            prerequisites=tuple(str(p) for p in (d.get("prerequisites") or [])),
            terms=_sorted_terms(d.get("terms") or [], where),
            slots=tuple(TimeSlot.from_dict(s, f"{where} 的 slots") for s in slots),
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "credits": self.credits,
            "category": self.category,
            "prerequisites": list(self.prerequisites),
            "terms": list(self.terms),
            "slots": [s.to_dict() for s in self.slots],
        }


@dataclass(frozen=True, slots=True)
class CreditRule:
    category: str
    min_credits: float

    @classmethod
    def from_dict(cls, d: dict, where: str = "credit_rule") -> "CreditRule":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        return cls(
            category=str(_req(d, "category", where)).strip(),
            min_credits=_to_float(_req(d, "min_credits", where), f"{where} 的 min_credits"),
        )

    def to_dict(self) -> dict:
        return {"category": self.category, "min_credits": self.min_credits}


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    college: str
    campus: str
    data_status: str
    note: str
    catalog_ref: str
    total_min_credits: float
    credit_rules: tuple[CreditRule, ...]
    total_terms: int = 8
    max_credits_per_term: float = 0.0
    courses: tuple[Course, ...] = ()

    @classmethod
    def from_dict(cls, d: dict, where: str = "培养方案") -> "Program":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")

        pid = str(_req(d, "id", where)).strip()
        where = f"培养方案 {pid}"

        courses = tuple(
            Course.from_dict(c, f"{where} 的 courses") for c in (_req(d, "courses", where) or [])
        )
        codes = [c.code for c in courses]
        dupes = sorted({code for code in codes if codes.count(code) > 1})
        if dupes:
            raise ModelError(f"{where} 存在重复课程代码: {', '.join(dupes)}")

        rules = tuple(
            CreditRule.from_dict(r, f"{where} 的 credit_rules")
            for r in (_req(d, "credit_rules", where) or [])
        )

        return cls(
            id=pid,
            name=str(_req(d, "name", where)).strip(),
            college=str(d.get("college") or "").strip(),
            campus=str(d.get("campus") or "").strip(),
            data_status=str(d.get("data_status") or DATA_STATUS_SAMPLE).strip(),
            note=str(d.get("note") or "").strip(),
            catalog_ref=str(d.get("catalog_ref") or "").strip(),
            total_min_credits=_to_float(
                _req(d, "total_min_credits", where), f"{where} 的 total_min_credits"
            ),
            credit_rules=rules,
            total_terms=int(d.get("total_terms") or 8),
            max_credits_per_term=_to_float(d.get("max_credits_per_term") or 0, where),
            courses=courses,
        )

    @property
    def schedule_status(self) -> str:
        return (
            SCHEDULE_AVAILABLE
            if any(c.slots for c in self.courses)
            else SCHEDULE_NOT_AVAILABLE
        )

    def by_code(self) -> dict:
        return {c.code: c for c in self.courses}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "college": self.college,
            "campus": self.campus,
            "data_status": self.data_status,
            "note": self.note,
            "catalog_ref": self.catalog_ref,
            "schedule_status": self.schedule_status,
            "total_terms": self.total_terms,
            "total_min_credits": self.total_min_credits,
            "max_credits_per_term": self.max_credits_per_term,
            "credit_rules": [r.to_dict() for r in self.credit_rules],
            "courses": [c.to_dict() for c in self.courses],
        }

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "college": self.college,
            "campus": self.campus,
            "data_status": self.data_status,
            "schedule_status": self.schedule_status,
            "total_terms": self.total_terms,
            "total_min_credits": self.total_min_credits,
            "course_count": len(self.courses),
        }


# ---------- 学生的规划 ----------


@dataclass(frozen=True, slots=True)
class CompletedCourse:
    course_code: str
    credits: float
    grade: Any = None
    term: str = ""
    passed: bool = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.passed is None:
            object.__setattr__(self, "passed", _grade_passed(self.grade))

    @classmethod
    def from_dict(cls, d: dict, where: str = "completed_course") -> "CompletedCourse":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        code = str(_req(d, "course_code", where)).strip()
        where = f"已修课程 {code}"
        passed = d.get("passed")
        return cls(
            course_code=code,
            credits=_to_float(d.get("credits") or 0, f"{where} 的 credits"),
            grade=d.get("grade"),
            term=str(d.get("term") or ""),
            passed=None if passed is None else bool(passed),
        )

    def to_dict(self) -> dict:
        return {
            "course_code": self.course_code,
            "credits": self.credits,
            "grade": self.grade,
            "term": self.term,
            "passed": bool(self.passed),
        }


@dataclass(frozen=True, slots=True)
class PlanItem:
    """把一门课安排在某个学期。"""

    course_code: str
    term: int

    @classmethod
    def from_dict(cls, d: dict, where: str = "plan_item") -> "PlanItem":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        term = _req(d, "term", where)
        if isinstance(term, bool) or not isinstance(term, int):
            raise ModelError(f"{where} 的 term 必须是整数，收到 {term!r}")
        return cls(course_code=str(_req(d, "course_code", where)).strip(), term=term)

    def to_dict(self) -> dict:
        return {"course_code": self.course_code, "term": self.term}


@dataclass(frozen=True)
class Plan:
    program_id: str
    items: tuple[PlanItem, ...] = ()
    completed: tuple[CompletedCourse, ...] = ()

    @classmethod
    def from_dict(cls, d: dict, where: str = "规划") -> "Plan":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        return cls(
            program_id=str(_req(d, "program_id", where)).strip(),
            items=tuple(PlanItem.from_dict(i, f"{where} 的 items") for i in (d.get("items") or [])),
            completed=tuple(
                CompletedCourse.from_dict(c, f"{where} 的 completed")
                for c in (d.get("completed") or [])
            ),
        )


# ---------- 冲突 ----------


@dataclass(frozen=True, slots=True)
class Conflict:
    """一条冲突。纯数据，可序列化，可比较（frozen + eq）。

    刻意不设 detail: dict —— dict 字段会让 frozen 变成假象（外部仍可改写），
    且 hash() 会直接 TypeError。改用强类型的 expected / actual，
    前端可据此直接画"12 / 40 学分"进度条。
    """

    kind: str
    severity: str
    message: str
    course_codes: tuple[str, ...] = ()
    term: int = 0
    expected: float | None = None
    actual: float | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "course_codes": list(self.course_codes),
            "term": self.term,
            "expected": self.expected,
            "actual": self.actual,
        }
