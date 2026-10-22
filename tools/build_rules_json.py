#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把《关于做好 2024 级普通全日制学生转专业的通知》正文转换成结构化 JSON。

与 build_majors_json.py 的区别值得说清楚：xlsx 是表格，字段就长在格子里，
脚本可以「解析」；通知是散文，哪一段属于「挂科要求」还是「专业限制」，
正则判不出来，只能人工判读。所以本脚本的形态是**人工分类 + 机器校验**：

  · 条款登记表（PROVISIONS / TIMELINE / GAPS）是人工判读的结果，写在本文件里；
  · 脚本负责装配，并在写盘前做**逐字引用回溯**——每条 quote、
    每个 factors 条目都必须能在原文里找到，每个条号都必须在原文里出现；
  · 缺口（GAPS）自带 absent_keywords 反证：声明「通知没写分数门槛」时，
    同时断言「门槛 / 分数线 / 绩点」这些词在原文里真的一次都没出现。

于是"我们没找到"不是一句托词，而是一句可被机器复核的话。同样的校验
validate_rules_json.py 里还有一份——第三方拿到产物，不必信任本脚本。

引文约定: quote / factors 为原文逐字，**仅去掉全部空白字符**
（原件从 PDF 转来，正文里混有换行与拆字空格，如「公 正」）。

用法:
    py -3.11 tools/build_rules_json.py
    py -3.11 tools/build_rules_json.py --txt <路径> --out <路径>

依赖: 仅标准库
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models import ModelError, RuleDoc  # noqa: E402

SOURCE = {
    "school": "枣庄学院",
    "title": "关于做好2024级普通全日制学生转专业的通知",
    "issuer": "枣庄学院教务处",
    "issued_date": "2025-02-17",
    "doc_no": "",
    "origin": "枣庄学院教务处发布的校级通知，随附 3 份附件（申请表 / 汇总表 / 专业目录一览表）",
    "raw_file": "docs/调研原始材料/校方文件/关于做好2024级普通全日制学生转专业的通知.txt",
    "generator": "tools/build_rules_json.py",
}

SCOPE = {
    "grade": "2024级",
    "student_types": ["普通全日制本科在校生", "普通全日制专科在校生"],
}

