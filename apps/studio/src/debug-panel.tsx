import {useEffect, useState} from 'react';
import type {Document, Lang} from './types';

export type Schema = {type?:string;properties?:Record<string,Schema>;items?:Schema;enum?:unknown[];default?:unknown;required?:string[];description?:string;minimum?:number;maximum?:number};
type Plan = {selected:string[];path:string[];boundary:{reference:string;source:string;field:string;optional:boolean;schema:Schema}[];upstream:Record<string,unknown>;previous_input?:Record<string,unknown>;source_contexts:string[];source_prefix:string;input_schema:{properties:{project:Schema;upstream:Schema}}};
type Api = (path:string,init?:RequestInit)=>Promise<Response>;

export function empty(schema:Schema):unknown {
  if(schema.default!==undefined)return schema.default;
  if(schema.enum?.length)return schema.enum[0];
  if(schema.type==='object')return Object.fromEntries(Object.entries(schema.properties??{}).map(([k,s])=>[k,empty(s)]));
  if(schema.type==='array')return [];
  if(schema.type==='boolean')return false;
  if(schema.type==='number'||schema.type==='integer')return Math.min(schema.maximum??Infinity,Math.max(schema.minimum??-Infinity,0));
  return '';
}

export function ValueField({schema,value,onChange,label,lang}:{schema:Schema;value:unknown;onChange:(v:unknown)=>void;label:string;lang:Lang}) {
  if(schema.enum)return <label>{label}<select aria-label={label} value={JSON.stringify(value??schema.enum[0])} onChange={e=>onChange(JSON.parse(e.target.value))}>{schema.enum.map(v=><option key={JSON.stringify(v)} value={JSON.stringify(v)}>{String(v)}</option>)}</select></label>;
  if(schema.type==='object'&&schema.properties)return <fieldset className="debug-fields"><legend>{label}</legend>{Object.entries(schema.properties).map(([key,s])=><ValueField key={key} schema={s} value={(value as Record<string,unknown>)?.[key]} onChange={v=>onChange({...value as object,[key]:v})} label={key} lang={lang}/>)}</fieldset>;
  if(schema.type==='array'&&schema.items){const items=Array.isArray(value)?value:[];return <fieldset className="debug-fields"><legend>{label}</legend>{items.map((v,i)=><div key={i}><ValueField schema={schema.items!} value={v} onChange={next=>onChange(items.map((old,j)=>j===i?next:old))} label={`${label} ${i+1}`} lang={lang}/><button onClick={()=>onChange(items.filter((_,j)=>j!==i))}>{lang==='zh'?'移除':'Remove'}</button></div>)}<button onClick={()=>onChange([...items,empty(schema.items!)])}>{lang==='zh'?'添加一项':'Add item'}</button></fieldset>;}
  if(schema.type==='boolean')return <label className="check"><input type="checkbox" checked={!!value} onChange={e=>onChange(e.target.checked)}/>{label}</label>;
  if(schema.type==='number'||schema.type==='integer')return <label>{label}<input aria-label={label} type="number" min={schema.minimum} max={schema.maximum} step={schema.type==='integer'?1:'any'} value={typeof value==='number'?value:''} onChange={e=>onChange(e.target.value===''?undefined:Number(e.target.value))}/>{schema.description&&<small>{schema.description}</small>}</label>;
  if(schema.type==='string')return <label>{label}<textarea aria-label={label} value={typeof value==='string'?value:''} onChange={e=>onChange(e.target.value)}/></label>;
  return <JsonField value={value??{}} onChange={onChange} label={label}/>;
}

function JsonField({value,onChange,label}:{value:unknown;onChange:(v:unknown)=>void;label:string}) {
  const [text,setText]=useState(JSON.stringify(value,null,2));const [error,setError]=useState('');
  useEffect(()=>setText(JSON.stringify(value,null,2)),[value]);
  return <label>{label}<textarea aria-label={label} value={text} onChange={e=>{setText(e.target.value);try{const v=JSON.parse(e.target.value);onChange(v);setError('');e.target.setCustomValidity('');}catch{setError('Invalid JSON');e.target.setCustomValidity('Invalid JSON');}}}/>{error&&<small role="alert">{error}</small>}</label>;
}

