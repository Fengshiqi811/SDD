/**
 * prototype.js
 * 共享壳层、假 API、列表/详情/生成页交互。
 * 注释中的字段名对齐后端 DTO；联调时可把 api.* 换成真实 fetch。
 */
(function (global) {
  'use strict';

  const MOCK = global.PDR_MOCK;
  if (!MOCK) {
    console.error('[PDR] mock-data.js 未加载');
    return;
  }

  const STORAGE_KEY = 'pdr.prototype.reports.v2';
  const PAGE_SIZE = 10;
  const GIT_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="6" cy="18" r="2"/><path d="M6 8v8M8 18h8M8 6h5a3 3 0 0 1 3 3v5"/></svg>';

  /* ---------- utils ---------- */
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $$(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return (
      d.getFullYear() +
      '-' +
      pad(d.getMonth() + 1) +
      '-' +
      pad(d.getDate()) +
      ' ' +
      pad(d.getHours()) +
      ':' +
      pad(d.getMinutes())
    );
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    return String(iso).slice(0, 10);
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(11, 16) || '—';
    const pad = (n) => String(n).padStart(2, '0');
    return pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function dash(v) {
    if (v === null || v === undefined || v === '') return '—';
    return v;
  }

  function statusLabel(code) {
    return MOCK.STATUS_LABELS[code] || code || '—';
  }

  function statusClass(code) {
    if (code === 'done') return 'done';
    if (code === 'in_progress' || code === 'doing') return 'doing';
    return 'todo';
  }

  function avatarClass(name) {
    const n = (name || '').charCodeAt(0) || 0;
    return ['a', 'b', 'c', 'd'][n % 4];
  }

  function shortSha(c) {
    if (c.sha) return c.sha;
    const s = String(c.message || c.author || 'x');
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h.toString(16).slice(0, 7);
  }

  function displayNameOf(row, fallbackKey) {
    if (row.display_name) return row.display_name;
    const key = row[fallbackKey] || row.author || row.assignee || row.sender || '';
    const hit = MOCK.MEMBERS.find(
      (m) => m.github === key || m.lark === key || m.name === key
    );
    return hit ? hit.name : key || '—';
  }

  /** 从日报扁平化三源数据（优先 raw_records） */
  function collectRawRecords(report) {
    if (report.raw_records) {
      return {
        github: report.raw_records.github,
        lark_task: report.raw_records.lark_task,
        lark_msg: report.raw_records.lark_msg,
      };
    }
    const github = [];
    const lark_task = [];
    const lark_msg = [];
    let taskFailed = false;
    let msgFailed = false;
    let ghFailed = false;
    (report.members || []).forEach((m) => {
      if (m.commits === null) ghFailed = true;
      else if (m.commits) github.push(...m.commits);
      if (m.tasks === null) taskFailed = true;
      else if (m.tasks) lark_task.push(...m.tasks);
      if (m.messages === null) msgFailed = true;
      else if (m.messages) lark_msg.push(...m.messages);
    });
    return {
      github: ghFailed && !github.length ? null : github,
      lark_task: taskFailed && !lark_task.length ? null : lark_task,
      lark_msg: msgFailed && !lark_msg.length ? null : lark_msg,
    };
  }

  function summaryFromMarkdown(md) {
    if (!md) return '—';
    const line = md
      .split('\n')
      .map((s) => s.trim())
      .find((s) => s && !s.startsWith('#'));
    return line ? line.replace(/\*\*/g, '').slice(0, 48) : '—';
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /** 极简 Markdown → HTML（原型够用；工程可换 marked） */
  function renderMarkdown(md) {
    if (!md) return '';
    let html = escapeHtml(md);
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(?:<li>.*<\/li>\n?)+/g, (block) => '<ul>' + block + '</ul>');
    html = html.replace(/^(?!<[hul]|<li)(.+)$/gm, (line) => {
      if (!line.trim()) return '';
      if (line.startsWith('<')) return line;
      return '<p>' + line + '</p>';
    });
    return html;
  }

  function qs(name) {
    return new URLSearchParams(location.search).get(name);
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  /* ---------- persistence (simulates ReportStorage) ---------- */
  function loadReports() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    const seed = JSON.parse(JSON.stringify(MOCK.REPORTS));
    saveReports(seed);
    return seed;
  }

  function saveReports(list) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  }

  /* ---------- toast / modal ---------- */
  function ensureToastHost() {
    let host = $('#toastHost');
    if (!host) {
      host = document.createElement('div');
      host.id = 'toastHost';
      host.className = 'toast-host';
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(msg) {
    const host = ensureToastHost();
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.remove(), 2200);
  }

  function confirmModal({ title, desc, confirmText, danger }) {
    return new Promise((resolve) => {
      let root = $('#modalRoot');
      if (!root) {
        root = document.createElement('div');
        root.id = 'modalRoot';
        root.className = 'modal-root';
        root.hidden = true;
        document.body.appendChild(root);
      }
      root.innerHTML =
        '<div class="modal" role="dialog" aria-modal="true">' +
        '<div class="modal__title"></div>' +
        '<div class="modal__desc"></div>' +
        '<div class="modal__actions">' +
        '<button type="button" class="btn btn--default" data-act="cancel">取消</button>' +
        '<button type="button" class="btn" data-act="ok"></button>' +
        '</div></div>';
      $('.modal__title', root).textContent = title;
      $('.modal__desc', root).textContent = desc;
      const ok = $('[data-act="ok"]', root);
      ok.textContent = confirmText || '确认';
      ok.className = 'btn ' + (danger ? 'btn--danger' : 'btn--primary');
      root.hidden = false;
      const close = (val) => {
        root.hidden = true;
        resolve(val);
      };
      $('[data-act="cancel"]', root).onclick = () => close(false);
      ok.onclick = () => close(true);
      root.onclick = (e) => {
        if (e.target === root) close(false);
      };
    });
  }

  /* ---------- fake API (maps to backend; gaps noted) ---------- */
  const api = {
    /**
     * 模拟 ReportStorage.list_reports(limit)
     * 缺口：无 date/team 服务端筛选、无 page/offset/total
     */
    async listReports({ date, team, page, pageSize, simulate } = {}) {
      await sleep(simulate === 'error' ? 400 : 500);
      if (simulate === 'error') {
        const err = new Error('数据加载失败，请重试');
        err.status = 500;
        throw err;
      }
      if (simulate === 'empty') return { items: [], total: 0, page: 1, pageSize: pageSize || PAGE_SIZE };

      let items = loadReports();
      if (date) items = items.filter((r) => r.report_date === date);
      if (team) items = items.filter((r) => r.team_name.includes(team));
      items = items.slice().sort((a, b) => (a.report_date < b.report_date ? 1 : -1));
      const total = items.length;
      const ps = pageSize || PAGE_SIZE;
      const p = Math.max(1, page || 1);
      const start = (p - 1) * ps;
      return { items: items.slice(start, start + ps), total, page: p, pageSize: ps };
    },

    /** 模拟 get_report(date, team_name) — HTTP 需后端新增 */
    async getReport(date, teamName) {
      await sleep(350);
      const items = loadReports();
      const hit = items.find(
        (r) => r.report_date === date && (!teamName || r.team_name === teamName)
      );
      if (!hit) {
        const err = new Error('未找到该日报');
        err.status = 404;
        throw err;
      }
      return hit;
    },

    /**
     * 对齐现网 POST /api/report
     * body: { date, member } → { code, raw, data }
     * USE_LIVE=1 时尝试真实后端（需 Flask 已启动）
     */
    async generateReport({ date, member, useLive }) {
      if (useLive) {
        try {
          const res = await fetch('http://127.0.0.1:5000/api/report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, member: member || '' }),
          });
          if (!res.ok) {
            const err = new Error('数据加载失败，请重试');
            err.status = res.status;
            throw err;
          }
          return await res.json();
        } catch (e) {
          if (e.status) throw e;
          const err = new Error(e.message || '无法连接后端，请确认服务已启动');
          err.status = 0;
          throw err;
        }
      }

      await sleep(700);
      const raw = MOCK.buildFlaskRaw(date, member);
      const data = MOCK.buildFlaskMarkdown(date, member);
      // 同时写入本地历史，模拟 save_report upsert
      const list = loadReports();
      const existing = list.find((r) => r.report_date === date && r.team_name === MOCK.TEAM_NAME);
      const record = {
        id: existing ? existing.id : Math.max(0, ...list.map((x) => x.id)) + 1,
        report_date: date,
        team_name: MOCK.TEAM_NAME,
        generated_at: new Date().toISOString(),
        members: [
          {
            name: member || '未指定成员',
            github_username: '—',
            commits: raw.github.map((g) => ({
              author: member || 'unknown',
              message: g.commit,
              timestamp: date + 'T12:00:00+08:00',
              repo: g.repo,
              additions: 0,
              deletions: 0,
              files_changed: 0,
            })),
            tasks: [],
            messages: raw.lark_msg.map((c) => ({
              sender: member || '—',
              content: c,
              timestamp: date + 'T12:00:00+08:00',
              chat_name: '研发日报群',
            })),
          },
        ],
        markdown: data,
        html: '',
        collect_meta: { collect_count: raw.github.length + raw.lark_msg.length, errors: [] },
        _flask_raw: raw,
        raw_records: {
          github: raw.github.map((g) => ({
            author: member || 'unknown',
            display_name: member || '—',
            message: g.commit,
            timestamp: date + 'T12:00:00+08:00',
            repo: g.repo,
            branch: 'main',
            sha: shortSha({ message: g.commit }),
            additions: 0,
            deletions: 0,
            files_changed: 0,
          })),
          lark_task: [],
          lark_msg: raw.lark_msg.map((c) => ({
            sender: member || '—',
            display_name: member || '—',
            content: c,
            timestamp: date + 'T12:00:00+08:00',
            chat_name: '研发日报群',
            keyword: '进度',
          })),
        },
      };
      if (existing) {
        const idx = list.indexOf(existing);
        list[idx] = record;
      } else {
        list.unshift(record);
      }
      saveReports(list);
      return { code: 0, raw, data };
    },

    /** 删除 — 需后端新增 DELETE；原型本地删 */
    async deleteReport(id) {
      await sleep(300);
      const list = loadReports().filter((r) => r.id !== id);
      saveReports(list);
      return { ok: true };
    },
  };

  /* ---------- shell ---------- */
  function mountShell({ current }) {
    const mount = $('#appShell');
    if (!mount) return;
    mount.innerHTML =
      '<header class="topbar">' +
      '<a class="brand" href="index.html">' +
      '<span class="brand__mark" aria-hidden="true">' +
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>' +
      '</span>' +
      '<span><span class="brand__title">智能日报生成器</span>' +
      '<span class="brand__sub">PageDailyReport · 列表 · 详情 · 生成</span></span>' +
      '</a>' +
      '<nav class="nav" aria-label="主导航">' +
      navLink('report-list.html', '日报列表', current) +
      navLink('report-detail.html', '日报详情', current) +
      navLink('report-generate.html', '生成日报', current) +
      '</nav>' +
      '<span class="topbar__spacer"></span>' +
      '<a class="btn btn--primary" href="report-generate.html">生成日报</a>' +
      '</header>';
  }

  function navLink(href, label, current) {
    const cur = current === href ? ' aria-current="page"' : '';
    return '<a href="' + href + '"' + cur + '>' + label + '</a>';
  }

  /* ---------- pages ---------- */
  async function initListPage() {
    mountShell({ current: 'report-list.html' });
    const tbody = $('#reportTbody');
    const empty = $('#emptyState');
    const loading = $('#loadingState');
    const errorBox = $('#errorBox');
    const tablePanel = $('#tablePanel');
    const pagerInfo = $('#pagerInfo');
    const btnPrev = $('#btnPrev');
    const btnNext = $('#btnNext');
    const filterDate = $('#filterDate');
    const filterTeam = $('#filterTeam');
    const btnQuery = $('#btnQuery');
    const btnReset = $('#btnReset');

    let page = 1;
    let simulate = qs('state') || 'ok'; // ok | empty | error | forbidden

    $$('[data-demo-state]').forEach((btn) => {
      btn.addEventListener('click', () => {
        simulate = btn.getAttribute('data-demo-state');
        page = 1;
        refresh();
      });
    });

    async function refresh() {
      errorBox.hidden = true;
      errorBox.innerHTML = '';
      empty.hidden = true;
      loading.hidden = false;
      tablePanel.hidden = true;

      if (simulate === 'forbidden') {
        loading.hidden = true;
        errorBox.hidden = false;
        errorBox.innerHTML =
          '<div class="alert alert--warn"><div class="alert__body"><div class="alert__title">无权限</div>' +
          '<div class="alert__desc">当前账号无权查看日报历史（预留态；后端尚未鉴权）。</div></div></div>';
        pagerInfo.textContent = '共 0 条';
        return;
      }

      try {
        const res = await api.listReports({
          date: filterDate.value || undefined,
          team: filterTeam.value.trim() || undefined,
          page,
          pageSize: PAGE_SIZE,
          simulate: simulate === 'ok' ? undefined : simulate,
        });
        loading.hidden = true;
        if (!res.items.length) {
          empty.hidden = false;
          pagerInfo.textContent = '共 0 条';
          btnPrev.disabled = true;
          btnNext.disabled = true;
          return;
        }
        tablePanel.hidden = false;
        tbody.innerHTML = res.items
          .map((r) => {
            const metaErr = (r.collect_meta && r.collect_meta.errors) || [];
            const chip = metaErr.length
              ? '<span class="chip chip--warn"><span class="chip__dot"></span>部分失败</span>'
              : r.collect_meta && r.collect_meta.collect_count === 0
                ? '<span class="chip chip--idle"><span class="chip__dot"></span>无记录</span>'
                : '<span class="chip chip--ok"><span class="chip__dot"></span>正常</span>';
            return (
              '<tr class="is-clickable" data-date="' +
              escapeHtml(r.report_date) +
              '" data-team="' +
              escapeHtml(r.team_name) +
              '">' +
              '<td class="mono cell-muted">' +
              dash(r.id) +
              '</td>' +
              '<td>' +
              fmtDate(r.report_date) +
              '</td>' +
              '<td>' +
              escapeHtml(dash(r.team_name)) +
              '</td>' +
              '<td>' +
              fmtDateTime(r.generated_at) +
              '</td>' +
              '<td>' +
              escapeHtml(summaryFromMarkdown(r.markdown)) +
              '</td>' +
              '<td>' +
              chip +
              '</td>' +
              '</tr>'
            );
          })
          .join('');

        $$('tr.is-clickable', tbody).forEach((tr) => {
          tr.addEventListener('click', () => {
            location.href =
              'report-detail.html?date=' +
              encodeURIComponent(tr.dataset.date) +
              '&team=' +
              encodeURIComponent(tr.dataset.team);
          });
        });

        const pages = Math.max(1, Math.ceil(res.total / res.pageSize));
        pagerInfo.textContent =
          '第 ' + res.page + ' / ' + pages + ' 页 · 共 ' + res.total + ' 条（客户端分页；后端仅有 limit）';
        btnPrev.disabled = res.page <= 1;
        btnNext.disabled = res.page >= pages;
      } catch (e) {
        loading.hidden = true;
        errorBox.hidden = false;
        errorBox.innerHTML =
          '<div class="alert alert--error"><div class="alert__body"><div class="alert__title">加载失败</div>' +
          '<div class="alert__desc">' +
          escapeHtml(e.message || '数据加载失败，请重试') +
          '</div></div>' +
          '<button type="button" class="btn btn--default" id="btnRetry">重试</button></div>';
        $('#btnRetry').onclick = refresh;
        pagerInfo.textContent = '共 — 条';
      }
    }

    btnQuery.addEventListener('click', () => {
      page = 1;
      simulate = 'ok';
      refresh();
    });
    btnReset.addEventListener('click', () => {
      filterDate.value = '';
      filterTeam.value = '';
      page = 1;
      simulate = 'ok';
      refresh();
    });
    btnPrev.addEventListener('click', () => {
      page -= 1;
      refresh();
    });
    btnNext.addEventListener('click', () => {
      page += 1;
      refresh();
    });

    refresh();
  }

  async function initDetailPage() {
    mountShell({ current: 'report-detail.html' });
    const date = qs('date') || MOCK.REPORTS[0].report_date;
    const team = qs('team') || MOCK.TEAM_NAME;
    const errorBox = $('#errorBox');
    const main = $('#detailMain');
    const loading = $('#detailLoading');

    $('#btnBack').href = 'report-list.html';
    $('#btnRegen').href = 'report-generate.html?date=' + encodeURIComponent(date);

    try {
      loading.hidden = false;
      main.hidden = true;
      const report = await api.getReport(date, team);
      loading.hidden = true;
      main.hidden = false;

      $('#metaDate').textContent = fmtDate(report.report_date);
      $('#metaTeam').textContent = dash(report.team_name);
      $('#metaGenerated').textContent = fmtDateTime(report.generated_at);
      const names = (report.members || []).map((m) => m.name).join('、') || '—';
      $('#metaMembers').textContent = names;

      const errors = (report.collect_meta && report.collect_meta.errors) || [];
      if (errors.length) {
        errorBox.hidden = false;
        errorBox.innerHTML =
          '<div class="alert alert--warn"><div class="alert__body"><div class="alert__title">部分数据源获取失败</div>' +
          '<div class="alert__desc">' +
          escapeHtml(errors.join('；')) +
          '</div></div></div>';
      } else {
        errorBox.hidden = true;
      }

      setupRawTabs(report);
      $('#previewBody').innerHTML = '<div class="markdown">' + renderMarkdown(report.markdown) + '</div>';

      $('#btnCopy').onclick = async () => {
        await navigator.clipboard.writeText(report.markdown || '');
        toast('Markdown 已复制');
      };
      $('#btnExport').onclick = () => {
        const html =
          '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>日报 ' +
          escapeHtml(report.report_date) +
          '</title></head><body>' +
          renderMarkdown(report.markdown) +
          '</body></html>';
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'daily-report-' + report.report_date + '.html';
        a.click();
        URL.revokeObjectURL(url);
        toast('HTML 已导出');
      };

      $('#btnNotifyEmail').onclick = async () => {
        const ok = await confirmModal({
          title: '推送邮件？',
          desc: '将调用 notifier.email.send（HTTP 尚未暴露，见 UI_SPEC 缺口）。原型仅演示确认流。',
          confirmText: '确认推送',
        });
        if (ok) toast('已记录推送意向（需后端新增接口）');
      };
      $('#btnNotifyLark').onclick = async () => {
        const ok = await confirmModal({
          title: '推送飞书？',
          desc: '将调用 notifier.lark_bot.send（HTTP 尚未暴露）。原型仅演示确认流。',
          confirmText: '确认推送',
        });
        if (ok) toast('已记录推送意向（需后端新增接口）');
      };
      $('#btnDelete').onclick = async () => {
        const ok = await confirmModal({
          title: '删除该日报？',
          desc: '删除后不可恢复。后端 DELETE 接口尚未提供，当前仅删除本地原型数据。',
          confirmText: '删除',
          danger: true,
        });
        if (!ok) return;
        await api.deleteReport(report.id);
        toast('已删除');
        location.href = 'report-list.html';
      };
    } catch (e) {
      loading.hidden = true;
      main.hidden = true;
      errorBox.hidden = false;
      const title = e.status === 404 ? '日报不存在' : '加载失败';
      errorBox.innerHTML =
        '<div class="alert alert--error"><div class="alert__body"><div class="alert__title">' +
        title +
        '</div><div class="alert__desc">' +
        escapeHtml(e.message || '数据加载失败，请重试') +
        '</div></div>' +
        '<a class="btn btn--default" href="report-list.html">返回列表</a></div>';
    }
  }

  /**
   * 原始数据区：Tab（GitHub / 飞书任务 / 飞书消息）+ 参考稿表格布局
   */
  function setupRawTabs(report) {
    const records = collectRawRecords(report);
    const pane = $('#rawPane');
    let active = 'github';

    function countOf(key) {
      const v = records[key];
      if (v === null) return '!';
      return Array.isArray(v) ? v.length : 0;
    }

    function syncBadges() {
      $$('[data-badge]', pane).forEach((el) => {
        el.textContent = String(countOf(el.getAttribute('data-badge')));
      });
    }

    function renderTab(tab) {
      active = tab;
      $$('.tab', pane).forEach((btn) => {
        btn.setAttribute('aria-selected', btn.getAttribute('data-tab') === tab ? 'true' : 'false');
      });
      $('#rawBody').innerHTML = tableForTab(tab, records[tab], report);
    }

    $$('.tab', pane).forEach((btn) => {
      btn.onclick = () => renderTab(btn.getAttribute('data-tab'));
    });

    syncBadges();
    renderTab(active);
  }

  function emptyRaw(title, desc) {
    return (
      '<div class="state" style="min-height:280px">' +
      '<div class="state__title">' +
      escapeHtml(title) +
      '</div>' +
      '<p class="state__desc">' +
      escapeHtml(desc || '') +
      '</p></div>'
    );
  }

  function failedRaw(source) {
    return emptyRaw('数据获取失败', source + ' 采集失败（CollectResult.success = false）');
  }

  function personCell(name) {
    const n = dash(name);
    const ch = n === '—' ? '?' : n[0];
    return (
      '<span class="person"><span class="person__avatar person__avatar--' +
      avatarClass(n) +
      '">' +
      escapeHtml(ch) +
      '</span>' +
      escapeHtml(n) +
      '</span>'
    );
  }

  function tableForTab(tab, rows, report) {
    /* Flask 瘦结构兜底：无完整 DTO 时仍可读 */
    if (report && report._flask_raw && tab === 'github' && (!rows || !rows.length)) {
      const slim = report._flask_raw.github || [];
      rows = slim.map((g, i) => ({
        message: g.commit,
        repo: g.repo,
        branch: '—',
        sha: shortSha({ message: g.commit }),
        additions: 0,
        deletions: 0,
        timestamp: (report.report_date || '') + 'T12:00:00+08:00',
        display_name: report._flask_raw.member || '—',
        author: report._flask_raw.member || '—',
      }));
    }
    if (report && report._flask_raw && tab === 'lark_msg' && (!rows || !rows.length)) {
      const slim = report._flask_raw.lark_msg || [];
      rows = slim.map((text) => ({
        content: text,
        chat_name: '—',
        keyword: '—',
        timestamp: (report.report_date || '') + 'T12:00:00+08:00',
        display_name: report._flask_raw.member || '—',
        sender: report._flask_raw.member || '—',
      }));
    }

    if (rows === null) {
      const labels = { github: 'GitHub', lark_task: '飞书任务', lark_msg: '飞书消息' };
      return failedRaw(labels[tab] || tab);
    }
    if (!rows || !rows.length) {
      return emptyRaw('今日无记录', '该数据源暂无采集结果');
    }

    if (tab === 'github') {
      return (
        '<div class="table-wrap"><table class="data"><thead><tr>' +
        '<th style="width:46%">提交内容</th><th>仓库 / 分支</th><th>成员</th><th>时间</th>' +
        '</tr></thead><tbody>' +
        rows
          .map((c) => {
            const name = displayNameOf(c, 'author');
            return (
              '<tr><td><div class="cell-primary">' +
              '<span class="cell-primary__main">' +
              escapeHtml(c.message) +
              '</span>' +
              '<span class="cell-sub"><span class="sha">' +
              escapeHtml(shortSha(c)) +
              '</span><span><span class="diff-add">+' +
              (c.additions ?? 0) +
              '</span> / <span class="diff-del">-' +
              (c.deletions ?? 0) +
              '</span></span></span></div></td>' +
              '<td><span class="repo">' +
              GIT_ICON +
              escapeHtml(dash(c.repo)) +
              '</span><div class="cell-sub">' +
              escapeHtml(dash(c.branch)) +
              '</div></td>' +
              '<td>' +
              personCell(name) +
              '</td>' +
              '<td class="cell-muted mono">' +
              fmtTime(c.timestamp) +
              '</td></tr>'
            );
          })
          .join('') +
        '</tbody></table></div>'
      );
    }

    if (tab === 'lark_task') {
      return (
        '<div class="table-wrap"><table class="data"><thead><tr>' +
        '<th style="width:40%">任务</th><th>状态</th><th>负责人</th><th>优先级</th><th>更新</th>' +
        '</tr></thead><tbody>' +
        rows
          .map((t) => {
            const name = displayNameOf(t, 'assignee');
            const st = t.status_to || t.status_from || 'unknown';
            const pri = t.priority || '—';
            const priClass =
              pri === '高' ? 'chip--err' : pri === '中' ? 'chip--warn' : 'chip--idle';
            return (
              '<tr><td><div class="cell-primary">' +
              '<span class="cell-primary__main">' +
              escapeHtml(t.title) +
              '</span>' +
              '<span class="cell-sub mono">' +
              escapeHtml(dash(t.task_id)) +
              '</span></div></td>' +
              '<td><span class="status status--' +
              statusClass(st) +
              '"><span class="status__dot"></span>' +
              escapeHtml(statusLabel(st)) +
              '</span></td>' +
              '<td>' +
              personCell(name) +
              '</td>' +
              '<td><span class="chip ' +
              priClass +
              '">' +
              escapeHtml(pri) +
              '</span></td>' +
              '<td class="cell-muted mono">' +
              fmtTime(t.updated_at) +
              '</td></tr>'
            );
          })
          .join('') +
        '</tbody></table></div>'
      );
    }

    /* lark_msg */
    return (
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      '<th style="width:50%">消息</th><th>关键词</th><th>发送人</th><th>时间</th>' +
      '</tr></thead><tbody>' +
      rows
        .map((m) => {
          const name = displayNameOf(m, 'sender');
          return (
            '<tr><td><div class="cell-primary">' +
            '<span class="cell-primary__main">' +
            escapeHtml(m.content) +
            '</span>' +
            '<span class="cell-sub">群「' +
            escapeHtml(dash(m.chat_name)) +
            '」</span></div></td>' +
            '<td><span class="kw">' +
            escapeHtml(dash(m.keyword)) +
            '</span></td>' +
            '<td>' +
            personCell(name) +
            '</td>' +
            '<td class="cell-muted mono">' +
            fmtTime(m.timestamp) +
            '</td></tr>'
          );
        })
        .join('') +
      '</tbody></table></div>'
    );
  }

  function initGeneratePage() {
    mountShell({ current: 'report-generate.html' });
    const form = $('#generateForm');
    const dateInput = $('#fieldDate');
    const memberSelect = $('#fieldMember');
    const liveToggle = $('#fieldLive');
    const dryRun = $('#fieldDryRun');
    const errDate = $('#errDate');
    const alertBox = $('#formAlert');
    const submitBtn = $('#btnSubmit');

    const preset = qs('date');
    if (preset) dateInput.value = preset;
    else dateInput.value = new Date().toISOString().slice(0, 10);

    memberSelect.innerHTML =
      '<option value="">全部 / 不指定</option>' +
      MOCK.MEMBERS.map(
        (m) =>
          '<option value="' +
          escapeHtml(m.name) +
          '">' +
          escapeHtml(m.name) +
          ' · ' +
          escapeHtml(m.github) +
          '</option>'
      ).join('');

    dryRun.disabled = true; // 需后端新增
    $('#teamReadonly').textContent = MOCK.TEAM_NAME;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      alertBox.hidden = true;
      errDate.hidden = true;
      dateInput.classList.remove('is-invalid');

      if (!dateInput.value) {
        dateInput.classList.add('is-invalid');
        errDate.hidden = false;
        errDate.textContent = '请选择日报日期';
        return;
      }

      submitBtn.classList.add('btn--loading');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="btn__spin" aria-hidden="true"></span> 生成中…';

      try {
        const res = await api.generateReport({
          date: dateInput.value,
          member: memberSelect.value,
          useLive: liveToggle.checked,
        });
        if (res.code !== 0) {
          throw new Error((res && res.message) || '生成失败');
        }
        toast('日报生成成功');
        location.href =
          'report-detail.html?date=' +
          encodeURIComponent(dateInput.value) +
          '&team=' +
          encodeURIComponent(MOCK.TEAM_NAME);
      } catch (err) {
        alertBox.hidden = false;
        alertBox.innerHTML =
          '<div class="alert alert--error"><div class="alert__body"><div class="alert__title">生成失败</div>' +
          '<div class="alert__desc">' +
          escapeHtml(err.message || '数据加载失败，请重试') +
          '</div></div></div>';
      } finally {
        submitBtn.classList.remove('btn--loading');
        submitBtn.disabled = false;
        submitBtn.textContent = '开始生成';
      }
    });
  }

  function initHubPage() {
    mountShell({ current: 'index.html' });
  }

  /* ---------- boot ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    const page = document.body.dataset.page;
    if (page === 'list') initListPage();
    else if (page === 'detail') initDetailPage();
    else if (page === 'generate') initGeneratePage();
    else if (page === 'hub') initHubPage();
  });

  global.PDR = { api, toast, confirmModal, renderMarkdown, fmtDateTime, loadReports };
})(typeof window !== 'undefined' ? window : globalThis);
