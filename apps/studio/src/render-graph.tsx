import {useEffect, useMemo, useState} from 'react';
import {ReactFlow, Background, Controls, MiniMap, Position, type Node, type Edge, type ReactFlowInstance} from '@xyflow/react';
import type {Api, Document, Lang} from './types';

type InputSchema={type?:string;enum?:unknown[];minimum?:number;maximum?:number;description?:string};
type ComputeNode={id:string;class_type:string;title:string;mode:number;position:number[]|Record<string,number>;inputs:Record<string,unknown>;input_schemas?:Record<string,InputSchema>};
type Recipe={name:string;revision:number;workflow_hash:string;workflow:Record<string,unknown>;nodes:ComputeNode[]};
function category(type:string){return /attention|chunk|preview|resolution|shift/i.test(type)?['tune','≋']:/sampl|scheduler|reference.*video/i.test(type)?['sample','◈']:/lora|unet|clip.*load|vae.*load/i.test(type)?['model','⬡']:/load.*image|load.*video|load.*audio/i.test(type)?['asset','▧']:/combine|save|decode/i.test(type)?['output','▸']:['value','·'];}
export function RenderGraph({api,projectId,lang,onSaved,onClose}:{api:Api;projectId:string;lang:Lang;onSaved:(doc:Document)=>void;onClose:()=>void}){
  const [names,setNames]=useState<{name:string;node_count:number}[]>([]),[name,setName]=useState('');
  const [recipe,setRecipe]=useState<Recipe>(),[selected,setSelected]=useState(''),[query,setQuery]=useState('');
  const [draft,setDraft]=useState('{}'),[enabled,setEnabled]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(false),[advanced,setAdvanced]=useState(false);
  const [flow,setFlow]=useState<ReactFlowInstance>();
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  useEffect(()=>{let active=true;api(`/projects/${projectId}/recipes`).then(r=>r.json()).then(rows=>{if(active){setNames(rows);setName(rows[0]?.name??'');}}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[projectId]);
  useEffect(()=>{if(!name)return;let active=true;setRecipe(undefined);api(`/projects/${projectId}/recipes/${encodeURIComponent(name)}`).then(r=>r.json()).then(data=>{if(active){setRecipe(data);setSelected('');}}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[projectId,name]);
  const view=useMemo(()=>{
    if(!recipe)return {nodes:[],edges:[]};
    const links=recipe.workflow.links as (unknown[]|Record<string,unknown>)[]|undefined;
    const edges:Edge[]=(links??[]).map((l,i)=>({id:String(i),source:String(Array.isArray(l)?l[1]:l.origin_id),target:String(Array.isArray(l)?l[3]:l.target_id),type:'smoothstep'}));
    if(!links)for(const n of recipe.nodes)for(const [key,value] of Object.entries(n.inputs)){if(Array.isArray(value)&&value.length===2&&typeof value[0]==='string')edges.push({id:n.id+key,source:value[0],target:n.id,type:'smoothstep'});}
    // API-format workflows have no saved positions. Lay out dependency layers.
    const positions=new Map<string,{x:number;y:number}>();
    if(!Array.isArray(recipe.workflow.nodes)){
      const ids=new Set(recipe.nodes.map(n=>n.id)),incoming=new Map([...ids].map(id=>[id,new Set<string>()])),outgoing=new Map([...ids].map(id=>[id,new Set<string>()]));
      for(const edge of edges)if(ids.has(edge.source)&&ids.has(edge.target)&&edge.source!==edge.target){incoming.get(edge.target)!.add(edge.source);outgoing.get(edge.source)!.add(edge.target);}
      const pending=new Map([...incoming].map(([id,from])=>[id,from.size])),depth=new Map([...ids].map(id=>[id,0]));
      const queue=[...ids].filter(id=>pending.get(id)===0);
      for(let i=0;i<queue.length;i++)for(const next of outgoing.get(queue[i])!){depth.set(next,Math.max(depth.get(next)!,depth.get(queue[i])!+1));pending.set(next,pending.get(next)!-1);if(pending.get(next)===0)queue.push(next);}
      const rows=new Map<number,number>();
      for(const id of ids){const column=depth.get(id)!,row=rows.get(column)??0;rows.set(column,row+1);positions.set(id,{x:column*340,y:row*170});}
    }
    const nodes:Node[]=recipe.nodes.map(n=>({id:n.id,position:positions.get(n.id)??{x:(Array.isArray(n.position)?n.position[0]:n.position["0"])??0,y:(Array.isArray(n.position)?n.position[1]:n.position["1"])??0},
      sourcePosition:Position.Right,targetPosition:Position.Left,width:240,height:120,measured:{width:240,height:120},selected:selected===n.id,
      data:{label:<><small>{n.id} · {n.class_type}</small><strong><b className="compute-icon">{category(n.class_type)[1]}</b>{n.title}</strong><span>{n.mode===4?say('已旁路','Bypassed'):n.mode===2?say('已禁用','Disabled'):say('已启用','Enabled')} · {Object.keys(n.inputs).length} {say('个参数','parameters')}</span></>},
      className:'compute-card compute-'+category(n.class_type)[0]+(n.mode?' muted':''),style:{height:120,opacity:!query||`${n.title} ${n.class_type} ${n.id}`.toLowerCase().includes(query.toLowerCase())?1:.18}}));
    return {nodes,edges};
  },[recipe,selected,query,lang]);
  const node=recipe?.nodes.find(n=>n.id===selected);
  let values:Record<string,unknown>={};try{values=JSON.parse(draft);}catch{/* The JSON editor displays its parse error when saving. */}
  function update(key:string,value:unknown){setDraft(JSON.stringify({...values,[key]:value},null,2));}
  const dirty=!!node&&(draft!==JSON.stringify(node.inputs,null,2)||enabled!==(node.mode===0));
  function discard(){return !dirty||window.confirm(say('放弃尚未保存的节点参数？','Discard unsaved node parameters?'));}
  function choose(id:string,focus=false){if(!discard())return;const n=recipe?.nodes.find(n=>n.id===id);if(!n)return;setSelected(id);setDraft(JSON.stringify(n.inputs,null,2));setEnabled(n.mode===0);setAdvanced(false);setError('');if(focus)flow?.fitView({nodes:[{id}],maxZoom:1,padding:1.2,duration:250});}
  async function save(){if(!recipe||!node)return;setBusy(true);setError('');try{
    const inputs=JSON.parse(draft);if(!inputs||Array.isArray(inputs)||typeof inputs!=='object')throw Error('Inputs must be a JSON object');
    const changedInputs=Object.fromEntries(Object.entries(inputs).filter(([key,value])=>JSON.stringify(value)!==JSON.stringify(node.inputs[key])));
    const changes:Record<string,unknown>={inputs:changedInputs};if(enabled!==(node.mode===0))changes.enabled=enabled;
    const result=await(await api(`/projects/${projectId}/recipes/${encodeURIComponent(name)}`,{method:'POST',body:JSON.stringify({revision:recipe.revision,workflow_hash:recipe.workflow_hash,changes:{[node.id]:changes}})})).json();
    const next=await(await api(`/projects/${projectId}/recipes/${encodeURIComponent(name)}`)).json();setRecipe(next);const saved=next.nodes.find((n:ComputeNode)=>n.id===node.id);if(saved){setDraft(JSON.stringify(saved.inputs,null,2));setEnabled(saved.mode===0);}onSaved(result.project);
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  function download(){if(!recipe)return;const url=URL.createObjectURL(new Blob([JSON.stringify(recipe.workflow,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  return <section className="render-graph" aria-label="Render graph"><header><div><h2>{say('渲染工作流','Render workflow')}</h2><span>{recipe?.nodes.length??0} {say('个节点 · 模型、参考素材、采样与输出','nodes · models, references, sampling and outputs')}</span></div><select aria-label="Render recipe" value={name} disabled={busy} onChange={e=>{if(discard())setName(e.target.value);}}>{names.map(n=><option key={n.name}>{n.name}</option>)}</select><button onClick={download} disabled={!recipe||dirty}>{say('导出 ComfyUI','Export ComfyUI')}</button><button disabled={busy} onClick={()=>{if(discard())onClose();}}>{say('返回制作团队','Back to team')}</button></header>
    {error&&<p role="alert">{error}</p>}{!names.length&&<p>{say('连接渲染配方后，可在这里编辑完整工作流。','Connect a render recipe to edit its complete workflow here.')}</p>}
    <div className="render-graph-body"><div className="compute-canvas"><input aria-label="Search compute nodes" placeholder={say('搜索模型或节点','Find a model or node')} value={query} onChange={e=>setQuery(e.target.value)}/>{recipe&&<ReactFlow onInit={setFlow} key={name} nodes={view.nodes} edges={view.edges} onlyRenderVisibleElements nodesConnectable={false} nodesDraggable={false} onNodeClick={(_,n)=>choose(n.id)} fitView minZoom={.03} maxZoom={2}><Background/><Controls showInteractive={false}/><MiniMap nodeColor="#bdc9c3" maskColor="#fafafa99" pannable zoomable/></ReactFlow>}</div>
      <aside>{!node&&<div className="compute-node-list">{recipe?.nodes.filter(n=>!query||`${n.title} ${n.class_type} ${n.id}`.toLowerCase().includes(query.toLowerCase())).map(n=><button key={n.id} onClick={()=>choose(n.id,true)}><small>{n.id} · {n.class_type}</small>{n.title}</button>)}</div>}<h3>{node?.title??say('选择一个节点','Select a node')}</h3>{node&&<><button disabled={busy} onClick={()=>{if(discard())setSelected('');}}>{say('全部节点','All nodes')}</button><code>{node.class_type}</code><fieldset disabled={busy}><label className="check"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>{say('启用','Enabled')}</label><div className="compute-fields">{!advanced&&Object.entries(values).map(([key,value])=>{const schema=node.input_schemas?.[key]??{};return <label key={key} title={schema.description}><span>{key.replaceAll('_',' ')}</span>{schema.enum?<select aria-label={key} value={JSON.stringify(value)} onChange={e=>update(key,JSON.parse(e.target.value))}>{schema.enum.map(v=><option key={JSON.stringify(v)} value={JSON.stringify(v)}>{String(v)}</option>)}</select>:typeof value==='boolean'?<input aria-label={key} type="checkbox" checked={value} onChange={e=>update(key,e.target.checked)}/>:typeof value==='number'?<input aria-label={key} type="number" min={schema.minimum} max={schema.maximum} step={schema.type==='integer'?1:'any'} value={value} onChange={e=>{if(e.target.value!==''&&Number.isFinite(e.target.valueAsNumber))update(key,e.target.valueAsNumber);}}/>:typeof value==='string'?<textarea aria-label={key} rows={value.length>100?5:2} value={value} onChange={e=>update(key,e.target.value)}/>:<code>{JSON.stringify(value)}</code>}</label>;})}</div><button onClick={()=>setAdvanced(!advanced)}>{advanced?say('使用参数表单','Use parameter form'):say('编辑 JSON','Edit JSON')}</button>{advanced&&<label>{say('节点参数','Node parameters')}<textarea aria-label="Compute node parameters" value={draft} onChange={e=>setDraft(e.target.value)} spellCheck={false}/></label>}</fieldset><button className="primary" onClick={save} disabled={busy||!dirty}>{say('保存参数','Save parameters')}</button></>}</aside></div>
  </section>;
}
