#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课径 CoursePath —— 把 docs/技术文档.md 转成可提交的 PDF。

提交物要求技术文档为 PDF（≤30 页）。本脚本把这条链路固化下来，
保证「文档改了、PDF 能一键重生成」，而不是手工导出。

链路:  pandoc（md → 自带样式的独立 HTML）  →  Edge 无头（HTML → PDF）

为什么不用 LaTeX: 本机没有 xelatex/pdflatex，装一套 TeX 发行版动辄数 GB，
而 Edge 已随 Windows 提供、且中文字体开箱可用。

用法:
    py -3.11 tools/build_tech_pdf.py
    py -3.11 tools/build_tech_pdf.py --md docs/技术文档.md --pdf docs/技术文档.pdf

依赖: 标准库 + 外部命令 pandoc、msedge（缺失时会明确报错并给出安装提示）
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

# 打印样式。正文用微软雅黑（Windows 自带，中文不缺字），代码用 Consolas。
PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
       font-size: 10.5pt; line-height: 1.7; color: #16181d; }
/* pandoc 会用 metadata 里的 title 再生成一个标题块，
   而文档自己已有 H1 —— 隐藏前者，避免标题出现两次 */
h1.title, header#title-block-header { display: none; }
h1 { font-size: 20pt; border-bottom: 2px solid #2a78d6; padding-bottom: 6px; }
h2 { font-size: 15pt; margin-top: 1.6em; border-bottom: 1px solid #e1e0d9;
     padding-bottom: 4px; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin-top: 1.3em; page-break-after: avoid; }
h4 { font-size: 11pt; page-break-after: avoid; }
code, pre { font-family: Consolas, monospace; font-size: 9pt; }
pre { background: #f7f7f5; border: 1px solid #e1e0d9; border-radius: 4px;
      padding: 8px 10px; page-break-inside: avoid; white-space: pre-wrap; }
code { background: #f7f7f5; padding: 1px 3px; border-radius: 3px; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt;
        page-break-inside: avoid; margin: 8px 0; }
th, td { border: 1px solid #d8d7d0; padding: 5px 7px; text-align: left; vertical-align: top; }
th { background: #f2f1ee; font-weight: 600; }
blockquote { border-left: 3px solid #2a78d6; margin: 10px 0; padding: 4px 12px;
             background: #f7f9fc; color: #3a3d45; }
hr { border: none; border-top: 1px solid #e1e0d9; margin: 18px 0; }
"""


def find_edge() -> str:
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("msedge")
    if found:
        return found
    raise SystemExit("× 找不到 Microsoft Edge。请安装 Edge，或用 --edge 指定可执行文件路径。")


def count_pages(pdf: Path) -> int:
    """粗略统计页数：数 /Type /Page（排除 /Pages）。够用了，不值得为它引 PDF 库。"""
    raw = pdf.read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", raw))


def main() -> int:
    parser = argparse.ArgumentParser(description="把技术文档 Markdown 转成 PDF")
    parser.add_argument("--md", default=str(REPO_ROOT / "docs" / "技术文档.md"))
    parser.add_argument("--pdf", default=str(REPO_ROOT / "docs" / "技术文档.pdf"))
    parser.add_argument("--edge", default="", help="Edge 可执行文件路径（默认自动查找）")
    args = parser.parse_args()

    md = Path(args.md)
    pdf = Path(args.pdf)
    if not md.is_file():
        raise SystemExit(f"× 找不到 Markdown: {md}")
    if not shutil.which("pandoc"):
        raise SystemExit("× 找不到 pandoc。请先安装：https://pandoc.org/installing.html")

    edge = args.edge or find_edge()

    with tempfile.TemporaryDirectory(prefix="kepath-pdf-") as tmp:
        tmpdir = Path(tmp)
        css = tmpdir / "print.css"
        html = tmpdir / "doc.html"
        profile = tmpdir / "edge-profile"
        css.write_text(PRINT_CSS, encoding="utf-8")

        subprocess.run(
            [
                "pandoc", str(md),
                "--standalone", "--embed-resources",
                f"--metadata=title:{md.stem}",
                f"--css={css}",
                "-o", str(html),
            ],
            check=True,
        )

        pdf.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                edge,
                "--headless=new", "--disable-gpu",
                "--no-first-run", "--no-default-browser-check",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}",
                html.as_uri(),
            ],
            check=True,
            capture_output=True,
        )

    if not pdf.is_file():
        raise SystemExit("× PDF 未生成。")

    pages = count_pages(pdf)
    size_kb = pdf.stat().st_size / 1024
    print(f"[OK] {pdf.relative_to(REPO_ROOT)}  {pages} 页 / {size_kb:.0f} KB")
    if pages > 30:
        print(f"[!] 超过提交要求的 30 页上限（当前 {pages} 页）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
