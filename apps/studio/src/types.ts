export type Binding = { ref: string } | { value: unknown };
export type NodeSpec = {
  type: 'model' | 'agent' | 'tool'; inputs: Record<string, Binding>;
  output_schema: Record<string, unknown>; model?: string | null;
  instructions?: string | { resource: string }; tools?: string[]; tool?: string | null;
  response_format?: 'text' | 'json';
};
export type Spec = {
  spec_version: '0.1'; id: string; input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  models: Record<string, { binding: string; requires: string[] }>;
  tools: Record<string, { plugin: string; version: string }>;
  resources: Record<string, { path: string; role: string }>;
  graph: { entry: string; nodes: Record<string, NodeSpec>; edges: { source: string; target: string }[]; output: Record<string, Binding> };
  execution?: Record<string, number>;
};
export type Document = { id: string; revision: number; spec: Spec; spec_hash: string; layout: Record<string, { x: number; y: number }> };
export function orderedNodes(spec: Spec): [string, NodeSpec][] {
  const pending = new Set(Object.keys(spec.graph.nodes)); const order: string[] = [];
  while (pending.size) {
    const ready = [...pending].filter(id => !spec.graph.edges.some(edge => edge.target === id && pending.has(edge.source))).sort();
    if (!ready.length) { order.push(...pending); break; }
    for (const id of ready) { order.push(id); pending.delete(id); }
  }
  return order.map(id => [id, spec.graph.nodes[id]]);
}
const objectSchema = (key: string) => ({ type: 'object', properties: { [key]: { type: 'string' } }, required: [key], additionalProperties: false });
export const starter = (id: string): Spec => ({
  spec_version: '0.1', id, input_schema: objectSchema('question'), output_schema: objectSchema('answer'),
  models: { main: { binding: 'main-model', requires: ['text'] } }, tools: {}, resources: {},
  graph: {
    entry: 'assistant', nodes: {
      assistant: { type: 'model', model: 'main', instructions: 'Answer the question clearly and briefly.',
        inputs: { question: { ref: 'input.question' } }, output_schema: objectSchema('text'), response_format: 'text' },
    }, edges: [], output: { answer: { ref: 'nodes.assistant.output.text' } },
  }, execution: { max_steps: 32, max_model_calls: 4, max_total_tokens: 8192, max_output_tokens: 512, timeout_seconds: 60 },
});
