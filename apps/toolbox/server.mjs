import http from 'node:http';
import {timingSafeEqual,randomUUID} from 'node:crypto';
import {mkdir,writeFile,readFile,readdir,stat,unlink} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {Toolbox} from './runtime.mjs';
const port=Number(process.env.EVOSPRIG_TOOLBOX_PORT??18769);
const root=resolve(process.env.EVOSPRIG_ARTIFACT_DIR??'.evosprig-artifacts');
const token=process.env.EVOSPRIG_TOOLBOX_TOKEN;
await mkdir(root,{recursive:true});
const types={svg:'image/svg+xml',png:'image/png',csv:'text/csv',json:'application/json',html:'text/html',txt:'text/plain'};
const toolbox=await new Toolbox({artifact:async({name,bytes})=>{
  const id=randomUUID().replaceAll('-','');
  const mime=types[name.split('.').pop()]??'application/octet-stream';
  await writeFile(join(root,id),bytes);
  return {name,mime,bytes:bytes.length,url:`http://127.0.0.1:${port}/artifacts/${id}`};
}}).start();
const cleanup=setInterval(async()=>{
  for(const name of await readdir(root)) {
    if(!/^[a-f0-9]{32}$/.test(name))continue;
    const path=join(root,name);
    if(Date.now()-(await stat(path)).mtimeMs>3600000)await unlink(path).catch(()=>{});
  }
},60000);cleanup.unref();
const server=http.createServer(async(req,res)=>{
  const send=(status,value)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(value));};
  if(token) {
    const expected=Buffer.from('Bearer '+token),supplied=Buffer.from(req.headers.authorization??'');
    if(expected.length!==supplied.length||!timingSafeEqual(expected,supplied))return send(401,{error:'Authentication required'});
  }
  try {
    if(req.method==='GET'&&req.url==='/health')return send(200,{status:'ready',tools:['python','preview','ocr']});
    if(req.method==='GET'&&/^\/artifacts\/[a-f0-9]{32}$/.test(req.url??'')) {
      const bytes=await readFile(join(root,req.url.split('/').pop()));
      res.writeHead(200,{'content-type':'application/octet-stream','content-disposition':'attachment','x-content-type-options':'nosniff'});res.end(bytes);return;
    }
    if(req.method!=='POST'||!['/python','/preview','/ocr'].includes(req.url))return send(404,{error:'Unknown endpoint'});
    let size=0;const chunks=[];
    for await(const chunk of req){size+=chunk.length;if(size>5000000)return send(413,{error:'Input too large'});chunks.push(chunk);}
    const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
    return send(200,await toolbox.run(req.url.slice(1),input));
  }catch(error){return send(error.status??400,{error:error.message.slice(0,500)});}
});
server.requestTimeout=30000;
server.listen(port,'127.0.0.1',()=>process.stdout.write(`EvoSprig Toolbox on http://127.0.0.1:${port}\n`));
const stop=async()=>{server.close();clearInterval(cleanup);await toolbox.close();};
process.once('SIGTERM',()=>{void stop();});process.once('SIGINT',()=>{void stop();});
