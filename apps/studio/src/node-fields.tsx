import {useEffect, useId, useRef, useState} from 'react';
import type {Binding, Document, Graph, Json, Lang, NodeSpec, Spec} from './types';

const format=(value:unknown)=>JSON.stringify(value,null,2);
export function JsonField({label,value,onChange}:{label:string;value:unknown;onChange:(value:Json)=>void}){
  const field=useRef<HTMLTextAreaElement>(null),serialized=format(value),[text,setText]=useState(serialized),[error,setError]=useState('');
  useEffect(()=>{setText(serialized);setError('');field.current?.setCustomValidity('');},[serialized]);
  return <label>{label}<textarea ref={field} aria-label={label} className="field-json" value={text} spellCheck={false} onChange={event=>{
    const next=event.target.value;setText(next);
    try {const parsed=JSON.parse(next);if(!parsed||typeof parsed!=='object'||Array.isArray(parsed))throw Error('Expected an object');event.target.setCustomValidity('');onChange(parsed);setError('');}
    catch {event.target.setCustomValidity('Invalid JSON');setError('JSON · '+(label.match(/[\u4e00-\u9fff]/)?'请完成对象格式后应用':'Complete the object before applying'));}
  }}/>{error&&<small role="alert">{error}</small>}</label>;
}
function BindingValue({value,onChange,label,paths,lang}:{value:Binding;onChange:(value:Binding)=>void;label:string;paths:string[];lang:Lang}){
  const list=useId(),isRef='ref' in value;
  return <div className="binding-value"><select aria-label={label+' source'} value={isRef?'ref':'value'} onChange={e=>onChange(e.target.value==='ref'?{ref:'input'}:{value:''})}>
    <option value="ref">{lang==='zh'?'来自输入 / 节点':'Input / node output'}</option><option value="value">{lang==='zh'?'固定值':'Fixed value'}</option>
  </select>{isRef?<><input aria-label={label+' reference'} value={value.ref} list={list} onChange={e=>onChange({...value,ref:e.target.value})}/><datalist id={list}>{paths.map(path=><option key={path} value={path}/>)}</datalist></>:<Literal value={value.value} label={label+' value'} onChange={v=>onChange({value:v})}/>}</div>;
}
function Literal({value,label,onChange}:{value:unknown;label:string;onChange:(value:unknown)=>void}){
  const field=useRef<HTMLTextAreaElement>(null),serialized=format(value),[text,setText]=useState(serialized),[invalid,setInvalid]=useState(false);
  useEffect(()=>{setText(serialized);setInvalid(false);field.current?.setCustomValidity('');},[serialized]);
  return <><textarea ref={field} aria-label={label} className="binding-literal" value={text} onChange={e=>{setText(e.target.value);try{const parsed=JSON.parse(e.target.value);e.target.setCustomValidity('');onChange(parsed);setInvalid(false);}catch{e.target.setCustomValidity('Invalid JSON');setInvalid(true);}}}/>{invalid&&<small role="alert">JSON</small>}</>;
}
export function BindingsEditor({value,onChange,label,paths=[],lang}:{value:Record<string,Binding>;onChange:(value:Record<string,Binding>)=>void;label:string;paths?:string[];lang:Lang}){
  const [name,setName]=useState('');
  return <div className="bindings-editor" aria-label={label}>{Object.entries(value).map(([key,binding])=><div className="binding-row" key={key}><div className="binding-key"><strong>{key}</strong><button aria-label={'Remove '+label+' '+key} onClick={()=>onChange(Object.fromEntries(Object.entries(value).filter(([k])=>k!==key)))}>×</button></div><BindingValue label={label+' '+key} value={binding} onChange={b=>onChange({...value,[key]:b})} paths={paths} lang={lang}/></div>)}<div className="inline-form"><input aria-label={label+' name'} value={name} placeholder={lang==='zh'?'字段名，例如 story':'Field name, e.g. story'} onChange={e=>setName(e.target.value)}/><button disabled={!/^[A-Za-z][A-Za-z0-9_]*$/.test(name)||name in value} onClick={()=>{onChange({...value,[name]:{ref:'input.'+name}});setName('');}}>{lang==='zh'?'添加字段':'Add field'}</button></div></div>;
}
export function outputPaths(graph:Graph){return ['input',...Object.entries(graph.nodes).flatMap(([id,node])=>['nodes.'+id+'.output',...Object.keys((node.output_schema?.properties??{}) as Json).map(key=>'nodes.'+id+'.output.'+key)])];}
export function NodeFields({node,doc,graph,lang,onChange}:{node:NodeSpec;doc:Document;graph:Graph;lang:Lang;onChange:(node:NodeSpec)=>void}){
  const say=(zh:string,en:string)=>lang==='zh'?zh:en,paths=outputPaths(graph),change=(patch:Partial<NodeSpec>)=>onChange({...node,...patch});
  return <div className="node-fields">
    {['tool','code'].includes(node.type)&&<section className="setting-section"><h4>{say('执行工具','Execution tool')}</h4><label>{say('选择工具','Select tool')}<select aria-label="Node tool" value={node.tool??''} onChange={e=>change({tool:e.target.value})}>{Object.entries(doc.spec.tools).filter(([,tool])=>node.type!=='code'||tool.plugin==='code.python').map(([alias,tool])=><option key={alias} value={alias}>{alias} · {tool.plugin}</option>)}</select></label>{node.type==='code'&&<label>{say('代码资源','Code resource')}<select aria-label="Node code resource" value={node.code??''} onChange={e=>change({code:e.target.value})}>{Object.entries(doc.spec.resources).filter(([,r])=>r.role==='code').map(([alias])=><option key={alias}>{alias}</option>)}</select></label>}</section>}
    {node.type==='map'&&<section className="setting-section"><h4>{say('逐项处理','Process each item')}</h4><BindingValue label="Map items" value={node.items??{ref:'input.items'}} onChange={items=>change({items})} paths={paths} lang={lang}/><label>{say('最多处理项数','Maximum items')}<input aria-label="Maximum items" type="number" value={node.max_items??32} onChange={e=>change({max_items:Number(e.target.value)})}/></label></section>}
    {node.type==='loop'&&<section className="setting-section"><h4>{say('重试与停止','Retry and stop')}</h4><label>{say('最多循环次数','Maximum iterations')}<input aria-label="Maximum iterations" type="number" value={node.max_iterations??3} onChange={e=>change({max_iterations:Number(e.target.value)})}/></label><label>{say('停止条件字段为真时退出','Stop when this field is true')}<input aria-label="Loop accepted reference" placeholder="input.accepted" value={node.until?.op==='truthy'&&'ref' in node.until.left?node.until.left.ref:''} onChange={e=>change({until:e.target.value?{left:{ref:e.target.value},op:'truthy'}:null})}/></label></section>}
    <details className="setting-section node-inputs" open><summary>{say('输入连接','Input connections')}</summary><BindingsEditor value={node.inputs} onChange={inputs=>change({inputs})} label="Node input" paths={paths} lang={lang}/></details>
    <details className="setting-section"><summary>{say('输出格式','Output schema')}</summary><JsonField label={say('输出格式 JSON','Output schema JSON')} value={node.output_schema} onChange={output_schema=>change({output_schema})}/></details>
  </div>;
}
export function WorkflowFields({spec,graph,lang,onChange,onGraph}:{spec:Spec;graph:Graph;lang:Lang;onChange:(spec:Spec)=>void;onGraph:(graph:Graph)=>void}){
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  return <div className="workflow-fields"><h3>{say('工作流设置','Workflow settings')}</h3><label>{say('开始节点','Entry node')}<select aria-label="Workflow entry" value={graph.entry} onChange={e=>onGraph({...graph,entry:e.target.value})}>{Object.keys(graph.nodes).map(id=><option key={id}>{id}</option>)}</select></label><details open><summary>{say('应用输入','Application input')}</summary><JsonField label={say('应用输入 JSON','Application input JSON')} value={spec.input_schema} onChange={input_schema=>onChange({...spec,input_schema})}/></details><details open><summary>{say('工作流输出','Workflow output')}</summary><BindingsEditor value={graph.output} onChange={output=>onGraph({...graph,output})} label="Workflow output" paths={outputPaths(graph)} lang={lang}/></details><details><summary>{say('应用输出与预算','Application output and budget')}</summary><JsonField label={say('应用输出 JSON','Application output JSON')} value={spec.output_schema} onChange={output_schema=>onChange({...spec,output_schema})}/><JsonField label={say('执行预算 JSON','Execution budget JSON')} value={spec.execution??{}} onChange={execution=>onChange({...spec,execution:execution as Spec['execution']})}/></details></div>;
}