# 条款登记表。clause 是原文的条号，quote 是原文的逐字引用——
# 两者都由脚本回原文复核，写错会直接让脚本退出 1。
PROVISIONS = [
    # ---- 一、（一）基本范围 ----
    {
        "id": "limit-one-transfer",
        "category": "quota",
        "verdict": "limit",
        "clause": "一、（一）",
        "quote": "原则上学生在校学习期间最多只能转一次专业",
        "max_count": 1,
    },
    # ---- 一、（二）1. 不得转专业 ----
    {
        "id": "deny-arts-sports-to-general",
        "category": "major_restriction",
        "verdict": "deny",
        "clause": "一、（二）1.（1）",
        "quote": "艺术、体育专业转到普通类专业的；",
        "restricted_from": ["艺术类专业", "体育类专业"],
        "restricted_to": ["普通类专业"],
    },
    {
        "id": "deny-upgrade-spring-five-year-to-general",
        "category": "major_restriction",
        "verdict": "deny",
        "clause": "一、（二）1.（2）",
        "quote": "专升本类、五年制高等师范教育类、春季高考类专业转到普通类专业的；",
        "restricted_from": ["专升本类", "五年制高等师范教育类", "春季高考类"],
        "restricted_to": ["普通类专业"],
    },
    {
        "id": "deny-discretionary-unsuitable",
        "category": "major_restriction",
        "verdict": "deny",
        "clause": "一、（二）1.（3）",
        "quote": "其他经学校审核认为不适合转专业的。",
        "discretionary": True,
    },
    # ---- 一、（二）2. 可以转专业（共同前提 + 5 类情形）----
    {
        "id": "require-all-courses-passed",
        "category": "academic_record",
        "verdict": "require",
        "clause": "一、（二）2.",
        "quote": "在原专业学习期间，已修读课程考核全部合格",
    },
    {
        "id": "require-vice-president-approval",
        "category": "eligibility",
        "verdict": "require",
        "clause": "一、（二）2.",
        "quote": "经分管校领导批准",
    },
    {
        "id": "allow-injury-or-illness",
        "category": "eligibility",
        "verdict": "allow",
        "clause": "一、（二）2.（1）",
        "quote": "学生入学后因伤致残或发现患某种疾病、生理缺陷，经学校指定二级甲等及以上医院诊断证明，不能在原专业学习，但尚能在本校其他专业学习的；",
    },
    {
        "id": "allow-major-discontinued",
        "category": "eligibility",
        "verdict": "allow",
        "clause": "一、（二）2.（2）",
        "quote": "保留入学资格的新生或休学学生，入（复）学时学校已停办其原专业的；",
    },
    {
        "id": "allow-entrepreneurship-or-veteran",
        "category": "eligibility",
        "verdict": "allow",
        "clause": "一、（二）2.（3）",
        "quote": "休学创业或退役后复学的学生，因自身情况需要转专业的；",
    },
    {
        "id": "allow-school-adjustment",
        "category": "eligibility",
        "verdict": "allow",
        "clause": "一、（二）2.（4）",
        "quote": "根据社会对人才需求情况的发展变化，学校认为需要调整专业的；",
    },
    {
        "id": "allow-learning-difficulty",
        "category": "eligibility",
        "verdict": "allow",
        "clause": "一、（二）2.（5）",
        "quote": "确有学习困难的，不转专业无法继续学习的。",
    },
    # ---- 一、（三）考核的触发条件 ----
    {
        "id": "assessment-trigger-over-30pct",
        "category": "assessment_method",
        "verdict": "conditional",
        "clause": "一、（三）",
        "quote": "转入学生数超过转入专业当年招生人数的30%时，需按照转入学院制定的考核方案择优选择。",
        "ratio": 0.3,
    },
    # ---- 二、（一）学院自主制定方案 ----
    {
        "id": "assessment-factors-by-college",
        "category": "assessment_method",
        "verdict": "info",
        "clause": "二、（一）",
        "quote": "拟采取的考核方案应充分考虑拟转入学生已修课程学习情况、专业基础、高考选考科目、高考成绩、单科成绩以及综合素质等。",
        "factors": [
            "已修课程学习情况",
            "专业基础",
            "高考选考科目",
            "高考成绩",
            "单科成绩",
            "综合素质",
        ],
    },
    {
        "id": "where-college-plan-is-published",
        "category": "assessment_method",
        "verdict": "info",
        "clause": "二、（一）",
        "quote": "各学院将确定的转专业方案在本学院网站公示",
        "defers_to": "各学院网站公示的《转专业工作方案》",
    },
    # ---- 二、（二）志愿数 ----

    {
        "id": "limit-one-application",
        "category": "quota",
        "verdict": "limit",
        "clause": "二、（二）",
        "quote": "每位学生仅可申请1个转专业志愿",
        "max_count": 1,
    },
    # ---- 二、（三）默认接收 ----
    {
        "id": "default-accept-by-receiving-college",
        "category": "assessment_method",
        "verdict": "allow",
        "clause": "二、（三）",
        "quote": "转专业坚持以学生为本，尊重学生自主成才意愿，转入学院原则上应予以接收。",
    },
    # ---- 三、3. 学分认定被指向另一份文件 ----
    {
        "id": "credit-recognition-deferred",
        "category": "credit_recognition",
        "verdict": "info",
        "clause": "三、3.",
        "quote": "在原专业修读课程学分的认定，按照学校相关学分认定管理方法执行。",
        "defers_to": "《学校学分认定管理办法》（尚未获取）",
    },
]

