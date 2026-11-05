import { useEffect, useState } from 'react';
import { MemoryControls } from './memory-controls';
import { MediaPreview } from './media-preview';
import { HumanResponse } from './human-response';
import {RunSteps,type DebugTarget} from './run-steps';
import type { Study } from './improve-panel';
export { ImprovePanel } from './improve-panel';
import type { Api, Document, Lang, Run } from './types';

type Props = { doc: Document; api: Api; lang: Lang; onError: (error: unknown) => void };
const json = (value: unknown) => JSON.stringify(value, null, 2);
const post = (body?: unknown): RequestInit => ({method:'POST', ...(body ? {body:JSON.stringify(body)} : {})});
const short = (value: string) => value.slice(0,12);
const say = (lang:Lang, zh:string,en:string) => lang==='zh'?zh:en;
function Empty({children}:{children:React.ReactNode}) { return <p className="panel-empty">{children}</p>; }

export function ResourcesPanel({doc,lang,onChange,onError}:Props & {onChange:(doc:Document)=>void}) {
  const [name,setName]=useState('instructions');const [role,setRole]=useState<'prompt'|'skill'|'code'>('prompt');
  const resources=doc.resources ?? {};
  function add() {
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(name)||doc.spec.resources[name]) throw new Error(say(lang,'资源名无效或已存在','Invalid or existing resource name'));
    const spec=structuredClone(doc.spec);
    const target=Object.values(spec.graph.nodes).find(node=>['model','agent'].includes(node.type));
    const content=role==='code'?'def run(inputs):\n    return inputs\n':typeof target?.instructions==='string'?target.instructions:'Write the instruction here.';
    spec.resources[name]={path:`${role==='code'?'code':role==='skill'?'skills':'prompts'}/${name}.${role==='code'?'py':'md'}`,role};
    if(role==='prompt' && target && typeof target.instructions==='string') target.instructions={resource:name};
    onChange({...doc,spec,resources:{...resources,[name]:content}});
  }
  return <section className="panel"><h2>{say(lang,'提示与技能资源','Prompt and skill resources')}</h2>
    <p className="muted">{say(lang,'编辑资源后保存项目。改进任务只会修改你选中的资源。','Save after editing. Improvement jobs change only the resources you select.')}</p>
    <div className="inline-form"><select aria-label="Resource type" value={role} onChange={e=>setRole(e.target.value as 'prompt'|'skill'|'code')}><option value="prompt">Prompt</option><option value="skill">Skill</option><option value="code">Code</option></select><input aria-label="Resource name" value={name} onChange={e=>setName(e.target.value)}/><button onClick={()=>{try{add();}catch(e){onError(e);}}}>{say(lang,'将指令保存为资源','Create instruction resource')}</button></div>
    <label className="library-import import-project">{say(lang,'导入工具与资源库','Import tool and resource library')}<input type="file" accept=".json" aria-label="Import resource library" onChange={async event=>{
      const file=event.target.files?.[0];if(!file)return;
      try{
        if(file.size>2_000_000)throw Error('Library exceeds 2 MB');
        const library=JSON.parse(await file.text()),spec=structuredClone(doc.spec),content={...resources};
        if(library.format!=='evosprig.library.v1')throw Error('Expected evosprig.library.v1');
        for(const [key,item] of Object.entries(library.resources??{}) as [string,{path:string;role:'prompt'|'skill'|'code';content:string}][]){
          if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(key)||spec.resources[key])throw Error('Invalid or existing resource: '+key);
          if(!item||typeof item.content!=='string'||typeof item.path!=='string'||!['prompt','skill','code'].includes(item.role))throw Error('Invalid resource: '+key);
          spec.resources[key]={path:item.path,role:item.role};content[key]=item.content;
        }
        for(const [key,item] of Object.entries(library.tools??{}) as [string,{plugin:string;version:string}][]){
          if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(key)||spec.tools[key]||typeof item?.plugin!=='string')throw Error('Invalid or existing tool: '+key);
          spec.tools[key]={plugin:item.plugin,version:item.version??'1'};
        }
        onChange({...doc,spec,resources:content});
      }catch(error){onError(error);}finally{event.target.value='';}
    }}/></label><p className="hint">{say(lang,'资源库包含提示词、技能、代码和工具声明。节点和连线在画布中创建。','Libraries provide prompts, skills, code and tool declarations. Create nodes and connections on the canvas.')}</p>
    {!Object.keys(doc.spec.resources).length && <Empty>{say(lang,'先将模型指令保存为资源，即可运行改进。','Create an instruction resource to enable improvement.')}</Empty>}
    {Object.entries(doc.spec.resources).map(([key,meta])=><article className="card" key={key}><h3>{key} <span className="pill">{meta.role}</span></h3><p className="mono muted">{meta.path}</p>
      <textarea className="resource-editor" aria-label={`Resource ${key}`} value={resources[key]??''} onChange={e=>onChange({...doc,resources:{...resources,[key]:e.target.value}})}/></article>)}
  </section>;
}

