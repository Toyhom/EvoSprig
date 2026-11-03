const $ = (id) => document.getElementById(id);
let project = new URLSearchParams(location.search).get("project");
if (!project) {
  const catalog = await fetch("/api/projects")
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => []);
  project =
    Array.isArray(catalog) &&
    !catalog.some((p) => p.id === "cowork") &&
    catalog.some((p) => p.id === "cowork-rsi")
      ? "cowork-rsi"
      : "cowork";
}
const root = "/api/projects/" + encodeURIComponent(project);
if (project === "cowork-rsi") {
  document.title = "CoworkRSI";
  $("brand-name").textContent = "CoworkRSI";
  $("application-name").textContent = "CoworkRSI";
}
let run = null,
  doc = null,
  dirty = false,
  busy = false,
  approvalPath = null,
  documentRequest = 0,
  runList = [],
  reviewDirty = false;
const words = {
  en: {
    start: "Start working",
    overview: "Workspace",
    approve: "Save and continue",
    save: "Save changes",
    edit: "Edit latest",
    ready: "Ready",
    working: "Working",
    steps: "steps completed",
    planning: "Planning the work…",
    open: "Open document",
    shared: "Shared document",
    revision: "Revision",
    viewing: "Viewing revision",
    discard: "Discard unsaved edits?",
    succeeded: "Completed",
    failed: "Failed",
    canceled: "Canceled",
    running: "Working",
    waiting_input: "Your review",
    waiting_external: "Waiting",
    queued: "Queued",
  },
  zh: {
    start: "开始工作",
    overview: "团队工作区",
    approve: "保存并继续",
    save: "保存修改",
    edit: "编辑",
    ready: "就绪",
    working: "正在工作",
    steps: "步已完成",
    planning: "正在安排工作…",
    open: "打开文档",
    shared: "共享文档",
    revision: "版本",
    viewing: "查看版本",
    discard: "放弃未保存的修改？",
    succeeded: "已完成",
    failed: "失败",
    canceled: "已取消",
    running: "正在工作",
    waiting_input: "等待审核",
    waiting_external: "等待工具",
    queued: "排队中",
  },
};
const t = (key) => words[$("language").value][key] || key;
function icon(kind = "document") {
  const paths = {
    refresh:
      "M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 13-3l2 3 M4 16l2 3a8 8 0 0 0 13-3",
    document: "M7 3h7l4 4v14H7z M14 3v5h4 M10 12h5 M10 16h5",
    chart: "M4 20h16 M7 16v-5 M12 16V5 M17 16V8",
    mail: "M3 5h18v14H3z M3 5l9 8 9-8",
    check: "M5 12l4 4L19 6",
    panel: "M3 4h18v16H3z M15 4v16",
    new: "M12 5v14 M5 12h14",
    back: "M14 6l-6 6 6 6",
    sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1",
    orbit: "M12 4l8 5v6l-8 5-8-5V9z M4 9l8 5 8-5 M12 14v6",
    calendar: "M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16",
    team: "M3 4h7v7H3z M14 4h7v7h-7z M3 15h7v6H3z M14 15h7v6h-7z",
    leaf: "M12 21V9 M12 14C3 14 3 7 3 4c6 0 9 3 9 8 M12 10c0-5 3-7 9-7 0 7-3 10-9 10",
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [k, v] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "1.6",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  }))
    svg.setAttribute(k, v);
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", paths[kind] || paths.document);
  svg.append(path);
  return svg;
}
async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!r.ok) {
    const d = await r.json();
    throw Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail),
    );
  }
  return r.json();
}
function fail(e) {
  $("error").textContent = e.message;
  $("error").hidden = false;
}
function clear() {
  $("error").hidden = true;
}
function safeButton(label, fn) {
  const b = document.createElement("button");
  b.textContent = label;
  b.onclick = () => Promise.resolve(fn()).catch(fail);
  return b;
}
async function refresh() {
  const list = await api(root + "/workspace/documents");
  $("document-count").textContent = list.documents.length;
  $("documents").replaceChildren(
    ...list.documents.map((d) => {
      const b = safeButton(d.name.split("/").pop(), () => openDocument(d.name));
      b.prepend(icon());
      b.title = d.name;
      b.classList.toggle(
        "active",
        doc?.name === d.name && !$("document-view").hidden,
      );
      return b;
    }),
  );
}
// Generated document content is rendered through text nodes.
function render(text) {
  const box = $("document-content");
  box.replaceChildren();
  let table = null;
  for (const line of text.split("\n")) {
    if (/^\|.*\|$/.test(line.trim())) {
      const cells = line.trim().slice(1, -1).split("|");
      if (cells.every((c) => /^\s*:?-+:?\s*$/.test(c))) continue;
      if (!table) {
        table = document.createElement("table");
        box.append(table);
      }
      const row = table.insertRow();
      for (const c of cells) row.insertCell().textContent = c.trim();
      continue;
    }
    table = null;
    const heading = line.match(/^(#{1,3}) (.*)$/);
    const el = document.createElement(heading ? "h" + heading[1].length : "p");
    el.textContent = heading
      ? heading[2]
      : line.replace(/^[-*] /, "• ").replace(/\*\*(.*?)\*\*/g, "$1");
    box.append(el);
  }
}
async function openDocument(name) {
  if (dirty && !confirm(t("discard"))) return;
  const request = ++documentRequest;
  const d = await api(
    root + "/workspace/document?name=" + encodeURIComponent(name),
  );
  if (request !== documentRequest) return;
  document.body.classList.remove("show-panel");
  syncPanels();
  doc = d;
  dirty = false;
  $("team-view").hidden = true;
  $("document-view").hidden = false;
  $("document-title").textContent = name.split("/").pop();
  $("revision").textContent = t("revision") + " " + d.revision;
  $("document-editor").value = d.content;
  $("document-editor").hidden = true;
  $("document-content").hidden = false;
  $("save").hidden = true;
  $("edit").hidden = false;
  $("download").href =
    root + "/workspace/download?name=" + encodeURIComponent(name);
  render(d.content);
  const history = await api(
    root + "/workspace/history?name=" + encodeURIComponent(name),
  );
  if (request !== documentRequest) return;
  $("history").replaceChildren(
    ...history.revisions.slice(0, 8).map((r) =>
      safeButton(t("revision") + " " + r.revision, async () => {
        if (dirty && !confirm(t("discard"))) return;
        const historyRequest = ++documentRequest;
        const old = await api(
          root +
            "/workspace/document?name=" +
            encodeURIComponent(name) +
            "&revision=" +
            r.revision,
        );
        if (historyRequest !== documentRequest) return;
        dirty = false;
        $("document-editor").hidden = true;
        $("document-content").hidden = false;
        $("save").hidden = true;
        $("edit").hidden = false;
        render(old.content);
        $("revision").textContent = t("viewing") + " " + r.revision;
      }),
    ),
  );
}
$("edit").onclick = () => {
  $("document-editor").value = doc.content;
  $("revision").textContent = t("revision") + " " + doc.revision;
  $("document-content").hidden = true;
  $("document-editor").hidden = false;
  $("save").hidden = false;
  $("edit").hidden = true;
  $("document-editor").focus();
};
$("document-editor").oninput = () => (dirty = true);
$("save").onclick = async () => {
  const selected = doc,
    request = documentRequest,
    content = $("document-editor").value;
  $("save").disabled = true;
  try {
    clear();
    const saved = await api(root + "/workspace/document", {
      method: "PUT",
      body: JSON.stringify({
        name: selected.name,
        content,
        expected_revision: selected.revision,
        operation_id: crypto.randomUUID(),
      }),
    });
    if (documentRequest !== request || doc !== selected) return;
    if ($("document-editor").value !== content) {
      doc = saved;
      $("revision").textContent = t("revision") + " " + saved.revision;
      return;
    }
    dirty = false;
    await openDocument(saved.name);
  } catch (e) {
    if (documentRequest === request) fail(e);
  } finally {
    $("save").disabled = false;
  }
};
function overview() {
  if (dirty && !confirm(t("discard"))) return false;
  documentRequest++;
  dirty = false;
  $("document-view").hidden = true;
  $("team-view").hidden = false;
  document.body.classList.remove("show-sidebar", "show-panel");
  syncPanels();
  return true;
}
$("overview").onclick = overview;
$("close-document").onclick = overview;
function showRun(r) {
  $("welcome").hidden = !!r;
  $("conversation").hidden = !r;
  $("run-details").hidden = !r;
  $("submitted-request").textContent =
    r?.input?.request || (r ? t("overview") : "");
  $("status").dataset.status = r?.status || "ready";
  $("status").textContent = t(r?.status || "ready");
  if (!r) {
    $("approval").hidden = $("followup").hidden = $("cancel").hidden = true;
    $("activity").replaceChildren();
    drawTeam([]);
  }
}
function leaveRun() {
  if (reviewDirty && !confirm(t("discard"))) return false;
  if (!overview()) return false;
  reviewDirty = false;
  return true;
}
async function selectRun(id) {
  const changed = id !== run;
  if (changed && !leaveRun()) return;
  if (!changed && !overview()) return;
  run = id;
  if (changed) approvalPath = null;
  clear();
  showRun(runList.find((r) => r.run_id === id));
  renderRuns();
  await poll();
}
function renderRuns() {
  $("conversations").replaceChildren(
    ...runList.map((r) => {
      const b = safeButton("", () => selectRun(r.run_id));
      b.className = "conversation-item";
      b.classList.toggle("active", r.run_id === run);
      const title = document.createElement("strong");
      title.textContent = r.input?.request || r.run_id.slice(0, 8);
      const sub = document.createElement("small");
      sub.textContent = t(r.status);
      b.append(title, sub);
      return b;
    }),
  );
}
async function refreshRuns() {
  runList = await api(root + "/runs");
  renderRuns();
}
$("new-task").onclick = () => {
  if (!leaveRun()) return;
  run = null;
  approvalPath = null;
  clear();
  showRun(null);
  renderRuns();
  $("request").value = "";
  $("request").focus();
};
$("refresh").onclick = () =>
  Promise.all([refresh(), refreshRuns()]).catch(fail);
$("request-form").onsubmit = async (e) => {
  e.preventDefault();
  if (reviewDirty && !confirm(t("discard"))) return;
  try {
    clear();
    $("start").disabled = true;
    const p = await api(root);
    const started = await api(root + "/runs", {
      method: "POST",
      body: JSON.stringify({
        revision: p.revision,
        input: {
          request: $("request").value,
          follow_up_seconds: Number($("delay").value) * 60,
        },
        mock: false,
        allow_writes: true,
      }),
    });
    run = started.run_id;
    approvalPath = null;
    reviewDirty = false;
    $("request").value = "";
    await refreshRuns();
    $("approval").hidden = true;
    $("followup").hidden = true;
    await poll();
  } catch (e) {
    fail(e);
  } finally {
    $("start").disabled = false;
  }
};
$("cancel").onclick = async () => {
  try {
    await api("/api/runs/" + run + "/cancel", { method: "POST" });
    await poll();
  } catch (e) {
    fail(e);
  }
};
$("review-text").oninput = () => (reviewDirty = true);
$("approve").onclick = async () => {
  const activeRun = run;
  try {
    clear();
    $("approve").disabled = true;
    await api("/api/runs/" + activeRun + "/input", {
      method: "POST",
      body: JSON.stringify({
        path: approvalPath,
        response: { content: $("review-text").value },
      }),
    });
    if (run !== activeRun) return;
    reviewDirty = false;
    approvalPath = null;
    $("approval").hidden = true;
    await poll();
  } catch (e) {
    fail(e);
  } finally {
    $("approve").disabled = false;
  }
};
function drawTeam(events) {
  const paths = [
    ...new Set(
      events
        .filter((e) => /\/item-\d+\/specialist$/.test(e.node_id || ""))
        .map((e) => e.node_id),
    ),
  ];
  const ns = "http://www.w3.org/2000/svg";
  const el = (name, attrs) => {
    const e = document.createElementNS(ns, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    return e;
  };
  const svg = el("svg", {
    viewBox: "0 0 260 150",
    role: "img",
    "aria-label": t("overview"),
  });
  const points = paths.slice(0, 8).map((p, i, a) => {
    const angle = (Math.PI * 2 * i) / a.length - Math.PI / 2;
    return [130 + 87 * Math.cos(angle), 75 + 49 * Math.sin(angle)];
  });
  for (const [x, y] of points)
    svg.append(el("line", { x1: 130, y1: 75, x2: x, y2: y }));
  function node(x, y, label, radius) {
    svg.append(el("circle", { cx: x, cy: y, r: radius }));
    const text = el("text", { x, y });
    text.textContent = label;
    svg.append(text);
  }
  points.forEach(([x, y], i) => node(x, y, String(i + 1), 14));
  node(130, 75, "M", 20);
  $("team-map").replaceChildren(svg);
  const zh = $("language").value === "zh";
  $("member-count").textContent = events.length ? paths.length + 1 : 0;
  $("team-members").replaceChildren(
    ...(events.length ? ["main", ...paths] : []).map((path, i) => {
      const row = document.createElement("div");
      row.className = "member";
      const dot = document.createElement("span");
      dot.className = "member-dot";
      const name = document.createElement("span");
      name.textContent = i
        ? (zh ? "专家 " : "Specialist ") + i
        : zh
          ? "主智能体"
          : "Main agent";
      const state = document.createElement("small");
      state.textContent = i
        ? events.some((e) => e.node_id === path && e.type === "node.completed")
          ? t("succeeded")
          : t("working")
        : $("status").textContent;
      row.append(dot, name, state);
      return row;
    }),
  );
}
function renderActivity(r, docs) {
  const zh = $("language").value === "zh";
  const labels = {
    context: ["Read project context", "读取项目资料"],
    recall: ["Recall team lessons", "检索团队经验"],
    plan: ["Plan assignments", "规划任务"],
    team: ["Coordinate specialists", "协调专家"],
    specialists: ["Coordinate specialists", "协调专家"],
    acceptance: ["Review deliverables", "验收交付稿"],
    assemble: ["Assemble the brief", "汇总交付稿"],
    review: ["Human review", "人工审核"],
    publish: ["Publish documents", "发布文档"],
    remember: ["Save project memory", "保存项目记忆"],
    retrospective: ["Reflect on the work", "复盘工作"],
    save_lessons: ["Save team lessons", "保存团队经验"],
    follow_up: ["Prepare next actions", "准备下一步行动"],
  };
  const complete = r.events.filter((e) => e.type === "node.completed");
  const steps = complete
    .filter((e) => labels[e.node_id?.split("/").pop()])
    .slice(-7);
  $("activity").replaceChildren(
    ...steps.map((e) => {
      const row = document.createElement("div");
      row.className = "activity-step";
      const label = document.createElement("span");
      label.textContent = labels[e.node_id.split("/").pop()][Number(zh)];
      const time = document.createElement("small");
      time.textContent = new Date(e.timestamp).toLocaleTimeString(
        zh ? "zh-CN" : "en-GB",
        { hour: "2-digit", minute: "2-digit" },
      );
      row.append(icon("check"), label, time);
      return row;
    }),
  );
  if (!steps.length) $("activity").textContent = t("planning");
  const brief = docs.documents.find((d) => d.name === "deliverables/brief.md");
  if (brief) {
    const b = safeButton("", () => openDocument(brief.name));
    b.className = "task";
    const label = document.createElement("span");
    label.textContent = zh ? "打开团队交付稿" : "Open the team brief";
    const meta = document.createElement("small");
    meta.textContent = t("revision") + " " + brief.revision;
    b.append(icon(), label, meta);
    $("activity").append(b);
  }
  $("run-summary").textContent = t(r.status);
  $("step-count").textContent = complete.length;
  $("tool-count").textContent = r.events.filter(
    (e) => e.type === "tool.result",
  ).length;
  drawTeam(r.events);
}
async function poll() {
  if (busy || !run) return;
  busy = true;
  const activeRun = run;
  try {
    const r = await api("/api/runs/" + activeRun);
    const docs = await api(root + "/workspace/documents");
    if (run !== activeRun) return;
    showRun(r);
    renderActivity(r, docs);
    const previous = runList.findIndex((item) => item.run_id === activeRun);
    if (previous >= 0) runList[previous] = r;
    renderRuns();
    $("cancel").hidden = ["succeeded", "failed", "canceled"].includes(r.status);
    const review =
      r.status === "waiting_input" &&
      (r.waiting || []).find(
        (w) => w.kind === "human" && w.path.endsWith("review"),
      );
    $("approval").hidden = !review;
    if (review) {
      if (approvalPath !== review.path)
        $("review-text").value = review.input.draft;
      approvalPath = review.path;
    } else approvalPath = null;
    $("followup").hidden = !r.output?.follow_up;
    if (r.output?.follow_up) $("next-actions").textContent = r.output.follow_up;
    if (r.error) fail(Error(r.error.message));
    await refresh();
  } catch (e) {
    if (run === activeRun) throw e;
  } finally {
    busy = false;
  }
}
const translations = {
  "workspace-label": ["PROJECT", "项目"],
  "workspace-name": ["Launch room", "项目团队"],
  "documents-label": ["Outputs", "产出物"],
  "workflow-link": ["Open the workflow", "打开工作流"],
  "workspace-title": ["My workspace", "我的工作区"],
  headline: ["What are we working on?", "这次一起做什么？"],
  intro: ["Bring your team a task.", "把任务交给你的团队。"],
  "request-label": ["Task request", "任务需求"],
  "delay-before": ["Follow up in", "跟进间隔"],
  "delay-after": ["minutes", "分钟"],
  cancel: ["Stop run", "停止运行"],
  "approval-title": ["Review the brief", "审核交付稿"],
  "followup-title": ["Next actions", "下一步行动"],
  "document-label": ["SHARED DOCUMENT", "共享文档"],
  download: ["Download", "下载"],
  "history-title": ["Revision history", "历史版本"],
  "new-task": ["New conversation", "新会话"],
  "conversations-label": ["RECENT TASKS", "最近任务"],
  "panel-title": ["Task workspace", "任务工作区"],
  "team-label": ["Agent team", "智能体团队"],
  "run-details-label": ["Run overview", "运行概览"],
  "steps-label": ["Completed steps", "已完成步骤"],
  "tools-label": ["Tool calls", "工具调用"],
  "main-label": ["Main agent", "主智能体"],
  "request-heading": ["You", "你"],
};
function language() {
  const zh = $("language").value === "zh";
  document.documentElement.lang = zh ? "zh" : "en";
  for (const [id, values] of Object.entries(translations))
    $(id).textContent = values[Number(zh)];
  $("request").placeholder = zh
    ? "让团队一起规划、调研或创作…"
    : "Ask your team to plan, research or create…";
  for (const id of ["start", "overview", "approve", "save", "edit"])
    $(id).textContent = t(id);
  $("overview").prepend(icon("team"));
  $("new-task").prepend(icon("new"));
  $("status").textContent = t($("status").dataset.status || "ready");
  renderRuns();
  if (!run) drawTeam([]);
  poll().catch(fail);
}
$("language").value =
  localStorage.getItem("evosprig-cowork-language") === "zh" ? "zh" : "en";
$("language").onchange = () => {
  localStorage.setItem("evosprig-cowork-language", $("language").value);
  language();
};
const theme = localStorage.getItem("cowork-theme");
document.documentElement.dataset.theme = ["light", "dark"].includes(theme)
  ? theme
  : "light";
$("theme").onclick = () => {
  const next =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("cowork-theme", next);
};
for (const [id, kind] of [
  ["brand-icon", "orbit"],
  ["welcome-icon", "orbit"],
  ["refresh", "refresh"],
  ["theme", "sun"],
  ["sidebar-toggle", "panel"],
  ["panel-toggle", "panel"],
  ["close-document", "back"],
])
  $(id).replaceChildren(icon(kind));
const mobilePanels = matchMedia("(max-width:900px)");
function syncPanels() {
  for (const [id, part] of [
    ["sidebar-toggle", "sidebar"],
    ["panel-toggle", "panel"],
  ]) {
    const open = mobilePanels.matches
      ? document.body.classList.contains("show-" + part)
      : !document.body.classList.contains(part + "-collapsed");
    $(id).setAttribute("aria-expanded", String(open));
  }
}
for (const [id, part] of [
  ["sidebar-toggle", "sidebar"],
  ["panel-toggle", "panel"],
])
  $(id).onclick = () => {
    document.body.classList.toggle(
      mobilePanels.matches ? "show-" + part : part + "-collapsed",
    );
    syncPanels();
  };
mobilePanels.addEventListener("change", syncPanels);
syncPanels();

language();
window.addEventListener("beforeunload", (e) => {
  if (dirty || reviewDirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
try {
  await refresh();
  await refreshRuns();
  if (runList.length) {
    run = runList[0].run_id;
    await poll();
  }
} catch (e) {
  fail(e);
}
setInterval(() => poll().catch(fail), 2500);
