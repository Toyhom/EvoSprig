import {Icon} from './studio-ui';
import {useEffect,useState} from 'react';
import type {Api,Document,Lang,NodeSpec,Spec} from './types';

type Connection={name:string;base_url:string;model:string;api_key_env:string;capabilities:string[];local_service?:string|null;key_configured?:boolean;[key:string]:unknown};
type Catalog={editable:boolean;services:string[];models:Connection[]};
const providers:Record<string,string>={OpenAI:'https://api.openai.com/v1',DeepSeek:'https://api.deepseek.com',Kimi:'https://api.moonshot.cn/v1',MiniMax:'https://api.minimax.io/v1',Qwen:'https://dashscope.aliyuncs.com/compatible-mode/v1','Local / Custom':'http://127.0.0.1:8000/v1'};
const empty:Connection={name:'',base_url:providers.OpenAI,model:'',api_key_env:'MODEL_API_KEY',capabilities:['text','structured_output','tool_calling'],json_mode:'without_tools',timeout_seconds:300};
export function DefaultModel({api,lang,doc,onChange}:{api:Api;lang:Lang;doc:Document;onChange:(models:Spec['models'])=>void}){
 const [catalog,setCatalog]=useState<Connection[]>([]);
 useEffect(()=>{let live=true;const update=()=>{api('/models').then(r=>r.json()).then(data=>{if(live)setCatalog(data.models);}).catch(()=>{});};update();window.addEventListener('evosprig-models',update);return()=>{live=false;window.removeEventListener('evosprig-models',update);};},[api]);
 const binding=doc.spec.models.main?.binding??'';
 return <label className="default-model">{lang==='zh'?'应用默认模型':'Application default model'}<select aria-label="Application default model" value={binding} onChange={e=>{const connection=catalog.find(item=>item.name===e.target.value);if(connection)onChange({...doc.spec.models,main:{binding:connection.name,requires:doc.spec.models.main?.requires??connection.capabilities}});}}>
  {!catalog.some(item=>item.name===binding)&&<option value={binding}>{binding||(lang==='zh'?'先添加模型连接':'Add a model connection')}</option>}
  {catalog.map(item=><option key={item.name} value={item.name}>{item.name} · {item.model}</option>)}
 </select><small>{lang==='zh'?'各节点默认使用 main，需要时单独覆盖。':'Nodes use main by default; override individual roles when needed.'}</small></label>;
}
export function ModelsPanel({api,lang}:{api:Api;lang:Lang}){
 const [catalog,setCatalog]=useState<Catalog>({editable:false,services:[],models:[]});const [form,setForm]=useState<Connection>(empty);const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);
 const say=(en:string,zh:string)=>lang==='zh'?zh:en;
 async function refresh(){try{setCatalog(await(await api('/models')).json());}catch(e){setMessage(String(e));}}
 return <details className="connection-settings" onToggle={e=>{if(e.currentTarget.open)void refresh();}}><summary><Icon name="model"/>{say('Model connections','模型连接')}</summary>
  <p className="hint">{say('Configure API or local endpoints, then assign a connection to each agent.','配置 API 或本地服务，再为各智能体选择连接。')}</p>
  {catalog.models.map(item=><button className="text-action" key={item.name} onClick={()=>setForm(item)}>{item.name} · {item.model}</button>)}
  {!catalog.editable?<p className="hint">{say('Start Studio with --profile deployment.yaml to edit connections.','使用 --profile deployment.yaml 启动工作台后可编辑连接。')}</p>:<>
   <label>{say('Provider preset','厂商地址预设')}<select aria-label="Provider preset" onChange={e=>setForm({...empty,base_url:providers[e.target.value],name:form.name})}><option value="OpenAI">OpenAI</option>{Object.keys(providers).slice(1).map(name=><option key={name}>{name}</option>)}</select></label>
   <label>{say('Connection name','连接名称')}<input aria-label="Connection name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
   <label>API Base URL<input aria-label="Model API URL" value={form.base_url} onChange={e=>setForm({...form,base_url:e.target.value})}/></label>
   <label>{say('Model ID','模型 ID')}<input aria-label="Connection model ID" value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/></label>
   <label>{say('API key environment variable','密钥环境变量名称')}<input aria-label="Model key environment" value={form.api_key_env} onChange={e=>setForm({...form,api_key_env:e.target.value})}/></label>
   <label className="check"><input aria-label="Connection supports vision" type="checkbox" checked={form.capabilities.includes('vision')} onChange={e=>setForm({...form,capabilities:e.target.checked?[...form.capabilities,'vision']:form.capabilities.filter(c=>c!=='vision')})}/>{say('Accepts images','支持图片输入')}</label>
   <label>{say('Resident local service','关联本地常驻服务')}<select aria-label="Connection local service" value={form.local_service??''} onChange={e=>setForm({...form,local_service:e.target.value||null})}><option value="">{say('API / externally managed','API / 外部管理')}</option>{catalog.services.map(name=><option key={name}>{name}</option>)}</select></label>
   <button disabled={busy||!form.name||!form.model} onClick={async()=>{setBusy(true);try{const {name,key_configured,...connection}=form;void key_configured;await api('/models',{method:'PUT',body:JSON.stringify({name,connection})});setMessage(say('Connection saved','连接已保存'));await refresh();window.dispatchEvent(new Event('evosprig-models'));}catch(e){setMessage(String(e));}finally{setBusy(false);}}}>{say('Save connection','保存连接')}</button>
  </>}{message&&<p role="status">{message}</p>}
 </details>;
}
export function NodeModel({api,lang,node,doc,onChange}:{api:Api;lang:Lang;node:NodeSpec;doc:Document;onChange:(node:NodeSpec,models?:Spec['models'])=>void}){
 const [catalog,setCatalog]=useState<Connection[]>([]);const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);const say=(en:string,zh:string)=>lang==='zh'?zh:en;
 useEffect(()=>{let live=true;const update=()=>{api('/models').then(r=>r.json()).then(data=>{if(live)setCatalog(data.models);}).catch(()=>{});};update();window.addEventListener('evosprig-models',update);return()=>{live=false;window.removeEventListener('evosprig-models',update);};},[api]);
 const binding=doc.spec.models[node.model??'']?.binding;const current=catalog.find(item=>item.name===binding);
 const available=catalog.filter(item=>!Object.values(doc.spec.models).some(model=>model.binding===item.name));
 return <section className="setting-section"><h4>{say('Model','模型')}</h4>
  <label>{say('Model binding','模型绑定')}<select aria-label="Model binding" value={node.model??''} onChange={e=>{const value=e.target.value;if(value.startsWith('connection:')){const name=value.slice(11),connection=catalog.find(c=>c.name===name)!;let alias=name;while(doc.spec.models[alias])alias+='_';onChange({...node,model:alias},{...doc.spec.models,[alias]:{binding:name,requires:connection.capabilities}});}else onChange({...node,model:value});}}>
   {Object.entries(doc.spec.models).map(([name,entry])=><option value={name} key={name}>{name==='main'?say('Default (main)','默认（main）'):name}{catalog.find(c=>c.name===entry.binding)?.model?' · '+catalog.find(c=>c.name===entry.binding)!.model:''}</option>)}
   {!!available.length&&<optgroup label={say('Configured connections','已配置连接')}>{available.map(item=><option value={'connection:'+item.name} key={item.name}>{item.name} · {item.model}</option>)}</optgroup>}
  </select></label>
  <p className="hint">{current?`${current.base_url} · ${current.api_key_env}`:say('Add endpoints under Model connections in the sidebar.','在左侧“模型连接”中添加厂商 API 或本地地址。')}</p>
  {current?.local_service&&<button disabled={busy} onClick={async()=>{setBusy(true);try{const s=await(await api('/services/'+encodeURIComponent(current.local_service!)+'/warmup',{method:'POST'})).json();setMessage(s.ready?say('Ready · retained across runs','已就绪 · 跨任务常驻'):say('Loading','加载中'));}catch(e){setMessage(String(e));}finally{setBusy(false);}}}>{busy?say('Loading…','加载中…'):say('Preload ','预加载 ')}{current.local_service}</button>}
  {message&&<p role="status">{message}</p>}
 </section>;
}
