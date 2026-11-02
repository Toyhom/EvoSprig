/** Ephemeral browser runtimes. Only explicit inputs and local runtime assets enter a job. */
import {chromium} from 'playwright';
import {createWorker} from 'tesseract.js';
import {readFile, realpath} from 'node:fs/promises';
import {dirname, join, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const modules = join(here, 'node_modules');
const mime = {'.js':'text/javascript','.wasm':'application/wasm','.json':'application/json','.zip':'application/zip'};
const pythonSetup = `
import os, sys, io, contextlib, traceback, json, html, types
os.makedirs('/workspace', exist_ok=True)
os.chdir('/workspace')
plot = types.ModuleType('evosprig_plot')
def bar(labels, values, path='chart.svg', title=''):
    if not 1 <= len(labels) <= 100 or len(labels) != len(values):
        raise ValueError('bar chart needs 1..100 paired labels and values')
    width, height = 800, 420
    maximum = max([abs(float(v)) for v in values] + [1])
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="420" viewBox="0 0 800 420">', '<rect width="800" height="420" fill="white"/>', '<g font-family="sans-serif" fill="#253047">', '<text x="30" y="35" font-size="20">'+html.escape(str(title))+'</text>']
    step = 720 / len(labels)
    for i, (label, value) in enumerate(zip(labels, values)):
        x, size = 40 + i * step, abs(float(value)) / maximum * 260
        svg += [f'<rect x="{x}" y="{340-size}" width="{step*0.72}" height="{size}" fill="#4b76c4"/>', f'<text x="{x}" y="365" font-size="12">{html.escape(str(label))}</text>', f'<text x="{x}" y="{330-size}" font-size="12">{float(value):g}</text>']
    svg.append('</g></svg>')
    with open(path,'w') as f: f.write(''.join(svg))
plot.bar = bar
sys.modules['evosprig_plot'] = plot
`;
function boundedString(value, max, name) {
  if (typeof value !== 'string' || Buffer.byteLength(value) > max) throw new Error(`Invalid ${name}`);
  return value;
}
export class Toolbox {
  constructor({timeout=20000,concurrency=2,artifact=async(value)=>value}={}) {
    this.timeout=timeout;this.concurrency=concurrency;this.active=0;this.artifact=artifact;
  }
  async start() {
    this.browser = await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
    return this;
  }
  async close() {await this.browser?.close();}
  async run(kind,input) {
    if(this.active>=this.concurrency) throw Object.assign(new Error('Tool capacity reached'),{status:429});
    this.active++;
    let context,timer,worker,stopped=false;
    const operation = async()=>{
      if(kind==='ocr') {
        const encoded=boundedString(input.image_base64,4_000_000,'image');
        if(!/^[A-Za-z0-9+/]*={0,2}$/.test(encoded)) throw new Error('Image must be base64 bytes');
        worker=await createWorker('eng',1,{
          langPath:join(modules,'@tesseract.js-data/eng/4.0.0_best_int'),
          cacheMethod:'none',gzip:true,logger:()=>{},errorHandler:()=>{},
        });
        if(stopped){await worker.terminate();throw new Error('Tool timed out');}
        const {data}=await worker.recognize(Buffer.from(encoded,'base64'));
        return {text:data.text.slice(0,100000),confidence:data.confidence};
      }
      context=await this.browser.newContext({serviceWorkers:'block',acceptDownloads:false});
      if(stopped){await context.close();throw new Error('Tool timed out');}
      await context.routeWebSocket('**/*',socket=>socket.close());
      await context.route('**/*',async route=>{
        const url=new URL(route.request().url());
        if(kind==='python' && url.origin==='https://runtime.evosprig.invalid' && route.request().method()==='GET' && /^\/[A-Za-z0-9_.-]+$/.test(url.pathname)) {
          const path=join(modules,'pyodide',url.pathname.slice(1));
          try {
            const actual=await realpath(path);
            if(!actual.startsWith(join(modules,'pyodide')+sep)) return route.abort();
            const extension='.'+actual.split('.').pop();
            if(!mime[extension]) return route.abort();
            return route.fulfill({body:await readFile(actual),contentType:mime[extension],headers:{'access-control-allow-origin':'*'}});
          } catch {return route.abort();}
        }
        return route.abort();
      });
      const page=await context.newPage();
      page.on('dialog',dialog=>dialog.dismiss());
      if(kind==='python') {
        const code=boundedString(input.code,50000,'code');
        const files=input.files??{};
        if(typeof files!=='object'||Array.isArray(files)||Object.keys(files).length>20) throw new Error('Invalid files');
        let size=0;
        for(const [name,content] of Object.entries(files)) {
          if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$/.test(name)) throw new Error('Invalid file name');
          size+=Buffer.byteLength(boundedString(content,500000,'file'));
        }
        if(size>1000000) throw new Error('Input files exceed limit');
        await page.addScriptTag({url:'https://runtime.evosprig.invalid/pyodide.js'});
        const result=await page.evaluate(async({code,files,pythonSetup})=>{
          const py=await window.loadPyodide({indexURL:'https://runtime.evosprig.invalid/'});
          await py.runPythonAsync(pythonSetup);
          for(const [name,content] of Object.entries(files)) py.FS.writeFile('/workspace/'+name,content);
          let stdout='',stderr='';
          const capture=target=>text=>{
            if((stdout.length+stderr.length+text.length)>100000) throw new Error('Output exceeds limit');
            if(target==='out')stdout+=text+'\n';else stderr+=text+'\n';
          };
          py.setStdout({batched:capture('out')});py.setStderr({batched:capture('err')});
          let ok=true;
          try {await py.runPythonAsync(code);} catch(error){ok=false;stderr+=String(error).slice(0,12000);}
          const artifacts=[];let bytes=0;
          for(const name of py.FS.readdir('/workspace')) {
            if(name==='.'||name==='..'||name in files||!/^\w[\w.-]*$/.test(name)) continue;
            const stat=py.FS.stat('/workspace/'+name);
            if(!py.FS.isFile(stat.mode))continue;
            bytes+=stat.size;
            if(bytes>4000000||artifacts.length>=20)throw new Error('Artifacts exceed limit');
            artifacts.push({name,data:Array.from(py.FS.readFile('/workspace/'+name))});
          }
          return {ok,stdout,stderr,artifacts};
        },{code,files,pythonSetup});
        result.artifacts=await Promise.all(result.artifacts.map(a=>this.artifact({name:a.name,bytes:Buffer.from(a.data)})));
        return result;
      }
      if(kind==='preview') {
        const html=boundedString(input.html,500000,'HTML');
        const actions=input.actions??[];
        if(!Array.isArray(actions)||actions.length>20) throw new Error('Invalid actions');
        const errors=[];
        page.on('pageerror',error=>{if(errors.length<20)errors.push(error.message.slice(0,2000));});
        await page.setViewportSize({width:1280,height:800});
        await page.setContent(html,{waitUntil:'domcontentloaded',timeout:this.timeout});
        const checks=[];
        for(const action of actions) {
          const locator=page.locator(boundedString(action.selector,300,'selector'));
          if(!['click','fill','text'].includes(action.kind))throw new Error('Unknown action');
          try {
          if(action.kind==='click') await locator.click({timeout:2000});
          else if(action.kind==='fill') await locator.fill(boundedString(action.value,5000,'value'),{timeout:2000});
          else if(action.kind==='text') {
            const observed=await locator.innerText({timeout:2000});
            checks.push({selector:action.selector,expected:action.contains,observed:observed.slice(0,5000),passed:observed.includes(boundedString(action.contains,5000,'expected text'))});
          }
          } catch(error) {checks.push({selector:action.selector,passed:false,error:String(error.message).slice(0,2000)});}
        }
        return {title:await page.title(),text:(await page.locator('body').innerText()).slice(0,20000),errors,checks,artifacts:[await this.artifact({name:'preview.png',bytes:await page.screenshot()})]};
      }
      throw new Error('Unknown tool');
    };
    try {
      return await Promise.race([operation(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Object.assign(new Error('Tool timed out'),{status:408})),this.timeout);})]);
    } finally {
      stopped=true;clearTimeout(timer);await context?.close();await worker?.terminate();this.active--;
    }
  }
}