type Memory = {id:string; content:string; source:string; revision:number};
type DocumentInfo = {id:string; title:string; source:string; chunks:number};
type Citation = {citation:string; title:string; source:string; text:string};
export function MemoryPanel({doc,api,lang,onError}:Props) {
  const [records,setRecords]=useState<Memory[]>([]); const [documents,setDocuments]=useState<DocumentInfo[]>([]);
  const [content,setContent]=useState(''); const [source,setSource]=useState('user:explicit'); const [title,setTitle]=useState(''); const [text,setText]=useState('');
  const [query,setQuery]=useState(''); const [hits,setHits]=useState<Citation[]>([]); const [busy,setBusy]=useState(false);
  const path=`/projects/${doc.id}`;
  async function refresh(){const [facts,docs]=await Promise.all([api(path+'/memory'),api(path+'/documents')]);setRecords(await facts.json());setDocuments(await docs.json());}
  useEffect(()=>{refresh().catch(onError);},[doc.id,api]);
  async function action(fn:()=>Promise<void>){setBusy(true);try{await fn();await refresh();}catch(e){onError(e);}finally{setBusy(false);}}
  return <section className="panel"><h2>{say(lang,'记忆与资料','Memory and documents')}</h2><p className="muted">{say(lang,'内容仅属于当前用户和项目。资料检索保留来源与引用位置。','Records belong to the current user and project. Document results retain sources and citation offsets.')}</p>
    <div className="panel-grid"><article className="card"><h3>{say(lang,'新增事实','Add a fact')}</h3><label>{say(lang,'内容','Content')}<textarea aria-label="Memory content" value={content} onChange={e=>setContent(e.target.value)}/></label>
      <label>{say(lang,'来源','Source')}<input aria-label="Memory source" value={source} onChange={e=>setSource(e.target.value)}/></label><button disabled={busy||!content.trim()} onClick={()=>action(async()=>{await api(path+'/memory',post({content,source}));setContent('');})}>{say(lang,'保存记忆','Save memory')}</button></article>
      <article className="card"><h3>{say(lang,'添加文档','Add a document')}</h3><label>{say(lang,'标题','Title')}<input aria-label="Document title" value={title} onChange={e=>setTitle(e.target.value)}/></label>
        <label>{say(lang,'正文','Text')}<textarea aria-label="Document text" value={text} onChange={e=>setText(e.target.value)}/></label><button disabled={busy||!text.trim()||!title.trim()} onClick={()=>action(async()=>{await api(path+'/documents',post({title,text,source:source||'user:document'}));setText('');setTitle('');})}>{say(lang,'保存文档','Save document')}</button></article></div>
    <div className="panel-grid"><article className="card"><h3>{say(lang,'事实记录','Facts')}</h3>{!records.length&&<Empty>{say(lang,'暂无记忆','No memory yet')}</Empty>}{records.map(record=><div className="record" key={record.id}><p>{record.content}</p><small>{record.source}</small><button aria-label={`Delete memory ${record.id}`} onClick={()=>action(async()=>{await api(path+'/memory/'+record.id,{method:'DELETE'});})}>{say(lang,'删除','Delete')}</button></div>)}</article>
    <article className="card"><h3>{say(lang,'项目资料','Project documents')}</h3>{!documents.length&&<Empty>{say(lang,'暂无资料','No documents yet')}</Empty>}{documents.map(record=><div className="record" key={record.id}><strong>{record.title}</strong><small>{record.source} · {record.chunks} chunks</small><button aria-label={`Delete document ${record.title}`} onClick={()=>action(async()=>{await api(path+'/documents/'+record.id,{method:'DELETE'});setHits([]);})}>{say(lang,'删除','Delete')}</button></div>)}</article></div>
    <MemoryControls project={doc.id} api={api} lang={lang} onError={onError}/>
    <article className="card"><h3>{say(lang,'检索引用','Search citations')}</h3><div className="inline-form"><input aria-label="Document query" value={query} onChange={e=>setQuery(e.target.value)} placeholder={say(lang,'输入关键词','Enter keywords')}/><button onClick={()=>api(path+'/documents/search?query='+encodeURIComponent(query)).then(r=>r.json()).then(setHits).catch(onError)}>{say(lang,'检索','Search')}</button></div>
      {hits.map(hit=><blockquote key={hit.citation}><strong>{hit.title}</strong><p>{hit.text}</p><cite>{hit.citation} · {hit.source}</cite></blockquote>)}</article>
  </section>;
}

