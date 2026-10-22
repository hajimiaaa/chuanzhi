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

# ---------- 转专业规则常量 ----------
# 规则条款按「学生想知道什么」分类，而不是按原文的章节顺序分类。
# 认知入口要回答的问题正是这几类，缺哪一类、哪一类没数据，一眼可见。

RULE_DOC_TYPES = ("school_notice", "college_plan", "credit_recognition_policy")

RULE_CATEGORIES = (
    "eligibility",          # 什么情形下可以转（含必须经谁批准）
    "academic_record",      # 挂科要求：已修读课程是否必须全部合格
    "score_threshold",      # 分数门槛：绩点 / 单科成绩 / 通识课分数线
    "assessment_method",    # 考核方式：要不要笔试、面试，怎么算分
    "major_restriction",    # 专业限制：哪些专业不能互转
    "campus_restriction",   # 校区限制：跨校区是否额外受限
    "quota",                # 次数与志愿数上限
    "credit_recognition",   # 转入后的学分认定依据
)

RULE_VERDICTS = ("deny", "require", "allow", "limit", "conditional", "info")

GAP_STATUS_NOT_AVAILABLE = "not_available"
GAP_STATUS_PARTIAL = "partial"
GAP_STATUSES = (GAP_STATUS_NOT_AVAILABLE, GAP_STATUS_PARTIAL)

# 溯源块的必需键，与 data/majors-枣庄学院-2024级.json 的 source 块保持一致。
SOURCE_REQUIRED_KEYS = ("school", "title", "origin", "raw_file", "generator")


class ModelError(ValueError):
    """数据不符合领域模型。消息里带上出错位置，便于定位。"""


# ---------- 内部小工具 ----------


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise ModelError(f"{where} 缺少必填字段 `{key}`")
    return d[key]


def _text(d: dict, key: str, where: str) -> str:
    value = str(_req(d, key, where) or "").strip()
    if not value:
        raise ModelError(f"{where} 的 `{key}` 不能为空")
    return value


def _opt_text(d: dict, key: str) -> str:
    return str(d.get(key) or "").strip()


