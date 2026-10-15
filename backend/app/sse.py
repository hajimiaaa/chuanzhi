#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— SSE 帧格式。

单独成文件：`llm.py` 管的是模型适配，这里是**传输格式**，两件事分开后
帧格式有唯一可单测的地方，也让路由层保持"哑管道"。

帧格式刻意只用 `data:` 前缀，事件类型放在 JSON 的 `type` 字段里：
前端用 fetch + ReadableStream 读流，`event:` 字段在那里没有任何消费者语义
（`addEventListener` 是 EventSource 的东西），只会多一份要同步的命名表。

用法:
    StreamingResponse((sse_event(e) for e in stream_conflicts(...)),
                      media_type="text/event-stream", headers=SSE_HEADERS)

依赖: 仅标准库
"""

import json

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",       # 反代下禁缓冲；本机无害且正确
    "X-CoursePath-Stream": "1",      # 演示时在 DevTools 里一眼可见
}

STREAM_MEDIA_TYPE = "text/event-stream"


def sse_event(payload: dict) -> str:
    """一帧。

    用 JSON 编码，正文里就算有换行也不可能破坏帧边界 —— 这是流式最常见的 bug。
    ensure_ascii=False 是刻意的：评委在 DevTools 的 EventStream 面板里
    要能直接读出中文，而不是 `\\u5b66\\u5206`。
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
