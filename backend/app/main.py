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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.constraints import check_all, summarize
from app.llm import explain_conflicts, get_provider
from app.models import Plan
from app.planner import plan_completion_order
from app.schemas import ExplainIn, PlanIn, SuggestIn
from app.store import DataError, list_programs, load_majors, load_program

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
