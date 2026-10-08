/**
 * mock-data.js
 * 真实感示例数据，结构对齐后端 DTO（见 specs/contracts/data-models.md / shared/storage.py）
 * 供 HTML 原型本地演示；不含 lorem。
 */
(function (global) {
  'use strict';

  /** @type {import('../UI_SPEC.md')} MemberConfig[] — shared.config.MemberConfig */
  const MEMBERS = [
    { name: '张伟', github: 'zhangwei', lark: 'zhangwei@company.com' },
    { name: '李娜', github: 'lina-dev', lark: 'lina@company.com' },
    { name: '王强', github: 'wangqiang', lark: 'wangqiang@company.com' },
    { name: '陈静', github: 'chenjing', lark: 'chenjing@company.com' },
  ];

  const TEAM_NAME = '研发团队';

  /**
   * CommitRecord + 展示扩展
   * DTO: author, message, timestamp, repo, additions, deletions, files_changed
   * UI 扩展: sha, branch, display_name（非后端字段，仅原型展示）
   */
  const COMMITS_ALL = [
    {
      author: 'zhangwei',
      display_name: '张伟',
      message: 'fix(date-picker): 修复跨月切换后面板不刷新的问题',
      timestamp: '2026-10-08T09:24:00+08:00',
      repo: 'opentiny/tiny-vue',
      branch: 'feat/date-picker',
      sha: 'a1b2c3d',
      additions: 42,
      deletions: 18,
      files_changed: 5,
    },
    {
      author: 'zhangwei',
      display_name: '张伟',
      message: 'feat(select): 多选标签支持一键清空',
      timestamp: '2026-10-08T11:02:00+08:00',
      repo: 'opentiny/tiny-vue',
      branch: 'feat/date-picker',
      sha: '7f8e9d0',
      additions: 76,
      deletions: 9,
      files_changed: 4,
    },
    {
      author: 'lina-dev',
      display_name: '李娜',
      message: 'perf(order): 退款查询接口合并两次数据库往返',
      timestamp: '2026-10-08T10:15:00+08:00',
      repo: 'team/refund-service',
      branch: 'main',
      sha: 'c3d4e5f',
      additions: 128,
      deletions: 64,
      files_changed: 6,
    },
    {
      author: 'lina-dev',
      display_name: '李娜',
      message: 'fix(payment): 修正并发场景下重复退款的幂等键',
      timestamp: '2026-10-08T15:40:00+08:00',
      repo: 'team/refund-service',
      branch: 'main',
      sha: '9a0b1c2',
      additions: 54,
      deletions: 31,
      files_changed: 3,
    },
    {
      author: 'wangqiang',
      display_name: '王强',
      message: 'test(refund): 补充退款超时与重试的端到端用例',
      timestamp: '2026-10-08T14:08:00+08:00',
      repo: 'team/refund-service',
      branch: 'test/e2e',
      sha: 'e5f6a7b',
      additions: 210,
      deletions: 12,
      files_changed: 8,
    },
    {
      author: 'chenjing',
      display_name: '陈静',
      message: 'docs(tokens): 更新色彩令牌说明与对比度记录',
      timestamp: '2026-10-08T16:22:00+08:00',
      repo: 'team/design-system',
      branch: 'main',
      sha: 'b7c8d9e',
      additions: 33,
      deletions: 5,
      files_changed: 2,
    },
  ];

  /**
   * TaskRecord[] + 展示扩展 priority / task_id
   */
  const TASKS_ALL = [
    {
      assignee: 'zhangwei@company.com',
      display_name: '张伟',
      title: '日期选择器跨月刷新缺陷修复',
      status_from: 'in_progress',
      status_to: 'done',
      updated_at: '2026-10-08T16:10:00+08:00',
      task_id: 'TASK-1024',
      priority: '高',
    },
    {
      assignee: 'lina@company.com',
      display_name: '李娜',
      title: '退款查询接口性能优化',
      status_from: 'todo',
      status_to: 'in_progress',
      updated_at: '2026-10-08T14:20:00+08:00',
      task_id: 'TASK-1025',
      priority: '中',
    },
    {
      assignee: 'wangqiang@company.com',
      display_name: '王强',
      title: '退款超时端到端用例补充',
      status_from: 'todo',
      status_to: 'todo',
      updated_at: '2026-10-08T11:30:00+08:00',
      task_id: 'TASK-1026',
      priority: '中',
    },
    {
      assignee: 'chenjing@company.com',
      display_name: '陈静',
      title: '设计令牌文档与对比度记录',
      status_from: 'in_progress',
      status_to: 'done',
      updated_at: '2026-10-08T17:00:00+08:00',
      task_id: 'TASK-1027',
      priority: '低',
    },
    {
      assignee: 'zhangwei@company.com',
      display_name: '张伟',
      title: 'Select 多选一键清空',
      status_from: 'todo',
      status_to: 'in_progress',
      updated_at: '2026-10-08T12:05:00+08:00',
      task_id: 'TASK-1028',
      priority: '高',
    },
  ];

  /**
   * MessageRecord[] + 展示扩展 keyword
   */
  const MSGS_ALL = [
    {
      sender: 'zhangwei@company.com',
      display_name: '张伟',
      content: '进度：date-picker 跨月问题已合入 feat 分支，下午提测。',
      timestamp: '2026-10-08T13:15:00+08:00',
      chat_name: '研发日报群',
      keyword: '进度',
    },
    {
      sender: 'lina@company.com',
      display_name: '李娜',
      content: '阻塞：退款库从库延迟偏高，查询合并方案先灰度。',
      timestamp: '2026-10-08T14:02:00+08:00',
      chat_name: '研发日报群',
      keyword: '阻塞',
    },
    {
      sender: 'wangqiang@company.com',
      display_name: '王强',
      content: '评审：e2e 超时用例覆盖率补到主路径。',
      timestamp: '2026-10-08T15:20:00+08:00',
      chat_name: '质量保障群',
      keyword: '评审',
    },
    {
      sender: 'chenjing@company.com',
      display_name: '陈静',
      content: '进度：tokens 对比度说明已更新，请设计侧确认。',
      timestamp: '2026-10-08T16:40:00+08:00',
      chat_name: '设计协作群',
      keyword: '进度',
    },
    {
      sender: 'lina@company.com',
      display_name: '李娜',
      content: '进度：幂等键修复已上预发，观察 30 分钟。',
      timestamp: '2026-10-08T17:05:00+08:00',
      chat_name: '研发日报群',
      keyword: '进度',
    },
  ];

  /**
   * MemberReport — commits/tasks/messages: list | null(失败)
   */
  function memberReport(name, github, commits, tasks, messages) {
    return { name, github_username: github, commits, tasks, messages };
  }

  /**
   * DailyReport + 存储层 DailyReportRecord 合并视图（原型用）
   */
  const REPORTS = [
    {
      id: 3,
      report_date: '2026-10-08',
      team_name: TEAM_NAME,
      generated_at: '2026-10-08T18:05:00+08:00',
      members: [
        memberReport('张伟', 'zhangwei', COMMITS_ALL.filter((c) => c.author === 'zhangwei'), TASKS_ALL.filter((t) => t.display_name === '张伟'), MSGS_ALL.filter((m) => m.display_name === '张伟')),
        memberReport('李娜', 'lina-dev', COMMITS_ALL.filter((c) => c.author === 'lina-dev'), TASKS_ALL.filter((t) => t.display_name === '李娜'), MSGS_ALL.filter((m) => m.display_name === '李娜')),
        memberReport('王强', 'wangqiang', COMMITS_ALL.filter((c) => c.author === 'wangqiang'), TASKS_ALL.filter((t) => t.display_name === '王强'), MSGS_ALL.filter((m) => m.display_name === '王强')),
        memberReport('陈静', 'chenjing', COMMITS_ALL.filter((c) => c.author === 'chenjing'), TASKS_ALL.filter((t) => t.display_name === '陈静'), MSGS_ALL.filter((m) => m.display_name === '陈静')),
      ],
      /* 扁平原始区（对齐设计稿 Tab 表格） */
      raw_records: {
        github: COMMITS_ALL,
        lark_task: TASKS_ALL,
        lark_msg: MSGS_ALL,
      },
      markdown:
        '# 研发团队 日报 2026-10-08\n\n## 张伟\n### 代码提交\n- `opentiny/tiny-vue` fix(date-picker): 修复跨月切换后面板不刷新的问题\n- `opentiny/tiny-vue` feat(select): 多选标签支持一键清空\n### 任务进展\n- 日期选择器跨月刷新缺陷修复：进行中 → 已完成\n\n## 李娜\n### 代码提交\n- `team/refund-service` perf(order): 退款查询接口合并两次数据库往返\n- `team/refund-service` fix(payment): 修正并发场景下重复退款的幂等键\n\n## 王强\n### 代码提交\n- `team/refund-service` test(refund): 补充退款超时与重试的端到端用例\n\n## 陈静\n### 代码提交\n- `team/design-system` docs(tokens): 更新色彩令牌说明与对比度记录\n',
      html: '',
      collect_meta: {
        collect_count: COMMITS_ALL.length + TASKS_ALL.length + MSGS_ALL.length,
        errors: [],
      },
    },
    {
      id: 2,
      report_date: '2026-10-07',
      team_name: TEAM_NAME,
      generated_at: '2026-10-07T18:12:00+08:00',
      members: [
        memberReport(
          '张伟',
          'zhangwei',
          [
            {
              author: 'zhangwei',
              display_name: '张伟',
              message: 'chore: 更新 config.yaml.example 注释',
              timestamp: '2026-10-07T11:00:00+08:00',
              repo: 'org/repo-a',
              branch: 'main',
              sha: 'd4e5f60',
              additions: 12,
              deletions: 2,
              files_changed: 1,
            },
          ],
          null,
          [
            {
              sender: 'zhangwei@company.com',
              display_name: '张伟',
              content: '评审：采集层返回值封装 ADR 已合入。',
              timestamp: '2026-10-07T16:40:00+08:00',
              chat_name: '研发日报群',
              keyword: '评审',
            },
          ]
        ),
      ],
      raw_records: {
        github: [
          {
            author: 'zhangwei',
            display_name: '张伟',
            message: 'chore: 更新 config.yaml.example 注释',
            timestamp: '2026-10-07T11:00:00+08:00',
            repo: 'org/repo-a',
            branch: 'main',
            sha: 'd4e5f60',
            additions: 12,
            deletions: 2,
            files_changed: 1,
          },
        ],
        lark_task: null,
        lark_msg: [
          {
            sender: 'zhangwei@company.com',
            display_name: '张伟',
            content: '评审：采集层返回值封装 ADR 已合入。',
            timestamp: '2026-10-07T16:40:00+08:00',
            chat_name: '研发日报群',
            keyword: '评审',
          },
        ],
      },
      markdown:
        '# 研发团队 日报 2026-10-07\n\n## 张伟\n### 代码提交\n- `org/repo-a` chore: 更新 config.yaml.example 注释\n### 任务进展\n数据获取失败\n### 协作沟通\n- 评审：采集层返回值封装 ADR 已合入。\n',
      html: '',
      collect_meta: {
        collect_count: 2,
        errors: ['lark_task: 获取 tenant_access_token 失败'],
      },
    },
    {
      id: 1,
      report_date: '2026-10-06',
      team_name: TEAM_NAME,
      generated_at: '2026-10-06T18:00:00+08:00',
      members: [
        memberReport('李娜', 'lina-dev', [], [], []),
        memberReport('王强', 'wangqiang', [], [], []),
      ],
      raw_records: { github: [], lark_task: [], lark_msg: [] },
      markdown: '# 研发团队 日报 2026-10-06\n\n## 李娜\n今日无记录\n\n## 王强\n今日无记录\n',
      html: '',
      collect_meta: { collect_count: 0, errors: [] },
    },
  ];

  /** 对齐现网 Flask POST /api/report 的瘦 raw 结构 */
  function buildFlaskRaw(date, member) {
    return {
      date: date || '',
      member: member || '',
      github: [
        { repo: 'demo-project', commit: '修复前端样式bug' },
        { repo: 'demo-project', commit: '完成SDD文档编写' },
      ],
      lark_msg: ['上午：需求评审会议', '下午：前后端联调测试'],
    };
  }

  function buildFlaskMarkdown(date, member) {
    return (
      '# 个人日报\n' +
      '**日期：' +
      (date || '—') +
      '**\n' +
      '**汇报人：' +
      (member || '—') +
      '**\n\n' +
      '## 今日完成\n' +
      '1. 完成SDD规范文档撰写\n' +
      '2. 前端页面开发与样式调整\n' +
      '3. 后端接口联调测试\n\n' +
      '## 遇到问题\n' +
      '- 环境依赖包缺失，逐步安装httpx、pyyaml等依赖\n' +
      '- 跨域问题，使用flask-cors解决\n\n' +
      '## 明日计划\n' +
      '1. 完善项目注释\n' +
      '2. 整理项目复现报告\n'
    );
  }

  global.PDR_MOCK = {
    TEAM_NAME,
    MEMBERS,
    REPORTS,
    buildFlaskRaw,
    buildFlaskMarkdown,
    STATUS_LABELS: {
      todo: '待办',
      in_progress: '进行中',
      doing: '进行中',
      done: '已完成',
      unknown: '未知',
    },
  };
})(typeof window !== 'undefined' ? window : globalThis);
