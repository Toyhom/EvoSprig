import { useState } from 'react';
import type { Api, Lang } from './types';

type Service={name:string;ready:boolean;reachable:boolean;managed:boolean;retention:string};
export function ServicesPanel({api,lang}:{api:Api;lang:Lang}){
  const [items,setItems]=useState<Service[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState('');
  const say=(en:string,zh:string)=>lang==='zh'?zh:en;
  async function refresh(){
    try {setItems((await(await api('/services')).json()).services);setError('');}
    catch(e){setError(String(e));}
  }
  return <details className="connection-settings" onToggle={e=>{if(e.currentTarget.open)void refresh();}}>
    <summary>{say('Local models & tools','本地模型与工具')}</summary>
    <p className="hint">{say('Preload once. Reuse across runs and debugging.','预加载一次，在运行与调试之间复用。')}</p>
    {items.map(item=><div key={item.name} className="service-status"><strong>{item.name}</strong><small>{item.ready?say('Ready · retained','就绪 · 常驻'):item.reachable?say('Needs warmup','待预热'):say('Offline','未启动')}</small>
      <button disabled={!!busy} onClick={async()=>{setBusy(item.name);try{await api(`/services/${encodeURIComponent(item.name)}/warmup`,{method:'POST'});await refresh();}catch(e){setError(String(e));}finally{setBusy('');}}}>{busy===item.name?say('Loading…','加载中…'):say('Preload','预加载')}</button></div>)}
    {!items.length&&<p className="hint">{say('Add services to deployment.yaml to connect local model servers.','在 deployment.yaml 的 services 中连接本地模型服务。')}</p>}
    {error&&<p role="alert">{error}</p>}
    <button onClick={()=>void refresh()}>{say('Refresh status','刷新状态')}</button>
  </details>;
}
