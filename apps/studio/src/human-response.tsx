import {useState} from 'react';
import {empty,ValueField} from './debug-panel';
import type {Schema} from './debug-panel';
import type {Lang,Run} from './types';

export function HumanResponse({wait,lang,onSubmit}:{wait:Run['waiting'][number];lang:Lang;onSubmit:(value:unknown)=>Promise<void>}){
  const schema=(wait.schema??{type:'object'}) as Schema;
  const shown=wait.input&&typeof wait.input==='object'?wait.input as Record<string,unknown>:{};
  const candidate=Object.fromEntries(Object.keys(schema.properties??{}).filter(key=>key in shown).map(key=>[key,shown[key]]));
  const canReuse=wait.kind==='human'&&Object.keys(candidate).length>0&&(schema.required??[]).every(key=>key in candidate);
  const [value,setValue]=useState<unknown>(canReuse?candidate:empty(schema));
  const [busy,setBusy]=useState(false);
  const [editing,setEditing]=useState(!canReuse);
  const say=(zh:string,en:string)=>lang==='zh'?zh:en;
  return <div>
    {canReuse&&<label className="check"><input type="checkbox" checked={editing} onChange={e=>setEditing(e.target.checked)}/>{say('调整后再继续','Edit before continuing')}</label>}
    {editing&&<ValueField schema={schema} value={value} onChange={setValue} label={say('你的回复','Your response')} lang={lang}/>}
    <button disabled={busy} onClick={async e=>{const fields=e.currentTarget.parentElement!.querySelectorAll<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement>('input,textarea,select');if(Array.from(fields).some(field=>!field.reportValidity()))return;setBusy(true);try{await onSubmit(editing?value:candidate);}finally{setBusy(false);}}}>{busy?say('正在提交…','Submitting…'):canReuse&&!editing?say('采用当前结果并继续','Use shown result and continue'):say('提交并继续','Submit and continue')}</button>
  </div>;
}
