# 智能日报生成器 · UI_SPEC.md

> 页面清单 · 字段↔API 对照 · 关键操作↔HTTP · 后端缺口  
> 版本：v1.0 · 解析自仓库 `main.py` / `collector/` / `generator/` / `shared/` / `notifier/`

---

## 1. 后端能力摘要

### 1.1 已实现 HTTP

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/report` | Flask 模拟生成：body `{ date, member }` → `{ code, raw, data }` |

### 1.2 库层能力（尚无 HTTP，UI 按模型预留）

| 能力 | 模块 | 说明 |
|------|------|------|
| 列表历史 | `ReportStorage.list_reports(limit)` | 按日期倒序 |
| 详情查询 | `ReportStorage.get_report(date, team_name)` | 唯一键 (date, team) |
| 落库 | `ReportStorage.save_report(...)` | upsert |
| 真实采集 | `collector.*.collect` | Commit / Task / Message |
| 团队日报生成 | `generator.generate` | DailyReport markdown+html |
| 邮件推送 | `notifier.email.send` | bool |
| 飞书推送 | `notifier.lark_bot.send` | bool |
| 配置 | `shared.config.AppConfig` | YAML + 环境变量 |

### 1.3 权限与角色

当前**无鉴权、无角色**。所有按钮默认可见。UI 预留「无权限」态，不伪造 RBAC。

---

## 2. 页面清单

| 页面 | 文件 | 主任务 | 核心资源 |
|------|------|--------|----------|
| 预览入口 | `index.html` | 导航到各屏 | — |
| 日报列表 | `report-list.html` | 浏览 / 筛选历史 | `DailyReportRecord` |
| 日报详情 | `report-detail.html` | 读采集明细 + 成品 | `DailyReport` + 采集记录 |
| 生成日报 | `report-generate.html` | 创建（触发采集生成） | `POST /api/report` |

主路径：**列表 → 详情 → 生成 → 回列表/详情**。

---

## 3. 字段对照

### 3.1 列表页 `report-list.html`

| UI 列 / 筛选项 | 中文名 | 数据来源字段 | 类型 | 备注 |
|----------------|--------|--------------|------|------|
| ID | 编号 | `DailyReportRecord.id` | int | 列表次要列 |
| 日报日期 | 日期 | `report_date` | date | 默认排序 DESC |
| 团队 | 团队 | `team_name` | str | |
| 生成时间 | 生成于 | `generated_at` | datetime | 格式 `YYYY-MM-DD HH:mm` |
| 摘要 | 摘要 | 由 `markdown` 截取首行 | str | 展示用，非独立字段 |
| 筛选：日期 | 日期 | — | date | **需后端新增** query；原型客户端过滤 |
| 筛选：团队 | 团队 | — | str | **需后端新增**；原型客户端过滤 |
| 分页 limit | 每页条数 | `list_reports(limit)` | int | 后端仅有 limit，**无 offset/page** → 缺口 |
| 空值 | — | — | — | 显示「—」 |

**状态：** 加载骨架 / 空态「暂无日报」/ 错误 Alert / 列表就绪。

### 3.2 详情页 `report-detail.html`

#### 页头只读

| UI | 字段 | 来源 |
|----|------|------|
| 日期 | `date` / `report_date` | DailyReport / Record |
| 团队 | `team_name` | 同上 |
| 生成时间 | `generated_at` | 同上 |
| 成员范围 | `member` 或 members[].name | POST mock 用单成员；库层为成员列表 |

#### 采集明细（左）

| UI 分组 | 字段 | DTO |
|---------|------|-----|
| GitHub 提交 | author, message, timestamp, repo, additions, deletions, files_changed | `CommitRecord` |
| 飞书任务 | assignee, title, status_from→status_to, updated_at | `TaskRecord` |
| 飞书消息 | sender, content, timestamp, chat_name | `MessageRecord` |
| 源失败 | CollectResult.error_message | 部分失败警告条 |

**当前 HTTP `raw` 形状（mock，字段更瘦）：**

| UI | `raw.*` |
|----|---------|
| 仓库/说明 | `raw.github[].repo` / `.commit` |
| 消息行 | `raw.lark_msg[]` 字符串 |
| 任务 | **mock 未返回** `lark_task` → 缺口对齐库层 |

#### 成品预览（右）

| UI | 字段 |
|----|------|
| Markdown 渲染 | `data`（HTTP）或 `markdown`（库） |
| HTML 切换 | `html`（库有；HTTP mock 无，前端可由 md 生成） |

### 3.3 生成表单 `report-generate.html`

| UI 控件 | 中文 | 请求字段 | 必填 | 校验 |
|---------|------|----------|------|------|
| 日期 | 日报日期 | `date` | 是 | 非空；`YYYY-MM-DD` |
| 成员 | 团队成员 | `member` | 否 | 自由文本；选项来自 config.members.name |
| 团队名 | 团队 | — | — | 配置只读展示；**POST 未传 team_name**（缺口） |
| dry-run | 仅生成不推送 | — | — | **需后端新增**；原型开关禁用并标注 |
| 提交 | 开始生成 | `POST /api/report` | — | loading / 成功 Toast / 失败 message |

**响应映射：**

| 响应 | UI |
|------|-----|
| `code === 0` | 成功 → 跳转详情（query 带 date/member）或回列表 |
| `raw` | 详情左侧原始区 |
| `data` | 详情右侧 markdown |
| 网络/500 | Alert「数据加载失败，请重试」；优先 `message` |

### 3.4 枚举可读标签

| code / 原值 | 界面标签 |
|-------------|----------|
| `todo` | 待办 |
| `in_progress` / `doing` | 进行中 |
| `done` | 已完成 |
| `unknown` | 未知 |
| CollectResult.success=false | 数据获取失败 |
| HTTP code=0 | 成功 |

---

## 4. 关键操作 ↔ HTTP / 库

| UI 操作 | 行为 | 对接 | 状态 |
|---------|------|------|------|
| 刷新列表 | 重新拉取历史 | `GET` 列表 **需后端新增**（现用 mock） | 原型模拟 |
| 打开详情 | 路由 + 读记录 | `GET` 详情 **需后端新增**；或沿用上次 POST 缓存 | 原型模拟 |
| 生成日报 | 表单提交 | **`POST /api/report`** | ✅ 已有 |
| 复制 Markdown | 剪贴板 | 纯前端 | ✅ |
| 导出 HTML | 下载文件 | 纯前端（可用 `html` 字段） | ✅ |
| 重新生成 | 确认后再次 POST | `POST /api/report` | ✅ |
| 删除历史 | 二次确认 | **需后端新增** DELETE | 原型模拟 + 缺口 |
| 推送邮件 | 二次确认 | `notifier.email.send` → **需后端新增** HTTP | 按钮可见，标注缺口 |
| 推送飞书 | 二次确认 | `notifier.lark_bot.send` → **需后端新增** | 同上 |
| 启用/禁用 | — | 后端无此资源 | **不做** |

写操作成功后：生成 → 进详情并 Toast；删除 → 回列表并刷新。

---

## 5. 待后端确认的缺口

1. **历史列表 HTTP**：`GET /api/reports?limit=&page=&date=&team_name=`（现仅有 `list_reports(limit)`）
2. **详情 HTTP**：`GET /api/reports/{date}?team_name=` 或 `GET /api/report?date=&team_name=`
3. **删除 HTTP**：`DELETE /api/reports/{id}` 或按 (date, team)
4. **推送 HTTP**：`POST /api/reports/{id}/notify` body `{ channels: ["email","lark"] }`
5. **契约统一**：设计稿曾定 `GET /api/report` + `raw_records` / `meta.errors`；现网为 `POST` + `raw` / `data` —— 需产品确认以谁为准
6. **POST 扩展**：`team_name`、`members[]`、`dry_run`、结构化 `raw_records`（含完整 CommitRecord/TaskRecord/MessageRecord）
7. **分页**：`offset` / `page` / `total`
8. **鉴权与角色**：谁可生成、谁可推送、谁可删
9. **Flask 依赖**：`flask` / `flask-cors` 未写入 `pyproject.toml`
10. **CLI 与 Flask**：工作区 `main.py` 为 Flask stub，集成测试仍期望 `run_pipeline` —— 工程需拆分入口

---

## 6. 原型数据说明

`assets/mock-data.js` 中示例数据对齐：

- `DailyReportRecord` / `DailyReport` / `MemberReport`
- `CommitRecord` / `TaskRecord` / `MessageRecord`
- `MemberConfig`（张三 / 李四 / 王五）
- 现网 `POST /api/report` 的 `raw` / `data` 瘦结构（用于「联调模式」演示）

不含 lorem 乱码。

---

## 7. 验收对照

| 标准 | 原型如何满足 |
|------|----------------|
| 列表→详情→创建→回列表 | 三页互链 + mock 状态机 |
| 字段可追溯或标缺口 | 本文 §3–§5 |
| 空/加载/错/无权限 | 列表工具条可切换演示态 |
| 桌面+窄屏 | CSS 断点 720 / 1180 |
| 风格统一 | `DESIGN-SYSTEM.md` + `tokens.css` |
