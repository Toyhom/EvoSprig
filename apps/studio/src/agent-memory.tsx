import {useEffect,useState} from 'react';
import type {Api,Lang} from './types';
import type {Banks} from './memory-panel';
import {Icon} from './studio-ui';

export function AgentMemoryBank({project,api,lang,hasInput,onConnect,onCatalog,initialBank,attachedPlugins,recallPlugin}:{project:string;api:Api;lang:Lang;hasInput:boolean;initialBank:string;attachedPlugins:string[];recallPlugin?:string;onCatalog:(banks:Banks)=>void;onConnect:(bank:string,write:boolean,automatic:boolean)=>void}){
 const t=(zh:string,en:string)=>lang==='zh'?zh:en;
 const plugin=(name:string,operation:string)=>name==='default'?`memory.${operation}`:`memory.${name}.${operation}`;
 const attachedKey=attachedPlugins.join('|');
 const [banks,setBanks]=useState<Banks|null>(null),[bank,setBank]=useState(initialBank),[write,setWrite]=useState(attachedPlugins.includes(plugin(initialBank,'write'))),[automatic,setAutomatic]=useState(['search','recall'].some(op=>recallPlugin===plugin(initialBank,op))),[error,setError]=useState(''),[connected,setConnected]=useState('');
 useEffect(()=>{let active=true;api(`/projects/${project}/memory/banks`).then(r=>r.json()).then(value=>{if(active){setBanks(value);if(!value.banks[initialBank])setBank('default');onCatalog(value);}}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[project,api]);
 useEffect(()=>{setWrite(attachedPlugins.includes(plugin(bank,'write')));setAutomatic(['search','recall'].some(op=>recallPlugin===plugin(bank,op)));},[bank,attachedKey,recallPlugin]);
 return <section className="setting-section"><h4><Icon name="database"/>{t('检索式外部记忆','Retrieval-based memory')}</h4><p className="hint">{t('从持久记忆库召回偏好、事实和经验。记忆页可创建库并配置向量模型。','Recall preferences, facts and experiences from a persistent bank. Create banks and configure embeddings on the Memory page.')}</p>{error&&<p role="alert">{error}</p>}
 {banks&&<div className="memory-bank-choice"><label>{t('记忆库','Memory bank')}<select aria-label="Agent memory bank" value={bank} onChange={e=>{setBank(e.target.value);setConnected('');}}>{Object.entries(banks.banks).map(([name,config])=><option key={name} value={name}>{name} · {config.retrieval}</option>)}</select></label>
 <label className="check"><input aria-label="Attach memory write tool" type="checkbox" disabled={!banks.banks[bank].agent_writes} checked={write} onChange={e=>setWrite(e.target.checked)}/>{t('附加记忆写入工具','Add a memory write tool')}</label>
 <label className="check"><input aria-label="Automatically recall selected bank" type="checkbox" disabled={!hasInput} checked={automatic} onChange={e=>setAutomatic(e.target.checked)}/>{t('每次任务开始前自动检索','Retrieve automatically before each task')}</label>
 <button onClick={()=>{onConnect(bank,write&&banks.banks[bank].agent_writes,automatic&&hasInput);setConnected(t('已接入；可在下方调整查询输入、条数和预算。','Connected. Adjust query input, result count and budget below.'));}}>{t('接入记忆库','Connect memory bank')}</button>{connected&&<p role="status" className="hint">{connected}</p>}
 <p className="hint">{t('选择同一库的节点共享记忆；不同库相互独立。未开启自动检索时，由智能体按需调用。','Nodes using the same bank share memories; different banks remain separate. Without automatic recall, the agent decides when to search.')}</p></div>}
 </section>;
}
