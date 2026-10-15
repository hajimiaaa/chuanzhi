#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 大模型适配层。

CLAUDE.md 的硬性要求：**必须支持 mock 模式** —— 无 API Key 时应用能完整运行，
这是评委"一键复现"的前提，也是本项目的结构性优势。

三条设计约束：
  1. 零第三方依赖 —— 用 urllib.request，不引 requests / openai SDK。
     于是"mock 与真实模式的切换不增加任何安装负担"。
  2. 导入期不联网、不读写文件 —— get_provider() 被调用时才读环境变量。
  3. MockProvider 必须确定性 —— 同样的 prompt 必得同样的输出，
     否则演示不可复现、单测无法断言。

`get_provider()` 是唯一的判定点，且**永不抛异常**：配置不全就回退 mock，
绝不因为缺 Key 让应用启动失败。

用法:
    text = explain_conflicts(program, conflicts)

依赖: 仅标准库 + app.models + app.config
"""

import json
import urllib.error
import urllib.request
from typing import Protocol

from app.config import env_str
from app.models import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING

SYSTEM_PROMPT = (
    "你是选课规划助手。请用中文、面向学生，简要解释下面的选课规划冲突，"
    "指出最需要先处理的问题并给出可执行的调整建议。不要复述原始 JSON。"
)

MOCK_RULES = (
    ("prerequisite_order", "先修顺序不对：有课程被排在它的先修课之前或同一学期，先修必须先修完。"),
    ("prerequisite_missing", "先修课缺位：有课程要修，但它的先修课既没修过也没排进规划。"),
    ("prerequisite_failed", "先修课未通过：有课程的先修课成绩不合格，需要重修通过后才能修该课。"),
    ("prerequisite_cycle", "培养方案存在循环先修，这属于数据问题，需要先修正方案本身。"),
    ("term_overload", "学期负荷超标：某一学期安排的学分超过了上限，建议把部分课程后移。"),
    ("course_not_offered", "开课学期不匹配：有课程被安排在该课并不开课的学期，请改到它实际开课的学期。"),
    ("credit_below_minimum", "学分结构未达标：有课程类别的已修学分低于培养方案的最低要求。"),
    ("time_overlap", "上课时段冲突：同一学期内有课程的上课时段重叠，需要调整其一。"),
    ("unknown_course", "存在课程代码不在培养方案课程库中，请核对代码是否写错。"),
    ("unknown_term", "存在学期编号超出学制范围，请核对学期。"),
)

MOCK_FALLBACK = "当前规划未发现明显的结构性问题，学分与先修关系均可满足。"

MOCK_PREFIX = "（mock 模式：以下解释由内置规则生成，未调用任何大模型）"


class Provider(Protocol):
    name: str

    def complete(self, prompt: str, *, system: str = "") -> str:
        ...


class MockProvider:
    """确定性应答，零网络。同样的 prompt 必得同样的输出。"""

    name = "mock"

    def complete(self, prompt: str, *, system: str = "") -> str:
        hits = [text for key, text in MOCK_RULES if key in prompt]
        if not hits:
            hits = [MOCK_FALLBACK]
        return MOCK_PREFIX + "\n" + "\n".join(f"- {h}" for h in hits)


class OpenAICompatProvider:
    """任何 OpenAI 兼容的 /chat/completions 端点。同步实现，用标准库 urllib。"""

    name = "openai-compat"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, *, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0}
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def get_provider() -> Provider:
    api_key = env_str("LLM_API_KEY")
    base_url = env_str("LLM_BASE_URL")
    model = env_str("LLM_MODEL")

    if not api_key:
        return MockProvider()
    if not base_url or not model:
        print("[!] LLM_API_KEY 已设置，但 LLM_BASE_URL / LLM_MODEL 不完整，回退 mock 模式")
        return MockProvider()
    return OpenAICompatProvider(api_key=api_key, base_url=base_url, model=model)


def build_conflict_prompt(program, conflicts) -> str:
    lines = [
        f"培养方案：{program.name}（{program.college} / {program.campus}）",
        f"数据状态：{program.data_status}",
        f"冲突总数：{len(conflicts)}",
        "",
    ]
    for i, conflict in enumerate(conflicts, 1):
        lines.append(f"{i}. [{conflict.severity}] {conflict.kind}: {conflict.message}")
    if not conflicts:
        lines.append("（无冲突）")
    return "\n".join(lines)


def explain_conflicts(program, conflicts, provider: Provider | None = None) -> dict:
    provider = provider or get_provider()
    prompt = build_conflict_prompt(program, conflicts)
    try:
        text = provider.complete(prompt, system=SYSTEM_PROMPT)
        error = ""
    except (urllib.error.URLError, OSError, KeyError, ValueError, TimeoutError) as exc:
        text = f"大模型调用失败，已降级说明：{exc}"
        error = str(exc)
    return {"provider": provider.name, "text": text, "error": error}


def severity_counts(conflicts) -> dict:
    counts = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 0, SEVERITY_INFO: 0}
    for conflict in conflicts:
        counts[conflict.severity] = counts.get(conflict.severity, 0) + 1
    return counts
