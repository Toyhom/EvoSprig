import {Icon} from './studio-ui';
import { useState } from 'react';
import type { Api, Lang } from './types';

type Service={name:string;ready:boolean;reachable:boolean;managed:boolean;retention:string;gpu_devices?:number[]|null;cuda_visible_devices?:string|null};
export function ServicesPanel({api,lang}:{api:Api;lang:Lang}){
  const [items,setItems]=useState<Service[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState('');
  const [placements,setPlacements]=useState<Record<string,string>>({});
  const say=(en:string,zh:string)=>lang==='zh'?zh:en;
  async function refresh(){
    try {setItems((await(await api('/services')).json()).services);setError('');}
    catch(e){setError(String(e));}
  }
  return <details className="connection-settings" onToggle={e=>{if(e.currentTarget.open)void refresh();}}>
    <summary><Icon name="tool"/>{say('Local models & tools','本地模型与工具')}</summary>
    <p className="hint">{say('Preload once. Reuse across runs and debugging.','预加载一次，在运行与调试之间复用。')}</p>
    {items.map(item=><div key={item.name} className="service-status"><strong>{item.name}</strong><small>{item.ready?say('Ready · retained','就绪 · 常驻'):item.reachable?say('Needs warmup','待预热'):say('Offline','未启动')}</small>
      <label>{say('GPU positions','GPU 位置')}<input aria-label={'GPUs '+item.name} disabled={item.managed||item.reachable||!!busy} placeholder={say('Inherit allocation','继承当前分配')} value={placements[item.name]??item.gpu_devices?.join(',')??''} onChange={e=>setPlacements({...placements,[item.name]:e.target.value})}/></label>
      {item.cuda_visible_devices&&<small>CUDA_VISIBLE_DEVICES={item.cuda_visible_devices}</small>}
      <button disabled={item.managed||item.reachable||!!busy} onClick={async()=>{setBusy(item.name);try{const value=(placements[item.name]??item.gpu_devices?.join(',')??'').trim();if(value&&!/^\d+(\s*,\s*\d+)*$/.test(value))throw new Error(say('Enter positions such as 0 or 0,1.','填写 0 或 0,1 这样的 GPU 位置。'));await api(`/services/${encodeURIComponent(item.name)}/placement`,{method:'PUT',body:JSON.stringify({gpu_devices:value?value.split(',').map(Number):null})});await refresh();}catch(e){setError(String(e));}finally{setBusy('');}}}>{say('Save placement','保存卡分配')}</button>
      <button disabled={!!busy} onClick={async()=>{setBusy(item.name);try{await api(`/services/${encodeURIComponent(item.name)}/warmup`,{method:'POST'});await refresh();}catch(e){setError(String(e));}finally{setBusy('');}}}>{busy===item.name?say('Loading…','加载中…'):say('Preload','预加载')}</button></div>)}
    {!items.length&&<p className="hint">{say('Add services to deployment.yaml to connect local model servers.','在 deployment.yaml 的 services 中连接本地模型服务。')}</p>}
    {error&&<p role="alert">{error}</p>}
    <button onClick={()=>void refresh()}>{say('Refresh status','刷新状态')}</button>
  </details>;
}
