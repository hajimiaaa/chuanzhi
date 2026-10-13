# 课径 CoursePath

> 把大学四年的培养方案，从一张看不懂的 PDF，变成一张能拖拽调整、实时算学分、自动查冲突的交互式路径图。

**参赛作品** — 第九届传智杯 · 全国高校 Vibe Coding 开发挑战赛 · B 组（个人赛）

---

## 这是什么

选课真正的困难不是"选哪门课好"，而是**约束满足**：

- **学分结构** — 必修 / 专业选修 / 通识 / 实践，每类各有最低学分要求
- **先修链** — A 必须先修 B，才能修 C
- **时间冲突** — 同一学期开课时间重叠
- **个人多目标** — 想保研 / 想早修完 / 想大四留出实习时间

课径把这些问题变成一个可视化规划器：拖动课程到不同学期，**实时**看到学分进度变化、冲突红色高亮、先修链断裂警告。

**特别针对的场景：转专业学生。** 转专业后已修课程如何折抵学分、需要补修哪些课、会不会延毕——这是现有工具几乎没有覆盖的真实痛点。

---

## 10 分钟极速复现指南

> 本节面向评审专家。**无需任何 API Key 即可完整运行核心功能。**

### 1. 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+ | 后端 |
| Node.js | 18+ | 前端 |
| Git | 任意 | |

> ⚠️ Windows 用户注意：若 `python` 命令报错，请改用 `py -3.11`。

### 2. 克隆仓库

```bash
git clone <仓库地址>
cd 课径
```

### 3. 后端

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r backend/requirements.txt
cp .env.example .env            # 无需填写任何值，留空即可运行
uvicorn app.main:app --reload --port 8000
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可。

### 5. 关于 AI 功能

应用**默认运行在 mock 模式**，使用内置样例数据，所有核心功能（学分校验、冲突检测、路径规划、可视化）**均无需联网即可完整演示**。

若需体验真实的大模型能力，在 `.env` 中填写你的 API Key 后重启后端即可。

---

## 项目结构

```
课径/
├── backend/                 FastAPI 后端
│   ├── app/
│   │   ├── main.py          入口
│   │   ├── models.py        数据模型
│   │   ├── constraints.py   约束校验引擎
│   │   ├── planner.py       路径规划算法
│   │   └── llm.py           大模型适配层（支持 mock）
│   └── requirements.txt
├── frontend/                React 前端
├── data/                    培养方案结构化数据
├── tools/
│   └── export_prompts.py    开发过程留痕导出工具
├── docs/
│   ├── prompts/             Prompt 链路记录（开发过程留痕）
│   ├── 开发日志.md
│   └── 技术文档.md
├── .env.example
└── .gitignore
```

---

## 技术栈

- **前端**：React + Vite + TypeScript，React Flow（依赖图）、ECharts（学分统计）
- **后端**：FastAPI + SQLAlchemy + SQLite（零配置，便于复现）
- **大模型**：可插拔适配层，无 Key 时自动降级为 mock

---

## 开发过程留痕

本作品的完整 AI 协作开发过程记录在 `docs/prompts/` 目录下，由 `tools/export_prompts.py` 从开发会话中自动导出，包含每次迭代的完整 Prompt 链。

每条 Git 提交对应一次与 AI 的核心对话或一个功能模块的落地。

---

## 开源许可

MIT
