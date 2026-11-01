import { StrictMode, useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Background, Controls, MiniMap, Position, addEdge, applyEdgeChanges, applyNodeChanges,
  type Node, type Edge, type Connection, type NodeChange, type EdgeChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './style.css';
import { orderedNodes, starter, type Document, type NodeSpec, type Spec } from './types';

type FlowNode = Node<{ label: string; config: NodeSpec }>;
const words = {
  zh: { projects: '工作空间', create: '新建项目', canvas: '画布', spec: '规格', code: 'Python',
    save: '保存', reload: '重新加载', run: '运行', cancel: '取消运行', export: '导出 Python',
    offline: '离线演示', live: '真实模型', node: '节点设置', input: '运行输入', output: '结果与事件',
    add: '添加模型节点', layout: '自动排列', instructions: '指令', binding: '模型引用',
    mappings: '输入映射（JSON）', nodeJson: '完整节点（JSON）', apply: '应用修改',
    empty: '创建项目，从一个可运行的智能体开始。', subtitle: '搭建 · 运行 · 带走',
    saved: '已保存', conflict: '版本冲突：本地修改已保留。请复制规格，再重新加载比较。',
    ready: '准备就绪', runHint: '运行和导出使用已保存版本；先保存当前修改。',
    settings: '连接', token: 'API 访问令牌（可选）', pending: '进化模块 · 计划中',
  },
  en: { projects: 'WORKSPACE', create: 'New project', canvas: 'Canvas', spec: 'Spec', code: 'Python',
    save: 'Save', reload: 'Reload', run: 'Run', cancel: 'Cancel run', export: 'Export Python',
    offline: 'Offline demo', live: 'Live model', node: 'NODE SETTINGS', input: 'RUN INPUT', output: 'RESULT & EVENTS',
    add: 'Add model node', layout: 'Arrange', instructions: 'Instructions', binding: 'Model reference',
    mappings: 'Input mappings (JSON)', nodeJson: 'Full node (JSON)', apply: 'Apply changes',
    empty: 'Create a project and start with a runnable agent.', subtitle: 'Build · Run · Take it with you',
    saved: 'Saved', conflict: 'Revision conflict: your edits are preserved. Copy the spec, then reload to compare.',
    ready: 'Ready', runHint: 'Run and export use the saved version. Save your edits first.',
    settings: 'Connection', token: 'API access token (optional)', pending: 'Evolution · planned',
  },
};

function App() {
  const [lang, setLang] = useState<'zh' | 'en'>('zh'); const t = words[lang];
  const [token, setToken] = useState('');
  const [projects, setProjects] = useState<Document[]>([]);
  const [doc, setDoc] = useState<Document | null>(null);
  const [nodes, setNodes] = useState<FlowNode[]>([]); const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<'canvas' | 'spec' | 'code'>('canvas');
  const [specText, setSpecText] = useState(''); const [code, setCode] = useState('');
  const [nodeText, setNodeText] = useState(''); const [input, setInput] = useState('{"question": "What can we build together?"}');
  const [mock, setMock] = useState(true); const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [runId, setRunId] = useState<string | null>(null); const [status, setStatus] = useState(t.ready);
  const [busy, setBusy] = useState(false); const [dirty, setDirty] = useState(false);
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const response = await fetch('/api' + path, { ...init, headers: { 'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } });
    if (!response.ok) {
      if (response.status === 409) throw new Error(words[lang].conflict);
      const body = await response.json(); throw new Error(JSON.stringify(body.detail ?? body));
    }
    return response;
  }, [lang, token]);
  const error = (e: unknown) => setStatus(e instanceof Error ? e.message : String(e));
  const load = (next: Document) => {
    setDoc(next); setNodes(orderedNodes(next.spec).map(([id, config], index) => ({ id, sourcePosition: Position.Right, targetPosition: Position.Left,
      position: next.layout[id] ?? { x: index * 300 + 40, y: 140 }, data: { label: `${id} · ${config.type}`, config } })));
    setEdges(next.spec.graph.edges.map(edge => ({ ...edge, id: `${edge.source}--${edge.target}` })));
    setSpecText(JSON.stringify(next.spec, null, 2)); setSelected(null); setDirty(false); setResult(null);
  };
  const refresh = useCallback(async () => {
    const items: Document[] = await (await api('/projects')).json(); setProjects(items); return items;
  }, [api]);
  useEffect(() => { refresh().then(items => { if (items.length) load(items[0]); }).catch(error); }, []);
  useEffect(() => () => { if (poll.current) clearTimeout(poll.current); }, []);
  const currentSpec = (): Spec => {
    if (!doc) throw new Error('Select a project');
    return { ...doc.spec, graph: { ...doc.spec.graph,
      nodes: Object.fromEntries(nodes.map(node => [node.id, node.data.config])),
      edges: edges.map(({ source, target }) => ({ source, target })) } };
  };
  const mutate = () => setDirty(true);
  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    setNodes(items => applyNodeChanges(changes, items));
    if (changes.some(change => change.type !== 'select' && change.type !== 'dimensions')) setDirty(true);
  }, []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => { setEdges(items => applyEdgeChanges(changes, items)); setDirty(true); }, []);
  const onConnect = useCallback((connection: Connection) => { setEdges(items => addEdge(connection, items)); setDirty(true); }, []);
  const chooseTab = async (next: typeof tab) => {
    if (!doc) return;
    if (tab === 'spec' && next !== 'spec') {
      try {
        const draft: Spec = JSON.parse(specText);
        if (draft.id !== doc.id || !draft.graph?.nodes || !Array.isArray(draft.graph.edges)) throw new Error('Invalid project shape or changed project ID');
        setDoc({ ...doc, spec: draft });
        setNodes(orderedNodes(draft).map(([id, config], index) => ({ id, sourcePosition: Position.Right, targetPosition: Position.Left,
          position: nodes.find(node => node.id === id)?.position ?? { x: index * 280 + 40, y: 140 },
          data: { label: `${id} · ${config.type}`, config } })));
        setEdges(draft.graph.edges.map(edge => ({ ...edge, id: `${edge.source}--${edge.target}` })));
        setSelected(null);
      } catch (e) { error(e); return; }
    }
    if (next === 'spec') setSpecText(JSON.stringify(currentSpec(), null, 2));
    if (next === 'code') {
      try { setCode((await (await api(`/projects/${doc.id}/code`)).json()).code); } catch (e) { error(e); }
    }
    setTab(next);
  };
  const save = async () => {
    if (!doc) return;
    setBusy(true);
    try {
      const spec = tab === 'spec' ? JSON.parse(specText) : currentSpec();
      const next = await (await api(`/projects/${doc.id}`, { method: 'PUT', body: JSON.stringify({ spec,
        revision: doc.revision, layout: Object.fromEntries(nodes.map(node => [node.id, node.position])) }) })).json();
      load(next); await refresh(); setStatus(`${t.saved} · r${next.revision}`);
    } catch (e) { error(e); } finally { setBusy(false); }
  };
  const addNode = () => {
    if (!doc) return;
    const id = 'node' + (Math.max(0, ...nodes.map(node => Number(node.id.replace('node', '')) || 0)) + 1);
    const config = structuredClone(starter('sample').graph.nodes.assistant);
    config.model = Object.keys(doc.spec.models)[0] ?? 'main';
    setNodes(items => [...items, { id, sourcePosition: Position.Right, targetPosition: Position.Left, position: { x: 60 + nodes.length * 260, y: 150 }, data: { label: `${id} · model`, config } }]);
    mutate();
  };
  const select = (node: FlowNode) => { setSelected(node.id); setNodeText(JSON.stringify(node.data.config, null, 2)); };
  const applyNode = (config: NodeSpec) => { setNodes(items => items.map(item => item.id === selected ? { ...item,
    data: { label: `${item.id} · ${config.type}`, config } } : item)); setNodeText(JSON.stringify(config, null, 2)); mutate(); };
  const active = nodes.find(node => node.id === selected);
  const run = async () => {
    if (!doc) return;
    try {
      setResult(null); const started = await (await api(`/projects/${doc.id}/runs`, { method: 'POST',
        body: JSON.stringify({ input: JSON.parse(input), revision: doc.revision, mock }) })).json();
      setRunId(started.run_id); setStatus('running');
      const tick = async () => {
        try {
          const next = await (await api(`/runs/${started.run_id}`)).json(); setResult(next);
          if (['queued', 'running'].includes(next.status)) poll.current = setTimeout(tick, 400);
          else { setRunId(null); setStatus(next.status); }
        } catch (e) { setRunId(null); error(e); }
      }; await tick();
    } catch (e) { error(e); }
  };
  const exportProject = async () => {
    if (!doc) return;
    setBusy(true);
    try {
      const response = await api(`/projects/${doc.id}/export`, { method: 'POST' });
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a');
      link.href = url; link.download = `${doc.id}.zip`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { error(e); } finally { setBusy(false); }
  };

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><svg className="sprig" width="36" height="46" viewBox="0 0 36 46" aria-hidden="true"><path d="M18 42V18" stroke="currentColor" strokeWidth="2" fill="none"/><path d="M18 30C4 30 3 20 4 13c12 0 16 6 14 17ZM18 21C31 21 34 10 31 3c-12 2-15 8-13 18Z" fill="currentColor"/></svg><div>EvoSprig<span>STUDIO</span></div></div>
      <p className="tagline">{t.subtitle}</p><div className="section-label">{t.projects}</div>
      <div className="projects">{projects.map(item => <button key={item.id} className={doc?.id === item.id ? 'project active' : 'project'}
        disabled={!!runId} onClick={async () => { try { load(await (await api(`/projects/${item.id}`)).json()); } catch (e) { error(e); } }}>
        <span>◇</span>{item.id}<small>r{item.revision}</small></button>)}</div>
      <button className="new-project" disabled={!!runId} onClick={async () => {
        try { const id = `agent-${Date.now().toString(36)}`; load(await (await api('/projects', { method: 'POST', body: JSON.stringify({ spec: starter(id) }) })).json()); await refresh(); }
        catch (e) { error(e); }
      }}>＋ {t.create}</button>
      <div className="sidebar-bottom"><p>{t.pending}</p><details><summary>{t.settings}</summary>
        <input aria-label={t.token} placeholder={t.token} type="password" value={token} onChange={e => setToken(e.target.value)} />
        <button onClick={() => refresh().then(items => { if (items.length) load(items[0]); }).catch(error)}>{t.reload}</button>
      </details><span className="stage">M0 · 0.1.0</span><button className="language" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>中文 / EN</button></div>
    </aside>
    <main><header><div><span className="eyebrow">AGENT WORKSPACE</span><h1>{doc?.id ?? 'EvoSprig'}{dirty && <span className="unsaved"> ●</span>}</h1></div>
      <div className="actions"><button onClick={() => doc && api(`/projects/${doc.id}`).then(r => r.json()).then(load).catch(error)} disabled={!doc || !!runId}>{t.reload}</button>
        <button onClick={save} disabled={!doc || busy || !!runId}>{t.save}</button><button className="primary" onClick={exportProject} disabled={!doc || dirty || busy}>{t.export} ↗</button></div></header>
      {!doc ? <div className="empty"><span>↟</span><h2>{t.empty}</h2></div> : <>
        <nav className="tabs">{(['canvas', 'spec', 'code'] as const).map(key => <button key={key} className={tab === key ? 'selected' : ''} onClick={() => chooseTab(key)}>{t[key]}</button>)}
          <span className="revision">r{doc.revision} · {doc.spec_hash.slice(0, 12)}</span></nav>
        <div className="editor">
          <section className="workspace">
            {tab === 'canvas' ? <><div className="canvas-tools"><button onClick={addNode}>＋ {t.add}</button><button onClick={() => { const order = orderedNodes(currentSpec()).map(([id]) => id); setNodes(items => items.map(node => ({ ...node, position: { x: order.indexOf(node.id) * 280 + 40, y: 150 } }))); mutate(); }}>{t.layout}</button></div>
              <ReactFlow key={`${doc.id}:${doc.revision}`} nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, node) => select(node)} fitView fitViewOptions={{ padding: 0.3, maxZoom: 1 }} minZoom={0.2} maxZoom={2} deleteKeyCode="Delete"><Background color="#d6dfd7" gap={22}/><Controls/><MiniMap nodeColor="#c2d9bf"/></ReactFlow></>
              : tab === 'spec' ? <textarea className="source-editor" aria-label="AgentSpec JSON" value={specText} onChange={e => { setSpecText(e.target.value); mutate(); }} spellCheck={false}/>
                : <pre className="source-editor code-view">{dirty ? `${t.runHint}\n\n` : ''}{code}</pre>}
          </section>
          <aside className="inspector"><div className="section-label">{t.node}</div>
            {active ? <><h3>{active.id}<span className="pill">{active.data.config.type}</span></h3>
              {typeof active.data.config.instructions === 'string' && active.data.config.type !== 'tool' && <label>{t.instructions}<textarea aria-label={t.instructions} value={active.data.config.instructions} onChange={e => applyNode({ ...active.data.config, instructions: e.target.value })}/></label>}
              {active.data.config.model && <label>{t.binding}<select value={active.data.config.model} onChange={e => applyNode({ ...active.data.config, model: e.target.value })}>{Object.keys(doc.spec.models).map(name => <option key={name}>{name}</option>)}</select></label>}
              <label>{t.nodeJson}<textarea className="node-json" aria-label={t.nodeJson} value={nodeText} onChange={e => setNodeText(e.target.value)}/></label>
              <button onClick={() => { try { applyNode(JSON.parse(nodeText)); } catch (e) { error(e); } }}>{t.apply}</button></> : <p className="muted">{lang === 'zh' ? '选择节点查看参数。拖动端口连接节点；在规格页编辑输入输出和工具。' : 'Select a node to edit its settings. Connect nodes by dragging handles; edit inputs, outputs and tools in Spec.'}</p>}
            <div className="divider"/><div className="section-label">{t.input}</div><label><textarea aria-label={t.input} value={input} onChange={e => setInput(e.target.value)}/></label>
            <select aria-label="Run mode" value={mock ? 'mock' : 'live'} onChange={e => setMock(e.target.value === 'mock')}><option value="mock">{t.offline}</option><option value="live">{t.live} · deepseek-flash</option></select>
            <button className="primary run" onClick={run} disabled={dirty || !!runId}>▷ {t.run}</button>
            {runId && <button onClick={() => api(`/runs/${runId}/cancel`, { method: 'POST' }).catch(error)}>{t.cancel}</button>}
            <p className="hint">{t.runHint}</p>
          </aside>
        </div>
        <section className="results"><div className="section-label">{t.output}<span>{result ? String(result.status) : '—'}</span></div>
          {result && <><pre>{JSON.stringify(result.output ?? result.error ?? {}, null, 2)}</pre><details><summary>Events / usage</summary><pre>{JSON.stringify(result, null, 2)}</pre></details></>}
        </section>
      </>}
      <footer role="status"><span className="dot"/>{status}</footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
