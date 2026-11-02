import { useEffect } from 'react';
import { Handle, Position, useNodesInitialized, useReactFlow, useStore, type Node, type NodeProps } from '@xyflow/react';
import type { Lang, NodeKind, NodeSpec } from './types';

export type IconName = 'grid' | 'folder' | 'search' | 'plus' | 'upload' | 'download' | 'code' | 'file' | 'history' | 'database' | 'chart' | 'layers' | 'settings' | 'arrow' | 'play' | 'branch' | 'tool' | 'model' | 'human' | 'menu' | 'close' | 'refresh';
const paths: Record<IconName, string> = {
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
  loop: ['循环', 'Loop'], parallel: ['并行', 'Parallel'], human: ['人工确认', 'Approval'],
};
const icons: Record<NodeKind, IconName> = {
  model: 'model', agent: 'model', tool: 'tool', condition: 'branch', transform: 'code',
  join: 'layers', loop: 'refresh', parallel: 'layers', human: 'human',
};
export type WorkflowData = { label: string; config: NodeSpec; lang?: Lang };
export type WorkflowFlowNode = Node<WorkflowData>;
export function WorkflowNode({ id, data, selected }: NodeProps<WorkflowFlowNode>) {
  const { config, lang = 'zh' } = data;
  // Drafts can contain an unsupported kind until server validation on save.
  const type = labels[config.type]?.[lang === 'zh' ? 0 : 1] ?? String(config.type ?? 'Node');
  const binding = typeof config.model === 'string' ? config.model : typeof config.tool === 'string' ? config.tool : undefined;
  const summary = typeof config.instructions === 'string' && config.instructions.trim() ? config.instructions
    : typeof config.instructions === 'object' && config.instructions?.resource ? `${lang === 'zh' ? '提示资源' : 'Prompt'} · ${config.instructions.resource}`
    : binding ?? (config.type === 'human' ? (lang === 'zh' ? '暂停并等待审核' : 'Pause for review') : type);
  return <div className={`workflow-node kind-${config.type}${selected ? ' is-selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="workflow-node-heading"><span className="node-symbol"><Icon name={icons[config.type] ?? 'settings'} size={17} /></span><strong title={id}>{id}</strong><span className="node-type">{type}</span></div>
    <p className="node-summary" title={summary}>{summary}</p>
    <div className="node-meta"><span>{binding ?? `${Object.keys(config.inputs ?? {}).length} ${lang === 'zh' ? '项输入' : 'inputs'}`}</span><span>{config.response_format === 'json' ? 'JSON' : config.type === 'human' ? (lang === 'zh' ? '需确认' : 'Review') : (lang === 'zh' ? '输出' : 'Output')} <Icon name="arrow" size={11} /></span></div>
    <Handle type="source" position={Position.Right} />
  </div>;
}
export const nodeTypes = { workflow: WorkflowNode };
export const tabIcons: Record<string, IconName> = { canvas: 'grid', spec: 'file', code: 'code', resources: 'folder', runs: 'history', memory: 'database', improve: 'chart', versions: 'layers' };

// Reframe after a container resize, while preserving user pan/zoom during editing.
export function FitWorkflowView() {
  const { fitView } = useReactFlow();
  const initialized = useNodesInitialized();
  const width = useStore(state => state.width);
  const height = useStore(state => state.height);
  useEffect(() => {
    if (initialized && width && height) void fitView({ padding: .22, maxZoom: 1 });
  }, [initialized, width, height, fitView]);
  return null;
}
