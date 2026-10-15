#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把学校发布的《专业目录一览表》(xlsx) 转换成结构化 JSON。

这是「官方文件 → 结构化数据」这条主线的第一个可复现实例：
任何人在拿到同一份官方文件后，运行本脚本都能得到同样的 JSON。

用法:
    py -3.11 tools/build_majors_json.py
    py -3.11 tools/build_majors_json.py --xlsx <路径> --out <路径>

依赖: 仅标准库（纯手写 xlsx 解析，避免为读一个表格引入整个 pandas）
"""

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REPO_ROOT = Path(__file__).resolve().parent.parent

# 从「专业名称」里识别出的身份标记。
# 这些标记直接决定转专业资格——《通知》明确规定
# 「专升本类、五年制高等师范教育类、春季高考类专业转到普通类专业的」不得转专业。
TAGS = [
    ("专升本", r"专升本"),
    ("春季高考", r"（春季）|\(春季\)"),
    ("中外合作", r"中外合作"),
    ("三二转段", r"32转段|三二转段"),
    ("专科", r"专科"),
    ("二年制", r"2年制"),
    ("五年制", r"5年制|五年制"),
]


def read_sheet_rows(xlsx_path):
    """读取 xlsx 首个工作表，产出「单元格列表」的迭代器。"""
    with zipfile.ZipFile(xlsx_path) as zf:
        strings = []
        try:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(f"{NS}t")) for si in root.findall(f"{NS}si")]
        except KeyError:
            pass

        sheets = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        root = ET.fromstring(zf.read(sheets[0]))

        for row in root.iter(f"{NS}row"):
            cells = {}
            for c in row.findall(f"{NS}c"):
                ref = c.get("r") or ""
                m = re.match(r"([A-Z]+)", ref)
                if not m:
                    continue
                col = 0
                for ch in m.group(1):
                    col = col * 26 + (ord(ch) - 64)
                col -= 1
                ctype = c.get("t")
                if ctype == "inlineStr":
                    el = c.find(f"{NS}is")
                    val = "".join(t.text or "" for t in el.iter(f"{NS}t")) if el is not None else ""
                else:
                    v = c.find(f"{NS}v")
                    val = v.text if v is not None and v.text else ""
                    if ctype == "s" and val != "":
                        val = strings[int(val)]
                if val:
                    cells[col] = val.strip()
            if cells:
                yield [cells.get(i, "") for i in range(max(cells) + 1)]


def tags_for(name):
    return [tag for tag, pat in TAGS if re.search(pat, name)]


def build(xlsx_path, meta):
    rows = list(read_sheet_rows(xlsx_path))
    if not rows:
        raise SystemExit("× 表里没有数据")

    title = rows[0][0] if rows else ""
    body = rows[1:]
    # 表头行：第一行里能对上「学院」「专业」的那行
    if body and any("专业" in c for c in body[0]):
        body = body[1:]

    colleges, campuses, seen = [], [], set()
    index = {}

    for r in body:
        if len(r) < 3:
            continue
        campus, college, major = r[0], r[1], r[2]
        level = r[3] if len(r) > 3 else ""
        if not major:
            continue

        if campus and campus not in campuses:
            campuses.append(campus)

        if college not in index:
            entry = {"name": college, "campus": campus, "majors": []}
            index[college] = entry
            colleges.append(entry)

        item = {"name": major, "level": level}
        tags = tags_for(major)
        if tags:
            item["tags"] = tags
        index[college]["majors"].append(item)
        seen.add(major)

    return {
        "source": meta,
        "campuses": campuses,
        "stats": {
            "colleges": len(colleges),
            "majors": len(seen),
        },
        "colleges": colleges,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", default=str(
        REPO_ROOT / "docs" / "调研原始材料" / "校方文件" / "附件3 枣庄学院2024级专业目录一览表.xlsx"))
    p.add_argument("--out", default=str(REPO_ROOT / "data" / "majors-枣庄学院-2024级.json"))
    args = p.parse_args()

    meta = {
        "school": "枣庄学院",
        "title": "枣庄学院2024级专业目录一览表",
        "origin": "枣庄学院教务处随《关于做好2024级普通全日制学生转专业的通知》发布的附件3",
        "raw_file": "docs/调研原始材料/校方文件/附件3 枣庄学院2024级专业目录一览表.xlsx",
        "generator": "tools/build_majors_json.py",
    }
    data = build(args.xlsx, meta)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    s = data["stats"]
    print(f"[OK] {s['colleges']} 个学院 / {s['majors']} 个专业 -> {out}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    main()
