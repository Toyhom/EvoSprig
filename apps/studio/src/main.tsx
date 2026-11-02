import { StrictMode, useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Background, Controls, MiniMap, Position, addEdge, applyEdgeChanges, applyNodeChanges,
  type Node, type Edge, type Connection, type NodeChange, type EdgeChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './style.css';
import { orderedNodes, starter, nodeTemplate, type Document, type NodeSpec, type NodeKind, type Spec, type Run } from './types';
import { ResourcesPanel, MemoryPanel, RunsPanel, RunDetails, ImprovePanel, VersionsPanel } from './panels';

type Tab = 'canvas'|'spec'|'code'|'resources'|'runs'|'memory'|'improve'|'versions';
const flowEdges = (spec:Spec): Edge[] => spec.graph.edges.map(edge=>({source:edge.source,target:edge.target,id:`${edge.source}--${edge.target}`,data:{when:edge.when},label:typeof edge.when==='boolean'?String(edge.when):undefined}));

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
    settings: '连接', token: 'API 访问令牌（可选）', pending: '构建 · 评测 · 持续改进', resources:'资源', runs:'历史', memory:'记忆与资料', improve:'改进', versions:'版本',
  },
  en: { projects: 'WORKSPACE', create: 'New project', canvas: 'Canvas', spec: 'Spec', code: 'Python',
    save: 'Save', reload: 'Reload', run: 'Run', cancel: 'Cancel run', export: 'Export Python',
    offline: 'Offline demo', live: 'Live model', node: 'NODE SETTINGS', input: 'RUN INPUT', output: 'RESULT & EVENTS',
    add: 'Add model node', layout: 'Arrange', instructions: 'Instructions', binding: 'Model reference',
    mappings: 'Input mappings (JSON)', nodeJson: 'Full node (JSON)', apply: 'Apply changes',
    empty: 'Create a project and start with a runnable agent.', subtitle: 'Build · Run · Take it with you',
    saved: 'Saved', conflict: 'Revision conflict: your edits are preserved. Copy the spec, then reload to compare.',
    ready: 'Ready', runHint: 'Run and export use the saved version. Save your edits first.',
    settings: 'Connection', token: 'API access token (optional)', pending: 'Build · Evaluate · Improve', resources:'Resources', runs:'History', memory:'Memory', improve:'Improve', versions:'Versions',
  },
};

