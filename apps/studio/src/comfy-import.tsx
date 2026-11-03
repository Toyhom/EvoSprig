import {useState} from 'react';
import type {Document,Lang} from './types';

export function ComfyImport({api,lang,onCreated,onClose}:{api:(path:string,init?:RequestInit)=>Promise<Response>;lang:Lang;onCreated:(doc:Document)=>void;onClose:()=>void}) {
  const [workflow,setWorkflow]=useState<object>();const [schema,setSchema]=useState<object>();
  const [server,setServer]=useState('http://127.0.0.1:8188');const [id,setId]=useState('comfy-'+Date.now().toString(36));
  const [render,setRender]=useState(false);const [preview,setPreview]=useState<{node_count:number;node_map:Record<string,string>}>();
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  async function read(file:File|undefined,assign:(data:object)=>void){if(!file)return;setPreview(undefined);try{assign(JSON.parse(await file.text()));setError('');}catch{setError(lang==='zh'?'请选择有效的 JSON 文件。':'Choose a valid JSON file.');}}
  async function send(create=false){setError('');setBusy(true);try{const body={workflow,object_info:schema??{},project_id:id,server:server||null,render};const value=await(await api('/comfy/'+(create?'import':'inspect'),{method:'POST',body:JSON.stringify(body)})).json();if(create)onCreated(value);else setPreview(value);}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section className="panel comfy-import" aria-label="ComfyUI import"><div className="debug-heading"><h2>{lang==='zh'?'导入 ComfyUI 工作流':'Import a ComfyUI workflow'}</h2><button onClick={onClose}>{lang==='zh'?'关闭':'Close'}</button></div><p>{lang==='zh'?'每个计算节点成为可单独调试的工具节点，保留原参数和画布位置。':'Turn compute nodes into tools with their saved parameters and canvas positions.'}</p>
    <div className="comfy-import-fields"><label>{lang==='zh'?'工作流 JSON':'Workflow JSON'}<input aria-label="ComfyUI workflow JSON" type="file" accept=".json" onChange={e=>read(e.target.files?.[0],setWorkflow)}/></label><label>{lang==='zh'?'ComfyUI 地址':'ComfyUI server'}<input aria-label="ComfyUI server" value={server} onChange={e=>{setServer(e.target.value);setPreview(undefined);}}/></label><label>{lang==='zh'?'项目名称':'Project ID'}<input aria-label="ComfyUI project ID" value={id} onChange={e=>setId(e.target.value)}/></label></div>
    <details><summary>{lang==='zh'?'使用离线节点定义':'Use saved node schemas'}</summary><p className="hint">{lang==='zh'?'上传 ComfyUI /object_info 接口保存的 JSON。':'Upload a JSON response saved from ComfyUI /object_info.'}</p><input aria-label="ComfyUI node schemas" type="file" accept=".json" onChange={e=>read(e.target.files?.[0],setSchema)}/></details>
    <label className="check"><input type="checkbox" checked={render} disabled={!server} onChange={e=>setRender(e.target.checked)}/>{lang==='zh'?'添加渲染节点，运行时提交到 ComfyUI':'Add a render node to submit jobs to ComfyUI'}</label><button disabled={!workflow||busy||(!schema&&!server)} onClick={()=>send()}>{lang==='zh'?'检查节点与参数':'Check nodes and parameters'}</button>
    {preview&&<><p>{preview.node_count} {lang==='zh'?'个工具节点已就绪':'tool nodes ready'}</p><button className="primary" disabled={busy} onClick={()=>send(true)}>{lang==='zh'?'在画布中打开':'Open on canvas'}</button></>}
    {error&&<p role="alert" className="debug-error">{error}</p>}
  </section>;
}
