import {useEffect,useState} from 'react';
import type {Api,Lang,Run} from './types';
import {MediaPreview} from './media-preview';

export type DebugTarget={name:string;path:string[];source_prefix:string;runId:string};
type Step={id:string;status:string;started?:string;finished?:string};
type Detail={name:string;type:string;status:string;inputs:unknown;output:unknown;error:unknown;feedback?:{reason?:string;feedback?:{message?:string}}[];path:string[];source_prefix:string};
const labels:Record<string,[string,string]>={running:['Running','运行中'],succeeded:['Completed','已完成'],failed:['Failed','失败'],waiting_input:['Your input','等待确认'],waiting_external:['Waiting for tool','等待工具'],canceled:['Canceled','已取消'],stopped:['Stopped','已停止']};
const say=(status:string,lang:Lang)=>labels[status]?.[lang==='zh'?1:0]??status;

export function executionSteps(run:Run):Step[]{
  const steps=new Map<string,Step>();
  for(const event of run.events??[]){
    const type=String(event.type??'');const id=typeof event.node_id==='string'?event.node_id:'';
    if(!id||!['node.started','node.completed','node.failed','node.waiting_input','node.waiting_external'].includes(type))continue;
    const step=steps.get(id)??{id,status:'running'};
    const timestamp=typeof event.timestamp==='string'?event.timestamp:undefined;
    if(type==='node.started')step.started??=timestamp;
    step.status=type==='node.completed'?'succeeded':type==='node.started'?'running':type.slice(5);
    if(type==='node.completed'||type==='node.failed')step.finished=timestamp;
    steps.set(id,step);
  }
  for(const step of steps.values()){
    if(step.status==='succeeded'||step.status==='failed')continue;
    const wait=run.waiting?.find(item=>item.path===step.id||item.path.startsWith(step.id+'/'));
    if(wait)step.status=wait.kind==='human'?'waiting_input':'waiting_external';
    else if(run.status==='failed'||run.status==='canceled')step.status=run.status==='canceled'?'canceled':'stopped';
  }
  return [...steps.values()];
}

function displayPath(path:string,lang:Lang){
  return path.replace(/^graph\//,'').split('/').map(part=>{
    const match=/^(item|iteration)-(\d+)$/.exec(part);
    return match?`${match[1]==='item'?(lang==='zh'?'第':'Item '):(lang==='zh'?'第':'Take ')}${Number(match[2])+1}${lang==='zh'?(match[1]==='item'?'项':'轮'):''}`:part;
  }).join(' › ');
}

export function RunSteps({run,api,lang,onDebug,disabled}:{run:Run;api:Api;lang:Lang;onDebug?:(target:DebugTarget)=>void;disabled?:boolean}){
  const [selected,setSelected]=useState<string>();const [detail,setDetail]=useState<Detail>();
  const [error,setError]=useState('');const [limit,setLimit]=useState(30);
  const steps=executionSteps(run);
  const status=steps.find(step=>step.id===selected)?.status;
  useEffect(()=>{
    let active=true;setDetail(undefined);setError('');
    if(selected)api(`/runs/${run.run_id}/nodes/${selected.split('/').map(encodeURIComponent).join('/')}`).then(r=>r.json()).then(next=>{if(active)setDetail(next);}).catch(e=>{if(active)setError(String(e));});
    return()=>{active=false;};
  },[run.run_id,selected,status,api]);
  if(!steps.length)return null;
  const finished=steps.filter(step=>step.status==='succeeded').length;
  return <details className="run-steps" open><summary>{lang==='zh'?'执行步骤':'Steps'} <span>{finished} / {steps.length} {lang==='zh'?'已完成':'completed'}</span></summary>
    <div className="run-step-list" aria-label={lang==='zh'?'执行步骤':'Execution steps'}>
      {steps.length>limit&&<button onClick={()=>setLimit(n=>n+50)}>{lang==='zh'?'显示更早的步骤':'Show earlier steps'}</button>}
      {steps.slice(-limit).map(step=><button key={step.id} className={`run-step ${selected===step.id?'selected':''}`} onClick={()=>setSelected(step.id)} title={step.id}>
        <span className={`step-dot step-${step.status}`} aria-hidden="true"/><span className="step-name">{displayPath(step.id,lang)}</span><span>{say(step.status,lang)}</span>
        {step.started&&step.finished&&<small>{Math.max(0,(Date.parse(step.finished)-Date.parse(step.started))/1000).toFixed(1)} s</small>}
      </button>)}
    </div>
    {selected&&<article className="run-step-detail" aria-label={lang==='zh'?'步骤详情':'Step details'}>
      <div className="run-step-heading"><strong>{displayPath(selected,lang)}</strong><button onClick={()=>setSelected(undefined)} aria-label={lang==='zh'?'关闭步骤':'Close step'}>×</button></div>
      {error&&<p role="alert">{error}</p>}
      {!detail&&!error&&<p>{lang==='zh'?'加载中…':'Loading…'}</p>}
      {detail&&<><p>{detail.type} · {say(detail.status,lang)}</p>
        {detail.error!=null&&<p className="debug-error">{String((detail.error as {message?:string}).message??'')}</p>}
        {!!detail.feedback?.length&&<details open={detail.status==='failed'}><summary>{lang==='zh'?'修正反馈':'Correction feedback'}</summary>{detail.feedback.map((item,i)=><p key={i}>{item.reason??item.feedback?.message??JSON.stringify(item)}</p>)}</details>}
        <MediaPreview value={detail.output} lang={lang}/>
        {([['inputs',lang==='zh'?'输入':'Input'],['output',lang==='zh'?'结果':'Output']] as const).map(([key,label])=><details key={key} open={key==='output'&&detail.output!=null}><summary>{label}</summary><pre className="json-block">{JSON.stringify(detail[key],null,2)??'—'}</pre></details>)}
        {onDebug&&detail.name!=='debug_start'&&<button disabled={disabled} onClick={()=>onDebug({...detail,runId:run.run_id})}>{lang==='zh'?'用这些输入调试':'Debug with these inputs'}</button>}
      </>}
    </article>}
  </details>;
}