export function DebugPanel({doc,nodes,path,api,lang,initialInput,sourceRunId,mock,allowWrites,disabled,onStart,onClose}:{doc:Document;nodes:string[];path:string[];api:Api;lang:Lang;initialInput:Record<string,unknown>;sourceRunId?:string;mock:boolean;allowWrites:boolean;disabled:boolean;onStart:(id:string)=>void;onClose:()=>void}) {
  const [plan,setPlan]=useState<Plan|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const [project,setProject]=useState<unknown>(path.length?{}:initialInput);const [upstream,setUpstream]=useState<Record<string,unknown>>({});
  const [reuse,setReuse]=useState<string>();
  const [sourcePrefix,setSourcePrefix]=useState('graph');
  const request={revision:doc.revision,nodes,path,...(reuse?{source_run_id:reuse,source_prefix:sourcePrefix}:{})};
  useEffect(()=>{let active=true;setPlan(null);setError('');api(`/projects/${doc.id}/debug/plan`,{method:'POST',body:JSON.stringify(request)}).then(r=>r.json()).then((next:Plan)=>{if(!active)return;setPlan(next);if(reuse&&next.previous_input)setProject(next.previous_input);setUpstream(Object.fromEntries(Object.entries(next.input_schema.properties.upstream.properties??{}).map(([key,s])=>[key,next.upstream[key]??empty(s)])));}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[doc.id,doc.revision,JSON.stringify(nodes),JSON.stringify(path),reuse,sourcePrefix,api]);
  return <section className="debug-panel" aria-label={lang==='zh'?'节点调试':'Node debug'}><div className="debug-heading"><strong>{lang==='zh'?'调试所选节点':'Debug selection'}</strong><button onClick={onClose} aria-label={lang==='zh'?'关闭调试':'Close debug'}>×</button></div><p>{nodes.join(' · ')}</p><p className="hint">{lang==='zh'?'填写输入，检查这一段的结果。上游节点不会重新运行。':'Supply inputs and inspect this section. Upstream nodes stay idle.'}</p>
    {sourceRunId&&<button disabled={busy} onClick={()=>{setReuse(sourceRunId);setSourcePrefix('graph');}}>{lang==='zh'?'填入上次运行的结果':'Use outputs from the last run'}</button>}
    {plan&&plan.source_contexts?.length>1&&<label>{lang==='zh'?'选择执行片段':'Saved execution'}<select aria-label={lang==='zh'?'选择执行片段':'Saved execution'} value={plan.source_prefix} onChange={e=>setSourcePrefix(e.target.value)}>{plan.source_contexts.map(prefix=><option key={prefix} value={prefix}>{prefix.replace(/^graph\//,'').replace(/item-(\d+)/g,(_,i)=>lang==='zh'?`第 ${Number(i)+1} 项`:`Item ${Number(i)+1}`).replace(/iteration-(\d+)/g,(_,i)=>lang==='zh'?`第 ${Number(i)+1} 轮`:`Take ${Number(i)+1}`)}</option>)}</select></label>}
    {plan&&<><ValueField schema={plan.input_schema.properties.project} value={project} onChange={setProject} label={lang==='zh'?(path.length?'子流程输入':'项目输入'):(path.length?'Subflow input':'Project input')} lang={lang}/>{plan.boundary.length>0&&<><h4>{lang==='zh'?'所需上游输出':'Upstream outputs'}</h4>{Object.entries(plan.input_schema.properties.upstream.properties??{}).map(([key,s])=><ValueField key={key+String(reuse)} schema={s} value={upstream[key]} onChange={v=>setUpstream(old=>({...old,[key]:v}))} label={key} lang={lang}/>)}</>}
      <button className="primary" disabled={disabled||busy} onClick={async e=>{const fields=e.currentTarget.closest('section')!.querySelectorAll<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement>('input,textarea,select');if(Array.from(fields).some(field=>!field.reportValidity()))return;setBusy(true);setError('');try{const result=await(await api(`/projects/${doc.id}/debug/runs`,{method:'POST',body:JSON.stringify({...request,input:project,upstream,mock,allow_writes:allowWrites})})).json();onStart(result.run_id);}catch(e){setError(String(e));}finally{setBusy(false);}}}>{busy?(lang==='zh'?'正在启动…':'Starting…'):(lang==='zh'?'运行所选节点':'Run selected nodes')}</button></>}
    {error&&<p role="alert" className="debug-error">{error}</p>}
  </section>;
}
