/* ==========================================================================
   智能日报生成器 · 应用脚本
   同时驱动 index.html（PageDailyReport）与 components.html（组件清单）
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ utils */
  const pad = (n) => String(n).padStart(2, '0');
  const keyOf = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parseKey = (s) => {
    const p = String(s).split('-').map(Number);
    return new Date(p[0], p[1] - 1, p[2]);
  };
  const dayDiff = (aKey, bKey) => Math.round((parseKey(aKey) - parseKey(bKey)) / 86400000);
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ------------------------------------------------------------------ icons */
  const svgWrap = (inner) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" ` +
    `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

  const ICON = {
    refresh: svgWrap('<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>'),
    download: svgWrap('<path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M5 21h14"/>'),
    copy: svgWrap('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2"/>'),
    calendar: svgWrap('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>'),
    chevron: svgWrap('<path d="m6 9 6 6 6-6"/>'),
    chevronLeft: svgWrap('<path d="m15 18-6-6 6-6"/>'),
    chevronRight: svgWrap('<path d="m9 18 6-6-6-6"/>'),
    check: svgWrap('<path d="M20 6 9 17l-5-5"/>'),
    close: svgWrap('<path d="M18 6 6 18M6 6l12 12"/>'),
    users: svgWrap('<path d="M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'),
    gitCommit: svgWrap('<circle cx="12" cy="12" r="4"/><path d="M2 12h6M16 12h6"/>'),
    listCheck: svgWrap('<path d="M8 6h13M8 12h13M8 18h13"/><path d="m3 6 1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2"/>'),
    message: svgWrap('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
    file: svgWrap('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/>'),
    code: svgWrap('<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>'),
    table: svgWrap('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/>'),
    inbox: svgWrap('<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'),
    alertTriangle: svgWrap('<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/>'),
    xCircle: svgWrap('<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>'),
    checkCircle: svgWrap('<circle cx="12" cy="12" r="10"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/>'),
    info: svgWrap('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>'),
    clock: svgWrap('<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'),
    spark: svgWrap('<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>'),
    searchEmpty: svgWrap('<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>')
  };

  /* -------------------------------------------------------------- mock data */
  const MEMBERS = [
    { id: 'zhangwei', name: '张伟', role: '前端' },
    { id: 'lina', name: '李娜', role: '后端' },
    { id: 'wangqiang', name: '王强', role: '测试' },
    { id: 'chenjing', name: '陈静', role: '产品' }
  ];

  const COMMITS = [
    { sha: 'a1b2c3d', repo: 'opentiny/tiny-vue', branch: 'feat/date-picker', message: 'fix(date-picker): 修复跨月切换后面板不刷新的问题', author: '张伟', time: '09:24', add: 42, del: 18 },
    { sha: '7f8e9d0', repo: 'opentiny/tiny-vue', branch: 'feat/date-picker', message: 'feat(select): 多选标签支持一键清空', author: '张伟', time: '11:02', add: 76, del: 9 },
    { sha: 'c3d4e5f', repo: 'team/refund-service', branch: 'main', message: 'perf(order): 退款查询接口合并两次数据库往返', author: '李娜', time: '10:15', add: 128, del: 64 },
    { sha: '9a0b1c2', repo: 'team/refund-service', branch: 'main', message: 'fix(payment): 修正并发场景下重复退款的幂等键', author: '李娜', time: '15:40', add: 54, del: 31 },
    { sha: 'e5f6a7b', repo: 'team/refund-service', branch: 'test/e2e', message: 'test(refund): 补充退款超时与重试的端到端用例', author: '王强', time: '14:08', add: 210, del: 12 },
    { sha: 'b7c8d9e', repo: 'team/design-system', branch: 'main', message: 'docs(tokens): 更新色彩令牌说明与对比度记录', author: '陈静', time: '16:22', add: 33, del: 5 }
  ];

  const LARK_TASKS = [
    { id: 'TASK-1042', title: '退款流程增加风控二次校验', status: '进行中', owner: '李娜', priority: '高', time: '16:41' },
    { id: 'TASK-1038', title: '日期选择器无障碍标签完善', status: '已完成', owner: '张伟', priority: '中', time: '15:12' },
    { id: 'TASK-1051', title: '退款 E2E 用例接入 CI', status: '进行中', owner: '王强', priority: '高', time: '17:03' },
    { id: 'TASK-1027', title: '日报数据源增加飞书关键词采集', status: '待处理', owner: '陈静', priority: '中', time: '11:20' },
    { id: 'TASK-1033', title: '表格虚拟滚动性能优化', status: '已完成', owner: '张伟', priority: '低', time: '10:05' }
  ];

  const LARK_MSGS = [
    { group: '日报机器人', sender: '陈静', keyword: '日报', text: '麻烦把今天的采集明细同步到日报里', time: '09:10' },
    { group: '退款服务', sender: '李娜', keyword: '退款', text: '并发幂等键已修复，CI 全绿', time: '15:42' },
    { group: '前端组', sender: '张伟', keyword: '日期选择器', text: '跨月刷新问题定位到了，是面板缓存没清', time: '09:30' },
    { group: '测试组', sender: '王强', keyword: 'E2E', text: '退款超时用例补完了，还差重试分支', time: '14:20' },
    { group: '日报机器人', sender: '系统', keyword: '采集', text: '今日采集完成，共 3 个数据源', time: '18:30' }
  ];

  function filterByMembers(list, key, members) {
    if (!members || !members.length) return list.slice();
    const names = members.map((id) => (MEMBERS.find((m) => m.id === id) || {}).name);
    return list.filter((item) => names.indexOf(item[key]) !== -1);
  }

  function buildRecords(members) {
    return {
      github: filterByMembers(COMMITS, 'author', members),
      lark_task: filterByMembers(LARK_TASKS, 'owner', members),
      lark_msg: filterByMembers(LARK_MSGS, 'sender', members)
    };
  }

  /* ----------------------------------------------------- markdown rendering */
  function inline(s) {
    let t = esc(s);
    t = t.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return t;
  }

  function renderMarkdown(src) {
    const lines = String(src || '').split('\n');
    const out = [];
    let i = 0;
    let listType = null;
    const closeList = () => { if (listType) { out.push(`</${listType}>`); listType = null; } };

    while (i < lines.length) {
      const line = lines[i];
      if (/^```/.test(line)) {
        closeList();
        const lang = line.replace(/```/, '').trim();
        const buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++;
        out.push(`<pre><code class="lang-${esc(lang)}">${esc(buf.join('\n'))}</code></pre>`);
        continue;
      }
      if (/^\s*$/.test(line)) { closeList(); i++; continue; }
      if (/^#{1,6}\s/.test(line)) {
        closeList();
        const m = /^(#{1,6})\s+(.*)$/.exec(line);
        out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`);
        i++; continue;
      }
      if (/^>\s?/.test(line)) {
        closeList();
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, '')); i++; }
        out.push(`<blockquote>${inline(buf.join(' '))}</blockquote>`);
        continue;
      }
      if (/^(-{3,}|\*{3,})\s*$/.test(line.trim())) { closeList(); out.push('<hr>'); i++; continue; }
      if (/^[-*]\s+/.test(line)) {
        if (listType !== 'ul') { closeList(); out.push('<ul>'); listType = 'ul'; }
        out.push(`<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`);
        i++; continue;
      }
      if (/^\d+\.\s+/.test(line)) {
        if (listType !== 'ol') { closeList(); out.push('<ol>'); listType = 'ol'; }
        out.push(`<li>${inline(line.replace(/^\d+\.\s+/, ''))}</li>`);
        i++; continue;
      }
      closeList();
      const buf = [line];
      i++;
      while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,6}\s|>|```|[-*]\s|\d+\.\s)/.test(lines[i])) {
        buf.push(lines[i]); i++;
      }
      out.push(`<p>${inline(buf.join(' '))}</p>`);
    }
    closeList();
    return out.join('\n');
  }

  /* --------------------------------------------------------- report builder */
  function countStatus(list, status) {
    return list.filter((t) => t.status === status).length;
  }

  function buildMarkdown(dateKey, rec, errors) {
    const out = [];
    const membersCount = new Set(
      rec.github.map((c) => c.author).concat(rec.lark_task.map((t) => t.owner))
    ).size;

    out.push(`# 智能日报 · ${dateKey}`);
    out.push('');
    out.push(`> 采集时间 18:30 · 覆盖成员 ${membersCount} 人 · 数据源：GitHub / 飞书任务 / 飞书消息`);
    out.push('');
    if (errors.length) {
      out.push(`> 注意：${errors.length} 个数据源获取失败（${errors.map((e) => e.source).join('、')}），本报告为降级版本。`);
      out.push('');
    }
    out.push('## 一、今日概览');
    out.push('');
    out.push(`- 代码提交 **${rec.github.length}** 次，覆盖 ${new Set(rec.github.map((c) => c.repo)).size} 个仓库`);
    out.push(
      `- 任务变更 **${rec.lark_task.length}** 项（完成 ${countStatus(rec.lark_task, '已完成')} · 进行中 ${countStatus(rec.lark_task, '进行中')} · 待处理 ${countStatus(rec.lark_task, '待处理')}）`
    );
    out.push(`- 关键词命中消息 **${rec.lark_msg.length}** 条`);
    out.push('');

    out.push('## 二、代码提交（GitHub）');
    out.push('');
    if (!rec.github.length) {
      out.push('- 无提交记录');
      out.push('');
    } else {
      const byRepo = {};
      rec.github.forEach((c) => { (byRepo[c.repo] = byRepo[c.repo] || []).push(c); });
      Object.keys(byRepo).forEach((repo) => {
        out.push(`### ${repo}`);
        out.push('');
        byRepo[repo].forEach((c) => {
          out.push(`- \`${c.sha}\` ${c.message} — ${c.author}（${c.time}，+${c.add}/-${c.del}）`);
        });
        out.push('');
      });
    }

    out.push('## 三、任务进展（飞书任务）');
    out.push('');
    if (!rec.lark_task.length) {
      out.push('- 无任务变更');
      out.push('');
    } else {
      rec.lark_task.forEach((t) => {
        out.push(`- **${t.title}** — ${t.status} · 负责人 ${t.owner} · 优先级 ${t.priority} · ${t.time}`);
      });
      out.push('');
    }

    out.push('## 四、关键词消息（飞书）');
    out.push('');
    if (!rec.lark_msg.length) {
      out.push(errors.some((e) => e.source === 'lark_msg') ? '- 数据源获取失败，暂无消息' : '- 无关键词命中消息');
      out.push('');
    } else {
      rec.lark_msg.forEach((m) => {
        out.push(`- 群「${m.group}」**${m.sender}**：${m.text}（关键词：${m.keyword} · ${m.time}）`);
      });
      out.push('');
    }
    return out.join('\n').trim();
  }

  /* ----------------------------------------------------------- mock backend */
  function resolveScenario(dateKey) {
    const today = keyOf(new Date());
    if (dateKey > today) return 'error';
    if (dateKey === today) return 'normal';
    const diff = dayDiff(today, dateKey);
    if (diff <= 3) return 'degraded';
    return 'empty';
  }

  function countRecords(rec) {
    return rec.github.length + rec.lark_task.length + rec.lark_msg.length;
  }

  async function fetchReport(params) {
    await delay(700 + Math.round(Math.random() * 350));
    const scenario = resolveScenario(params.date);

    if (scenario === 'error') {
      const err = new Error('请求失败');
      err.status = 500;
      err.scenario = 'error';
      throw err;
    }

    if (scenario === 'empty') {
      return {
        code: 0,
        data: {
          raw_records: { github: [], lark_task: [], lark_msg: [] },
          report_markdown: '',
          report_html: '',
          meta: { collect_count: 0, errors: [] }
        }
      };
    }

    const rec = buildRecords(params.members);
    const errors =
      scenario === 'degraded'
        ? [{ source: 'lark_msg', message: '飞书消息接口响应超时（>5000ms）' }]
        : [];
    if (scenario === 'degraded') rec.lark_msg = [];

    const md = buildMarkdown(params.date, rec, errors);
    return {
      code: 0,
      data: {
        raw_records: rec,
        report_markdown: md,
        report_html: renderMarkdown(md),
        meta: { collect_count: countRecords(rec), errors }
      }
    };
  }

  /* ------------------------------------------------------------------ toast */
  function toast(message, type) {
    const host = $('#toastHost');
    if (!host) return;
    const el = document.createElement('div');
    el.className = `toast toast--${type || 'success'}`;
    el.setAttribute('role', 'status');
    el.innerHTML = `${type === 'info' ? ICON.info : ICON.checkCircle}<span>${esc(message)}</span>`;
    host.appendChild(el);
    setTimeout(() => {
      el.style.transition = 'opacity var(--tv-duration-base) var(--tv-ease-out)';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 220);
    }, 2200);
  }

  /* ======================================================= date picker ===== */
  function createDatePicker(root, options) {
    let selected = options.value;
    let view = parseKey(selected);
    let open = false;

    root.innerHTML =
      '<div class="select">' +
      '<div class="select__control" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false" aria-label="选择日期">' +
      '<span class="select__top"><span style="display:flex;color:var(--tv-color-icon)">' + ICON.calendar + '</span>' +
      '<span class="select__value"><span data-label class="mono"></span></span></span>' +
      '<span class="select__chevron">' + ICON.chevron + '</span>' +
      '</div>' +
      '<div class="popover" role="dialog" aria-label="日期选择" hidden></div>' +
      '</div>';

    const control = $('.select__control', root);
    const pop = $('.popover', root);
    const label = $('[data-label]', root);

    function calendarHtml() {
      const y = view.getFullYear();
      const m = view.getMonth();
      const startDow = new Date(y, m, 1).getDay();
      const daysInMonth = new Date(y, m + 1, 0).getDate();
      const prevDays = new Date(y, m, 0).getDate();
      const todayKey = keyOf(new Date());
      const dow = ['日', '一', '二', '三', '四', '五', '六'];
      const cells = [];
      for (let i = startDow - 1; i >= 0; i--) cells.push({ day: prevDays - i, muted: true, date: new Date(y, m - 1, prevDays - i) });
      for (let d = 1; d <= daysInMonth; d++) cells.push({ day: d, muted: false, date: new Date(y, m, d) });
      let tail = 1;
      while (cells.length % 7 !== 0) { cells.push({ day: tail, muted: true, date: new Date(y, m + 1, tail) }); tail++; }

      let html = '<div class="calendar">';
      html +=
        '<div class="calendar__head">' +
        '<button type="button" class="calendar__nav" data-nav="-1" aria-label="上一个月">' + ICON.chevronLeft + '</button>' +
        '<span class="calendar__title">' + y + ' 年 ' + (m + 1) + ' 月</span>' +
        '<button type="button" class="calendar__nav" data-nav="1" aria-label="下一个月">' + ICON.chevronRight + '</button>' +
        '</div>';
      html += '<div class="calendar__grid">';
      dow.forEach((d) => { html += '<span class="calendar__dow">' + d + '</span>'; });
      cells.forEach((c) => {
        const k = keyOf(c.date);
        const cls = ['calendar__day'];
        if (c.muted) cls.push('calendar__day--muted');
        if (k === todayKey) cls.push('calendar__day--today');
        html +=
          '<button type="button" class="' + cls.join(' ') + '" data-date="' + k + '" aria-selected="' +
          (k === selected) + '">' + c.day + '</button>';
      });
      html += '</div></div>';
      return html;
    }

    function paint() {
      label.textContent = selected;
      pop.innerHTML = calendarHtml();
    }

    function toggle(next) {
      open = typeof next === 'boolean' ? next : !open;
      pop.hidden = !open;
      control.setAttribute('aria-expanded', String(open));
      if (open) {
        view = parseKey(selected);
        paint();
        const sel = $('.calendar__day[aria-selected="true"]:not(.calendar__day--muted)', pop);
        if (sel) sel.focus();
      }
    }

    control.addEventListener('click', () => toggle());
    control.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') { e.preventDefault(); toggle(true); }
    });
    pop.addEventListener('click', (e) => {
      const nav = e.target.closest('[data-nav]');
      if (nav) {
        view = new Date(view.getFullYear(), view.getMonth() + Number(nav.dataset.nav), 1);
        paint();
        return;
      }
      const day = e.target.closest('[data-date]');
      if (day) {
        selected = day.dataset.date;
        paint();
        toggle(false);
        control.focus();
        options.onChange(selected);
      }
    });
    pop.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { toggle(false); control.focus(); }
    });
    document.addEventListener('click', (e) => { if (open && !root.contains(e.target)) toggle(false); });

    paint();
    return { get value() { return selected; }, set value(v) { selected = v; paint(); } };
  }

  /* ====================================================== multi select ===== */
  function createMultiSelect(root, options) {
    let selected = options.value.slice();
    let open = false;

    root.innerHTML =
      '<div class="select">' +
      '<div class="select__control" role="button" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-label="选择团队成员">' +
      '<span class="select__top"><span class="select__value" data-value></span></span>' +
      '<span class="select__chevron">' + ICON.chevron + '</span>' +
      '</div>' +
      '<div class="popover" role="listbox" aria-multiselectable="true" aria-label="团队成员" hidden></div>' +
      '</div>';

    const control = $('.select__control', root);
    const pop = $('.popover', root);
    const valueBox = $('[data-value]', root);

    function paintValue() {
      if (!selected.length) {
        valueBox.innerHTML = '<span class="select__placeholder">全部成员</span>';
        return;
      }
      valueBox.innerHTML = selected
        .map((id) => {
          const m = MEMBERS.find((x) => x.id === id);
          if (!m) return '';
          return (
            '<span class="tag"><span class="tag__avatar">' + esc(m.name[0]) + '</span>' +
            '<span class="tag__text">' + esc(m.name) + '</span>' +
            '<button type="button" class="tag__remove" data-remove="' + id + '" aria-label="移除 ' + esc(m.name) + '">' +
            ICON.close.replace('<svg ', '<svg width="10" height="10" ') + '</button></span>'
          );
        })
        .join('');
    }

    function paintPop() {
      const allChecked = selected.length === MEMBERS.length;
      pop.innerHTML =
        '<div class="options">' +
        '<div class="options__all"><span>已选 ' + selected.length + ' / ' + MEMBERS.length + '</span>' +
        '<button type="button" class="btn btn--text btn--sm" data-all>' + (allChecked ? '清空' : '全选') + '</button></div>' +
        MEMBERS.map((m) => {
          const checked = selected.indexOf(m.id) !== -1;
          return (
            '<div class="check" role="option" tabindex="0" data-id="' + m.id + '" aria-checked="' + checked + '">' +
            '<span class="check__box">' + ICON.check + '</span>' +
            '<span class="check__avatar">' + esc(m.name[0]) + '</span>' +
            '<span class="od-stack" style="gap:0"><span class="check__name">' + esc(m.name) + '</span>' +
            '<span class="check__role">' + esc(m.role) + '</span></span>' +
            '</div>'
          );
        }).join('') +
        '</div>';
    }

    function toggle(next) {
      open = typeof next === 'boolean' ? next : !open;
      pop.hidden = !open;
      control.setAttribute('aria-expanded', String(open));
      if (open) paintPop();
    }

    function commit() {
      paintValue();
      options.onChange(selected.slice());
    }

    control.addEventListener('click', (e) => {
      if (e.target.closest('[data-remove]')) return;
      toggle();
    });
    control.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') { e.preventDefault(); toggle(true); }
    });
    control.addEventListener('click', (e) => {
      const rm = e.target.closest('[data-remove]');
      if (rm) {
        e.stopPropagation();
        selected = selected.filter((id) => id !== rm.dataset.remove);
        commit();
      }
    });
    pop.addEventListener('click', (e) => {
      if (e.target.closest('[data-all]')) {
        selected = selected.length === MEMBERS.length ? [] : MEMBERS.map((m) => m.id);
        paintPop(); commit();
        return;
      }
      const item = e.target.closest('.check');
      if (item) {
        const id = item.dataset.id;
        selected = selected.indexOf(id) === -1 ? selected.concat(id) : selected.filter((x) => x !== id);
        paintPop(); commit();
      }
    });
    pop.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { toggle(false); control.focus(); }
      if (e.key === 'Enter' && e.target.classList.contains('check')) {
        e.preventDefault();
        e.target.click();
      }
    });
    document.addEventListener('click', (e) => { if (open && !root.contains(e.target)) toggle(false); });

    paintValue();
    return { get value() { return selected.slice(); } };
  }

  /* ================================================= shared state markup === */
  function stateBlock(type, opts) {
    const o = opts || {};
    if (type === 'error') {
      return (
        '<div class="state state--error">' +
        '<div class="state__art">' + ICON.xCircle + '</div>' +
        '<div class="state__title">数据加载失败，请重试</div>' +
        '<p class="state__desc">' + esc(o.desc || '请求超时或服务返回 500，已保留当前筛选条件，点击下方按钮重新拉取。') + '</p>' +
        '<div class="state__actions"><button type="button" class="btn btn--primary" data-retry>' + ICON.refresh + '重新加载</button></div>' +
        '</div>'
      );
    }
    if (type === 'empty') {
      return (
        '<div class="state">' +
        '<div class="state__art">' + ICON.inbox + '</div>' +
        '<div class="state__title">' + esc(o.title || '今日无记录') + '</div>' +
        '<p class="state__desc">' + esc(o.desc || '所选日期与成员范围内没有任何采集记录，调整筛选条件后会自动重新获取。') + '</p>' +
        '</div>'
      );
    }
    return '';
  }

  function badgeClassStatus(status) {
    return ({ '待处理': 'todo', '进行中': 'doing', '已完成': 'done' })[status] || 'todo';
  }
  function badgeClassPriority(p) {
    return ({ '高': 'high', '中': 'mid', '低': 'low' })[p] || 'low';
  }

  function tableFor(tab, rows) {
    if (tab === 'github') {
      return (
        '<div class="table-wrap"><table class="od-table"><thead><tr>' +
        '<th style="width:46%">提交内容</th><th>仓库 / 分支</th><th>成员</th><th>时间</th>' +
        '</tr></thead><tbody>' +
        rows.map((c) =>
          '<tr><td><div class="cell-primary">' +
          '<span class="cell-primary__main od-clamp-2">' + esc(c.message) + '</span>' +
          '<span class="cell-sub"><span class="sha">' + esc(c.sha) + '</span> +' + c.add + ' / -' + c.del + '</span>' +
          '</div></td>' +
          '<td><span class="repo">' + ICON.gitCommit + esc(c.repo) + '</span>' +
          '<div class="cell-sub">' + esc(c.branch) + '</div></td>' +
          '<td><span class="person"><span class="person__avatar">' + esc(c.author[0]) + '</span>' + esc(c.author) + '</span></td>' +
          '<td class="cell-sub mono od-nowrap">' + esc(c.time) + '</td></tr>'
        ).join('') +
        '</tbody></table></div>'
      );
    }
    if (tab === 'lark_task') {
      return (
        '<div class="table-wrap"><table class="od-table"><thead><tr>' +
        '<th style="width:40%">任务</th><th>状态</th><th>负责人</th><th>优先级</th><th>更新</th>' +
        '</tr></thead><tbody>' +
        rows.map((t) =>
          '<tr><td><div class="cell-primary">' +
          '<span class="cell-primary__main od-clamp-2">' + esc(t.title) + '</span>' +
          '<span class="cell-sub mono">' + esc(t.id) + '</span>' +
          '</div></td>' +
          '<td><span class="status status--' + badgeClassStatus(t.status) + '"><span class="status__dot"></span>' + esc(t.status) + '</span></td>' +
          '<td><span class="person"><span class="person__avatar">' + esc(t.owner[0]) + '</span>' + esc(t.owner) + '</span></td>' +
          '<td><span class="status status--' + badgeClassPriority(t.priority) + '">' + esc(t.priority) + '</span></td>' +
          '<td class="cell-sub mono od-nowrap">' + esc(t.time) + '</td></tr>'
        ).join('') +
        '</tbody></table></div>'
      );
    }
    return (
      '<div class="table-wrap"><table class="od-table"><thead><tr>' +
      '<th style="width:50%">消息</th><th>关键词</th><th>发送人</th><th>时间</th>' +
      '</tr></thead><tbody>' +
      rows.map((m) =>
        '<tr><td><div class="cell-primary">' +
        '<span class="cell-primary__main od-clamp-2">' + esc(m.text) + '</span>' +
        '<span class="cell-sub">群「' + esc(m.group) + '」</span>' +
        '</div></td>' +
        '<td><span class="kw">' + esc(m.keyword) + '</span></td>' +
        '<td><span class="person"><span class="person__avatar">' + esc(m.sender[0]) + '</span>' + esc(m.sender) + '</span></td>' +
        '<td class="cell-sub mono od-nowrap">' + esc(m.time) + '</td></tr>'
      ).join('') +
      '</tbody></table></div>'
    );
  }

  /* ======================================================= index page ===== */
  function initReportPage() {
    const state = {
      date: keyOf(new Date()),
      members: [],
      loading: false,
      error: null,
      data: null,
      tab: 'github',
      mode: 'markdown'
    };

    const rawPane = $('#rawPane');
    const previewPane = $('#previewPane');

    rawPane.innerHTML =
      '<div class="pane__head">' +
      '<div class="pane__title">' + ICON.table + '<span>原始数据区</span></div>' +
      '<div class="tabs" role="tablist" aria-label="原始数据来源">' +
      '<button class="tab" role="tab" data-tab="github" aria-selected="true">GitHub 提交<span class="tab__badge" data-badge="github">0</span></button>' +
      '<button class="tab" role="tab" data-tab="lark_task" aria-selected="false">飞书任务<span class="tab__badge" data-badge="lark_task">0</span></button>' +
      '<button class="tab" role="tab" data-tab="lark_msg" aria-selected="false">飞书消息<span class="tab__badge" data-badge="lark_msg">0</span></button>' +
      '</div>' +
      '</div>' +
      '<div class="pane__body" id="rawBody" role="tabpanel" aria-label="原始数据表格"></div>';

    previewPane.innerHTML =
      '<div class="pane__head">' +
      '<div class="pane__title">' + ICON.file + '<span>日报成品预览</span></div>' +
      '<div class="pane__spacer"></div>' +
      '<div class="segmented" role="group" aria-label="渲染模式">' +
      '<button type="button" data-mode="markdown" aria-pressed="true">' + ICON.file + 'Markdown</button>' +
      '<button type="button" data-mode="html" aria-pressed="false">' + ICON.code + 'HTML</button>' +
      '</div>' +
      '</div>' +
      '<div class="pane__body pane__body--pad" id="previewBody" aria-label="日报预览"></div>';

    const rawBody = $('#rawBody');
    const previewBody = $('#previewBody');

    createDatePicker($('#dateMount'), { value: state.date, onChange: (v) => { state.date = v; load(); } });
    createMultiSelect($('#memberMount'), { value: state.members, onChange: (v) => { state.members = v; load(); } });

    /* tabs */
    $$('.tab', rawPane).forEach((tab) => {
      tab.addEventListener('click', () => {
        state.tab = tab.dataset.tab;
        $$('.tab', rawPane).forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
        renderRaw();
      });
    });

    /* render mode */
    $$('.segmented button', previewPane).forEach((btn) => {
      btn.addEventListener('click', () => {
        state.mode = btn.dataset.mode;
        $$('.segmented button', previewPane).forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
        renderPreview();
      });
    });

    /* topbar actions */
    $('#btnRefresh').addEventListener('click', () => load());
    $('#btnCopy').addEventListener('click', copyMarkdown);
    $('#btnExport').addEventListener('click', exportHtml);

    function setBusy(busy) {
      [rawBody, previewBody].forEach((el) => {
        const existing = $('.loading-mask', el);
        if (busy && !existing) {
          const mask = document.createElement('div');
          mask.className = 'loading-mask';
          mask.innerHTML = '<div class="loading-box"><span class="spinner" role="progressbar" aria-label="加载中"></span><span>正在加载日报数据…</span></div>';
          el.appendChild(mask);
        } else if (!busy && existing) {
          existing.remove();
        }
      });
      $('#btnRefresh').classList.toggle('btn--loading', busy);
      $('#btnRefresh').disabled = busy;
    }

    function renderBanners() {
      const host = $('#banners');
      const errors = (state.data && state.data.meta.errors) || [];
      if (!errors.length) { host.innerHTML = ''; host.hidden = true; return; }
      host.hidden = false;
      host.innerHTML =
        '<div class="alert alert--warning" role="alert">' +
        '<span class="alert__icon">' + ICON.alertTriangle + '</span>' +
        '<div class="alert__body"><div class="alert__title">部分数据源获取失败</div>' +
        '<div class="alert__desc">' + errors.map((e) => esc(e.source) + '：' + esc(e.message)).join('；') +
        '。其余数据已正常展示，可点击刷新重试。</div></div>' +
        '<button type="button" class="alert__close" aria-label="关闭提示">' + ICON.close + '</button>' +
        '</div>';
      $('.alert__close', host).addEventListener('click', () => { host.hidden = true; host.innerHTML = ''; });
    }

    function renderMeta() {
      const meta = $('#collectMeta');
      if (state.error) { meta.textContent = '采集状态：加载失败'; return; }
      if (!state.data) { meta.textContent = '采集状态：—'; return; }
      meta.textContent = `采集明细 ${state.data.meta.collect_count} 条 · 数据源 ${state.data.meta.errors.length ? '部分失败' : '正常'}`;
    }

    function renderBadges() {
      const rec = state.data ? state.data.raw_records : { github: [], lark_task: [], lark_msg: [] };
      ['github', 'lark_task', 'lark_msg'].forEach((k) => {
        const el = $('[data-badge="' + k + '"]', rawPane);
        if (el) el.textContent = rec[k].length;
      });
    }

    function renderRaw() {
      if (state.error) { rawBody.innerHTML = stateBlock('error'); wireRetry(rawBody); return; }
      if (!state.data) { rawBody.innerHTML = ''; return; }
      const rows = state.data.raw_records[state.tab] || [];
      if (!rows.length) { rawBody.innerHTML = stateBlock('empty', { title: '本数据源无记录', desc: '当前日期与成员范围内该数据源没有采集到记录。' }); return; }
      rawBody.innerHTML = tableFor(state.tab, rows);
    }

    function renderPreview() {
      if (state.error) { previewBody.innerHTML = stateBlock('error'); wireRetry(previewBody); return; }
      if (!state.data) { previewBody.innerHTML = ''; return; }
      if (!state.data.report_markdown) { previewBody.innerHTML = stateBlock('empty'); return; }
      const doc = state.mode === 'html' ? state.data.report_html : renderMarkdown(state.data.report_markdown);
      previewBody.innerHTML = '<div class="markdown">' + doc + '</div>';
    }

    function wireRetry(scope) {
      const btn = $('[data-retry]', scope);
      if (btn) btn.addEventListener('click', () => load());
    }

    async function load() {
      state.loading = true;
      state.error = null;
      setBusy(true);
      try {
        const res = await fetchReport({ date: state.date, members: state.members });
        state.data = res.data;
      } catch (e) {
        state.error = e;
        state.data = null;
      } finally {
        state.loading = false;
        setBusy(false);
        renderBanners();
        renderBadges();
        renderMeta();
        renderRaw();
        renderPreview();
      }
    }

    async function copyMarkdown() {
      if (!state.data || !state.data.report_markdown) { toast('暂无可复制的日报内容', 'info'); return; }
      const text = state.data.report_markdown;
      try {
        await navigator.clipboard.writeText(text);
        toast('已复制 Markdown 到剪贴板');
      } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); toast('已复制 Markdown 到剪贴板'); }
        catch (e2) { toast('复制失败，请手动选择内容', 'info'); }
        ta.remove();
      }
    }

    function exportHtml() {
      if (!state.data || !state.data.report_html) { toast('暂无可导出的日报', 'info'); return; }
      const css =
        'body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:#191919;line-height:1.6;max-width:820px;margin:40px auto;padding:0 24px}' +
        'h1{font-size:22px;border-bottom:1px solid #e6e6e6;padding-bottom:12px}h2{font-size:18px;margin-top:24px}' +
        'h3{font-size:16px;margin-top:16px}blockquote{border-left:3px solid #b3d6ff;background:#f0f7ff;margin:12px 0;padding:8px 16px;color:#595959}' +
        'code{background:#f5f5f5;border:1px solid #f0f0f0;border-radius:2px;padding:1px 5px;font-size:.86em}';
      const doc =
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>智能日报 ' + state.date +
        '</title><style>' + css + '</style></head><body>' + state.data.report_html + '</body></html>';
      const blob = new Blob([doc], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = '日报-' + state.date + '.html';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast('已导出 HTML 日报');
    }

    load();
  }

  /* =================================================== components page ===== */
  function initComponentsPage() {
    createDatePicker($('#demoDate'), { value: keyOf(new Date()), onChange: function () {} });
    createMultiSelect($('#demoSelect'), { value: ['zhangwei', 'lina'], onChange: function () {} });

    $$('[data-toast]').forEach((btn) => {
      btn.addEventListener('click', () => toast(btn.dataset.toast, btn.dataset.toastType || 'success'));
    });
    $$('.alert__close').forEach((btn) => {
      btn.addEventListener('click', () => { const a = btn.closest('.alert'); if (a) a.remove(); });
    });
    $$('[data-retry]').forEach((btn) => {
      btn.addEventListener('click', () => toast('演示：已重新发起数据请求', 'info'));
    });
  }

  /* -------------------------------------------------------------- bootstrap */
  function boot() {
    if (document.body.dataset.page === 'report') initReportPage();
    else if (document.body.dataset.page === 'components') initComponentsPage();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
