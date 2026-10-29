#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 打包「作品提交」zip。

预提交/省赛要求把完整作品上传网盘。手工压容易犯两类错，这个脚本把两类都堵住：

  1. **压丢了跑不起来的东西** —— 前端若只打包 `src/`，缺 package.json / vite.config.ts /
     index.html，评委 `npm install` 第一步就断。脚本在写盘前检查一组必需文件。
  2. **压进了不该有的东西** —— node_modules / .venv / __pycache__ / .env / 录屏原片。

文件名由 Python 的 zipfile 写入，会自动带 UTF-8 标志位，
Windows / macOS / Linux 解压都不会乱码（Windows 自带压缩在很多情况下不会设这个位）。

用法:
    py -3.11 tools/build_submission_zip.py
    py -3.11 tools/build_submission_zip.py --out <zip 路径>

依赖: 仅标准库
"""

import argparse
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFIX = "课径-CoursePath"

# 目录名命中即跳过（任意层级）
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".claude",
    "recordings",  # 录屏原片：视频走 B站/抖音链接，不进作品包
    ".idea",
    ".vscode",
}

# 精确文件名命中即跳过
SKIP_FILES = {".env", ".DS_Store", "Thumbs.db"}

# 这些文件缺一个，评委就跑不起来
REQUIRED = (
    "README.md",
    ".env.example",
    "backend/requirements.txt",
    "frontend/package.json",
    "frontend/vite.config.ts",
    "frontend/index.html",
    "data/majors-枣庄学院-2024级.json",
    "data/rules/转专业通知-枣庄学院-2024级.json",
    "docs/技术文档.pdf",
    "docs/作品介绍.pdf",
)


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix == ".pyc":
            continue
        # 桌面截图（表单截图）不是作品材料
        if path.name.startswith("微信图片_"):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="打包作品提交 zip")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT.parent / "课径-作品提交.zip"),
        help="输出路径（默认放在仓库同级的 竞赛/ 目录下）",
    )
    args = parser.parse_args()

    missing = [name for name in REQUIRED if not (REPO_ROOT / name).is_file()]
    if missing:
        print("[×] 缺少必需文件，拒绝打包：")
        for name in missing:
            print(f"      - {name}")
        return 1

    files = list(iter_files(REPO_ROOT))
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = f"{PREFIX}/{path.relative_to(REPO_ROOT).as_posix()}"
            archive.write(path, arcname)

    # 写盘后自检：确认该在的在、该没的没
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
        if not any(n.endswith("frontend/package.json") for n in names):
            print("[×] 自检失败：包里没有 frontend/package.json")
            return 1
        banned = [n for n in names if any(k in n for k in ("__pycache__", ".pytest_cache", "node_modules", ".venv/"))]
        if banned:
            print(f"[×] 自检失败：包里混进了 {len(banned)} 个缓存/依赖文件")
            return 1

    size_mb = out.stat().st_size / 1048576
    print(f"[OK] {out}")
    print(f"     {len(files)} 个文件 / {size_mb:.1f} MB（压缩后）/ 顶层目录 {PREFIX}/")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
