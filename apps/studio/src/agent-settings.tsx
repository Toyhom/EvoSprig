import { useState } from 'react';
import type { Document, Lang, NodeSpec, Spec } from './types';
import { Icon } from './studio-ui';

type Changes={resources?:Document['resources']; definitions?:Spec['resources']; tools?:Spec['tools']};
type Props={id:string;node:NodeSpec;doc:Document;lang:Lang;onChange:(node:NodeSpec,changes?:Changes)=>void};
export function AgentSettings({id,node:originalNode,doc,lang,onChange}:Props){
  const node={...originalNode,...Object.fromEntries(Object.entries(originalNode.harness??{}).filter(([key,value])=>key!=='memory'&&value!==null))} as NodeSpec;
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  const [newSkill,setNewSkill]=useState('');
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
  const memory=tools.filter(([,t])=>/^(memory|documents)\./.test(t.plugin));
  function attachMemory(plugin:string){
    const existing=tools.find(([,t])=>t.plugin===plugin)?.[0];
    let alias=existing??plugin.replace('.','_');let n=2;
    if(!existing)while(doc.spec.tools[alias])alias=plugin.replace('.','_')+'_'+n++;
    onChange({...node,tools:[...new Set([...(node.tools??[]),alias])]},{tools:{...doc.spec.tools,[alias]:{plugin,version:'1'}}});
  }
  function toolList(items:typeof tools){return items.map(([name,tool])=><label className="check setting-option" key={name}><input aria-label={`Tool ${name}`} type="checkbox" checked={node.tools?.includes(name)??false} onChange={e=>change({tools:e.target.checked?[...(node.tools??[]),name]:(node.tools??[]).filter(t=>t!==name)})}/><span>{name}<small>{tool.plugin}</small></span></label>);}
  return <div className="agent-settings">
    {node.type==='agent'&&<section className="setting-section"><h4><Icon name="settings"/>Harness</h4><label className="check"><input aria-label="Structured harness" type="checkbox" checked={!!node.harness} onChange={e=>change({harness:e.target.checked?{max_tool_rounds:node.max_tool_rounds??8,tool_selection:node.tool_selection??'all',tool_limit:node.tool_limit??8,parallel_tool_calls:node.parallel_tool_calls??false,tool_errors:node.tool_errors??'raise',output_errors:node.output_errors??'raise',max_output_retries:node.max_output_retries??1,max_output_tokens:node.max_output_tokens??512}:null})}/>{say('使用独立 harness 配置','Use a per-agent harness')}</label><p className="hint">{say('下面的工具与恢复设置保存到该智能体的 harness，可在改进页指定搜索范围。','Tool and recovery settings below belong to this agent’s harness. Set their search bounds in Improve.')}</p><label>{say('消息收件箱','Peer mailbox')}<input aria-label="Peer mailbox" value={typeof node.mailbox==='string'?node.mailbox:''} placeholder="analyst" onChange={e=>change({mailbox:e.target.value||null})}/></label>
    {node.harness&&<><label>{say('自动检索记忆','Retrieve memory before each task')}<select aria-label="Harness memory tool" value={node.harness.memory?.tool??''} onChange={e=>change({harness:{...node.harness,memory:e.target.value?{tool:e.target.value,query_input:Object.keys(node.inputs)[0]??'',limit:5,max_chars:4000}:null}})}><option value="">{say('关闭','Off')}</option>{memory.filter(([alias,t])=>node.tools?.includes(alias)&&['memory.search','memory.recall','documents.search'].includes(t.plugin)).map(([alias])=><option key={alias}>{alias}</option>)}</select></label>{node.harness.memory&&<><label>{say('查询输入','Query input')}<select aria-label="Memory query input" value={node.harness.memory.query_input} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,query_input:e.target.value}}})}>{Object.keys(node.inputs).map(name=><option key={name}>{name}</option>)}</select></label><label>{say('检索条数','Retrieved records')}<input aria-label="Harness memory limit" type="number" min={1} max={20} value={node.harness.memory.limit} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,limit:Number(e.target.value)}}})}/></label><label>{say('记忆字符预算','Memory character budget')}<input aria-label="Harness memory characters" type="number" min={128} max={16000} value={node.harness.memory.max_chars} onChange={e=>change({harness:{...node.harness,memory:{...node.harness!.memory!,max_chars:Number(e.target.value)}}})}/></label></>}</>}
    </section>}
    <section className="setting-section"><h4><Icon name="file"/>{say('提示词','Prompt')}</h4>
      <select aria-label="Instruction source" value={resource} onChange={e=>change({instructions:e.target.value?{resource:e.target.value}:content})}><option value="">{say('节点内编辑','Inline instruction')}</option>{Object.entries(doc.spec.resources).filter(([,r])=>r.role==='prompt').map(([name])=><option key={name} value={name}>{name}</option>)}</select>
      <textarea aria-label={say('指令','Instructions')} className="prompt-input" value={content} onChange={e=>resource?onChange(node,{resources:{...doc.resources,[resource]:e.target.value}}):change({instructions:e.target.value})}/>
      {!resource&&<button className="text-action" onClick={()=>create('prompt')}>{say('保存为可进化资源','Make prompt evolvable')}</button>}
      {resource&&<small className="setting-note">{say('可在改进页选择此资源','Available for selection in Improve')} · {resource}</small>}
    </section>
    <section className="setting-section"><h4><Icon name="layers"/>{say('技能','Skills')}<span>{node.skills?.length??0}</span></h4>
      <p className="hint">{say('按顺序附加到主提示词，可共享、编辑和独立进化。','Reusable procedures, appended in order and optimized separately.')}</p>
      {skillEntries.map(([name])=><div key={name}><label className="check"><input type="checkbox" aria-label={`Skill ${name}`} checked={node.skills?.includes(name)??false} onChange={e=>change({skills:e.target.checked?[...(node.skills??[]),name]:(node.skills??[]).filter(s=>s!==name)})}/>{name}</label>{node.skills?.includes(name)&&<textarea aria-label={`Skill content ${name}`} value={doc.resources?.[name]??''} onChange={e=>onChange(node,{resources:{...doc.resources,[name]:e.target.value}})}/>}</div>)}
      <div className="inline-form"><input aria-label="New skill name" placeholder={say('例如 writing_style','e.g. writing_style')} value={newSkill} onChange={e=>setNewSkill(e.target.value)}/><button disabled={!/^[A-Za-z][A-Za-z0-9_-]{0,54}$/.test(newSkill.trim())} onClick={()=>create('skill')}>{say('添加','Add')}</button></div>
    </section>
    {node.type==='agent'&&<><section className="setting-section"><h4><Icon name="tool"/>{say('工具','Tools')}<span>{node.tools?.length??0}</span></h4>
      {toolList(tools.filter(([,t])=>! /^(memory|documents)\./.test(t.plugin)))}
      {!tools.length&&<p className="hint">{say('在规格中声明工具，部署配置连接 HTTP、MCP 或 Python 插件。','Declare tools in the spec; connect HTTP, MCP or Python plugins in your deployment.')}</p>}
      <label>{say('工具选择','Tool selection')}<select aria-label="Tool selection" value={node.tool_selection??'all'} onChange={e=>change({tool_selection:e.target.value as 'all'|'relevant'})}><option value="all">{say('全部已选工具','All selected tools')}</option><option value="relevant">{say('按任务筛选','Match to the task')}</option></select></label>
      {node.tool_selection==='relevant'&&<label>{say('最多提供工具数','Tools per turn')}<input aria-label="Tool limit" type="number" min={1} max={64} value={node.tool_limit??8} onChange={e=>change({tool_limit:Number(e.target.value)})}/></label>}
      <label className="check"><input aria-label="Parallel read tools" type="checkbox" checked={node.parallel_tool_calls??false} onChange={e=>change({parallel_tool_calls:e.target.checked})}/>{say('并行执行只读工具','Run read tools concurrently')}</label>
      <label>{say('最多工具轮数','Tool rounds')}<input aria-label="Tool rounds" type="number" min={1} max={256} value={node.max_tool_rounds??''} placeholder={say('使用运行预算','Use run budget')} onChange={e=>change({max_tool_rounds:e.target.value?Number(e.target.value):null})}/></label>
      <label>{say('工具失败处理','Tool errors')}<select aria-label="Tool error policy" value={node.tool_errors??'raise'} onChange={e=>change({tool_errors:e.target.value as 'raise'|'feedback'})}><option value="raise">{say('停止并报告','Stop and report')}</option><option value="feedback">{say('反馈给智能体','Let the agent recover')}</option></select></label>
    </section><section className="setting-section"><h4><Icon name="database"/>{say('记忆与知识','Memory and knowledge')}</h4><p className="hint">{say('当前用户、当前项目中的智能体共享这些记录。不同用户和项目隔离。','Agents share records within this user and project. Users and projects have separate stores.')}</p>{toolList(memory)}<div className="memory-shortcuts">{[['memory.search',say('事实检索','Facts')],['memory.write',say('保存事实','Save facts')],['memory.recall',say('经验召回','Experiences')],['documents.search',say('知识检索','Documents')]].filter(([plugin])=>!tools.some(([alias,t])=>t.plugin===plugin&&node.tools?.includes(alias))).map(([plugin,label])=><button key={plugin} onClick={()=>attachMemory(plugin)}>+ {label}</button>)}</div></section></>}
    {doc.spec.models[node.model??'']?.requires.includes('vision')&&<section className="setting-section"><h4><Icon name="image"/>{say('图片输入','Image inputs')}</h4><p className="hint">{say('选择包含图片 URI 或资产的输入，模型会读取图片内容。','Select inputs containing image URIs or assets to send as visual content.')}</p>{Object.keys(node.inputs??{}).map(name=><label className="check" key={name}><input aria-label={`Image input ${name}`} type="checkbox" checked={node.image_inputs?.includes(name)??false} onChange={e=>change({image_inputs:e.target.checked?[...(node.image_inputs??[]),name]:(node.image_inputs??[]).filter(x=>x!==name)})}/>{name}</label>)}</section>}
    <details className="setting-section" open><summary><Icon name="model"/>{say('模型参数','Model parameters')}</summary>
      <label>{say('模型绑定','Model binding')}<select aria-label="Model binding" value={node.model??''} onChange={e=>change({model:e.target.value})}>{Object.keys(doc.spec.models).map(name=><option key={name}>{name}</option>)}</select></label>
      <div className="sampling-grid"><label>Temperature<input aria-label="Temperature" type="number" min={0} max={2} step={0.1} placeholder="0" value={node.temperature??''} onChange={e=>change({temperature:e.target.value?Number(e.target.value):null})}/></label><label>Top P<input aria-label="Top P" type="number" min={0.01} max={1} step={0.05} placeholder={say('供应商默认','Provider default')} value={node.top_p??''} onChange={e=>change({top_p:e.target.value?Number(e.target.value):null})}/></label></div>
      <label>{say('单次输出 token 上限','Output token limit')}<input aria-label="Node output token limit" type="number" min={1} max={32768} placeholder={String(doc.spec.execution?.max_output_tokens??512)} value={node.max_output_tokens??''} onChange={e=>change({max_output_tokens:e.target.value?Number(e.target.value):null})}/></label>
      <label>{say('响应格式','Response format')}<select aria-label="Response format" value={node.response_format??'text'} onChange={e=>change({response_format:e.target.value as 'text'|'json'})}><option value="text">Text</option><option value="json">JSON</option></select></label>
      <label>{say('输出格式错误处理','Invalid output handling')}<select aria-label="Output error policy" value={node.output_errors??'raise'} onChange={e=>change({output_errors:e.target.value as 'raise'|'feedback'})}><option value="raise">{say('停止并报告','Stop and report')}</option><option value="feedback">{say('反馈给模型重试','Ask model to repair')}</option></select></label>
      {node.output_errors==='feedback'&&<label>{say('最多修复次数','Maximum repair attempts')}<input aria-label="Output repair attempts" type="number" min={0} max={3} value={node.max_output_retries??1} onChange={e=>change({max_output_retries:Number(e.target.value)})}/></label>}
    </details>
  </div>;
}
