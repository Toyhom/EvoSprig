import type {Banks} from './memory-panel';
import {AgentMemoryBank} from './agent-memory';
import {NodeModel} from './model-connections';
import { useState } from 'react';
import type { Api, Document, Graph, Lang, NodeSpec, Spec } from './types';
import { Icon } from './studio-ui';

type Changes={models?:Spec['models'];resources?:Document['resources']; definitions?:Spec['resources']; tools?:Spec['tools']};
type Props={api:Api;id:string;node:NodeSpec;doc:Document;lang:Lang;onChange:(node:NodeSpec,changes?:Changes)=>void};
export function AgentSettings({api,id,node:originalNode,doc,lang,onChange}:Props){
  const node={...originalNode,...Object.fromEntries(Object.entries(originalNode.harness??{}).filter(([key,value])=>key!=='memory'&&key!=='max_tool_result_chars'&&key!=='tool_history'&&value!==null))} as NodeSpec;
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  const [newSkill,setNewSkill]=useState('');
  const [section,setSection]=useState('design');
  const [memoryBanks,setMemoryBanks]=useState<Banks|null>(null);
  const resource=typeof node.instructions==='object'?node.instructions.resource:'';
  const content=resource?doc.resources?.[resource]??'':String(node.instructions??'');
  const change=(patch:Partial<NodeSpec>)=>{
    const next={...node,...patch};
    if(node.harness&&!('harness' in patch)) next.harness={...node.harness,...Object.fromEntries(Object.entries(patch).filter(([key])=>['max_tool_rounds','tool_selection','tool_limit','parallel_tool_calls','tool_errors','output_errors','max_output_retries','max_output_tokens'].includes(key)))};
    onChange(next);
  };
  function create(role:'prompt'|'skill'){
    const stem=(role==='skill'?newSkill.trim():id+'_prompt').replace(/[^A-Za-z0-9_-]/g,'_').slice(0,55);
    if(!/^[A-Za-z]/.test(stem))return;
    let name=stem;let index=2;while(doc.spec.resources[name])name=stem+'_'+index++;
    onChange({...node,...(role==='prompt'?{instructions:{resource:name}}:{skills:[...(node.skills??[]),name]})},{definitions:{...doc.spec.resources,[name]:{path:`${role==='skill'?'skills':'prompts'}/${name}.md`,role}},resources:{...doc.resources,[name]:role==='prompt'?content:'Describe the procedure, constraints and output format.'}});
    setNewSkill('');
  }
  const skillEntries=Object.entries(doc.spec.resources).filter(([,value])=>value.role==='skill');
  const tools=Object.entries(doc.spec.tools);
  const memory=tools.filter(([,t])=>t.plugin.startsWith('memory.'));
  const documents=tools.filter(([,t])=>t.plugin.startsWith('documents.'));
  function attachMemory(plugin:string){
    const existing=tools.find(([,t])=>t.plugin===plugin)?.[0];
    let alias=existing??plugin.replaceAll('.','_').slice(0,58);let n=2;
    if(!existing)while(doc.spec.tools[alias])alias=plugin.replaceAll('.','_').slice(0,58)+'_'+n++;
    onChange({...node,tools:[...new Set([...(node.tools??[]),alias])]},{tools:{...doc.spec.tools,[alias]:{plugin,version:'1'}}});
  }
  function connectBank(bank:string,write:boolean,automatic:boolean){
    const definitions={...doc.spec.tools};
    const writePlugin=bank==='default'?'memory.write':`memory.${bank}.write`;
    const removed=(node.tools??[]).filter(alias=>!write&&definitions[alias]?.plugin===writePlugin);
    const attached=(node.tools??[]).filter(alias=>!removed.includes(alias));let search='';
    function uses(graph:Graph,alias:string):number{return Object.values(graph.nodes).reduce((count,item)=>count+(item.tools?.includes(alias)||item.tool===alias?1:0)+(item.body?uses(item.body,alias):0)+Object.values(item.branches??{}).reduce((total,branch)=>total+uses(branch,alias),0),0);}
    for(const alias of removed)if(uses(doc.spec.graph,alias)<=1)delete definitions[alias];
    for(const operation of (write?['search','write']:['search'])){
      const plugin=bank==='default'?`memory.${operation}`:`memory.${bank}.${operation}`;
      const existing=Object.entries(definitions).find(([,tool])=>tool.plugin===plugin)?.[0];
      const stem=plugin.replaceAll('.','_').slice(0,58);let alias=existing??stem,n=2;
      if(!existing)while(definitions[alias])alias=stem+'_'+n++;
      definitions[alias]={plugin,version:'1'};if(!attached.includes(alias))attached.push(alias);
      if(operation==='search')search=alias;
    }
    const previous=node.harness?.memory;
    const previousPlugin=doc.spec.tools[previous?.tool??'']?.plugin;
    const sameBank=previousPlugin&&(bank==='default'?/^memory\.(search|recall)$/.test(previousPlugin):previousPlugin.startsWith(`memory.${bank}.`));
    const memoryPolicy=automatic?{limit:5,max_chars:4000,...(sameBank?previous:{}),tool:search,query_input:previous&&sameBank&&previous.query_input in node.inputs?previous.query_input:Object.keys(node.inputs)[0]}:null;
    onChange({...node,tools:attached,...(automatic||sameBank?{harness:{...node.harness,memory:memoryPolicy}}:{})},{tools:definitions});
  }
  function toolList(items:typeof tools){return items.map(([name,tool])=><label className="check setting-option" key={name}><input aria-label={`Tool ${name}`} type="checkbox" checked={node.tools?.includes(name)??false} onChange={e=>change({tools:e.target.checked?[...(node.tools??[]),name]:(node.tools??[]).filter(t=>t!==name),...(!e.target.checked&&node.harness?.memory?.tool===name?{harness:{...node.harness,memory:null}}:{})})}/><span>{name}<small>{tool.plugin}</small></span></label>);}
  return <div className="agent-settings"><NodeModel api={api} lang={lang} node={node} doc={doc} onChange={(next,models)=>onChange(next,{models})}/>
    <nav className="settings-sections" aria-label="Agent settings sections">{[['design',say('设计','Design')],['tools',say('工具与知识','Tools & knowledge')],['memory',say('记忆','Memory')],['runtime',say('运行','Runtime')]].map(([key,label])=><button key={key} aria-pressed={section===key} onClick={()=>setSection(key)}>{label}</button>)}</nav>
    <section hidden={section!=='design'} className="setting-section"><h4><Icon name="file"/>{say('提示词','Prompt')}</h4>
      <select aria-label="Instruction source" value={resource} onChange={e=>change({instructions:e.target.value?{resource:e.target.value}:content})}><option value="">{say('节点内编辑','Inline instruction')}</option>{Object.entries(doc.spec.resources).filter(([,r])=>r.role==='prompt').map(([name])=><option key={name} value={name}>{name}</option>)}</select>
      <textarea aria-label={say('指令','Instructions')} className="prompt-input" value={content} onChange={e=>resource?onChange(node,{resources:{...doc.resources,[resource]:e.target.value}}):change({instructions:e.target.value})}/>
      {!resource&&<button className="text-action" onClick={()=>create('prompt')}>{say('保存为可进化资源','Make prompt evolvable')}</button>}
      {resource&&<small className="setting-note">{say('可在改进页选择此资源','Available for selection in Improve')} · {resource}</small>}
    </section>
    <section hidden={section!=='design'} className="setting-section"><h4><Icon name="layers"/>{say('技能','Skills')}<span>{node.skills?.length??0}</span></h4>
      <p className="hint">{say('按顺序附加到主提示词，可共享、编辑和独立进化。','Reusable procedures, appended in order and optimized separately.')}</p>
      {skillEntries.map(([name])=><div key={name}><label className="check"><input type="checkbox" aria-label={`Skill ${name}`} checked={node.skills?.includes(name)??false} onChange={e=>change({skills:e.target.checked?[...(node.skills??[]),name]:(node.skills??[]).filter(s=>s!==name)})}/>{name}</label>{node.skills?.includes(name)&&<textarea aria-label={`Skill content ${name}`} value={doc.resources?.[name]??''} onChange={e=>onChange(node,{resources:{...doc.resources,[name]:e.target.value}})}/>}</div>)}
      <div className="inline-form"><input aria-label="New skill name" placeholder={say('例如 writing_style','e.g. writing_style')} value={newSkill} onChange={e=>setNewSkill(e.target.value)}/><button disabled={!/^[A-Za-z][A-Za-z0-9_-]{0,54}$/.test(newSkill.trim())} onClick={()=>create('skill')}>{say('添加','Add')}</button></div>
    </section>
    {node.type==='agent'&&<section hidden={section!=='runtime'} className="setting-section"><h4><Icon name="settings"/>Harness</h4><label className="check"><input aria-label="Structured harness" type="checkbox" checked={!!node.harness} onChange={e=>change({harness:e.target.checked?{max_tool_rounds:node.max_tool_rounds??8,tool_selection:node.tool_selection??'all',tool_limit:node.tool_limit??8,parallel_tool_calls:node.parallel_tool_calls??false,tool_errors:node.tool_errors??'raise',output_errors:node.output_errors??'raise',max_output_retries:node.max_output_retries??1,max_output_tokens:node.max_output_tokens??512}:null})}/>{say('使用独立 harness 配置','Use a per-agent harness')}</label><p className="hint">{say('下面的工具与恢复设置保存到该智能体的 harness，可在改进页指定搜索范围。','Tool and recovery settings below belong to this agent’s harness. Set their search bounds in Improve.')}</p><label>{say('消息收件箱','Peer mailbox')}<input aria-label="Peer mailbox" value={typeof node.mailbox==='string'?node.mailbox:''} placeholder="analyst" onChange={e=>change({mailbox:e.target.value||null})}/></label>
    {node.harness&&<><label>{say('工具输出字符上限','Tool result character limit')}<input aria-label="Tool result character limit" type="number" min={512} max={1000000} placeholder="Unlimited" value={node.harness.max_tool_result_chars??''} onChange={e=>change({harness:{...node.harness,max_tool_result_chars:e.target.value?Number(e.target.value):null}})}/></label></>}
    </section>}
    {section==='memory'&&node.type==='agent'&&<AgentMemoryBank project={doc.id} api={api} lang={lang} hasInput={Object.keys(node.inputs).length>0} initialBank={(()=>{const plugin=doc.spec.tools[node.harness?.memory?.tool??'']?.plugin??memory.find(([alias])=>node.tools?.includes(alias))?.[1].plugin??'';return plugin.split('.').length===3?plugin.split('.')[1]:'default';})()} onConnect={connectBank} onCatalog={setMemoryBanks} attachedPlugins={(node.tools??[]).map(alias=>doc.spec.tools[alias]?.plugin??'')} recallPlugin={doc.spec.tools[node.harness?.memory?.tool??'']?.plugin}/>}
    <section hidden={section!=='memory'} className="setting-section"><h4><Icon name="layers"/>{say('工作上下文与历史','Working context & history')}</h4>{node.type==='agent'&&!node.harness&&<button onClick={()=>change({harness:{}})}>{say('配置上下文策略','Configure context policy')}</button>}{node.harness&&<><p className="hint">{say('缩短较早的工具结果，保留最近轮次和完整运行记录。','Shorten older tool results while keeping recent rounds and the full run record.')}</p><label className="check"><input aria-label="Prune tool history" type="checkbox" checked={!!node.harness.tool_history} onChange={e=>change({harness:{...node.harness,tool_history:e.target.checked?{max_chars:16000,keep_recent_rounds:2}:null}})}/>{say('限制工具历史长度','Limit tool history')}</label>{node.harness.tool_history&&<div className="sampling-grid"><label>{say('字符预算','Character budget')}<input aria-label="Tool history budget" type="number" min={512} value={node.harness.tool_history.max_chars} onChange={e=>change({harness:{...node.harness,tool_history:{...node.harness!.tool_history!,max_chars:Number(e.target.value)}}})}/></label><label>{say('完整保留最近轮次','Keep recent rounds')}<input aria-label="Keep recent tool rounds" type="number" min={0} max={32} value={node.harness.tool_history.keep_recent_rounds} onChange={e=>change({harness:{...node.harness,tool_history:{...node.harness!.tool_history!,keep_recent_rounds:Number(e.target.value)}}})}/></label></div>}</>}<p className="hint">{say('语义压缩可由普通模型或智能体节点完成：输入旧摘要与历史，输出新摘要，再与近期消息一起传给后续节点。','For semantic compression, use an ordinary model or agent node: combine the previous summary and history into a new summary, then pass it alongside recent messages to the next node.')}</p></section>
    {node.harness&&<section hidden={section!=='memory'} className="setting-section"><h4>{say('任务前召回','Recall before a task')}</h4><label>{say('自动检索记忆','Retrieve memory before each task')}<select aria-label="Harness memory tool" value={node.harness.memory?.tool??''} onChange={e=>change({harness:{...node.harness,memory:e.target.value?{tool:e.target.value,query_input:Object.keys(node.inputs)[0]??'',limit:5,max_chars:4000}:null}})}><option value="">{say('关闭','Off')}</option>{[...memory,...documents.filter(([alias])=>alias===node.harness?.memory?.tool)].filter(([alias,t])=>node.tools?.includes(alias)&&(/^(memory\.(?:[A-Za-z][A-Za-z0-9_-]*\.)?(search|recall)|documents\.search)$/.test(t.plugin))).map(([alias])=><option key={alias}>{alias}</option>)}</select></label>{node.harness.memory&&<><label>{say('查询输入','Query input')}<select aria-label="Memory query input" value={node.harness.memory.query_input} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,query_input:e.target.value}}})}>{Object.keys(node.inputs).map(name=><option key={name}>{name}</option>)}</select></label><label>{say('检索条数','Retrieved records')}<input aria-label="Harness memory limit" type="number" min={1} max={20} value={node.harness.memory.limit} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,limit:Number(e.target.value)}}})}/></label><label>{say('记忆字符预算','Memory character budget')}<input aria-label="Harness memory characters" type="number" min={128} max={16000} value={node.harness.memory.max_chars} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,max_chars:Number(e.target.value)}}})}/></label></>}</section>}
    {node.type==='agent'&&<><section hidden={section!=='tools'} className="setting-section"><h4><Icon name="tool"/>{say('工具','Tools')}<span>{node.tools?.length??0}</span></h4>
      {toolList(tools.filter(([,t])=>! /^(memory|documents)\./.test(t.plugin)))}
      {!tools.length&&<p className="hint">{say('在规格中声明工具，部署配置连接 HTTP、MCP 或 Python 插件。','Declare tools in the spec; connect HTTP, MCP or Python plugins in your deployment.')}</p>}
    </section><section hidden={section!=='runtime'} className="setting-section"><h4><Icon name="tool"/>{say('工具执行','Tool execution')}</h4>
      <label>{say('工具选择','Tool selection')}<select aria-label="Tool selection" value={node.tool_selection??'all'} onChange={e=>change({tool_selection:e.target.value as 'all'|'relevant'})}><option value="all">{say('全部已选工具','All selected tools')}</option><option value="relevant">{say('按任务筛选','Match to the task')}</option></select></label>
      {node.tool_selection==='relevant'&&<label>{say('最多提供工具数','Tools per turn')}<input aria-label="Tool limit" type="number" min={1} max={64} value={node.tool_limit??8} onChange={e=>change({tool_limit:Number(e.target.value)})}/></label>}
      <label className="check"><input aria-label="Parallel read tools" type="checkbox" checked={node.parallel_tool_calls??false} onChange={e=>change({parallel_tool_calls:e.target.checked})}/>{say('并行执行只读工具','Run read tools concurrently')}</label>
      <label>{say('最多工具轮数','Tool rounds')}<input aria-label="Tool rounds" type="number" min={1} max={256} value={node.max_tool_rounds??''} placeholder={say('使用运行预算','Use run budget')} onChange={e=>change({max_tool_rounds:e.target.value?Number(e.target.value):null})}/></label>
      <label>{say('工具失败处理','Tool errors')}<select aria-label="Tool error policy" value={node.tool_errors??'raise'} onChange={e=>change({tool_errors:e.target.value as 'raise'|'feedback'})}><option value="raise">{say('停止并报告','Stop and report')}</option><option value="feedback">{say('反馈给智能体','Let the agent recover')}</option></select></label>
    </section><section hidden={section!=='tools'} className="setting-section"><h4><Icon name="book"/>{say('外部知识库 · RAG','Knowledge library · RAG')}</h4><p className="hint">{say('在知识库页管理业务文档；在这里指定该智能体可以调用的检索工具。','Manage business documents in Knowledge; choose this agent’s retrieval tools here.')}</p>{toolList(documents)}<div className="memory-shortcuts">{[['documents.search',say('单次检索','Search')],['documents.retrieve',say('多查询检索','Multi-query retrieval')]].filter(([plugin])=>!tools.some(([alias,t])=>t.plugin===plugin&&node.tools?.includes(alias))).map(([plugin,label])=><button key={plugin} onClick={()=>attachMemory(plugin)}>+ {label}</button>)}</div></section>
    <section hidden={section!=='memory'} className="setting-section"><h4><Icon name="database"/>{say('长期记忆工具','Long-term memory tools')}</h4><p className="hint">{say('保存偏好、事实和经验，与外部知识库独立。记录在同一用户与项目内共享。','Save preferences, facts and experiences independently of the knowledge library. Records are shared within the same user and project.')}</p>{toolList(memory)}<div className="memory-shortcuts">{[['memory.search',say('事实检索','Facts')],['memory.write',say('保存事实','Save facts')],['memory.recall',say('经验召回','Experiences')],['memory.remember',say('保存经验','Save experience')],['memory.context',say('工作上下文','Working context')],['memory.summarize',say('保存经验摘要','Save experience summary')]].filter(([plugin])=>!tools.some(([alias,t])=>t.plugin===plugin&&node.tools?.includes(alias))).map(([plugin,label])=><button key={plugin} disabled={['memory.write','memory.remember','memory.summarize'].includes(plugin)&&memoryBanks?.banks.default.agent_writes===false} title={['memory.write','memory.remember','memory.summarize'].includes(plugin)&&memoryBanks?.banks.default.agent_writes===false?say('该记忆库未开放智能体写入','Agent writes are disabled for this bank'):undefined} onClick={()=>attachMemory(plugin)}>+ {label}</button>)}</div></section></>}
    {doc.spec.models[node.model??'']?.requires.includes('vision')&&<section hidden={section!=='design'} className="setting-section"><h4><Icon name="image"/>{say('图片输入','Image inputs')}</h4><p className="hint">{say('选择包含图片 URI 或资产的输入，模型会读取图片内容。','Select inputs containing image URIs or assets to send as visual content.')}</p>{Object.keys(node.inputs??{}).map(name=><label className="check" key={name}><input aria-label={`Image input ${name}`} type="checkbox" checked={node.image_inputs?.includes(name)??false} onChange={e=>change({image_inputs:e.target.checked?[...(node.image_inputs??[]),name]:(node.image_inputs??[]).filter(x=>x!==name)})}/>{name}</label>)}</section>}
    <details hidden={section!=='runtime'} className="setting-section" open><summary><Icon name="model"/>{say('模型参数','Model parameters')}</summary>

      <div className="sampling-grid"><label>Temperature<input aria-label="Temperature" type="number" min={0} max={2} step={0.1} placeholder="0" value={node.temperature??''} onChange={e=>change({temperature:e.target.value?Number(e.target.value):null})}/></label><label>Top P<input aria-label="Top P" type="number" min={0.01} max={1} step={0.01} placeholder={say('供应商默认','Provider default')} value={node.top_p??''} onChange={e=>change({top_p:e.target.value?Number(e.target.value):null})}/></label></div>
      <label>{say('单次输出 token 上限','Output token limit')}<input aria-label="Node output token limit" type="number" min={1} max={32768} placeholder={String(doc.spec.execution?.max_output_tokens??512)} value={node.max_output_tokens??''} onChange={e=>change({max_output_tokens:e.target.value?Number(e.target.value):null})}/></label>
      <label>{say('响应格式','Response format')}<select aria-label="Response format" value={node.response_format??'text'} onChange={e=>change({response_format:e.target.value as 'text'|'json'})}><option value="text">Text</option><option value="json">JSON</option></select></label>
      <label>{say('输出格式错误处理','Invalid output handling')}<select aria-label="Output error policy" value={node.output_errors??'raise'} onChange={e=>change({output_errors:e.target.value as 'raise'|'feedback'})}><option value="raise">{say('停止并报告','Stop and report')}</option><option value="feedback">{say('反馈给模型重试','Ask model to repair')}</option></select></label>
      <label>{say('业务规则校验','Application validation')}<select aria-label="Output validator" value={node.output_validator??''} onChange={e=>change({output_validator:e.target.value||null})}><option value="">{say('仅检查输出格式','Output schema only')}</option>{Object.entries(doc.spec.resources).filter(([,r])=>r.role==='code').map(([name])=><option key={name}>{name}</option>)}</select></label>
      {node.output_validator&&<textarea aria-label="Output validator code" value={doc.resources?.[node.output_validator]??''} onChange={e=>onChange(node,{resources:{...doc.resources,[node.output_validator!]:e.target.value}})}/>}
      {node.output_errors==='feedback'&&<label>{say('最多修复次数','Maximum repair attempts')}<input aria-label="Output repair attempts" type="number" min={0} max={3} value={node.max_output_retries??1} onChange={e=>change({max_output_retries:Number(e.target.value)})}/></label>}
    </details>
  </div>;
}