function App() {
  const [lang, setLang] = useState<'zh' | 'en'>('zh'); const t = words[lang];
  const [token, setToken] = useState('');
  const [exportTarget,setExportTarget]=useState('python');
  const [imported,setImported]=useState<{spec:Spec;resources:Record<string,string>;report:unknown}|null>(null);
  const [importId,setImportId]=useState('');
  const [projects, setProjects] = useState<Document[]>([]);
  const [doc, setDoc] = useState<Document | null>(null);
  const [nodes, setNodes] = useState<FlowNode[]>([]); const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('canvas');
  const [nodeKind,setNodeKind]=useState<NodeKind>('model'); const [selectedEdge,setSelectedEdge]=useState<string|null>(null);
  const [allowWrites,setAllowWrites]=useState(false); const [useRelease,setUseRelease]=useState(false);
  const [specText, setSpecText] = useState(''); const [code, setCode] = useState('');
  const [nodeText, setNodeText] = useState(''); const [input, setInput] = useState('{"question": "What can we build together?"}');
  const [mock, setMock] = useState(true); const [result, setResult] = useState<Run | null>(null);
  const [runId, setRunId] = useState<string | null>(null); const [status, setStatus] = useState(t.ready);
  const [busy, setBusy] = useState(false); const [dirty, setDirty] = useState(false);
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const response = await fetch('/api' + path, { ...init, headers: { 'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } });
    if (!response.ok) {
      const body = await response.json();
      if(response.status===409 && /revision changed|release changed|save or reload|project revision/.test(String(body.detail))) throw new Error(words[lang].conflict);
      throw new Error(JSON.stringify(body.detail ?? body));
    }
    return response;
  }, [lang, token]);
  const error = (e: unknown) => setStatus(e instanceof Error ? e.message : String(e));
  const load = (next: Document) => {
    setDoc(next); setNodes(orderedNodes(next.spec).map(([id, config], index) => ({ id, sourcePosition: Position.Right, targetPosition: Position.Left,
      position: next.layout[id] ?? { x: index * 300 + 40, y: 140 }, data: { label: `${id} · ${config.type}`, config } })));
    setEdges(flowEdges(next.spec));
    setSpecText(JSON.stringify(next.spec, null, 2)); setSelected(null);setSelectedEdge(null); setDirty(false); setResult(null);
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
      edges: edges.map(({source,target,data})=>({source,target,...(typeof data?.when==='boolean'?{when:data.when}:{} )})) } };
  };
  const mutate = () => setDirty(true);
  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    setNodes(items => applyNodeChanges(changes, items));
    if (changes.some(change => change.type !== 'select' && change.type !== 'dimensions')) setDirty(true);
  }, []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => { setEdges(items => applyEdgeChanges(changes, items)); setDirty(true); }, []);
  const onConnect = useCallback((connection: Connection) => { const conditional=nodes.find(n=>n.id===connection.source)?.data.config.type==='condition'; setEdges(items => addEdge({...connection,data:conditional?{when:true}:{},label:conditional?'true':undefined}, items)); setDirty(true); }, [nodes]);
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
        setEdges(flowEdges(draft));
        setSelected(null);
      } catch (e) { error(e); return; }
    }
    if(tab!=='spec') setDoc({...doc,spec:currentSpec()});
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
        revision: doc.revision, resources:doc.resources, layout: Object.fromEntries(nodes.map(node => [node.id, node.position])) }) })).json();
      load(next); await refresh(); setStatus(`${t.saved} · r${next.revision}`);
    } catch (e) { error(e); } finally { setBusy(false); }
  };
  const addNode = () => {
    if (!doc) return;
    const id = 'node' + (Math.max(0, ...nodes.map(node => Number(node.id.replace('node', '')) || 0)) + 1);
    const spec=structuredClone(doc.spec);
    if(!['model','agent','tool'].includes(nodeKind)) spec.spec_version='0.2';
    if(['model','agent'].includes(nodeKind)&&!Object.keys(spec.models).length) spec.models.main={binding:'main-model',requires:['text']};
    if(nodeKind==='tool'&&!Object.keys(spec.tools).length) spec.tools.add={plugin:'builtin.add',version:'1'};
    const config = nodeTemplate(nodeKind,Object.keys(spec.models)[0],Object.keys(spec.tools)[0]);
    if(nodeKind==='tool' && spec.tools[config.tool!]?.plugin==='builtin.add') config.inputs={a:{value:1},b:{value:2}};
    setDoc({...doc,spec});
    setNodes(items => [...items, { id, sourcePosition: Position.Right, targetPosition: Position.Left, position: { x: 60 + nodes.length * 260, y: 150 }, data: { label: `${id} · ${nodeKind}`, config } }]);
    mutate();
  };
  const select = (node: FlowNode) => { setSelectedEdge(null);setSelected(node.id); setNodeText(JSON.stringify(node.data.config, null, 2)); };
  const applyNode = (config: NodeSpec) => { setNodes(items => items.map(item => item.id === selected ? { ...item,
    data: { label: `${item.id} · ${config.type}`, config } } : item)); setNodeText(JSON.stringify(config, null, 2)); mutate(); };
  const active = nodes.find(node => node.id === selected);
  const watchRun = async (id:string) => {
    if(poll.current) clearTimeout(poll.current);
    setRunId(id);
    const tick=async()=>{try{const next:Run=await(await api(`/runs/${id}`)).json();setResult(next);
      if(['queued','running','waiting_external'].includes(next.status)) poll.current=setTimeout(tick,600);
      else {setRunId(null);setStatus(next.status);}
    }catch(e){setRunId(null);error(e);}};
    await tick();
  };
  const run = async (versionId?:string) => {
    if (!doc) return;
    try {
      setResult(null); const started = await (await api(`/projects/${doc.id}/runs`, { method: 'POST',
        body: JSON.stringify({ input: JSON.parse(input), revision: doc.revision, mock, allow_writes:allowWrites, ...(versionId?{version_id:versionId}:{use_release:useRelease}) }) })).json();
      setStatus('running');await watchRun(started.run_id);
    } catch (e) { error(e); }
  };
  const exportProject = async (versionId?:string) => {
    if (!doc) return;
    setBusy(true);
    try {
      const response = await api(`/projects/${doc.id}/export?target=${exportTarget}${versionId?`&version_id=${encodeURIComponent(versionId)}`:''}`, { method: 'POST' });
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
      <label className="new-project import-project">{lang==='zh'?'导入工程 ZIP':'Import project ZIP'}<input aria-label="Import project ZIP" type="file" accept=".zip" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{const item=await(await api('/import/inspect',{method:'POST',headers:{'Content-Type':'application/zip'},body:file})).json();setImported(item);setImportId(item.spec.id+'-import');}catch(err){error(err);}e.target.value='';}}/></label>
      <div className="sidebar-bottom"><p>{t.pending}</p><details><summary>{t.settings}</summary>
        <input aria-label={t.token} placeholder={t.token} type="password" value={token} onChange={e => setToken(e.target.value)} />
        <button onClick={() => refresh().then(items => { if (items.length) load(items[0]); }).catch(error)}>{t.reload}</button>
      </details><span className="stage">ALPHA · 0.1</span><button className="language" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>中文 / EN</button></div>
    </aside>
    <main><header><div><span className="eyebrow">AGENT WORKSPACE</span><h1>{doc?.id ?? 'EvoSprig'}{dirty && <span className="unsaved"> ●</span>}</h1></div>
      <div className="actions"><button onClick={() => doc && api(`/projects/${doc.id}`).then(r => r.json()).then(load).catch(error)} disabled={!doc || !!runId}>{t.reload}</button>
        <button onClick={save} disabled={!doc || busy || !!runId}>{t.save}</button><select aria-label="Export target" value={exportTarget} onChange={e=>setExportTarget(e.target.value)}><option value="python">Python</option><option value="http">HTTP service</option><option value="container">Container</option></select><button className="primary" onClick={()=>exportProject()} disabled={!doc || dirty || busy}>{exportTarget==='python'?t.export:(lang==='zh'?'导出 ':'Export ')+exportTarget} ↗</button></div></header>
      {imported&&<section className="panel"><h2>{lang==='zh'?'检查导入工程':'Review imported project'}</h2><p>{lang==='zh'?'已校验规格、资源和文件哈希。外部服务需要在部署配置中绑定。':'Spec, resources and file hashes verified. Bind external services in your deployment profile.'}</p><label>Project ID<input aria-label="Imported project ID" value={importId} onChange={e=>setImportId(e.target.value)}/></label><pre className="json-block">{JSON.stringify(imported.report,null,2)}</pre><button onClick={async()=>{try{const created=await(await api('/projects',{method:'POST',body:JSON.stringify({spec:{...imported.spec,id:importId},resources:imported.resources})})).json();load(created);await refresh();setImported(null);}catch(e){error(e);}}}>{lang==='zh'?'创建导入项目':'Create imported project'}</button><button onClick={()=>setImported(null)}>{lang==='zh'?'关闭':'Close'}</button></section>}
      {!doc ? <div className="empty"><span>↟</span><h2>{t.empty}</h2></div> : <>
        <nav className="tabs">{(['canvas','spec','code','resources','runs','memory','improve','versions'] as const).map(key => <button key={key} className={tab === key ? 'selected' : ''} onClick={() => chooseTab(key)}>{t[key]}</button>)}
          <span className="revision">r{doc.revision} · {doc.spec_hash.slice(0, 12)}</span></nav>
        {tab==='resources' ? <ResourcesPanel key={doc.id} doc={{...doc,spec:currentSpec()}} api={api} lang={lang} onError={error} onChange={next=>{setDoc(next);setNodes(items=>items.map(node=>({...node,data:{...node.data,config:next.spec.graph.nodes[node.id]}})));mutate();}}/>
        :tab==='memory'?<MemoryPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error}/>
        :tab==='runs'?<RunsPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error}/>
        :tab==='improve'?<ImprovePanel key={doc.id} doc={doc} api={api} lang={lang} onError={error} dirty={dirty}/>
        :tab==='versions'?<VersionsPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error} onExport={exportProject} onRun={run}/>
        :<div className="editor">
          <section className="workspace">
            {tab === 'canvas' ? <><div className="canvas-tools"><select aria-label="New node type" value={nodeKind} onChange={e=>setNodeKind(e.target.value as NodeKind)}>{(['model','agent','tool','transform','condition','join','loop','parallel','human'] as const).map(kind=><option key={kind}>{kind}</option>)}</select><button onClick={addNode}>＋ {nodeKind==='model'?t.add:(lang==='zh'?'添加节点':'Add node')}</button><button onClick={() => { const order = orderedNodes(currentSpec()).map(([id]) => id); setNodes(items => items.map(node => ({ ...node, position: { x: order.indexOf(node.id) * 280 + 40, y: 150 } }))); mutate(); }}>{t.layout}</button></div>
              <ReactFlow key={`${doc.id}:${doc.revision}`} nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, node) => select(node)} onEdgeClick={(_,edge)=>{setSelectedEdge(edge.id);setSelected(null);}} fitView fitViewOptions={{ padding: 0.3, maxZoom: 1 }} minZoom={0.2} maxZoom={2} deleteKeyCode="Delete"><Background color="#d6dfd7" gap={22}/><Controls/><MiniMap nodeColor="#c2d9bf"/></ReactFlow></>
              : tab === 'spec' ? <textarea className="source-editor" aria-label="AgentSpec JSON" value={specText} onChange={e => { setSpecText(e.target.value); mutate(); }} spellCheck={false}/>
                : <pre className="source-editor code-view">{dirty ? `${t.runHint}\n\n` : ''}{code}</pre>}
          </section>
          <aside className="inspector"><div className="section-label">{t.node}</div>
            {selectedEdge&&<label>{lang==='zh'?'分支条件':'Branch condition'}<select aria-label="Edge condition" value={typeof edges.find(edge=>edge.id===selectedEdge)?.data?.when==='boolean'?String(edges.find(edge=>edge.id===selectedEdge)?.data?.when):'always'} onChange={e=>{const value=e.target.value;setEdges(items=>items.map(edge=>edge.id===selectedEdge?{...edge,data:{when:value==='always'?undefined:value==='true'},label:value==='always'?undefined:value}:edge));mutate();}}><option value="always">{lang==='zh'?'始终执行':'Always'}</option><option value="true">true</option><option value="false">false</option></select></label>}
            {active ? <><h3>{active.id}<span className="pill">{active.data.config.type}</span></h3>
              {typeof active.data.config.instructions === 'string' && ['model','agent'].includes(active.data.config.type) && <label>{t.instructions}<textarea aria-label={t.instructions} value={active.data.config.instructions} onChange={e => applyNode({ ...active.data.config, instructions: e.target.value })}/></label>}
              {active.data.config.model && <label>{t.binding}<select value={active.data.config.model} onChange={e => applyNode({ ...active.data.config, model: e.target.value })}>{Object.keys(doc.spec.models).map(name => <option key={name}>{name}</option>)}</select></label>}
              <label>{t.nodeJson}<textarea className="node-json" aria-label={t.nodeJson} value={nodeText} onChange={e => setNodeText(e.target.value)}/></label>
              <button onClick={() => { try { applyNode(JSON.parse(nodeText)); } catch (e) { error(e); } }}>{t.apply}</button></> : <p className="muted">{lang === 'zh' ? '选择节点查看参数。拖动端口连接节点；在规格页编辑输入输出和工具。' : 'Select a node to edit its settings. Connect nodes by dragging handles; edit inputs, outputs and tools in Spec.'}</p>}
            <div className="divider"/><div className="section-label">{t.input}</div><label><textarea aria-label={t.input} value={input} onChange={e => setInput(e.target.value)}/></label>
            <select aria-label="Run mode" value={mock ? 'mock' : 'live'} onChange={e => setMock(e.target.value === 'mock')}><option value="mock">{t.offline}</option><option value="live">{t.live} · deepseek-flash</option></select>
            <label className="check"><input type="checkbox" checked={allowWrites} onChange={e=>setAllowWrites(e.target.checked)}/>{lang==='zh'?'允许已配置的写入工具':'Allow configured write tools'}</label>
            <label className="check"><input type="checkbox" checked={useRelease} onChange={e=>setUseRelease(e.target.checked)}/>{lang==='zh'?'运行发布版本':'Run active release'}</label>
            <button className="primary run" onClick={()=>run()} disabled={dirty || !!runId}>▷ {t.run}</button>
            {runId && <button onClick={() => api(`/runs/${runId}/cancel`, { method: 'POST' }).catch(error)}>{t.cancel}</button>}
            <p className="hint">{t.runHint}</p>
          </aside>
        </div>}
        <section className="results"><div className="section-label">{t.output}<span>{result ? String(result.status) : '—'}</span></div>
          {result && <RunDetails key={result.run_id} run={result} api={api} lang={lang} onError={error} onRefresh={()=>watchRun(result.run_id)}/> }
        </section>
      </>}
      <footer role="status"><span className="dot"/>{status}</footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
