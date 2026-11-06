import { useEffect, useState } from 'react';
import type { Api, Lang } from './types';

type Block = {id:string; content:string; revision:number; source:string; metadata:{block:string; max_chars:number}};
type Relation = {id:string; source:string; valid_from:number; valid_until:number|null; metadata:{relation:[string,string,string]}};
const say = (lang:Lang, en:string, zh:string) => lang === 'en' ? en : zh;

export function MemoryControls({project, bank="default", api, lang, onError}:{project:string; bank?:string; api:Api; lang:Lang; onError:(error:unknown)=>void}) {
  const base = `/projects/${project}`;
  const suffix = "?bank="+encodeURIComponent(bank);
  const [blocks,setBlocks] = useState<Block[]>([]);
  const [name,setName] = useState('profile');
  const [content,setContent] = useState('');
  const [revision,setRevision] = useState(0);
  const [source,setSource] = useState('user:explicit');
  const [subject,setSubject] = useState('');
  const [predicate,setPredicate] = useState('works_on');
  const [object,setObject] = useState('');
  const [at,setAt] = useState('');
  const [relations,setRelations] = useState<Relation[]>([]);
  const [busy,setBusy] = useState(false);
  async function refresh() { const response = await (await api(base+'/context'+suffix)).json(); setBlocks(response.blocks); }
  useEffect(() => { refresh().catch(onError); }, [project,api]);
  async function act(work:()=>Promise<void>) { setBusy(true); try { await work(); } catch(error) { onError(error); } finally { setBusy(false); } }
  async function query() {
    const params = new URLSearchParams({subject,bank});
    if(at) { const time = Date.parse(at); if(!Number.isFinite(time)) throw new Error('Invalid date'); params.set('at',String(time/1000)); }
    setRelations(await (await api(base+'/relations?'+params)).json());
  }
  return <div className="panel-grid">
    <article className="card"><h3>{say(lang,'Context blocks','上下文块')}</h3><p className="muted">{say(lang,'Keep a bounded profile or working context across sessions.','保存跨会话的用户资料或工作上下文，并限制内容长度。')}</p>
      <div className="inline-form">{blocks.map(block=><button key={block.id} onClick={()=>{setName(block.metadata.block);setContent(block.content);setRevision(block.revision);setSource(block.source);}}>{block.metadata.block} · r{block.revision}</button>)}</div>
      <label>{say(lang,'Block name','块名称')}<input aria-label="Context block name" value={name} onChange={e=>{setName(e.target.value);setRevision(0);}}/></label>
      <label>{say(lang,'Content','内容')}<textarea aria-label="Context block content" maxLength={4000} value={content} onChange={e=>setContent(e.target.value)}/></label>
      <label>{say(lang,'Source','来源')}<input aria-label="Context source" value={source} onChange={e=>setSource(e.target.value)}/></label>
      <div className="inline-form"><button disabled={busy||!name.trim()||!content.trim()} onClick={()=>act(async()=>{const block=await(await api(base+'/context/'+encodeURIComponent(name)+suffix,{method:'PUT',body:JSON.stringify({content,source,revision,max_chars:4000})})).json();setRevision(block.revision);await refresh();})}>{say(lang,'Save context','保存上下文')}</button>
      <button disabled={busy} onClick={()=>act(refresh)}>{say(lang,'Refresh blocks','刷新上下文块')}</button><small>{content.length}/4000</small></div>
    </article>
    <article className="card"><h3>{say(lang,'Temporal relationships','时序关系')}</h3><p className="muted">{say(lang,'Updates keep prior values available for historical queries.','更新会保留旧值，支持查询过去某个时刻的关系。')}</p>
      <label>{say(lang,'Subject','主体')}<input aria-label="Relation subject" value={subject} onChange={e=>setSubject(e.target.value)}/></label>
      <div className="inline-form"><label>{say(lang,'Relationship','关系')}<input aria-label="Relation predicate" value={predicate} onChange={e=>setPredicate(e.target.value)}/></label><label>{say(lang,'Object','对象')}<input aria-label="Relation object" value={object} onChange={e=>setObject(e.target.value)}/></label></div>
      <button disabled={busy||!subject.trim()||!predicate.trim()||!object.trim()} onClick={()=>act(async()=>{await api(base+'/relations'+suffix,{method:'POST',body:JSON.stringify({subject,predicate,object_:object,source:'user:explicit'})});await query();})}>{say(lang,'Save relationship','保存关系')}</button>
      <label>{say(lang,'As of (optional)','历史时间（可选）')}<input aria-label="Relation as of" type="datetime-local" value={at} onChange={e=>setAt(e.target.value)}/></label>
      <button disabled={busy||!subject.trim()} onClick={()=>act(query)}>{say(lang,'Query relationships','查询关系')}</button>
      {relations.map(item=><div className="record" key={item.id}><strong>{item.metadata.relation.join(' → ')}</strong><small>{item.source} · {new Date(item.valid_from*1000).toLocaleString(lang==='zh'?'zh-CN':'en-US')}</small></div>)}
    </article>
  </div>;
}
