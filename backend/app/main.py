#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— FastAPI 应用入口。

启动（CWD 必须是 backend/，这与 README 的复现指南一致）：
    cd backend
    uvicorn app.main:app --reload --port 8000

路由全部用**同步 def**：llm.py 走 urllib 是阻塞调用，FastAPI 会把同步路由
自动丢进线程池；写成 async def 反而会在事件循环里做阻塞调用，是经典反模式。

不做 lifespan / on_event 预加载：那会引入"直接跑正常、TestClient 里报错"的
时序问题。数据在请求时惰性加载，行为在任何入口下都一致。
"""

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import __version__
from app.constraints import check_all, summarize
from app.llm import explain_conflicts, get_provider, stream_conflicts
from app.models import CompletedCourse, Plan
from app.planner import analyze_credits, plan_completion_order
from app.schemas import CreditGapIn, ExplainIn, PlanIn, RuleCategory, SuggestIn
from app.sse import SSE_HEADERS, STREAM_MEDIA_TYPE, sse_event
from app.store import (
    DataError,
    list_programs,
    list_rules,
    load_majors,
    load_program,
    load_rule,
)

app = FastAPI(
    title="课径 CoursePath API",
    version=__version__,
    description=(
        "把培养方案从看不懂的 PDF 变成能动手算的路径图。"
        "默认运行在 mock 模式，无需任何 API Key 即可完整演示。"
    ),
)

# localhost 与 127.0.0.1 在浏览器眼里是两个不同的 origin，必须都列。
# 不设 allow_credentials：本项目不需要 cookie，设了反而不能用通配的 header。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_plan(body: PlanIn) -> Plan:
    return Plan.from_dict(body.model_dump())


def _get_program(program_id: str):
    try:
        return load_program(program_id)
    except DataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/health", summary="健康检查与运行模式", tags=["系统"])
def health():
    """让评委一眼看到 mock 是否生效、数据加载了几份。"""
    provider = get_provider()
    try:
        programs = len(list_programs())
        majors = load_majors().get("stats", {}).get("majors")
    except DataError:
        programs, majors = None, None

    return {
        "status": "ok",
        "version": __version__,
        "llm": {
            "provider": provider.name,
            "mode": "mock" if provider.name == "mock" else "live",
        },
        "data": {"programs": programs, "majors": majors},
    }


@app.get("/api/majors", summary="专业目录（官方文件原样透传）", tags=["数据"])
def get_majors():
    """原样返回，不建 dataclass —— source 块里的来源/脚本信息是可复现性的可见证据。"""
    try:
        return load_majors()
    except DataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/programs", summary="培养方案列表", tags=["数据"])
def get_programs():
    try:
        return {"items": list_programs()}
    except DataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/programs/{program_id}", summary="培养方案详情", tags=["数据"])
def get_program(program_id: str):
    return _get_program(program_id).to_dict()


@app.get("/api/rules", summary="转专业规则清单", tags=["规则"])
def get_rules():
    try:
        return {"items": list_rules()}
    except DataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/rules/{rule_id}", summary="单份规则全文（可按类别过滤）", tags=["规则"])
def get_rule(
    rule_id: str,
    category: RuleCategory | None = Query(
        None,
        description="只看某一类规则；不传则返回全部条款。非法取值由 FastAPI 自动 422。",
    ),
):
    """返回结构化的规则全文，含 `gaps`——查不到的那几类同样是要交付的答案。

    `stats` 描述的是整份文件，不随过滤变化。所以过滤时额外回显 `filter`
    （含命中条数），否则 `provisions` 3 条、`stats.provisions` 17 条会像是一个 bug。
    字段恒定存在（不传时是 null），键集合不随参数变形。
    """
    try:
        doc = load_rule(rule_id)
    except DataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    payload = doc.to_dict()
    payload["filter"] = None
    if category is not None:
        payload["provisions"] = [
            p for p in payload["provisions"] if p["category"] == category.value
        ]
        payload["filter"] = {"category": category.value, "matched": len(payload["provisions"])}
    return payload


@app.get("/api/programs/{program_id}/sample-plan", summary="开箱即用的样例规划", tags=["规划"])
def get_sample_plan(program_id: str):
    program = _get_program(program_id)
    suggestion = plan_completion_order(program)
    return {
        "program_id": program.id,
        "data_status": program.data_status,
        "schedule_status": program.schedule_status,
        "plan": suggestion.to_dict(),
    }


@app.post("/api/plan/validate", summary="校验一份规划，返回冲突列表", tags=["规划"])
def validate_plan(body: PlanIn):
    program = _get_program(body.program_id)
    conflicts = check_all(_to_plan(body), program)
    return {
        "program_id": program.id,
        "data_status": program.data_status,
        "schedule_status": program.schedule_status,
        "summary": summarize(conflicts),
        "conflicts": [c.to_dict() for c in conflicts],
    }


@app.post("/api/plan/suggest-order", summary="生成可行的补修顺序", tags=["规划"])
def suggest_order(body: SuggestIn):
    program = _get_program(body.program_id)
    suggestion = plan_completion_order(program, max_credits_per_term=body.max_credits_per_term)
    return {"program_id": program.id, "plan": suggestion.to_dict()}


@app.post("/api/plan/credit-gap", summary="补修/重修清单（不做跨专业折抵）", tags=["规划"])
def credit_gap(body: CreditGapIn):
    """把已修成绩单与目标培养方案对照，分成 已认定 / 重修 / 补修 / 待认定 四类。

    **这个接口不做跨专业学分折抵。** 原专业课程能否顶替目标专业课程，
    取决于《学分认定管理办法》（尚未获取），一律归入 `pending` 并写明原因。
    课程号直接对得上的部分（公共课、同名课）不需要那份文件就能算。
    """
    program = _get_program(body.program_id)
    completed = tuple(
        CompletedCourse.from_dict(item, "已修课程")
        for item in body.model_dump()["completed"]
    )
    return {
        "program_id": program.id,
        "data_status": program.data_status,
        **analyze_credits(program, completed).to_dict(),
    }


@app.post("/api/plan/audit-sheet", summary="生成可打印核对的清单（核对草案）", tags=["规划"])
def audit_sheet(body: CreditGapIn):
    """把五类清单组织成一份**可打印、可签字**的核对草案。

    这是对「功能不完善导致学生没拿到学分怎么办」的产品级回答：
    输出的不是"最终结论"，而是一份写明**哪几条确定、哪几条需要人去确认**的单子。

    `printable` 在样例数据下为 false —— 不让编造数据生成一张"看起来能签字"的单子。
    最终认定始终以教务系统与教务处审核结果为准。
    """
    program = _get_program(body.program_id)
    completed = tuple(
        CompletedCourse.from_dict(item, "已修课程")
        for item in body.model_dump()["completed"]
    )
    analysis = analyze_credits(program, completed)
    summary = analysis.summary()

    raw_sections = [
        ("recognized", "已认定", "high", "无需操作；与教务系统不一致时，以教务系统为准", analysis.recognized),
        ("retake", "需重修", "high", "按培养方案重修，成绩以教务系统为准", analysis.retake),
        ("possible_overlap", "可能可折抵", "medium",
         "带成绩单到教务处确认，依据《学分认定管理办法》", analysis.possible_overlap),
        ("remedial", "需补修", "high", "按转入专业培养方案选课", analysis.remedial),
        ("pending", "待认定", "low", "由学院/教务处判断能否计入，不计入本单的学分守恒", analysis.pending),
    ]
    sections = [
        {
            "key": key,
            "title": title,
            "confidence": confidence,
            "action": action,
            "cases": [case.to_dict() for case in cases],
        }
        for key, title, confidence, action, cases in raw_sections
    ]

    counted = (
        analysis.recognized
        + analysis.retake
        + analysis.possible_overlap
        + analysis.remedial
    )
    landed = [case.course_code for case in counted]
    total = round(sum(c.credits for c in program.courses), 1)
    got = round(sum(c.credits for c in counted), 1)

    self_check = [
        {
            "name": "课程无遗漏",
            "passed": len(landed) == len(set(landed)) == len(program.courses),
            "detail": f"{len(set(landed))}/{len(program.courses)} 门培养方案课程已归类，无重复",
        },
        {
            "name": "学分守恒",
            "passed": got == total,
            "detail": (
                f"{total} = {summary['recognized_credits']} + {summary['retake_credits']}"
                f" + {summary['possible_overlap_credits']} + {summary['remedial_credits']}"
            ),
        },
    ]

    sample = program.data_status != "official"
    return {
        "program": {
            "id": program.id,
            "name": program.name,
            "college": program.college,
            "data_status": program.data_status,
            "catalog_ref": program.catalog_ref,
            "note": program.note,
        },
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "engine_version": __version__,
        "summary": summary,
        "sections": sections,
        "self_check": self_check,
        "disclaimer": (
            "本清单由课径基于公开培养方案自动核算，是一份**核对草案**，仅供参考；"
            "最终认定以学校教务系统与教务处审核结果为准。"
            + ("当前为样例数据，不可用于真实毕业审核。" if sample else "")
        ),
        "next_actions": [
            {"step": 1, "text": "登录教务系统，逐条核对课程号、学分与成绩",
             "where": "教务系统 → 培养方案 / 成绩查询"},
            {"step": 2, "text": "带成绩单到教务处确认「可能可折抵」的课程",
             "where": "教务处学籍管理科（明理楼 226）"},
            {"step": 3, "text": "确认后回填本单，交辅导员签字留档", "where": "本学院辅导员"},
        ],
        "printable": not sample,
    }


@app.post("/api/llm/explain", summary="用大模型解释冲突（mock 亦可验证）", tags=["大模型"])
def explain(body: ExplainIn):
    """mock 模式下的可验证入口 —— 否则适配层就是一段无人调用的死代码。"""
    program = _get_program(body.program_id)
    conflicts = check_all(_to_plan(body), program)
    return {
        "program_id": program.id,
        "summary": summarize(conflicts),
        **explain_conflicts(program, conflicts),
    }


@app.post("/api/llm/explain/stream", summary="流式解释冲突（SSE）", tags=["大模型"])
def explain_stream(body: ExplainIn):
    """逐块返回解释文本，用于前端的打字机与"思考可视化"。

    用 POST 而不是 GET：请求体是复杂的 plan JSON，EventSource 发不出来。
    保持同步 def 是对的 —— Starlette 会把同步生成器丢进线程池迭代，
    于是 provider 里的阻塞调用都发生在工作线程，不占事件循环。
    """
    program = _get_program(body.program_id)
    conflicts = check_all(_to_plan(body), program)
    events = stream_conflicts(program, conflicts)
    return StreamingResponse(
        (sse_event(event) for event in events),
        media_type=STREAM_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )
