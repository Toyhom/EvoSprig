import {test,after,before} from 'node:test';
import assert from 'node:assert/strict';
import {Toolbox} from '../runtime.mjs';
let box;
before(async()=>{box=await new Toolbox({timeout:30000}).start();});
after(async()=>{await box?.close();});
test('executes Python, reads explicit data, returns actual SVG and starts each job fresh',async()=>{
 const result=await box.run('python',{files:{'sales.csv':'region,sales\nEast,30\nWest,20\n'},code:"import csv\nfrom evosprig_plot import bar\nrows=list(csv.DictReader(open('sales.csv')))\nvalues=[int(r['sales']) for r in rows]\nprint(sum(values))\nbar([r['region'] for r in rows],values,title='Sales')"});
 assert.equal(result.ok,true);assert.match(result.stdout,/50/);assert.equal(result.artifacts[0].name,'chart.svg');assert.match(result.artifacts[0].bytes.toString(),/<svg/);
 const fresh=await box.run('python',{code:"import os\nprint(os.path.exists('sales.csv'))\nprint(os.path.exists('/etc/passwd'))"});
 assert.match(fresh.stdout,/False\nFalse/);
});
test('checks real DOM interaction, blocks outbound requests and performs offline OCR',async()=>{
 const result=await box.run('preview',{html:'<h1>COFFEE RECEIPT</h1><p>TOTAL 12.50</p><button onclick="this.textContent=\'Added\'">Add</button><script>fetch("http://127.0.0.1:18799").catch(()=>document.body.dataset.blocked="yes")</script>',actions:[{kind:'click',selector:'button'},{kind:'text',selector:'button',contains:'Added'},{kind:'text',selector:'body[data-blocked=yes]',contains:'TOTAL'}]});
 assert(result.checks.every(c=>c.passed));
 const ocr=await box.run('ocr',{image_base64:result.artifacts[0].bytes.toString('base64')});
 assert.match(ocr.text,/COFFEE/);assert.match(ocr.text,/12.50/);
});
test('rejects host paths and bounds a stalled job',async()=>{
 await assert.rejects(box.run('python',{code:'pass',files:{'../escape':'x'}}),/file name/);
 const old=box.timeout;box.timeout=1000;
 await assert.rejects(box.run('preview',{html:'<script>while(true){}</script>'}),/timed out/);box.timeout=old;
 assert.equal((await box.run('preview',{html:'<p>Recovered</p>'})).text,'Recovered');
});
