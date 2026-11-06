const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const {randomBytes}=require('node:crypto');
const {join}=require('node:path');
const {once}=require('node:events');

function backendCommand({packaged,resources,python,root,executable,platform=process.platform}) {
  if(executable)return [executable,[]];
  return packaged
    ? [join(resources,'backend',platform==='win32'?'evosprig-backend.exe':'evosprig-backend'),[]]
    : [python||'python',['-u',join(root,'backend.py')]];
}
function startBackend({workspace,studio,credentials={},onLog=()=>{},...options}) {
  const [command,args]=backendCommand(options);
  const token=randomBytes(32).toString('hex');
  const child=spawn(command,[...args,'--workspace',workspace,'--studio',studio],{
    stdio:['pipe','pipe','pipe'],windowsHide:true,env:{...process.env,PYTHONUTF8:'1',PYTHONUNBUFFERED:'1'},
  });
  child.stdin.on('error',()=>{});
  child.stdin.write(JSON.stringify({token,credentials})+'\n');
  child.stderr.on('data',chunk=>onLog(chunk.toString()));
  let origin='';
  const ready=new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{reject(new Error('The local backend did not become ready within 90 seconds.'));child.stdin.end();},90000);
    const lines=createInterface({input:child.stdout});
    const fail=error=>{clearTimeout(timer);reject(error);};
    child.once('error',fail);
    child.once('exit',(code)=>fail(new Error(`Local backend exited (${code}). Open the desktop log for details.`)));
    lines.on('line',line=>{
      let message;try{message=JSON.parse(line);}catch{onLog(line+'\n');return;}
      if(!origin&&Number.isInteger(message.port)&&message.port>0&&message.port<65536){
        origin=`http://127.0.0.1:${message.port}`;clearTimeout(timer);resolve(origin);
      }
    });
  });
  async function stop(){
    if(child.exitCode!==null||child.signalCode)return;
    const exited=once(child,'exit').catch(()=>{});
    child.stdin.end();
    const timer=setTimeout(()=>child.kill(),12000);
    try{await exited;}finally{clearTimeout(timer);}
  }
  return {child,token,ready,stop,get origin(){return origin;}};
}
function isLocalApi(url,origin){try{const target=new URL(url);return target.origin===origin&&target.pathname.startsWith('/api/');}catch{return false;}}
function externalLink(url){try{const target=new URL(url);return ['https:','http:'].includes(target.protocol)&&!['127.0.0.1','localhost','::1','[::1]'].includes(target.hostname);}catch{return false;}}
module.exports={backendCommand,startBackend,isLocalApi,externalLink};
