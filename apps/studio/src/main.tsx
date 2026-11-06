import {NodeFields,WorkflowFields} from './node-fields';
import {DefaultModel,ModelsPanel} from './model-connections';
import { ServicesPanel } from "./services-panel";
import { version as studioVersion } from '../package.json';
import { AgentSettings } from './agent-settings';
import { DebugPanel } from './debug-panel';
import type {DebugTarget} from './run-steps';
import { ComfyImport } from './comfy-import';
import { RenderGraph } from './render-graph';
import { edgeTypes } from './workflow-edge';
import { StrictMode, useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Background, Controls, MiniMap, Position, addEdge, applyEdgeChanges, applyNodeChanges,
  type Edge, type Connection, type NodeChange, type EdgeChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './style.css';
import './workspace-settings.css';
import { orderedNodes, starter, nodeTemplate, initialInput, type Document, type NodeSpec, type NodeKind, type Spec, type Run } from './types';
import { arrange, canvasView, childGraphs, cleanGroups, graphAt, graphEdges, layoutKey, leaves, pathKey, withGraph, type CanvasState, type FlowNode } from './canvas';
import { useDraftGuard } from './draft-guard';
import { Icon, FitWorkflowView, nodeTypes, tabIcons } from './studio-ui';
import { ResourcesPanel, MemoryPanel, RunsPanel, RunDetails, ImprovePanel, VersionsPanel } from './panels';

type Tab = 'canvas'|'spec'|'code'|'resources'|'runs'|'memory'|'improve'|'versions';



const words = {
  zh: { projects: '工作空间', create: '新建项目', canvas: '画布', spec: '规格', code: 'Python',
    save: '保存', reload: '重新加载', run: '运行', cancel: '取消运行', export: '导出 Python',
    offline: '离线演示', live: '真实模型', node: '节点设置', input: '运行输入', output: '结果与事件',
    add: '添加模型节点', layout: '自动排列', instructions: '指令', binding: '模型引用',
    mappings: '输入映射（JSON）', nodeJson: '完整节点（JSON）', apply: '应用修改',
    empty: '创建项目，从一个可运行的智能体开始。', subtitle: '搭建 · 运行 · 带走',
    saved: '已保存', conflict: '版本冲突：本地修改已保留。请复制规格，再重新加载比较。',
    ready: '准备就绪', runHint: '运行和导出使用已保存版本；先保存当前修改。',
    settings: '连接', token: 'API 访问令牌（可选）', pending: '构建 · 评测 · 自进化', resources:'资源', runs:'历史', memory:'记忆与资料', improve:'自进化', versions:'版本',
  },
  en: { projects: 'WORKSPACE', create: 'New project', canvas: 'Canvas', spec: 'Spec', code: 'Python',
    save: 'Save', reload: 'Reload', run: 'Run', cancel: 'Cancel run', export: 'Export Python',
    offline: 'Offline demo', live: 'Live model', node: 'Node settings', input: 'Run input', output: 'Results and events',
    add: 'Add model node', layout: 'Arrange', instructions: 'Instructions', binding: 'Model reference',
    mappings: 'Input mappings (JSON)', nodeJson: 'Full node (JSON)', apply: 'Apply changes',
    empty: 'Create a project and start with a runnable agent.', subtitle: 'Build · Run · Take it with you',
    saved: 'Saved', conflict: 'Revision conflict: your edits are preserved. Copy the spec, then reload to compare.',
    ready: 'Ready', runHint: 'Run and export use the saved version. Save your edits first.',
    settings: 'Connection', token: 'API access token (optional)', pending: 'Build · Evaluate · Improve', resources:'Resources', runs:'History', memory:'Memory', improve:'Improve', versions:'Versions',
  },
};

function App() {
  const [lang, setLang] = useState<'zh' | 'en'>(() => { try { return localStorage.getItem('evosprig.language') === 'zh' ? 'zh' : 'en'; } catch { return 'en'; } }); const t = words[lang];
  useEffect(() => { document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'; try { localStorage.setItem('evosprig.language', lang); } catch { /* Storage can be disabled by the browser. */ } }, [lang]);
  const [token, setToken] = useState('');
  const [projectQuery,setProjectQuery]=useState('');
  const [projectName,setProjectName]=useState('');
  const [sidebarOpen,setSidebarOpen]=useState(false);
  const [exportTarget,setExportTarget]=useState('python');
  const [imported,setImported]=useState<{spec:Spec;resources:Record<string,string>;report:{documents?:Record<string,unknown>}}|null>(null);
  const [importId,setImportId]=useState('');
  const [projects, setProjects] = useState<Document[]>([]);
  const [doc, setDoc] = useState<Document | null>(null);
  const projectLoaded = useRef(false);
  const projectListRequest = useRef(0);
  const runWatch = useRef(0);
  const runStarting = useRef(false);
  const [nodes, setNodes] = useState<FlowNode[]>([]); const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('canvas');
  const [newNodeName,setNewNodeName]=useState('');
  const [workflowSettings,setWorkflowSettings]=useState(false);
  const [nodeKind,setNodeKind]=useState<NodeKind>('model'); const [selectedEdge,setSelectedEdge]=useState<string|null>(null);
  const [allowWrites,setAllowWrites]=useState(false); const [useRelease,setUseRelease]=useState(false);
  const [specText, setSpecText] = useState(''); const [code, setCode] = useState('');
  const [nodeText, setNodeText] = useState(''); const [nodeDraftDirty, setNodeDraftDirty] = useState(false); const [input, setInput] = useState('{"question": "What can we build together?"}');
  const [mock, setMock] = useState(true); const [result, setResult] = useState<Run | null>(null);
  const [runId, setRunId] = useState<string | null>(null); const [status, setStatus] = useState(t.ready);
  const [busy, setBusy] = useState(false); const [dirty, setDirty] = useState(false);
  const [canvasFit,setCanvasFit]=useState(0);
  const [canvasFocus,setCanvasFocus]=useState(false);
  useEffect(()=>{const exit=(event:KeyboardEvent)=>{if(event.key==='Escape')setCanvasFocus(false);};window.addEventListener('keydown',exit);return()=>window.removeEventListener('keydown',exit);},[]);
  const [graphPath,setGraphPath]=useState<string[]>([]);
  const [canvas,setCanvas]=useState<CanvasState>({groups:{}});
  const [groupSelection,setGroupSelection]=useState<string[]>([]);
  const [debugOpen,setDebugOpen]=useState(false);
  const [debugSource,setDebugSource]=useState<DebugTarget>();
  const [comfyOpen,setComfyOpen]=useState(false);
  const [renderGraphOpen,setRenderGraphOpen]=useState(false);
  const groups=useMemo(()=>cleanGroups(canvas.groups[pathKey(graphPath)]??[],nodes.map(n=>n.id)),[canvas,graphPath,nodes]);
  const debugNodes=Array.from(new Set([...nodes.filter(n=>n.selected).map(n=>n.id),...groupSelection.flatMap(id=>leaves(id,groups)),...(selected?[selected]:[])]));
  const setGroups=(next:typeof groups)=>{setCanvas(state=>({...state,groups:{...state.groups,[pathKey(graphPath)]:next}}));setDirty(true);};
  const view=useMemo(()=>canvasView(nodes,edges,groups,lang,id=>setGroups(groups.map(g=>g.id===id?{...g,collapsed:!g.collapsed}:g)),(id,path)=>navigate([...graphPath,id,...path])),[nodes,edges,groups,lang,graphPath,doc,busy]);
  const displayNodes=view.nodes.map(n=>{
    const config=n.type==='workflow'?n.data.config as NodeSpec:undefined;
    const promptPreview=typeof config?.instructions==='object'?doc?.resources?.[config.instructions.resource]:undefined;
    return {...n,data:{...n.data,busy,promptPreview,toolPlugins:doc?.spec.tools},...(n.type==='groupCard'?{selected:groupSelection.includes(n.id)}:{})};
  });
  const currentLayout=()=>({...doc?.layout,...Object.fromEntries(nodes.map(n=>[layoutKey(graphPath,n.id),n.position]))});
  const loadGraph=(spec:Spec,path:string[],layout:Document['layout'])=>{
    setDebugSource(undefined);
    const graph=graphAt(spec,path);
    setNodes(orderedNodes({...spec,graph}).map(([id,config],index)=>({id,sourcePosition:Position.Right,targetPosition:Position.Left,
      position:layout[layoutKey(path,id)]??{x:index*330+40,y:150},data:{label:id,config}})));
    setEdges(graphEdges(graph));setGraphPath(path);setSelected(null);setSelectedEdge(null);setGroupSelection([]);setNodeDraftDirty(false);
  };
  const navigate=(path:string[])=>{
    if(!doc||busy||!commitNodeDraft())return;
    try {const spec=currentSpec(),layout=currentLayout();setDoc({...doc,spec,layout});loadGraph(spec,path,layout);}catch(e){error(e);}
  };
  const groupSelected=()=>{
    const members=[...nodes.filter(n=>n.selected).map(n=>n.id),...groupSelection];
    if(!members.length)return;
    const parents=members.map(id=>groups.find(g=>g.members.includes(id))?.id);
    if(parents.some(p=>p!==parents[0])){setStatus(lang==='zh'?'请选择同一层级的节点或分组。':'Select nodes or groups at the same level.');return;}
    const id='group:g'+Date.now().toString(36);
    setGroups([...groups.map(g=>g.id===parents[0]?{...g,members:[...g.members.filter(m=>!members.includes(m)),id]}:g),{id,label:lang==='zh'?'新分组':'New group',members,collapsed:false}]);
    setNodes(items=>items.map(n=>({...n,selected:false})));setGroupSelection([id]);setSelected(null);
  };
  const ungroup=(id:string)=>{const target=groups.find(g=>g.id===id)!;setGroups(groups.filter(g=>g.id!==id).map(g=>({...g,members:g.members.flatMap(m=>m===id?target.members:[m])})));setGroupSelection([]);};
  const visibleProjects=projects.filter(project=>project.id.toLowerCase().includes(projectQuery.toLowerCase()));
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!sidebarOpen) return;
    const media = window.matchMedia('(max-width: 760px)');
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => Array.from(sidebarRef.current?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), summary, [tabindex="0"]',
    ) ?? []).filter(element => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setSidebarOpen(false); }
      if (event.key === 'Tab') {
        const elements = focusable();
        const target = event.shiftKey ? elements.at(-1) : elements[0];
        const boundary = event.shiftKey ? elements[0] : elements.at(-1);
        if (document.activeElement === boundary) { event.preventDefault(); target?.focus(); }
      }
    };
    const onResize = () => { if (!media.matches) setSidebarOpen(false); };
    document.addEventListener('keydown', onKeyDown);
    media.addEventListener('change', onResize);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
      media.removeEventListener('change', onResize);
      menuRef.current?.focus();
    };
  }, [sidebarOpen]);

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
  const load = (next: Document, path:string[] = [], preserveNode:string|null = null) => {
    projectLoaded.current = true;
    runWatch.current++;
    if (poll.current) clearTimeout(poll.current);
    setRunId(null);
    setSidebarOpen(false); setDoc(next);setCanvas({groups:next.canvas?.groups??{}});
    try{graphAt(next.spec,path);}catch{path=[];}
    loadGraph(next.spec,path,next.layout);
    const savedNode=preserveNode?graphAt(next.spec,path).nodes[preserveNode]:undefined;
    if(savedNode){setSelected(preserveNode);setNodeText(JSON.stringify(savedNode,null,2));}
    if(next.id!==doc?.id) setInput(JSON.stringify(initialInput(next.spec.input_schema),null,2));
    setSpecText(JSON.stringify(next.spec, null, 2));setDirty(false);setResult(null);
  };
  const refresh = useCallback(async () => {
    const request = ++projectListRequest.current;
    const items: Document[] = await (await api('/projects')).json();
    if (request === projectListRequest.current) setProjects(items);
    return items;
  }, [api]);
  useEffect(() => {
    let active = true;
    refresh().then(items => {
      if (active && !projectLoaded.current && items.length) load(items[0]);
    }).catch(e => { if (active) error(e); });
    return () => { active = false; };
  }, []);
  useEffect(() => () => { runWatch.current++; if (poll.current) clearTimeout(poll.current); }, []);
  const currentSpec = (includeDraft = true): Spec => {
    if (!doc) throw new Error('Select a project');
    return withGraph(doc.spec,graphPath,{ ...graphAt(doc.spec,graphPath),
      entry:nodes.some(n=>n.id===graphAt(doc.spec,graphPath).entry)?graphAt(doc.spec,graphPath).entry:(nodes[0]?.id??''),
      nodes: Object.fromEntries(nodes.map(node => [node.id, includeDraft && node.id === selected && nodeDraftDirty ? parseNodeDraft() : node.data.config])),
      edges: edges.map(({source,target,data})=>({source,target,...(typeof data?.when==='boolean'?{when:data.when}:{} )})) });
  };
  const parseNodeDraft = (): NodeSpec => {
    const value = JSON.parse(nodeText);
    if (!value || typeof value !== 'object' || Array.isArray(value) || typeof value.type !== 'string') {
      throw new Error(lang === 'zh' ? '节点 JSON 必须是包含 type 的对象。' : 'Node JSON must be an object with a type.');
    }
    return value;
  };
  const commitNodeDraft = () => {
    if (!nodeDraftDirty) return true;
    try { applyNode(parseNodeDraft()); return true; } catch (e) { error(e); return false; }
  };
  const mutate = () => setDirty(true);
  const onNodesChange = (changes: NodeChange[]) => {
    const regular=changes.filter(c=>!('id' in c)||!c.id.startsWith('group:')) as NodeChange<FlowNode>[];
    setNodes(items=>{
      let next=applyNodeChanges(regular,items);
      for(const change of changes){if(!('id' in change)||!change.id.startsWith('group:'))continue;
        if(change.type==='position'&&change.position){const before=view.boxes.get(change.id);if(before){const ids=leaves(change.id,groups);next=next.map(n=>ids.includes(n.id)?{...n,position:{x:n.position.x+change.position!.x-before.x,y:n.position.y+change.position!.y-before.y}}:n);}}
      }return next;
    });
    for(const c of changes){if(!('id' in c)||!c.id.startsWith('group:'))continue;
      if(c.type==='select')setGroupSelection(ids=>c.selected?[...new Set([...ids,c.id])]:ids.filter(id=>id!==c.id));
      if(c.type==='remove')ungroup(c.id);
    }
    if(changes.some(c=>{
      if(c.type==='select'||c.type==='dimensions')return false;
      if(c.type==='position'){const before=view.boxes.get(c.id);return !!c.position&&!!before&&(c.position.x!==before.x||c.position.y!==before.y);}
      return true;
    }))setDirty(true);
  };
  const onEdgesChange = (changes: EdgeChange[]) => { setEdges(items => applyEdgeChanges(changes.filter(c=>c.type!=='remove'||view.edges.find(e=>e.id===c.id)?.deletable!==false), items)); if (changes.some(change => change.type !== 'select')) setDirty(true); };
  const onConnect = (connection: Connection) => {
    if(connection.source.startsWith('group:')||connection.target.startsWith('group:')){setStatus(lang==='zh'?'展开分组后连接具体节点。':'Expand the group to connect its nodes.');return;}
    const conditional=nodes.find(n=>n.id===connection.source)?.data.config.type==='condition';
    setEdges(items => addEdge({...connection,type:'smoothstep',data:conditional?{when:connection.sourceHandle!=='false'}:{},label:conditional?String(connection.sourceHandle!=='false'):undefined},items));setDirty(true);
  };
  const chooseTab = async (next: typeof tab) => {
    if (!doc || busy || !commitNodeDraft()) return;
    if (tab === 'spec' && next !== 'spec') {
      try {
        const draft: Spec = JSON.parse(specText);
        if (draft.id !== doc.id || !draft.graph?.nodes || !Array.isArray(draft.graph.edges)) throw new Error('Invalid project shape or changed project ID');
        const layout=currentLayout();setDoc({...doc,spec:draft,layout});
        loadGraph(draft,[],layout);
      } catch (e) { error(e); return; }
    }
    if(tab!=='spec') setDoc({...doc,spec:currentSpec()});
    if (next === 'spec') setSpecText(JSON.stringify(currentSpec(), null, 2));
    if (next === 'code') {
      try { setCode((await (await api(`/projects/${doc.id}/code`)).json()).code); } catch (e) { error(e); }
    }
    setTab(next);
  };
  const tidyCanvas=(spec:Spec):CanvasState=>({groups:Object.fromEntries(Object.entries(canvas.groups).flatMap(([key,value])=>{
    try{return [[key,cleanGroups(value,Object.keys(graphAt(spec,key.split('/').slice(1)).nodes))]];}catch{return [];}
  }))});
  const save = async (): Promise<boolean> => {
    if (!doc) return false;
    const invalid=document.querySelector<HTMLInputElement|HTMLTextAreaElement>('.editor input:invalid,.editor textarea:invalid');
    if(invalid){invalid.reportValidity();setStatus(lang==='zh'?'请先修正标记的字段。':'Correct the marked field before saving.');return false;}
    setBusy(true);
    try {
      const spec = tab === 'spec' ? JSON.parse(specText) : currentSpec();
      const next = await (await api(`/projects/${doc.id}`, { method: 'PUT', body: JSON.stringify({ spec,
        revision: doc.revision, resources:doc.resources, layout: currentLayout(), canvas: tidyCanvas(spec) }) })).json();
      load(next,graphPath,selected); await refresh(); setStatus(`${t.saved} · r${next.revision}`); return true;
    } catch (e) { error(e); return false; } finally { setBusy(false); }
  };
  const { guard, prompt } = useDraftGuard(dirty || nodeDraftDirty, save, status, lang);
  const replaceProject = (action: () => void | Promise<unknown>) => {
    setSidebarOpen(false);
    guard(async () => {
      setBusy(true);
      try { await action(); } finally { setBusy(false); }
    });
  };
  const addNode = () => {
    if (!doc) return;
    const id = newNodeName.trim() || 'node' + (Math.max(0, ...nodes.map(node => Number(node.id.replace('node', '')) || 0)) + 1);
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)||nodes.some(n=>n.id===id)){setStatus(lang==='zh'?'节点名需为英文标识，且不能重复。':'Choose a unique node identifier.');return;}
    if(!commitNodeDraft())return;
    const spec=structuredClone(currentSpec());
    if(nodeKind==='map') spec.spec_version='0.3';
    else if(!['model','agent','tool'].includes(nodeKind) && spec.spec_version==='0.1') spec.spec_version='0.2';
    if(['model','agent'].includes(nodeKind)&&!Object.keys(spec.models).length) spec.models.main={binding:'main-model',requires:['text']};
    if(nodeKind==='tool'&&!Object.keys(spec.tools).length) spec.tools.add={plugin:'builtin.add',version:'1'};
    const config = nodeTemplate(nodeKind,spec.models.main?'main':Object.keys(spec.models)[0],Object.keys(spec.tools)[0]);
    if(nodeKind==='tool' && spec.tools[config.tool!]?.plugin==='builtin.add') config.inputs={a:{value:1},b:{value:2}};
    const resources={...doc.resources};
    if(nodeKind==='code'){
      spec.spec_version='0.3';
      let alias='python';while(spec.tools[alias]&&spec.tools[alias].plugin!=='code.python')alias+='_';
      spec.tools[alias]={plugin:'code.python',version:'1'};
      let resource=Object.keys(spec.resources).find(key=>spec.resources[key].role==='code');
      if(!resource){resource=id+'_code';while(spec.resources[resource])resource+='_';spec.resources[resource]={path:`code/${resource}.py`,role:'code'};resources[resource]='def run(inputs):\n    return inputs\n';}
      config.tool=alias;config.code=resource;
    }
    setDoc({...doc,spec,resources});
    setNodes(items => [...items, { id, sourcePosition: Position.Right, targetPosition: Position.Left, position: { x: 60 + nodes.length * 260, y: 150 }, data: { label: `${id} · ${nodeKind}`, config } }]);
    setNewNodeName('');setSelected(id);setNodeText(JSON.stringify(config,null,2));setNodeDraftDirty(false);setWorkflowSettings(false);setCanvasFit(n=>n+1);
    mutate();
  };
  const select = (node: FlowNode) => { setWorkflowSettings(false); if (node.id === selected || !commitNodeDraft()) return; setDebugSource(undefined);setSelectedEdge(null);setSelected(node.id); setNodeText(JSON.stringify(node.data.config, null, 2)); };
  const applyNode = (config: NodeSpec) => { setNodes(items => items.map(item => item.id === selected ? { ...item,
    data: { label: `${item.id} · ${config.type}`, config } } : item)); setNodeText(JSON.stringify(config, null, 2)); setNodeDraftDirty(false); mutate(); };
  const active = nodes.find(node => node.id === selected);
  const watchRun = async (id:string) => {
    const request = ++runWatch.current;
    if(poll.current) clearTimeout(poll.current);
    setRunId(id);
    let after=0;let collected:Run['events']=[];
    const tick=async()=>{try{const next:Run=await(await api(`/runs/${id}?after=${after}`)).json();
      if(request!==runWatch.current)return;
      collected=[...collected,...next.events];after=Number(collected.at(-1)?.sequence??0);
      setResult({...next,events:collected});
      if(['queued','running','waiting_external'].includes(next.status)) poll.current=setTimeout(tick,600);
      else {setRunId(null);setStatus(next.status);}
    }catch(e){if(request===runWatch.current){setRunId(null);error(e);}}};
    await tick();
  };
  const run = async (versionId?:string) => {
    if (!doc || busy || runId || runStarting.current) return;
    runStarting.current = true;
    setBusy(true);
    try {
      setResult(null); const started = await (await api(`/projects/${doc.id}/runs`, { method: 'POST',
        body: JSON.stringify({ input: JSON.parse(input), revision: doc.revision, mock, allow_writes:allowWrites, ...(versionId?{version_id:versionId}:{use_release:useRelease}) }) })).json();
      setStatus('running');await watchRun(started.run_id);
    } catch (e) { error(e); } finally { runStarting.current = false; setBusy(false); }
  };
  const debugStep=(target:DebugTarget)=>{
    if(!doc||busy||runId)return;
    if(dirty||nodeDraftDirty){setStatus(lang==='zh'?'先保存修改，再使用历史输入调试。':'Save your changes before debugging with saved inputs.');return;}
    try{
      const node=graphAt(doc.spec,target.path).nodes[target.name];
      if(!node)throw new Error(lang==='zh'?'当前项目中已没有这个节点。':'This node is no longer in the current project.');
      loadGraph(doc.spec,target.path,currentLayout());setSelected(target.name);setNodeText(JSON.stringify(node,null,2));
      setDebugSource(target);setDebugOpen(true);setCanvasFocus(false);setTab('canvas');
    }catch(e){error(e);}
  };
  const exportProject = async (versionId?:string) => {
    if (!doc) return;
    setBusy(true);
    try {
      if(exportTarget==='comfy'){const response=await api(`/projects/${doc.id}/comfy/export`);const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=doc.id+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),60_000);return;}
      const response = await api(`/projects/${doc.id}/export?target=${exportTarget}${versionId?`&version_id=${encodeURIComponent(versionId)}`:''}`, { method: 'POST' });
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a');
      link.href = url; link.download = `${doc.id}.zip`; link.hidden = true;
      document.body.appendChild(link); link.click(); link.remove();
      // Keep the blob alive while the browser hands the download to a slow filesystem.
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) { error(e); } finally { setBusy(false); }
  };

  return <div className={`app${sidebarOpen?' sidebar-open':''}${canvasFocus&&tab==='canvas'?' canvas-focus':''}`}>
    <button className="sidebar-scrim" tabIndex={-1} aria-label={lang==='zh'?'关闭项目导航':'Close project navigation'} onClick={()=>setSidebarOpen(false)}/>
    <aside ref={sidebarRef} id="project-navigation" className="sidebar" aria-label={lang==='zh'?'项目导航':'Project navigation'}>
      <div className="brand"><span className="brand-mark"><svg width="20" height="24" viewBox="0 0 36 46" fill="none" aria-hidden="true"><path d="M18 42V18M18 30C4 30 3 20 4 13c12 0 16 6 14 17ZM18 21C31 21 34 10 31 3c-12 2-15 8-13 18Z" stroke="currentColor" strokeWidth="3" strokeLinejoin="round"/></svg></span><span>EvoSprig</span><span className="brand-edition">Studio</span><button className="mobile-close icon-button" aria-label={lang==='zh'?'关闭项目导航':'Close project navigation'} onClick={()=>setSidebarOpen(false)}><Icon name="close"/></button></div>
      <div className="workspace-name"><span className="workspace-avatar">E</span><div><strong>{lang==='zh'?'我的工作空间':'My workspace'}</strong><small>{lang==='zh'?'本地项目':'Local projects'}</small></div></div>
      <label className="project-search"><Icon name="search"/><input aria-label="Search projects" placeholder={lang==='zh'?'搜索项目…':'Search projects…'} value={projectQuery} onChange={e=>setProjectQuery(e.target.value)}/></label>
      <div className="sidebar-section"><span>{lang==='zh'?'项目':'Projects'}</span><span>{projects.length}</span></div>
      <div className="projects">{visibleProjects.map(item => <button key={item.id} className={doc?.id === item.id ? 'project active' : 'project'} aria-current={doc?.id===item.id?'page':undefined} title={item.id}
        disabled={!!runId || busy} onClick={() => { if(item.id===doc?.id){setSidebarOpen(false);return;} replaceProject(async () => { try { load(await (await api(`/projects/${item.id}`)).json()); } catch (e) { error(e); } }); }}>
        <Icon name="folder"/><span className="project-name">{item.id}</span><small>r{item.revision}</small></button>)}{!visibleProjects.length&&<p className="sidebar-empty">{lang==='zh'?(projectQuery?'没有匹配的项目':'创建第一个项目'):(projectQuery?'No matching projects':'Create your first project')}</p>}</div>
      <div className="project-actions"><input className="new-project-name" aria-label="New project name" placeholder={lang==='zh'?'新工程名称（可选）':'New project name (optional)'} value={projectName} onChange={e=>setProjectName(e.target.value)}/><button className="new-project" aria-label={'＋ '+t.create} disabled={!!runId || busy} onClick={() => replaceProject(async () => {
        try { const id = projectName.trim() || `agent-${Date.now().toString(36)}`; if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id))throw Error(lang==='zh'?'工程名需以英文字母开头。':'Start the project name with a letter.');setProjectName(''); setProjectQuery(''); load(await (await api('/projects', { method: 'POST', body: JSON.stringify({ spec: starter(id) }) })).json()); await refresh(); }
        catch (e) { error(e); }
      })}><Icon name="plus"/>{t.create}</button>
      <label className="new-project import-project"><Icon name="upload"/>{lang==='zh'?'导入工程':'Import project'}<input aria-label="Import project ZIP" type="file" accept=".zip" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{const item=await(await api('/import/inspect',{method:'POST',headers:{'Content-Type':'application/zip'},body:file})).json();setImported(item);setImportId(item.spec.id+'-import');setSidebarOpen(false);}catch(err){error(err);}e.target.value='';}}/></label></div>
      <button className="new-project" disabled={busy||!!runId} onClick={()=>{setComfyOpen(true);setSidebarOpen(false);}}>ComfyUI · {lang==='zh'?'导入工作流':'Import workflow'}</button><div className="sidebar-bottom"><details className="connection-settings"><summary><Icon name="settings"/>{t.settings}</summary>
        <input aria-label={t.token} placeholder={t.token} type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} />
        <button disabled={busy || !!runId} onClick={() => replaceProject(() => refresh().then(items => { if (items.length) load(items[0]); }).catch(error))}>{t.reload}</button>
      </details>{doc&&<DefaultModel api={api} lang={lang} doc={doc} onChange={models=>{if(!commitNodeDraft())return;setDoc({...doc,spec:{...currentSpec(),models}});mutate();}}/>}<ModelsPanel api={api} lang={lang}/><ServicesPanel api={api} lang={lang}/><div className="sidebar-meta"><span>v{studioVersion}</span><button className="language" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>中文 / EN</button></div></div>
    </aside>
    <main inert={sidebarOpen}><header className="app-header"><div className="project-heading"><button ref={menuRef} className="mobile-menu icon-button" aria-controls="project-navigation" aria-expanded={sidebarOpen} aria-label={lang==='zh'?'打开项目导航':'Open project navigation'} onClick={()=>setSidebarOpen(true)}><Icon name="menu"/></button><span className="breadcrumb">{lang==='zh'?'项目':'Projects'}<Icon name="arrow" size={12}/></span><h1 title={doc?.id}>{doc?.id ?? 'EvoSprig'}</h1>{doc&&<span className={`save-state${dirty || nodeDraftDirty?' is-dirty':''}`}>{dirty || nodeDraftDirty?(lang==='zh'?'未保存':'Unsaved'):(lang==='zh'?'已保存':'Saved')}</span>}</div>
      <div className="actions"><button className="reload-button icon-button" aria-label={t.reload} title={t.reload} onClick={() => replaceProject(async () => { if (doc) await api(`/projects/${doc.id}`).then(r => r.json()).then(load).catch(error); })} disabled={!doc || !!runId || busy}><Icon name="refresh"/></button>
        <button onClick={save} disabled={!doc || busy || !!runId}>{t.save}</button><span className="action-separator"/><select aria-label="Export target" value={exportTarget} onChange={e=>setExportTarget(e.target.value)}><option value="python">Python</option><option value="http">HTTP service</option><option value="container">Container</option>{doc&&Object.values(doc.spec.tools).some(tool=>tool.plugin.startsWith('comfy.node.'))&&<option value="comfy">ComfyUI JSON</option>}</select><button className="export-button" aria-label={(exportTarget==='python'?t.export:(lang==='zh'?'导出 ':'Export ')+exportTarget)+' ↗'} onClick={()=>exportProject()} disabled={!doc || dirty || nodeDraftDirty || busy}><Icon name="download"/>{lang==='zh'?'导出':'Export'}</button></div></header>
      {doc&&Object.values(doc.spec.tools).some(tool=>tool.plugin==='film.recipe'||tool.plugin.endsWith('.recipe'))&&<button className="render-graph-launch" disabled={dirty||nodeDraftDirty||!!runId} onClick={()=>setRenderGraphOpen(true)}>{lang==='zh'?'展开渲染工作流':'Open render workflow'}</button>}
      {renderGraphOpen&&doc&&<RenderGraph key={doc.id} api={api} projectId={doc.id} lang={lang} onSaved={next=>{load(next);refresh();}} onClose={()=>setRenderGraphOpen(false)}/>}
      {comfyOpen&&<ComfyImport api={api} lang={lang} onCreated={next=>replaceProject(async()=>{load(next);await refresh();setComfyOpen(false);})} onClose={()=>setComfyOpen(false)}/>}
      {imported&&<section className="panel"><h2>{lang==='zh'?'检查导入工程':'Review imported project'}</h2><p>{lang==='zh'?'已校验规格、资源和文件哈希。外部服务需要在部署配置中绑定。':'Spec, resources and file hashes verified. Bind external services in your deployment profile.'}</p><label>Project ID<input aria-label="Imported project ID" value={importId} onChange={e=>setImportId(e.target.value)}/></label><pre className="json-block">{JSON.stringify(imported.report,null,2)}</pre><button disabled={busy || !!runId} onClick={()=>replaceProject(async()=>{try{const created=await(await api('/projects',{method:'POST',body:JSON.stringify({spec:{...imported.spec,id:importId},resources:imported.resources})})).json();if(imported.report.documents)await api(`/projects/${encodeURIComponent(created.spec.id)}/documents/settings`,{method:"PUT",body:JSON.stringify(imported.report.documents)});load(created);await refresh();setImported(null);}catch(e){error(e);}})}>{lang==='zh'?'创建导入项目':'Create imported project'}</button><button onClick={()=>setImported(null)}>{lang==='zh'?'关闭':'Close'}</button></section>}
      {!doc ? <div className="empty"><div className="empty-symbol"><Icon name="grid" size={25}/></div><h2>{lang==='zh'?'开始构建你的智能体':'Build your first agent'}</h2><p>{t.empty}</p></div> : <>
        <nav className="tabs">{(['canvas','spec','code','resources','runs','memory','improve','versions'] as const).map(key => <button key={key} disabled={busy} aria-current={tab===key?'page':undefined} className={tab === key ? 'selected' : ''} onClick={() => chooseTab(key)}><Icon name={tabIcons[key]} size={15}/>{t[key]}</button>)}
          <span className="revision">r{doc.revision}</span></nav>
        {tab==='resources' ? <ResourcesPanel key={doc.id} doc={{...doc,spec:currentSpec()}} api={api} lang={lang} onError={error} onChange={next=>{setDoc(next);setNodes(items=>items.map(node=>({...node,data:{...node.data,config:graphAt(next.spec,graphPath).nodes[node.id]}})));mutate();}}/>
        :tab==='memory'?<MemoryPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error}/>
        :tab==='runs'?<RunsPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error} onDebug={debugStep} debugDisabled={busy||!!runId}/>
        :tab==='improve'?<ImprovePanel key={doc.id} doc={doc} api={api} lang={lang} onError={error} dirty={dirty || nodeDraftDirty}/>
        :tab==='versions'?<VersionsPanel key={doc.id} doc={doc} api={api} lang={lang} onError={error} onExport={exportProject} onRun={run}/>
        :<div className="editor" inert={busy} aria-busy={busy}>
          <section className="workspace">
            {tab === 'canvas' ? <><div className="canvas-tools"><div className="canvas-breadcrumb"><button disabled={busy} onClick={()=>navigate([])}>{lang==='zh'?'工作流':'Workflow'}</button>{graphPath.map((part,i)=>part==='body'||part==='branches'||graphPath[i+1]==='branches'?null:<button key={i} disabled={busy} onClick={()=>navigate(graphPath.slice(0,i+(graphPath[i+1]==='body'?2:1)))}><Icon name="arrow" size={12}/>{part}</button>)}</div><div className="canvas-actions"><div className="canvas-tool-group create-node-group"><input aria-label="New node name" placeholder={lang==='zh'?'节点名（可选）':'Node name (optional)'} value={newNodeName} onChange={e=>setNewNodeName(e.target.value)}/><select aria-label="New node type" value={nodeKind} onChange={e=>setNodeKind(e.target.value as NodeKind)}>{(['model','agent','tool','transform','condition','join','loop','parallel','map','human','code'] as const).map(kind=><option key={kind} value={kind}>{lang==='zh'?({model:'模型',agent:'智能体',tool:'工具',transform:'数据映射',condition:'条件',join:'汇合',loop:'循环',parallel:'并行',map:'逐项处理',human:'人工',code:'代码'}[kind]):kind}</option>)}</select><button disabled={busy||!!runId} onClick={addNode}><Icon name="plus"/>{nodeKind==='model'?t.add:(lang==='zh'?'添加节点':'Add node')}</button></div><div className="canvas-tool-group"><button disabled={busy||!!runId||dirty||nodeDraftDirty||!debugNodes.length} onClick={()=>{setCanvasFocus(false);setDebugOpen(true);}}><Icon name="play"/>{lang==='zh'?'调试所选':'Debug selection'}</button><button onClick={groupSelected} disabled={!nodes.some(n=>n.selected)&&!groupSelection.length}><Icon name="layers"/>{lang==='zh'?'分组':'Group'}</button><button disabled={busy} onClick={async()=>{setBusy(true);try{const layout=await arrange(nodes,edges,groups);setNodes(items=>items.map(item=>({...item,position:layout.find(n=>n.id===item.id)?.position??item.position})));setCanvasFit(n=>n+1);mutate();}catch(e){error(e);}finally{setBusy(false);}}}><Icon name="grid"/>{t.layout}</button><button aria-pressed={canvasFocus} onClick={()=>setCanvasFocus(value=>!value)}><Icon name={canvasFocus?"collapse":"expand"}/>{lang==='zh'?(canvasFocus?'退出专注':'专注画布'):(canvasFocus?'Exit focus':'Focus canvas')}</button><button aria-label="Workflow settings" aria-pressed={workflowSettings} onClick={()=>{if(commitNodeDraft()){setWorkflowSettings(v=>!v);setSelected(null);}}}><Icon name="settings"/>{lang==='zh'?'工作流设置':'Workflow settings'}</button></div></div></div>
              <ReactFlow onlyRenderVisibleElements key={`${doc.id}:${doc.revision}:${pathKey(graphPath)}`} nodes={displayNodes} nodeTypes={nodeTypes} edgeTypes={edgeTypes} elevateNodesOnSelect={false} multiSelectionKeyCode="Shift" edges={view.edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, node) => {if(node.type==='groupCard'){if(commitNodeDraft())setSelected(null);}else {const actual=nodes.find(n=>n.id===node.id);if(actual)select(actual);}}} onEdgeClick={(_,edge)=>{if (!commitNodeDraft()) return; setSelectedEdge(edge.id);setSelected(null);}} fitView fitViewOptions={{ padding: 0.22, maxZoom: 1 }} minZoom={0.08} maxZoom={2} deleteKeyCode="Delete"><FitWorkflowView revision={String(canvasFit)+String(canvasFocus)+groups.map(g=>g.id+g.collapsed).join()}/><Background color="#d4d4d8" gap={20} size={1}/><Controls showInteractive={false}/><MiniMap style={{width:112,height:68}} nodeColor="#d4d4d8" maskColor="rgba(250,250,250,.65)"/></ReactFlow><div className="canvas-summary">{nodes.length} {lang==='zh'?'个节点':'nodes'}<span>·</span>{edges.length} {lang==='zh'?'条连接':'connections'}</div></>
              : tab === 'spec' ? <textarea className="source-editor" aria-label="AgentSpec JSON" value={specText} onChange={e => { setSpecText(e.target.value); mutate(); }} spellCheck={false}/>
                : <pre className="source-editor code-view">{dirty ? `${t.runHint}\n\n` : ''}{code}</pre>}
          </section>
          <aside className="inspector"><div className="inspector-design">{workflowSettings&&<WorkflowFields key={`${doc.id}:${pathKey(graphPath)}`} spec={currentSpec()} graph={graphAt(currentSpec(),graphPath)} lang={lang} onChange={spec=>{setDoc({...doc,spec});mutate();}} onGraph={graph=>{setDoc({...doc,spec:withGraph(currentSpec(),graphPath,graph)});mutate();}}/>}{debugOpen&&debugNodes.length>0&&<DebugPanel key={`${doc.id}:${doc.revision}:${pathKey(graphPath)}:${debugNodes.join()}:${debugSource?.runId??''}:${debugSource?.source_prefix??''}`} doc={doc} nodes={debugNodes} path={graphPath} api={api} lang={lang} initialInput={(()=>{try{return JSON.parse(input);}catch{return {};}})()} sourceRunId={result?.run_id} initialSource={debugSource} mock={mock} allowWrites={allowWrites} disabled={dirty||nodeDraftDirty||!!runId} onStart={id=>{setResult(null);watchRun(id);}} onClose={()=>setDebugOpen(false)}/>}<div className="inspector-heading"><Icon name="settings"/><span>{t.node}</span></div>
            {groupSelection.length===1&&groups.filter(g=>g.id===groupSelection[0]).map(group=><div className="group-settings" key={group.id}><label>{lang==='zh'?'分组名称':'Group name'}<input aria-label="Group name" value={group.label} maxLength={80} onChange={e=>setGroups(groups.map(g=>g.id===group.id?{...g,label:e.target.value}:g))}/></label><button onClick={()=>setGroups(groups.map(g=>g.id===group.id?{...g,collapsed:!g.collapsed}:g))}>{group.collapsed?(lang==='zh'?'展开分组':'Expand group'):(lang==='zh'?'折叠分组':'Collapse group')}</button><label>{lang==='zh'?'分组布局':'Group layout'}<select aria-label="Group layout" value={group.direction??'DOWN'} onChange={e=>setGroups(groups.map(g=>g.id===group.id?{...g,direction:e.target.value as 'RIGHT'|'DOWN'}:g))}><option value="DOWN">{lang==='zh'?'纵向':'Vertical'}</option><option value="RIGHT">{lang==='zh'?'横向':'Horizontal'}</option></select></label><button onClick={()=>ungroup(group.id)}>{lang==='zh'?'取消分组':'Ungroup'}</button></div>)}
            {selectedEdge&&<label>{lang==='zh'?'分支条件':'Branch condition'}<select aria-label="Edge condition" value={typeof edges.find(edge=>edge.id===selectedEdge)?.data?.when==='boolean'?String(edges.find(edge=>edge.id===selectedEdge)?.data?.when):'always'} onChange={e=>{const value=e.target.value;setEdges(items=>items.map(edge=>edge.id===selectedEdge?{...edge,data:{when:value==='always'?undefined:value==='true'},label:value==='always'?undefined:value}:edge));mutate();}}><option value="always">{lang==='zh'?'始终执行':'Always'}</option><option value="true">true</option><option value="false">false</option></select></label>}
            {active ? <><h3>{active.id}<span className="pill">{active.data.config.type}</span></h3>
              {childGraphs(active.data.config).map(child=><button key={child.label} disabled={busy} onClick={()=>navigate([...graphPath,active.id,...child.path])}>{lang==='zh'?'打开子流程':'Open subflow'} · {child.label}</button>)}
              {['model','agent'].includes(active.data.config.type)&&<AgentSettings api={api} key={active.id} id={active.id} node={active.data.config} doc={doc} lang={lang} onChange={(node,changes)=>{const spec=currentSpec();if(changes?.models)spec.models=changes.models;if(changes?.definitions)spec.resources=changes.definitions;if(changes?.tools)spec.tools=changes.tools;if(node.type==='agent'||node.output_validator||node.output_errors==='feedback'||(node.max_output_retries??1)!==1)spec.spec_version='0.3';setDoc({...doc,spec,resources:changes?.resources??doc.resources});applyNode(node);}}/>}
              <NodeFields key={`${doc.id}:${pathKey(graphPath)}:${active.id}`} node={active.data.config} doc={doc} graph={graphAt(currentSpec(false),graphPath)} lang={lang} onChange={applyNode}/>{active.data.config.type==='code'&&<label>{lang==='zh'?'JSON 值上限（字符）':'JSON value limit (characters)'}<input type="number" aria-label="Code JSON value limit" min={1024} max={8388608} placeholder="1048576" value={active.data.config.code_max_value_chars??''} onChange={e=>applyNode({...active.data.config,code_max_value_chars:e.target.value?Number(e.target.value):null})}/></label>}
              <details className="advanced-node"><summary>{lang==='zh'?'高级：完整节点':'Advanced: full node'}</summary><label>{t.nodeJson}<textarea className="node-json" aria-label={t.nodeJson} value={nodeText} onChange={e => { setNodeText(e.target.value); setNodeDraftDirty(true); }}/></label>
              <button onClick={() => { try { applyNode(parseNodeDraft()); } catch (e) { error(e); } }}>{t.apply}</button></details></> : <div className="inspector-empty"><span className="empty-symbol"><Icon name="settings" size={21}/></span><strong>{lang==='zh'?'选择一个节点':'Select a node'}</strong><p>{lang==='zh'?'点击画布中的节点，查看和编辑参数。':'Click a node on the canvas to edit its properties.'}</p></div>}
            </div><section className="run-settings"><div className="section-label input-heading"><Icon name="play" size={14}/>{t.input}</div><label><textarea aria-label={t.input} value={input} onChange={e => setInput(e.target.value)}/></label>
            <select aria-label="Run mode" value={mock ? 'mock' : 'live'} onChange={e => setMock(e.target.value === 'mock')}><option value="mock">{t.offline}</option><option value="live">{t.live}</option></select>
            <label className="check"><input type="checkbox" checked={allowWrites} onChange={e=>setAllowWrites(e.target.checked)}/>{lang==='zh'?'允许已配置的写入工具':'Allow configured write tools'}</label>
            <label className="check"><input type="checkbox" checked={useRelease} onChange={e=>setUseRelease(e.target.checked)}/>{lang==='zh'?'运行发布版本':'Run active release'}</label>
            <button className="primary run" aria-label={'▷ '+t.run} onClick={()=>run()} disabled={busy || dirty || nodeDraftDirty || !!runId}><Icon name="play" size={14}/>{t.run}</button>
            {runId && <button onClick={() => api(`/runs/${runId}/cancel`, { method: 'POST' }).catch(error)}>{t.cancel}</button>}
            <p className="hint">{t.runHint}</p></section>
          </aside>
        </div>}
        <section className="results"><div className="results-heading"><span><Icon name="code" size={15}/>{t.output}</span>{result&&<span className={`status-badge status-${result.status}`}>{result.status}</span>}</div>{!result&&<p className="results-placeholder">{lang==='zh'?'运行工作流后，在这里查看输出、用量和事件。':'Run your workflow to inspect its output, usage and events.'}</p>}
          {result && <RunDetails key={result.run_id} run={result} api={api} lang={lang} onError={error} onRefresh={()=>watchRun(result.run_id)} onDebug={debugStep} debugDisabled={busy||!!runId}/> }
        </section>
      </>}
      <footer role="status"><span className="status-message"><span className="dot"/>{status}</span><span className="footer-meta">EvoSprig Studio</span></footer>
    </main>
    {prompt}
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
