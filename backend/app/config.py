#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 全局配置与路径基准。

**这是全项目唯一解析仓库路径的地方。**
本文件位于 backend/app/config.py，到仓库根是三层：config.py → app → backend → 仓库根。
写成 parents[1] 会静默指向 backend/，表现为"接口返回 200 但列表为空"，极难排查。

同时负责加载 .env：uvicorn 不会自动读 .env，而 README 承诺"填 Key 后重启即可"。
只填空缺，绝不覆盖已存在的真实环境变量。

用法:
    from app.config import REPO_ROOT, PROGRAMS_DIR, env_str

依赖: 仅标准库
"""

import os
from pathlib import Path

# ---------- 路径 ----------

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
PROGRAMS_DIR = DATA_DIR / "programs"
SCHEDULE_DIR = DATA_DIR / "schedule"

ENV_FILES = (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env")

# ---------- .env 加载 ----------

_env_loaded = False


def load_env() -> None:
    """把 .env 中缺失的键补进 os.environ；已存在的环境变量一律不覆盖。幂等。"""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True

    for path in ENV_FILES:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def env_str(name: str, default: str = "") -> str:
    load_env()
    return os.environ.get(name, "").strip() or default