def _str_tuple(value, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ModelError(f"{where} 必须是数组")
    return tuple(text for text in (str(v).strip() for v in value) if text)


def _seq(d: dict, key: str, where: str) -> list:
    value = d.get(key) or []
    if not isinstance(value, list):
        raise ModelError(f"{where} 的 `{key}` 必须是数组")
    return value


def _opt_float(value, where: str) -> float | None:
    return None if value is None else _to_float(value, where)


def _opt_int(value, where: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelError(f"{where} 必须是整数: {value!r}")
    return value


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


# ---------- 转专业规则 ----------
#
# 规则数据的设计要点：**装得下的一律逐字引用，装不下的一律显式列为缺口。**
#
# 校级通知只给了框架（30% 触发考核），真正的分数门槛散在 21 个学院的方案里。
# 与其编一个好看的数字，不如让 `gaps` 把"查不到"本身变成一条可查询的数据——
# 每条缺口都带 `absent_keywords`（反证：这些词在原文里必须不出现），
# 于是"我们没找到"是一句可以被机器复核的话，而不是一句托词。


@dataclass(frozen=True, slots=True)
class RuleSource:
    """规则文件的溯源块。必需键与 data/majors-*.json 的 source 块一致。

    刻意做成强类型而不是自由 dict：`Conflict` 那条理由在这里同样成立——
    自由 dict 让 frozen 变成假象，且溯源块恰恰是最不能随手塞东西的地方。
    """

    school: str
    title: str
    origin: str
    raw_file: str
    generator: str
    issuer: str = ""
    issued_date: str = ""
    doc_no: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str = "source") -> "RuleSource":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        for key in SOURCE_REQUIRED_KEYS:
            if not str(d.get(key) or "").strip():
                raise ModelError(f"{where} 缺少必填字段 `{key}`")
        raw_file = str(d["raw_file"]).strip()
        if "\\" in raw_file:
            raise ModelError(f"{where} 的 raw_file 必须是仓库相对路径且用正斜杠: {raw_file}")
        return cls(
            school=str(d["school"]).strip(),
            title=str(d["title"]).strip(),
            origin=str(d["origin"]).strip(),
            raw_file=raw_file,
            generator=str(d["generator"]).strip(),
            issuer=str(d.get("issuer") or "").strip(),
            issued_date=str(d.get("issued_date") or "").strip(),
            doc_no=str(d.get("doc_no") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "school": self.school,
            "title": self.title,
            "origin": self.origin,
            "raw_file": self.raw_file,
            "generator": self.generator,
            "issuer": self.issuer,
            "issued_date": self.issued_date,
            "doc_no": self.doc_no,
        }


@dataclass(frozen=True, slots=True)
class RuleScope:
    """这份规则约束谁。"""

    grade: str
    student_types: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict, where: str = "applies_to") -> "RuleScope":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        return cls(
            grade=_text(d, "grade", where),
            student_types=_str_tuple(d.get("student_types"), f"{where} 的 student_types"),
        )

    def to_dict(self) -> dict:
        return {"grade": self.grade, "student_types": list(self.student_types)}


@dataclass(frozen=True, slots=True)
class Provision:
    """一条可检索的规则条款。一条 = 原文里的一段话，不是一次释义。

    `quote` 是逐字引用，必须能在 `raw_file` 里原样找到（校验脚本会抹掉空白后比对）。
    这是本模块最硬的约束：任何人拿到产物，都能独立验证我们没有编造条款。
    """

    id: str
    category: str
    verdict: str
    clause: str
    quote: str
    restricted_from: tuple[str, ...] = ()
    restricted_to: tuple[str, ...] = ()
    factors: tuple[str, ...] = ()
    ratio: float | None = None
    max_count: int | None = None
    defers_to: str = ""
    discretionary: bool = False

    @classmethod
    def from_dict(cls, d: dict, where: str = "provision") -> "Provision":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        pid = _text(d, "id", where)
        where = f"条款 {pid}"
        category = _text(d, "category", where)
        if category not in RULE_CATEGORIES:
            raise ModelError(f"{where} 的类别 {category!r} 不在 {RULE_CATEGORIES} 中")
        verdict = _text(d, "verdict", where)
        if verdict not in RULE_VERDICTS:
            raise ModelError(f"{where} 的判定 {verdict!r} 不在 {RULE_VERDICTS} 中")
        return cls(
            id=pid,
            category=category,
            verdict=verdict,
            clause=_text(d, "clause", where),
            quote=_text(d, "quote", where),
            restricted_from=_str_tuple(d.get("restricted_from"), f"{where} 的 restricted_from"),
            restricted_to=_str_tuple(d.get("restricted_to"), f"{where} 的 restricted_to"),
            factors=_str_tuple(d.get("factors"), f"{where} 的 factors"),
            ratio=_opt_float(d.get("ratio"), f"{where} 的 ratio"),
            max_count=_opt_int(d.get("max_count"), f"{where} 的 max_count"),
            defers_to=_opt_text(d, "defers_to"),
            discretionary=bool(d.get("discretionary") or False),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "verdict": self.verdict,
            "clause": self.clause,
            "quote": self.quote,
            "restricted_from": list(self.restricted_from),
            "restricted_to": list(self.restricted_to),
            "factors": list(self.factors),
            "ratio": self.ratio,
            "max_count": self.max_count,
            "defers_to": self.defers_to,
            "discretionary": self.discretionary,
        }


@dataclass(frozen=True, slots=True)
class TimelineStep:
    """时间线上的一个节点。

    `deadline` 是规范化的 ISO 日期，`quote` 保留原文写法（通知写作"2025 年 2 月 14 日"）。
    规范化只是排版，原文就在旁边，可对照。
    """

    id: str
    label: str
    deadline: str
    quote: str
    clause: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str = "timeline") -> "TimelineStep":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        sid = _text(d, "id", where)
        where = f"时间线 {sid}"
        return cls(
            id=sid,
            label=_text(d, "label", where),
            deadline=_text(d, "deadline", where),
            quote=_text(d, "quote", where),
            clause=_opt_text(d, "clause"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "deadline": self.deadline,
            "clause": self.clause,
            "quote": self.quote,
        }


@dataclass(frozen=True, slots=True)
class RuleGap:
    """一条缺口：这类规则我们**没有**，以及为什么没有、该去哪里找。

    对认知入口来说，这条数据的价值和条款是同等的——学生问"通识课真卡 70 分吗"，
    "校级通知没规定，答案在学院方案里"本身就是答案。
    """

    category: str
    status: str
    detail: str
    evidence_clause: str = ""
    absent_keywords: tuple[str, ...] = ()
    where_to_find: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str = "gap") -> "RuleGap":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")
        category = _text(d, "category", where)
        if category not in RULE_CATEGORIES:
            raise ModelError(f"{where} 的类别 {category!r} 不在 {RULE_CATEGORIES} 中")
        status = _text(d, "status", where)
        if status not in GAP_STATUSES:
            raise ModelError(f"{where} 的状态 {status!r} 不在 {GAP_STATUSES} 中")
        where = f"缺口 {category}"
        return cls(
            category=category,
            status=status,
            detail=_text(d, "detail", where),
            evidence_clause=_opt_text(d, "evidence_clause"),
            absent_keywords=_str_tuple(d.get("absent_keywords"), f"{where} 的 absent_keywords"),
            where_to_find=_opt_text(d, "where_to_find"),
        )

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "status": self.status,
            "detail": self.detail,
            "evidence_clause": self.evidence_clause,
            "absent_keywords": list(self.absent_keywords),
            "where_to_find": self.where_to_find,
        }