export function RunDetails({run,api,lang,onError,onRefresh,onDebug,debugDisabled}:{run:Run;api:Api;lang:Lang;onError:(e:unknown)=>void;onRefresh:()=>void;onDebug?:(target:DebugTarget)=>void;debugDisabled?:boolean}){
  const act=async(path:string,body?:unknown)=>{try{await api(`/runs/${run.run_id}/${path}`,post(body));onRefresh();}catch(e){onError(e);}};
  return <div><div className="metrics"><span className={`status-badge status-${run.status}`}>{run.status}</span><span className="mono">{short(run.agent_version)}</span><span>{String(run.usage?.input_tokens??0)} / {String(run.usage?.output_tokens??0)} tokens</span></div>
    <RunSteps run={run} api={api} lang={lang} onDebug={onDebug} disabled={debugDisabled}/>
    <MediaPreview value={run.output} lang={lang}/>
    <pre className="json-block">{json(run.output??run.error??{})}</pre>
    {run.waiting?.map(wait=><article className="card" key={run.run_id+wait.path}><h3>{wait.kind==='human'?say(lang,'等待你的确认','Waiting for your input'):say(lang,'等待外部结果','Waiting for external result')}</h3><p className="mono">{wait.path}</p>
      <MediaPreview value={wait.input} lang={lang}/>
      <details><summary>{say(lang,'查看输入','View input')}</summary><pre className="json-block">{json(wait.input??wait)}</pre></details>
      {run.status==='waiting_input'&&<HumanResponse wait={wait} lang={lang} onSubmit={response=>act('input',{path:wait.path,response})}/>}
    </article>)}
    {!['succeeded','failed','canceled'].includes(run.status)&&<div className="inline-form">{['queued','running','waiting_external'].includes(run.status)&&<button onClick={()=>act('resume')}>{say(lang,'恢复运行','Resume')}</button>}<button onClick={()=>act('cancel')}>{say(lang,'取消运行','Cancel run')}</button></div>}
    <details><summary>{say(lang,'事件与用量','Events and usage')}</summary><pre className="json-block">{json(run)}</pre></details>
  </div>;
}

export function RunsPanel({doc,api,lang,onError,onDebug,debugDisabled}:Props&{onDebug?:(target:DebugTarget)=>void;debugDisabled?:boolean}){
  const [runs,setRuns]=useState<Run[]>([]);const [selected,setSelected]=useState<string|null>(null);const [revision,setRevision]=useState(0);
  useEffect(()=>{let active=true;let timer:ReturnType<typeof setTimeout>;const update=async()=>{try{const next:Run[]=await(await api(`/projects/${doc.id}/runs`)).json();if(!active)return;setRuns(next);timer=setTimeout(update,1500);}catch(e){if(active)onError(e);}};void update();return()=>{active=false;clearTimeout(timer);};},[doc.id,api,revision]);
  const run=runs.find(item=>item.run_id===selected)??runs[0];
  return <section className="panel"><h2>{say(lang,'运行历史与恢复','Run history and recovery')}</h2>{!runs.length?<Empty>{say(lang,'运行项目后，可在这里查看历史。','Run the project to see its history here.')}</Empty>:<div className="history-layout"><div className="history-list">{runs.map(item=><button className={run?.run_id===item.run_id?'selected-record':''} key={item.run_id} onClick={()=>setSelected(item.run_id)}><strong>{item.status}</strong><small>{short(item.run_id)} · {short(item.agent_version)}</small></button>)}</div><article className="card">{run&&<RunDetails key={run.run_id} run={run} api={api} lang={lang} onError={onError} onRefresh={()=>setRevision(n=>n+1)} onDebug={onDebug} debugDisabled={debugDisabled}/>}</article></div>}</section>;
}