TIMELINE = [
    {
        "id": "publish-college-plan",
        "label": "各学院制定并公示本学院转专业工作方案",
        "deadline": "2025-02-14",
        "clause": "二、（一）",
        "quote": "（一）确定转专业工作方案（2025年2月14日前完成）",
    },
    {
        "id": "student-apply",
        "label": "学生提交申请（交至转出学院）",
        "deadline": "2025-02-21",
        "clause": "二、（二）",
        "quote": "（二）学生申请（2025年2月21日前完成）",
    },
    {
        "id": "assessment",
        "label": "转专业考核完成",
        "deadline": "2025-03-03",
        "clause": "二、（三）",
        "quote": "（三）转专业考核（2025年3月3日前完成）",
    },
    {
        "id": "review-and-publicity",
        "label": "教务处审核并对拟同意名单公示（不少于 3 天）",
        "deadline": "2025-03-05",
        "clause": "二、（四）",
        "quote": "（四）审核公示（2025年3月5日前完成）",
    },
    {
        "id": "school-approval",
        "label": "学校审批、发文确定同意名单",
        "deadline": "2025-03-07",
        "clause": "二、（五）",
        "quote": "（五）学校审批（2025年3月7日前完成）",
    },
]

# 本轮最重要的一组数据：**查不到的那几类**。
# 每条 not_available / partial 都带 absent_keywords —— 这些词在原文里必须不出现，
# 校验脚本会真的去查一遍。负向断言让"通知没规定"变成可复核的结论。
GAPS = [
    {
        "category": "score_threshold",
        "status": "not_available",
        "detail": "校级通知未规定任何分数门槛。通知只要求「已修读课程考核全部合格」，"
                  "并把计划数与考核方案交给各学院自行制定。",
        "evidence_clause": "二、（一）",
        "absent_keywords": ["门槛", "分数线", "绩点", "70"],
        "where_to_find": "21 个学院的《转专业工作方案》（各学院网站公示），尚未采集",
    },
    {
        "category": "assessment_method",
        "status": "partial",
        "detail": "通知规定了启动考核的条件与学院应考量的因素，但未规定具体形式"
                  "——是笔试、面试还是材料审核，以及各占多少权重。",
        "evidence_clause": "一、（三）",
        "absent_keywords": ["笔试", "面试"],
        "where_to_find": "同上，各学院《转专业工作方案》",
    },
    {
        "category": "campus_restriction",
        "status": "not_available",
        "detail": "通知全文未涉及跨校区转专业是否受限。",
        "evidence_clause": "",
        "absent_keywords": ["校区"],
        "where_to_find": "需向教务处确认（docs/校方文件分析.md 第七节已列为待确认）",
    },
    {
        "category": "credit_recognition",
        "status": "not_available",
        "detail": "通知把学分认定指向另一份文件，本身未给任何认定细则。",
        "evidence_clause": "三、3.",
        "absent_keywords": ["折算", "互认"],
        "where_to_find": "《学校学分认定管理办法》（尚未获取）",
    },
    {
        "category": "major_restriction",
        "status": "partial",
        "detail": "通知使用「艺术、体育专业」的表述，但从未给出「艺术类 / 体育类」的界定，"
                  "《专业目录一览表》里也没有对应标注——无法从 data/majors-*.json "
                  "判定某个专业是否落入该条。专升本 / 春季高考 / 五年制高等师范教育类"
                  "可由目录 tags 判定。",
        "evidence_clause": "一、（二）1.（1）",
        "absent_keywords": ["艺术类", "体育类"],
        "where_to_find": "需人工确认专业归属（如空乘是否属艺术类）",
    },
]

NOTE = (
    "本文件只承载校级通知能支撑的规则；查不到的类别见 gaps。"
    "一、（二）2. 的五类「可以转专业」情形是并列关系，共同前提是"
    "「已修读课程考核全部合格」并经分管校领导批准——条款以扁平列表给出，"
    "组合关系看 clause 相同的条目。通知未定义「合格」的分数线，"
    "本模块不替学校假定为 60 分。引文为原文逐字，仅去掉全部空白字符。"
)