@dataclass(frozen=True)
class RuleDoc:
    """一份来源文件的结构化结果。一份文件 = 一个 JSON。"""

    id: str
    doc_type: str
    data_status: str
    title: str
    source: RuleSource
    applies_to: RuleScope
    provisions: tuple[Provision, ...] = ()
    timeline: tuple[TimelineStep, ...] = ()
    gaps: tuple[RuleGap, ...] = ()
    note: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str = "规则文件") -> "RuleDoc":
        if not isinstance(d, dict):
            raise ModelError(f"{where} 必须是对象")

        rid = _text(d, "id", where)
        where = f"规则文件 {rid}"

        doc_type = _text(d, "doc_type", where)
        if doc_type not in RULE_DOC_TYPES:
            raise ModelError(f"{where} 的 doc_type {doc_type!r} 不在 {RULE_DOC_TYPES} 中")

        data_status = str(d.get("data_status") or DATA_STATUS_SAMPLE).strip()
        if data_status not in (DATA_STATUS_SAMPLE, DATA_STATUS_OFFICIAL):
            raise ModelError(f"{where} 的 data_status 非法: {data_status!r}")

        provisions = tuple(
            Provision.from_dict(p, f"{where} 的 provisions")
            for p in _seq(d, "provisions", where)
        )
        pids = [p.id for p in provisions]
        dupes = sorted({pid for pid in pids if pids.count(pid) > 1})
        if dupes:
            raise ModelError(f"{where} 存在重复条款 id: {', '.join(dupes)}")

        return cls(
            id=rid,
            doc_type=doc_type,
            data_status=data_status,
            title=_text(d, "title", where),
            source=RuleSource.from_dict(_req(d, "source", where), f"{where} 的 source"),
            applies_to=RuleScope.from_dict(
                _req(d, "applies_to", where), f"{where} 的 applies_to"
            ),
            provisions=provisions,
            timeline=tuple(
                TimelineStep.from_dict(s, f"{where} 的 timeline")
                for s in _seq(d, "timeline", where)
            ),
            gaps=tuple(
                RuleGap.from_dict(g, f"{where} 的 gaps") for g in _seq(d, "gaps", where)
            ),
            note=_opt_text(d, "note"),
        )

    def stats(self) -> dict:
        """统计是算出来的，不是存下来的——存一份就有漂移的可能。

        `by_category` 刻意列出全部类别（含计数为 0 的）：零本身就是信息，
        它让"这一类别通知里没有"在接口响应里直接可见。
        """
        by_category = {category: 0 for category in RULE_CATEGORIES}
        for provision in self.provisions:
            by_category[provision.category] += 1
        return {
            "provisions": len(self.provisions),
            "by_category": by_category,
            "gaps": len(self.gaps),
        }

    def by_id(self, provision_id: str) -> Provision | None:
        for provision in self.provisions:
            if provision.id == provision_id:
                return provision
        return None

    def in_category(self, category: str) -> tuple[Provision, ...]:
        return tuple(p for p in self.provisions if p.category == category)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doc_type": self.doc_type,
            "data_status": self.data_status,
            "title": self.title,
            "source": self.source.to_dict(),
            "applies_to": self.applies_to.to_dict(),
            "stats": self.stats(),
            "provisions": [p.to_dict() for p in self.provisions],
            "timeline": [s.to_dict() for s in self.timeline],
            "gaps": [g.to_dict() for g in self.gaps],
            "note": self.note,
        }

    def summary(self) -> dict:
        return {
            "id": self.id,
            "doc_type": self.doc_type,
            "data_status": self.data_status,
            "title": self.title,
            "issued_by": self.source.issuer,
            "issued_date": self.source.issued_date,
            "raw_file": self.source.raw_file,
            "provision_count": len(self.provisions),
            "gap_count": len(self.gaps),
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