type Candidate={id:string;version_id:string;base_version:string;method:string;diff:Record<string,string>};
type Release={revision:number;version_id:string|null;reason?:string};
export function VersionsPanel({doc,api,lang,onError,onExport,onRun}:Props&{onExport:(id?:string)=>void;onRun:(id?:string)=>void}){
  const [candidates,setCandidates]=useState<Candidate[]>([]);const [studies,setStudies]=useState<Study[]>([]);const [release,setRelease]=useState<Release>({revision:0,version_id:null});const [history,setHistory]=useState<Release[]>([]);const base=`/projects/${doc.id}`;
  async function refresh(){const values=await Promise.all(['/candidates','/studies','/release','/release/history'].map(path=>api(base+path).then(r=>r.json())));setCandidates(values[0]);setStudies(values[1]);setRelease(values[2]);setHistory(values[3]);}
  useEffect(()=>{refresh().catch(onError);},[doc.id,api]);
  async function action(path:string,body:unknown){try{await api(base+path,post(body));await refresh();}catch(e){onError(e);}}
  return <section className="panel"><h2>{say(lang,'版本对比与发布','Compare and release versions')}</h2><article className="card"><h3>{say(lang,'当前发布','Active release')}</h3><p className="mono">{release.version_id?short(release.version_id):say(lang,'尚未启用版本','No active version')} · r{release.revision}</p>
    {release.version_id?<div className="inline-form"><button onClick={()=>onRun(release.version_id!)}>{say(lang,'运行发布版本','Run active release')}</button><button onClick={()=>onExport(release.version_id!)}>{say(lang,'导出发布版本','Export active release')}</button></div>:<button onClick={()=>action('/release/initial',{revision:doc.revision,release_revision:0})}>{say(lang,'启用当前版本作为基线','Enable current version as baseline')}</button>}</article>
    {studies.filter(item=>item.status==='completed'&&item.result).map(study=><article className="card" key={study.id}><h3>{study.config.method.toUpperCase()} · {short(study.result!.selected_version)}</h3><p>{study.result!.gate.passed?say(lang,'已通过发布验证','Passed release validation'):say(lang,'未达到发布门槛','Release gate not passed')}</p><div className="inline-form"><button className="primary" disabled={!study.result!.gate.passed||study.result!.selected_version===release.version_id} onClick={()=>action('/release',{study_id:study.id,release_revision:release.revision})}>{say(lang,'启用此版本','Enable this version')}</button><button onClick={()=>onExport(study.result!.selected_version)}>{say(lang,'导出候选','Export candidate')}</button></div></article>)}
    <h3>{say(lang,'候选资源差异','Candidate resource diffs')}</h3>{!candidates.length&&<Empty>{say(lang,'完成改进后，候选版本和差异会显示在这里。','Candidates and resource diffs appear after improvement.')}</Empty>}{candidates.map(candidate=><article className="card" key={candidate.id}><h3>{candidate.method.toUpperCase()} · {short(candidate.version_id)}</h3><p className="mono muted">{short(candidate.base_version)} → {short(candidate.version_id)}</p>{Object.entries(candidate.diff).map(([name,diff])=><details key={name}><summary>{name}</summary><pre className="json-block diff">{diff}</pre></details>)}<button onClick={()=>onExport(candidate.version_id)}>{say(lang,'导出此快照','Export snapshot')}</button></article>)}
    <h3>{say(lang,'发布历史','Release history')}</h3>{history.map(item=><div className="release-row" key={item.revision}><span>r{item.revision}</span><code>{item.version_id&&short(item.version_id)}</code><span>{item.reason}</span><button disabled={item.version_id===release.version_id} onClick={()=>action('/release/rollback',{version_id:item.version_id,release_revision:release.revision})}>{say(lang,'回滚至此版本','Roll back to this version')}</button></div>)}
  </section>;
}