# 条号：一、/（二）/ 1. /（1）
CLAUSE_TOKEN = re.compile(r"[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|（\d+）|\d+\.")
WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """去掉全部空白字符。原件自 PDF 转来，正文混有换行与拆字空格（如「公 正」）。"""
    return WHITESPACE.sub("", text)


def check_against_source(flat: str) -> list[str]:
    """把条款登记表拿回原文对一遍。返回问题列表，空表示全通过。"""
    problems = []

    for clause in PROVISIONS + TIMELINE:
        cid = clause["id"]
        if normalize(clause["quote"]) not in flat:
            problems.append(f"{cid} 的 quote 在原文里找不到: {clause['quote']}")
        for factor in clause.get("factors", []):
            if normalize(factor) not in flat:
                problems.append(f"{cid} 的 factors 条目「{factor}」在原文里找不到")
        for token in CLAUSE_TOKEN.findall(clause.get("clause", "")):
            if token not in flat:
                problems.append(f"{cid} 的条号「{token}」在原文里找不到")

    for gap in GAPS:
        label = gap["category"]
        for token in CLAUSE_TOKEN.findall(gap.get("evidence_clause", "")):
            if token not in flat:
                problems.append(f"缺口 {label} 的 evidence_clause 条号「{token}」在原文里找不到")
        for word in gap.get("absent_keywords", []):
            if normalize(word) in flat:
                problems.append(
                    f"缺口 {label} 声明「{word}」在原文中不存在，但它出现了——缺口不成立"
                )

    return problems


def build(txt_path: Path) -> tuple[dict, list[str]]:
    flat = normalize(txt_path.read_text(encoding="utf-8"))
    problems = check_against_source(flat)
    if problems:
        return {}, problems

    payload = {
        "id": "transfer-notice-2024",
        "doc_type": "school_notice",
        "data_status": "official",
        "title": SOURCE["title"],
        "source": SOURCE,
        "applies_to": SCOPE,
        "provisions": PROVISIONS,
        "timeline": TIMELINE,
        "gaps": GAPS,
        "note": NOTE,
    }

    # 过一遍领域模型再落盘。两个好处：登记表里写错类别 / 判定 / 必填字段时当场退出，
    # 而不是产出一个能写进文件、却会在接口 500 的 JSON；以及**落盘形状与接口响应恒等**
    # ——文件就是 RuleDoc.to_dict()，不含手工登记表的"缺哪个键就省哪个键"。
    try:
        doc = RuleDoc.from_dict(payload)
    except ModelError as exc:
        return {}, [f"条款登记表不符合规则模型: {exc}"]

    return doc.to_dict(), []


def main() -> int:
    parser = argparse.ArgumentParser(description="把转专业通知正文转换成结构化 JSON")
    parser.add_argument("--txt", default=str(
        REPO_ROOT / "docs" / "调研原始材料" / "校方文件" / "关于做好2024级普通全日制学生转专业的通知.txt"))
    parser.add_argument("--out", default=str(
        REPO_ROOT / "data" / "rules" / "转专业通知-枣庄学院-2024级.json"))
    args = parser.parse_args()

    txt_path = Path(args.txt)
    if not txt_path.is_file():
        print(f"[×] 原始文件不存在: {txt_path}")
        return 1

    data, problems = build(txt_path)
    if problems:
        print(f"[×] 引用回溯未通过（{len(problems)} 处）——引用与原文对不上，拒绝生成:")
        for problem in problems:
            print(f"      - {problem}")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[OK] {len(data['provisions'])} 条条款 / {len(data['timeline'])} 个时间节点"
        f" / {len(data['gaps'])} 处缺口 -> {out}"
    )
    print("[OK] 全部引用与条号已在原文中逐字复核")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
