import { useEffect } from 'react';
import { Handle, Position, useNodesInitialized, useReactFlow, useStore, type Node, type NodeProps } from '@xyflow/react';
import { childGraphs, nodeSize, type Group } from './canvas';
import type { Lang, NodeKind, NodeSpec } from './types';

export type IconName = 'grid' | 'folder' | 'search' | 'plus' | 'upload' | 'download' | 'code' | 'file' | 'history' | 'database' | 'chart' | 'layers' | 'settings' | 'arrow' | 'play' | 'branch' | 'tool' | 'model' | 'human' | 'menu' | 'close' | 'refresh' | 'robot' | 'scan' | 'globe' | 'terminal' | 'mail' | 'film' | 'check' | 'merge' | 'expand' | 'collapse' | 'network';
const paths: Record<IconName, string> = {
  robot: 'M8 4h8M12 2v2M4 7h16v13H4zM8 11v2m8-2v2M9 17h6M1 10v6m22-6v6',
  scan: 'M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5M6 12h12M8 7h8M8 17h8',
  globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18',
  terminal: 'M3 4h18v16H3zM7 8l4 4-4 4m6 0h4',
  mail: 'M3 5h18v14H3zM3 5l9 8 9-8',
  film: 'M3 3h18v18H3zM7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4',
  check: 'M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4M8 12l3 3 5-6',
  merge: 'M4 4l8 8m-8 8 8-8h9m-4-4 4 4-4 4',
  expand: 'M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5',
  collapse: 'M3 8h5V3m8 0v5h5M8 21v-5H3m18 0h-5v5',
  network: 'M9 2h6v6H9zM2 16h6v6H2zM16 16h6v6h-6zM12 8v4M5 16v-4h14v4',
  grid: 'M3 3h6v6H3zM15 3h6v6h-6zM3 15h6v6H3zM15 15h6v6h-6z',
  folder: 'M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7z',
  search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14M15 15l6 6',
  plus: 'M12 5v14M5 12h14',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5',
  download: 'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',
  code: 'm8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18',
  file: 'M14 3H5v18h14V8l-5-5v5h5M8 12h8m-8 4h6',
  history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-5v6l4 2',
  database: 'M3 6c0-4 18-4 18 0s-18 4-18 0v12c0 4 18 4 18 0V6M3 12c0 4 18 4 18 0',
  chart: 'M4 3v17h17M8 15l4-5 4 3 5-7',
  layers: 'm12 3 10 5-10 5L2 8l10-5zm-10 9 10 5 10-5M2 16l10 5 10-5',
  settings: 'M4 6h16M4 18h16M8 3v6m8 6v6M4 12h16',
  arrow: 'm9 5 7 7-7 7',
  play: 'm7 4 14 8-14 8V4z',
  branch: 'M6 3v12a4 4 0 0 0 4 4h8M6 9h8a4 4 0 0 0 4-4V3m-3 13 3 3-3 3',
  tool: 'M14 4a6 6 0 0 0-7 8L3 17a3 3 0 0 0 4 4l5-5a6 6 0 0 0 8-7l-4 4-5-5 3-4z',
  model: 'M7 7h10v10H7zM9 2v5m6-5v5M9 17v5m6-5v5M2 9h5m-5 6h5m10-6h5m-5 6h5',
  human: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M4 21v-2a8 5 0 0 1 16 0v2',
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'm6 6 12 12M6 18 18 6',
  refresh: 'M20 8a9 9 0 1 0 1 7M20 3v5h-5',
};
export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="icon"><path d={paths[name]} /></svg>;
}
const labels: Record<NodeKind, [string, string]> = {
  model: ['模型', 'Model'], agent: ['智能体', 'Agent'], tool: ['工具', 'Tool'],
  condition: ['条件', 'Condition'], transform: ['转换', 'Transform'], join: ['汇合', 'Join'],
  loop: ['循环', 'Loop'], parallel: ['并行', 'Parallel'], map: ['批量任务', 'Map'], human: ['人工确认', 'Approval'],
};
const icons: Record<NodeKind, IconName> = {
  model: 'model', agent: 'robot', tool: 'tool', condition: 'branch', transform: 'code',
  join: 'merge', loop: 'refresh', parallel: 'network', map: 'layers', human: 'human',
};
export type WorkflowData = { label: string; config: NodeSpec; lang?: Lang; direction?:'RIGHT'|'DOWN'; busy?:boolean; promptPreview?:string; onOpen?:(path:string[])=>void };
export type WorkflowFlowNode = Node<WorkflowData>;
export function WorkflowNode({ id, data, selected }: NodeProps<WorkflowFlowNode>) {
  const { config, lang = 'en' } = data;
  // Drafts can contain an unsupported kind until server validation on save.
  const type = labels[config.type]?.[lang === 'zh' ? 0 : 1] ?? String(config.type ?? 'Node');
  const binding = typeof config.model === 'string' ? config.model : typeof config.tool === 'string' ? config.tool : undefined;
  const summary = data.promptPreview || (typeof config.instructions === 'string' && config.instructions.trim() ? config.instructions
    : typeof config.instructions === 'object' && config.instructions?.resource ? `${lang === 'zh' ? '提示资源' : 'Prompt'} · ${config.instructions.resource}`
    : binding ?? (config.type === 'human' ? (lang === 'zh' ? '暂停并等待审核' : 'Pause for review') : type));
  const capability=(config.tool??'').toLowerCase();
  const toolIcon:IconName=/ocr|scan|receipt/.test(capability)?'scan':/python|code|execute/.test(capability)?'terminal':/search|browse|fetch|web/.test(capability)?'globe':/video|image|render/.test(capability)?'film':/mail|message/.test(capability)?'mail':/memory|sql|database/.test(capability)?'database':'tool';
  const vertical=data.direction==='DOWN';
  const compact=['tool','transform','join'].includes(config.type);
  const children=childGraphs(config);
  return <div style={nodeSize(config)} className={`workflow-node kind-${config.type}${vertical?' vertical-node':''}${selected ? ' is-selected' : ''}`}>
    <Handle type="target" position={vertical?Position.Top:Position.Left} />
    <div className="workflow-node-heading"><span className="node-symbol"><Icon name={config.type==='tool'?toolIcon:icons[config.type] ?? 'settings'} size={18} /></span><strong title={id}>{id.replaceAll('_',' ')}</strong>{!compact&&<span className="node-type">{type}</span>}</div>
    {config.type!=='join'&&<p className="node-summary" title={summary}>{compact?(binding??summary):summary}</p>}
    {config.type==='tool'&&<span className="tool-mode">{lang==='zh'?'确定性任务':'Deterministic task'}</span>}
    {config.type==='agent'&&<div className="agent-tools"><Icon name="tool" size={12}/><span>{(config.tools??[]).slice(0,2).join(' · ') || (lang==='zh'?'自主选择工具':'Agent-selected tools')}{(config.tools??[]).length>2?` +${config.tools!.length-2}`:''}</span></div>}
    {(config.type==='agent'||(config.type==='model'&&!!config.skills?.length))&&<div className="agent-resources"><span><Icon name="file" size={10}/>{lang==='zh'?'提示词':'Prompt'}</span><span><Icon name="layers" size={10}/>{config.skills?.length??0} {lang==='zh'?'技能':'skills'}</span><span><Icon name="settings" size={10}/>{config.temperature??0} T</span></div>}
    {children.length>0&&<div className="subflow-links">{children.map(child=><button className="nodrag nopan" disabled={data.busy} key={child.label} onClick={()=>data.onOpen?.(child.path)}><Icon name="layers" size={12}/>{child.label} · {Object.keys((child.path[0]==='body'?config.body:config.branches?.[child.label])?.nodes??{}).length}<Icon name="arrow" size={11}/></button>)}</div>}
    {!compact&&config.type!=='condition'&&children.length===0&&<div className="node-meta"><span>{binding ?? `${Object.keys(config.inputs ?? {}).length} ${lang === 'zh' ? '项输入' : 'inputs'}`}</span><span>{config.response_format==='json'?'JSON':config.type==='human'?(lang==='zh'?'需审核':'Review'):'Output'}</span></div>}
    {config.type==='condition'?<><Handle id="true" type="source" position={vertical?Position.Bottom:Position.Right} style={{[vertical?'left':'top']:'35%'}}/><Handle id="false" type="source" position={vertical?Position.Bottom:Position.Right} style={{[vertical?'left':'top']:'75%'}}/><span className="branch-label branch-true">true</span><span className="branch-label branch-false">false</span></>:<Handle type="source" position={vertical?Position.Bottom:Position.Right} />}
  </div>;
}
function GroupCard({data,selected}:NodeProps<Node<{group:Group;count:number;lang:Lang;onToggle:()=>void;busy?:boolean}>>) {
  const {group,count,lang}=data;
  return <div className={`canvas-group ${group.collapsed?'is-collapsed':'is-expanded'}${selected?' is-selected':''}`}>
    {group.collapsed&&<Handle type="target" position={Position.Left}/>}
    <div className="group-heading"><Icon name="layers"/><strong>{group.label}</strong><button aria-label={(group.collapsed?'Expand ':'Collapse ')+group.label} className="nodrag nopan" disabled={data.busy} onClick={data.onToggle}><Icon name={group.collapsed?'expand':'collapse'} size={14}/></button></div>
    {group.collapsed&&<p>{count} {lang==='zh'?'个节点':'nodes'} · {lang==='zh'?'展开查看流程':'Expand to explore'}</p>}
    {group.collapsed&&<Handle type="source" position={Position.Right}/>}
  </div>;
}
export const nodeTypes = { workflow: WorkflowNode, groupCard:GroupCard };
export const tabIcons: Record<string, IconName> = { canvas: 'grid', spec: 'file', code: 'code', resources: 'folder', runs: 'history', memory: 'database', improve: 'chart', versions: 'layers' };

// Reframe after a container resize, while preserving user pan/zoom during editing.
export function FitWorkflowView({revision=""}:{revision?:string}) {
  const { fitView } = useReactFlow();
  const initialized = useNodesInitialized();
  const width = useStore(state => state.width);
  const height = useStore(state => state.height);
  useEffect(() => {
    if (initialized && width && height) void fitView({ padding: .22, maxZoom: 1 });
  }, [initialized, width, height, fitView,revision]);
  return null;
}
