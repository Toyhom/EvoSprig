const $ = id => document.getElementById(id);
const project = new URLSearchParams(location.search).get('project') || 'cowork';
const root = '/api/projects/' + encodeURIComponent(project);
let run = null, doc = null, dirty = false, busy = false, approvalPath = null;
const words = {
  en: { start: 'Start working', overview: 'Team workspace', approve: 'Save and continue', save: 'Save changes', edit: 'Edit latest', ready: 'Ready', working: 'Working', steps: 'steps completed', planning: 'Planning the work…', open: 'Open document', shared: 'Shared document', revision: 'Revision', viewing: 'Viewing revision', discard: 'Discard unsaved edits?', succeeded: 'Completed', failed: 'Failed', canceled: 'Canceled', running: 'Working', waiting_input: 'Your review', waiting_external: 'Waiting', queued: 'Queued' },
  zh: { start: '开始工作', overview: '团队工作区', approve: '保存并继续', save: '保存修改', edit: '编辑', ready: '就绪', working: '正在工作', steps: '步已完成', planning: '正在安排工作…', open: '打开文档', shared: '共享文档', revision: '版本', viewing: '查看版本', discard: '放弃未保存的修改？', succeeded: '已完成', failed: '失败', canceled: '已取消', running: '正在工作', waiting_input: '等待审核', waiting_external: '等待工具', queued: '排队中' }
};
const t = key => words[$('language').value][key] || key;
function icon(kind = 'document') {
  const paths = {
    refresh: 'M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 13-3l2 3 M4 16l2 3a8 8 0 0 0 13-3',
    document: 'M7 3h7l4 4v14H7z M14 3v5h4 M10 12h5 M10 16h5',
    chart: 'M4 20h16 M7 16v-5 M12 16V5 M17 16V8',
    mail: 'M3 5h18v14H3z M3 5l9 8 9-8',
    calendar: 'M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16',
    team: 'M3 4h7v7H3z M14 4h7v7h-7z M3 15h7v6H3z M14 15h7v6h-7z',
    leaf: 'M12 21V9 M12 14C3 14 3 7 3 4c6 0 9 3 9 8 M12 10c0-5 3-7 9-7 0 7-3 10-9 10'
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) svg.setAttribute(k, v);
  const path = document.createElementNS(svg.namespaceURI, 'path');
  path.setAttribute('d', paths[kind] || paths.document); svg.append(path); return svg;
}
async function api(path, options = {}) {
  const r = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
  if (!r.ok) { const d = await r.json(); throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)); }
  return r.json();
}
function fail(e) { $('error').textContent = e.message; $('error').hidden = false; }
function clear() { $('error').hidden = true; }
function safeButton(label, fn) {
  const b = document.createElement('button'); b.textContent = label;
  b.onclick = () => Promise.resolve(fn()).catch(fail); return b;
}
async function refresh() {
  const list = await api(root + '/workspace/documents');
  $('documents').replaceChildren(...list.documents.map(d => {
    const b = safeButton(d.name.split('/').pop(), () => openDocument(d.name));
    b.prepend(icon()); b.title = d.name; return b;
  }));
}
// Generated document content is rendered through text nodes.
function render(text) {
  const box = $('document-content'); box.replaceChildren(); let table = null;
  for (const line of text.split('\n')) {
    if (/^\|.*\|$/.test(line.trim())) {
      const cells = line.trim().slice(1, -1).split('|');
      if (cells.every(c => /^\s*:?-+:?\s*$/.test(c))) continue;
      if (!table) { table = document.createElement('table'); box.append(table); }
      const row = table.insertRow(); for (const c of cells) row.insertCell().textContent = c.trim(); continue;
    }
    table = null; const heading = line.match(/^(#{1,3}) (.*)$/);
    const el = document.createElement(heading ? 'h' + heading[1].length : 'p');
    el.textContent = heading ? heading[2] : line.replace(/^[-*] /, '• ').replace(/\*\*(.*?)\*\*/g, '$1'); box.append(el);
  }
}
async function openDocument(name) {
  if (dirty && !confirm(t('discard'))) return;
  const d = await api(root + '/workspace/document?name=' + encodeURIComponent(name));
  doc = d; dirty = false; $('team-view').hidden = true; $('document-view').hidden = false;
  $('document-title').textContent = name.split('/').pop(); $('revision').textContent = t('revision') + ' ' + d.revision;
  $('document-editor').value = d.content; $('document-editor').hidden = true; $('document-content').hidden = false;
  $('save').hidden = true; $('edit').hidden = false;
  $('download').href = root + '/workspace/download?name=' + encodeURIComponent(name); render(d.content);
  const history = await api(root + '/workspace/history?name=' + encodeURIComponent(name));
  $('history').replaceChildren(...history.revisions.slice(0, 8).map(r => safeButton(t('revision') + ' ' + r.revision, async () => {
    if (dirty && !confirm(t('discard'))) return;
    const old = await api(root + '/workspace/document?name=' + encodeURIComponent(name) + '&revision=' + r.revision);
    dirty = false; $('document-editor').hidden = true; $('document-content').hidden = false;
    $('save').hidden = true; $('edit').hidden = false; render(old.content);
    $('revision').textContent = t('viewing') + ' ' + r.revision;
  })));
}
$('edit').onclick = () => {
  $('document-editor').value = doc.content; $('revision').textContent = t('revision') + ' ' + doc.revision;
  $('document-content').hidden = true; $('document-editor').hidden = false;
  $('save').hidden = false; $('edit').hidden = true; $('document-editor').focus();
};
$('document-editor').oninput = () => dirty = true;
$('save').onclick = async () => {
  try {
    clear(); const saved = await api(root + '/workspace/document', { method: 'PUT', body: JSON.stringify({ name: doc.name, content: $('document-editor').value, expected_revision: doc.revision, operation_id: crypto.randomUUID() }) });
    dirty = false; await openDocument(saved.name);
  } catch (e) { fail(e); }
};
$('overview').onclick = () => {
  if (dirty && !confirm(t('discard'))) return;
  dirty = false; $('document-view').hidden = true; $('team-view').hidden = false;
};
$('refresh').onclick = () => refresh().catch(fail);
$('request-form').onsubmit = async e => {
  e.preventDefault();
  try {
    clear(); $('start').disabled = true; const p = await api(root);
    const started = await api(root + '/runs', { method: 'POST', body: JSON.stringify({ revision: p.revision, input: { request: $('request').value, follow_up_seconds: Number($('delay').value) * 60 }, mock: false, allow_writes: true }) });
    run = started.run_id; approvalPath = null; $('approval').hidden = true; $('followup').hidden = true; await poll();
  } catch (e) { fail(e); } finally { $('start').disabled = false; }
};
$('cancel').onclick = async () => { try { await api('/api/runs/' + run + '/cancel', { method: 'POST' }); await poll(); } catch (e) { fail(e); } };
$('approve').onclick = async () => {
  try {
    clear(); $('approve').disabled = true;
    await api('/api/runs/' + run + '/input', { method: 'POST', body: JSON.stringify({ path: approvalPath, response: { content: $('review-text').value } }) });
    approvalPath = null; $('approval').hidden = true; await poll();
  } catch (e) { fail(e); } finally { $('approve').disabled = false; }
};
async function poll() {
  if (busy || !run) return;
  busy = true; const activeRun = run;
  try {
    const r = await api('/api/runs/' + activeRun);
    const docs = await api(root + '/workspace/documents');
    if (run !== activeRun) return;
    $('status').textContent = t(r.status); $('status').dataset.status = r.status;
    $('cancel').hidden = ['succeeded', 'failed', 'canceled'].includes(r.status);
    const nodes = r.events.filter(e => e.type === 'node.completed');
    const list = docs.documents.filter(d => d.name !== 'deliverables/brief.md');
    $('activity').replaceChildren(...list.map(d => {
      const div = document.createElement('div'); div.className = 'task';
      const badge = document.createElement('div'); badge.className = 'icon';
      badge.append(icon(/budget|analysis|funnel/.test(d.name) ? 'chart' : /email|invitation/.test(d.name) ? 'mail' : 'calendar'));
      const title = document.createElement('h3'); title.textContent = d.name.split('/').pop().replace(/[-_]/g, ' ');
      const p = document.createElement('p'); p.textContent = t('shared') + ' · ' + t('revision').toLowerCase() + ' ' + d.revision;
      const button = safeButton(t('open'), () => openDocument(d.name)); button.className = 'done';
      div.append(badge, title, p, button); return div;
    }));
    if (!list.length) {
      const p = document.createElement('p'); p.className = 'muted';
      p.textContent = nodes.length ? t('working') + ' · ' + nodes.length + ' ' + t('steps') : t('planning'); $('activity').append(p);
    }
    const review = r.status === 'waiting_input' && (r.waiting || []).find(w => w.kind === 'human' && w.path.endsWith('review'));
    $('approval').hidden = !review;
    if (review) {
      if (approvalPath !== review.path) $('review-text').value = review.input.draft;
      approvalPath = review.path;
    } else approvalPath = null;
    $('followup').hidden = !r.output?.follow_up;
    if (r.output?.follow_up) $('next-actions').textContent = r.output.follow_up;
    if (r.error) fail(Error(r.error.message)); await refresh();
  } finally { busy = false; }
}
const translations = {
  'workspace-label': ['WORKSPACE', '工作区'], 'workspace-name': ['Launch room', '项目团队'], 'documents-label': ['DOCUMENTS', '文档'],
  'workflow-link': ['Open the workflow', '打开工作流'], 'workspace-title': ['My workspace', '我的工作区'],
  'eyebrow': ['YOUR TEAM, ONE WORKSPACE', '你的团队，共享工作区'], 'headline': ['From a brief to finished work.', '从需求到交付。'],
  'intro': ['Plan the work. Bring in specialists. Edit the result together.', '安排任务，让专业智能体协作，一起编辑结果。'],
  'request-label': ['What are we working on?', '这次需要完成什么？'], 'delay-before': ['Follow up in', '跟进间隔'], 'delay-after': ['minutes', '分钟'],
  'activity-title': ['Team activity', '团队进度'], 'cancel': ['Stop run', '停止运行'], 'approval-title': ['Review the brief', '审核交付稿'],
  'followup-title': ['Next actions', '下一步行动'], 'document-label': ['SHARED DOCUMENT', '共享文档'], 'download': ['Download', '下载'], 'history-title': ['Revision history', '历史版本']
};
function language() {
  const zh = $('language').value === 'zh'; document.documentElement.lang = zh ? 'zh' : 'en';
  for (const [id, values] of Object.entries(translations)) $(id).textContent = values[Number(zh)];
  $('request').placeholder = zh ? '为新项目准备上线计划、预算和客户邀请邮件…' : 'Prepare a launch plan, budget and customer emails for our new pilot…';
  if (!run) $('activity').textContent = zh ? '团队进度将在这里显示。' : 'Your team’s progress will appear here.';
  for (const id of ['start', 'overview', 'approve', 'save', 'edit']) $(id).textContent = t(id);
  $('overview').prepend(icon('team')); $('status').textContent = t($('status').dataset.status || 'ready');
  poll().catch(fail);
}
$('language').value = localStorage.getItem('evosprig-cowork-language') === 'zh' ? 'zh' : 'en';
$('language').onchange = () => { localStorage.setItem('evosprig-cowork-language', $('language').value); language(); };
$('brand-icon').append(icon('leaf')); $('refresh').replaceChildren(icon('refresh')); language();
window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
try { await refresh(); const runs = await api(root + '/runs'); if (runs.length) { run = runs[0].run_id; await poll(); } } catch (e) { fail(e); }
setInterval(() => poll().catch(fail), 2500);
