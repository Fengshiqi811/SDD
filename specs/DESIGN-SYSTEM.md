# 智能日报生成器 · DESIGN-SYSTEM.md

> 视觉与组件契约（OpenDesign / 工程实现以此为准）。  
> 版本：v2.0 · 对齐后端模块：采集 / 生成 / 存储 / 推送  
> 说明：仓库已有架构文档 `design.md`；Windows 下文件名大小写不敏感，故视觉规范使用本文件名，避免互相覆盖。

---

## 1. 品牌与产品气质

| 项 | 说明 |
|----|------|
| 产品名 | 智能日报生成器（PageDailyReport） |
| 气质 | 工程协作工具：冷静、可读、偏「工作台」而非营销落地页 |
| 主任务 | 按日期生成日报 → 浏览历史 → 查看采集明细与成品 → 导出/推送 |
| 品牌信号 | 顶栏左侧墨色字标 + 青绿强调色块 Logo；首屏以「日报列表 / 生成」业务为主 |

---

## 2. 色板（CSS 变量）

```css
:root {
  --brand: #0f766e;
  --brand-hover: #0d9488;
  --brand-active: #115e59;
  --brand-soft: #ccfbf1;
  --brand-ink: #134e4a;

  --ink: #0f1c24;
  --ink-2: #3d4f5c;
  --ink-3: #6b7c88;
  --line: #d5dde3;
  --line-soft: #e8eef2;
  --surface: #ffffff;
  --surface-2: #f4f7f9;
  --bg: #e7eef2;

  --ok: #15803d;
  --ok-soft: #dcfce7;
  --warn: #c2410c;
  --warn-soft: #ffedd5;
  --danger: #dc2626;
  --danger-soft: #fee2e2;
  --info-soft: #e0f2fe;

  --code-bg: #152028;
  --code-fg: #d7e0e8;
}
```

**禁止：** 紫白渐变套路、奶油底+衬线+陶土色、报纸密排、无意义 glow。

---

## 3. 字体

| 用途 | 字体 | 后备 |
|------|------|------|
| 标题 / 字标 | **Sora** | "Noto Sans SC", sans-serif |
| 正文 / 表格 | **Noto Sans SC** | "PingFang SC", "Microsoft YaHei", sans-serif |
| 代码 / JSON | **JetBrains Mono** | Consolas, monospace |

字号：12 / 13 / 14 / 16 / 18 / 22 / 28 · 字重 400 / 500 / 600

---

## 4. 间距与圆角

- 间距：4 / 8 / 12 / 16 / 20 / 24 / 32 / 40
- 控件高：28 / 32 / 40
- 圆角：控件 6px · 面板 10px · 胶囊 999px
- 最大宽 1440px；阴影仅一层轻阴影

---

## 5. 布局骨架

Topbar（Logo + 导航 + 主 CTA）→ PageHead → FilterBar / Form / Detail 双栏。  
列表第一屏只做「查日报」；详情左采集右预览；生成页单列表单 + 右侧说明。

---

## 6. 组件规则

主按钮实心品牌色；次按钮描边；危险操作二次确认。  
表格 sticky 表头、空值「—」。表单标签在上、必填 `*`。  
状态：成功绿 / 失败红 / 部分失败橙 / 空闲灰。  
Alert / Toast / Modal / Empty / Loading / Skeleton 见 `assets/prototype.css`。

---

## 7. 动效（克制）

1. 页面进入 fade-up 220ms  
2. 列表加载 ↔ 空态/表格切换 180ms  
3. 提交按钮 loading + Toast 滑入  

`prefers-reduced-motion: reduce` 时关闭。

---

## 8. 文件映射

| 文件 | 职责 |
|------|------|
| `DESIGN-SYSTEM.md` | 本文 |
| `UI_SPEC.md` | 字段 / API / 缺口 |
| `index.html` | 预览入口 |
| `report-list.html` | 列表 |
| `report-detail.html` | 详情 |
| `report-generate.html` | 生成表单 |
| `assets/tokens.css` | 令牌 |
| `assets/prototype.css` | 样式 |
| `assets/mock-data.js` | 示例数据 |
| `assets/prototype.js` | 交互 |
