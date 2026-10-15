# 智能日报生成器

从 GitHub / 飞书自动采集工作数据，生成结构化日报并推送邮件或飞书消息。

## 快速开始

```bash
# 安装依赖
uv sync

# 复制并填写配置
cp config.yaml.example config.yaml
```

### 飞书数据接入

在飞书开放平台创建企业自建应用，并为应用开通任务、群消息读取权限。然后配置：

```powershell
$env:LARK_APP_ID="你的飞书应用 App ID"
$env:LARK_APP_SECRET="你的飞书应用 App Secret"
$env:LARK_PROJECT_ID="飞书任务清单 ID"
$env:LARK_CHAT_ID="飞书群聊 ID"
$env:LARK_MEMBER_ID="你的飞书成员 ID"
$env:REPORT_MEMBER_NAME="冯诗祺"
$env:LARK_KEYWORDS="进度,阻塞,评审,完成,会议"
```

### QQ 邮箱发送

```powershell
$env:MAIL_USER="你的QQ邮箱@qq.com"
$env:MAIL_AUTH_CODE="邮箱授权码"
$env:SMTP_HOST="smtp.qq.com"
$env:SMTP_PORT="465"
$env:SMTP_USE_SSL="true"
```

### 任务清单用户授权（个人清单必需）

1. 在飞书开放平台的“安全设置”中增加重定向 URL：

```text
http://127.0.0.1:5000/oauth/callback
```

2. 在“权限管理”中开通以下用户授权权限，并发布新版本：

```text
offline_access
task:tasklist:read
task:tasklist:write
task:task:read
```

3. 启动后端后访问 `http://127.0.0.1:5000/api/oauth/start`，用你的飞书账号确认授权。
4. 回调成功后，系统会把应用机器人加入任务清单协作者。之后任务采集仍由后台自动完成，无需重复授权。

### 启动

```powershell
# 启动后端，网页默认端口 5000
python main.py

# 另一个终端启动前端
cd frontend
npm run dev
```

页面点击“刷新”时，系统会实时采集飞书任务、飞书消息和 GitHub 提交并生成日报。点击“生成并发送”后，后端会重新采集并生成最新日报，再发送到老师邮箱，不依赖前端拼接内容。

### 命令行运行

```bash
python main.py --dry-run    # 只采集和生成，不推送
python main.py --demo       # 使用本地演示数据跑通全流程
```

### 日报洞察与邮件标题

系统现在会自动生成指标概览、AI 今日总结、每日变化对比、重点事项、待办提取和数据同步状态。

邮件标题格式为：

```text
REPORT_GRADE + 成员姓名 + 日期 + 智能日报
```

例如：

```text
研一冯诗祺2026-10-13智能日报
```

可通过环境变量 `REPORT_GRADE` 调整年级前缀，默认值为 `研一`。

## 项目结构

```
collector/   # 采集层
generator/   # 生成层
notifier/    # 推送层
shared/      # 共享基础层
tests/       # 测试
```
# PageDailyReport 智能日报生成器
## 启动步骤
1. 启动后端：python main.py （端口5000）
2. 启动前端：npm install 、npm run dev （端口5173）
3. 浏览器访问 http://localhost:5173
4. 填写日期、姓名，点击刷新生成日报

