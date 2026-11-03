import { useEffect } from 'react';
import { Handle, Position, useNodesInitialized, useReactFlow, useStore, type Node, type NodeProps } from '@xyflow/react';
import { childGraphs, nodeSize, type Group } from './canvas';
import type { Lang, NodeKind, NodeSpec } from './types';

export type IconName = 'image' | 'grid' | 'folder' | 'search' | 'plus' | 'upload' | 'download' | 'code' | 'file' | 'history' | 'database' | 'chart' | 'layers' | 'settings' | 'arrow' | 'play' | 'branch' | 'tool' | 'model' | 'human' | 'menu' | 'close' | 'refresh' | 'robot' | 'scan' | 'globe' | 'terminal' | 'mail' | 'film' | 'check' | 'merge' | 'expand' | 'collapse' | 'network' | 'briefcase' | 'graduate' | 'pen' | 'calendar' | 'book' | 'headset' | 'compass' | 'receipt' | 'clock' | 'spark';
const paths: Record<IconName, string> = {
  image: 'M3 3h18v18H3zM3 17l6-6 4 4 3-3 5 5M15 7h.01',
  briefcase:'M3 7h18v14H3zM8 7V3h8v4M3 12c5 4 13 4 18 0M10 13h4v3h-4z',
  graduate:'m2 9 10-5 10 5-10 5L2 9m4 3v6c4 3 8 3 12 0v-6m4-3v10',
  pen:'m4 16 12-12 4 4-12 12H4v-4zm9-9 4 4M3 22h18',
  calendar:'M3 5h18v16H3zM7 2v6m10-6v6M3 11h18M7 15h3m4 0h3m-10 3h3',
  book:'M12 5c-3-3-7-3-10-2v16c4-1 7 0 10 2 3-2 6-3 10-2V3c-3-1-7-1-10 2v16',
  headset:'M3 12a9 9 0 0 1 18 0M3 11h4v8H3zm14 0h4v8h-4zM21 19c0 3-5 3-9 3',
  compass:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0m-5-5-2 7-7 3 3-7 6-3',
  receipt:'M5 2l3 2 4-2 4 2 3-2v20l-3-2-4 2-4-2-3 2V2m4 6h6m-6 4h6m-6 4h4',
  clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 6v6l4 2',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3',
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
  code: ['代码', 'Code'], model: ['模型', 'Model'], agent: ['智能体', 'Agent'], tool: ['工具', 'Tool'],
  condition: ['条件', 'Condition'], transform: ['转换', 'Transform'], join: ['汇合', 'Join'],
  loop: ['循环', 'Loop'], parallel: ['并行', 'Parallel'], map: ['批量任务', 'Map'], human: ['人工确认', 'Approval'],
};
const icons: Record<NodeKind, IconName> = {
  code: 'terminal', model: 'model', agent: 'robot', tool: 'tool', condition: 'branch', transform: 'code',
  join: 'merge', loop: 'refresh', parallel: 'network', map: 'layers', human: 'human',
};
export type WorkflowData = { label: string; config: NodeSpec; lang?: Lang; direction?:'RIGHT'|'DOWN'; busy?:boolean; promptPreview?:string; toolPlugins?:Record<string,{plugin:string}>; onOpen?:(path:string[])=>void };
export type WorkflowFlowNode = Node<WorkflowData>;
const readable=(name:string)=>name.replaceAll('_',' ').replaceAll('-',' ').replace(/^./,c=>c.toUpperCase()).replace(/\b(api|sop|ocr|sql|llm|http|mcp|json)\b/gi,word=>word.toUpperCase());
function capabilityIcon(name:string):IconName{
  return /ocr|scan/.test(name)?'scan':/receipt|invoice|expense/.test(name)?'receipt':/python|code|build|execute/.test(name)?'terminal':/sql|database|memory|recall/.test(name)?'database':/search|browse|fetch|research/.test(name)?'globe':/video|image|render|shot/.test(name)?'film':/mail|message/.test(name)?'mail':/resume|interview|career|fit_review/.test(name)?'briefcase':/quiz|learn|lesson|teach/.test(name)?'graduate':/chapter|outline|book/.test(name)?'book':/review|check|verify/.test(name)?'check':/write|draft|editor|content/.test(name)?'pen':/travel|trip|plan|day/.test(name)?'compass':/meeting|calendar/.test(name)?'calendar':/support|customer/.test(name)?'headset':'tool';
}
export function WorkflowNode({ id, data, selected }: NodeProps<WorkflowFlowNode>) {
  const {config,lang='en'}=data;
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  const type=labels[config.type]?.[lang==='zh'?0:1]??String(config.type??'Node');
  const isAgent=config.type==='agent',isModel=config.type==='model',isText=isAgent||isModel;
  const children=childGraphs(config),vertical=data.direction==='DOWN';
  const prompt=data.promptPreview||(typeof config.instructions==='string'?config.instructions:'');
  const inputNames=Object.keys(config.inputs??{});
  const summary=isText?(prompt||say('设置角色、任务与输出要求','Define the role, task and expected output')):
    config.type==='human'?say('在这里收集用户回答或审批意见','Collect a response before continuing'):
    config.type==='map'?say('为每个输入启动一个子流程','Run a subflow for each input item'):
    config.type==='parallel'?say('分派独立任务，等待各分支完成','Run branches together, then collect results'):
    config.type==='loop'?say('重复执行，直到满足结束条件','Repeat until the exit condition is met'):
    config.type==='condition'?say('按规则选择下一条路径','Choose a path from the rule result'):
    config.type==='tool'?(config.tool??say('选择一个工具','Select a tool')):
    inputNames.join(' · ')||say('连接数据','Connect data');
  const tools=(config.tools??[]).map(name=>({name,plugin:data.toolPlugins?.[name]?.plugin??name}));
  const skillNames=config.skills??[];
  const roleIcon=capabilityIcon(id.toLowerCase());
  const icon=config.type==='tool'?capabilityIcon(config.tool??id):isText?(roleIcon==='tool'?icons[config.type]:roleIcon):icons[config.type]??'settings';
  return <div style={nodeSize(config)} className={`workflow-node kind-${config.type}${vertical?' vertical-node':''}${selected?' is-selected':''}`}>
    <Handle type="target" position={vertical?Position.Top:Position.Left}/>
    <div className="workflow-node-heading"><span className="node-symbol"><Icon name={icon} size={18}/></span><div className="node-heading-text"><span className="node-type">{type}</span><strong title={id}>{readable(id)}</strong></div>{isAgent&&<span className="node-autonomy" title={say('智能体决定工具调用顺序','The agent chooses its next tool')}><Icon name="spark" size={13}/></span>}</div>
    {config.type!=='join'&&<p className="node-summary" title={summary}>{summary}</p>}
    {isText&&!!skillNames.length&&<div className="node-skills" title={skillNames.join(', ')}><Icon name="layers" size={12}/>{skillNames.slice(0,2).map(name=><span key={name}>{readable(name)}</span>)}{skillNames.length>2&&<small>+{skillNames.length-2}</small>}</div>}
    {isAgent&&<div className="node-tool-row">{tools.length?tools.slice(0,3).map(tool=><span key={tool.name} title={tool.plugin}><Icon name={capabilityIcon(tool.plugin)} size={12}/>{readable(tool.name)}</span>):<span>{say('尚未选择工具','No tools selected')}</span>}{tools.length>3&&<small>+{tools.length-3}</small>}</div>}
    {children.length>0&&<div className="subflow-links">{children.map(child=>{const graph=child.path[0]==='body'?config.body:config.branches?.[child.label];return <button className="nodrag nopan" disabled={data.busy} key={child.label} onClick={()=>data.onOpen?.(child.path)}><span className="mini-flow"><i/><i/><i/></span><span><strong>{child.label==='body'?say('子流程','Subflow'):readable(child.label)}</strong><small>{Object.keys(graph?.nodes??{}).length} {say('个步骤','steps')}</small></span><Icon name="arrow" size={14}/></button>})}</div>}
    {isText&&<div className="node-meta"><span><Icon name="model" size={12}/>{config.model??'Model'}</span><span>{config.response_format==='json'?'JSON':say('文本','Text')}{config.max_output_tokens?` · ${config.max_output_tokens.toLocaleString()} ${say('token','tokens')}`:''}</span></div>}
    {config.type==='tool'&&<div className="tool-mode"><span className="always-dot"/>{say('流程到此自动执行','Always runs at this step')}</div>}
    {config.type==='human'&&<div className="human-mode"><Icon name="clock" size={12}/>{say('等待回答后继续','Pause → respond → resume')}</div>}
    {config.type==='condition'?<><Handle id="true" type="source" position={vertical?Position.Bottom:Position.Right} style={{[vertical?'left':'top']:'35%'}}/><Handle id="false" type="source" position={vertical?Position.Bottom:Position.Right} style={{[vertical?'left':'top']:'75%'}}/><span className="branch-label branch-true">true</span><span className="branch-label branch-false">false</span></>:<Handle type="source" position={vertical?Position.Bottom:Position.Right}/>}
  </div>;
}
function GroupCard({data,selected}:NodeProps<Node<{group:Group;count:number;lang:Lang;onToggle:()=>void;busy?:boolean}>>) {
  const {group,count,lang}=data;
  return <div className={`canvas-group ${group.collapsed?'is-collapsed':'is-expanded'}${selected?' is-selected':''}`}>
    {group.collapsed&&<Handle type="target" position={Position.Left}/>}
    <div className="group-heading"><Icon name="layers"/><strong>{group.label}</strong><span className="group-count">{count}</span><button aria-label={(group.collapsed?'Expand ':'Collapse ')+group.label} className="nodrag nopan" disabled={data.busy} onClick={data.onToggle}><Icon name={group.collapsed?'expand':'collapse'} size={14}/></button></div>
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
