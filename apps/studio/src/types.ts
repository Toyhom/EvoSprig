export type Json = Record<string, unknown>;
export type Binding = { ref: string; optional?: boolean; default?: unknown } | { value: unknown };
export type Predicate = { left: Binding; op: 'eq'|'ne'|'lt'|'le'|'gt'|'ge'|'contains'|'truthy'; right?: Binding|null };
export type NodeKind = 'model'|'agent'|'tool'|'transform'|'condition'|'join'|'loop'|'parallel'|'map'|'human';
export type NodeSpec = {
  type: NodeKind; inputs: Record<string, Binding>; output_schema: Json; model?: string | null;
  instructions?: string | { resource: string }; tools?: string[]; tool?: string | null;
  response_format?: 'text' | 'json'; condition?: Predicate|null; body?: Graph|null;
  items?: Binding|null; max_items?: number; tool_errors?: 'raise'|'feedback';
  branches?: Record<string, Graph>; max_iterations?: number; until?: Predicate|null; join?: 'all'|'selected';
};
export type GraphEdge = { source: string; target: string; when?: boolean|null };
export type Graph = { entry: string; nodes: Record<string, NodeSpec>; edges: GraphEdge[]; output: Record<string, Binding> };
export type Spec = {
  spec_version: '0.1'|'0.2'|'0.3'; id: string; input_schema: Json; output_schema: Json;
  models: Record<string, { binding: string; requires: string[] }>;
  tools: Record<string, { plugin: string; version: string }>;
  resources: Record<string, { path: string; role: 'prompt'|'skill' }>;
  graph: Graph; execution?: Record<string, number|boolean>;
};
export type Document = { id: string; revision: number; spec: Spec; spec_hash: string; resources: Record<string,string>|null; layout: Record<string, { x: number; y: number }> };
export type Api = (path: string, init?: RequestInit) => Promise<Response>;
export type Lang = 'zh'|'en';
export type Run = {run_id:string; agent_version:string; status:string; output:unknown; error:unknown; usage:Json; events:Json[]; waiting:{path:string; kind:string; input?:unknown; schema?:Json}[]};
export function orderedNodes(spec: Spec): [string, NodeSpec][] {
  const pending = new Set(Object.keys(spec.graph.nodes)); const order: string[] = [];
  while (pending.size) {
    const ready = [...pending].filter(id => !spec.graph.edges.some(edge => edge.target === id && pending.has(edge.source))).sort();
    if (!ready.length) { order.push(...pending); break; }
    for (const id of ready) { order.push(id); pending.delete(id); }
  }
  return order.map(id => [id, spec.graph.nodes[id]]);
}
export const objectSchema = (key: string): Json => ({ type: 'object', properties: { [key]: { type: 'string' } }, required: [key], additionalProperties: false });
export const starter = (id: string): Spec => ({
  spec_version: '0.2', id, input_schema: objectSchema('question'), output_schema: objectSchema('answer'),
  models: { main: { binding: 'main-model', requires: ['text'] } }, tools: {}, resources: {},
  graph: {
    entry: 'assistant', nodes: {
      assistant: { type: 'model', model: 'main', instructions: 'Answer the question clearly and briefly.',
        inputs: { question: { ref: 'input.question' } }, output_schema: objectSchema('text'), response_format: 'text' },
    }, edges: [], output: { answer: { ref: 'nodes.assistant.output.text' } },
  }, execution: { max_steps: 32, max_model_calls: 4, max_total_tokens: 8192, max_output_tokens: 512, timeout_seconds: 60 },
});
export function nodeTemplate(kind:NodeKind, model='main', tool='add'):NodeSpec {
  if (kind==='model'||kind==='agent') return {...structuredClone(starter('sample').graph.nodes.assistant), type:kind, model, ...(kind==='agent'?{tools:[]}:{} )};
  if(kind==='tool') return {type:kind,tool,inputs:{},output_schema:{type:'object'}};
  if(kind==='condition') return {type:kind,inputs:{},condition:{left:{value:true},op:'truthy'},output_schema:{type:'object',properties:{value:{type:'boolean'}},required:['value']}};
  const inner:Graph={entry:'step',nodes:{step:{type:'transform',inputs:{text:{value:'example'}},output_schema:objectSchema('text')}},edges:[],output:{text:{ref:'nodes.step.output.text'}}};
  if(kind==='map') return {type:kind,inputs:{},items:{value:['first','second']},max_items:32,body:{entry:'step',nodes:{step:{type:'transform',inputs:{item:{ref:'input.item'}},output_schema:{type:'object'}}},edges:[],output:{item:{ref:'nodes.step.output.item'}}},output_schema:{type:'object',properties:{items:{type:'array'}},required:['items']}};
  if(kind==='loop') return {type:kind,inputs:{},output_schema:objectSchema('text'),body:inner,max_iterations:3};
  if(kind==='parallel') return {type:kind,inputs:{},output_schema:{type:'object'},branches:{first:inner,second:structuredClone(inner)},join:'all'};
  return {type:kind,inputs:{text:{value:'example'}},output_schema:objectSchema('text'),...(kind==='join'?{join:'all' as const}:{})};
}
