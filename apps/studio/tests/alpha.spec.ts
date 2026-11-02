import { test, expect } from '@playwright/test';
import path from 'node:path';

const object=(name:string,type='string')=>({type:'object',properties:{[name]:{type}},required:[name],additionalProperties:false});

test('conditional graph keeps branch flags through canvas and spec editing',async({page,request})=>{
  const id='branch-'+Date.now().toString(36);
  const spec={spec_version:'0.2',id,input_schema:object('flag','boolean'),output_schema:object('text'),models:{},tools:{},resources:{},graph:{entry:'choose',nodes:{
    choose:{type:'condition',condition:{left:{ref:'input.flag'},op:'truthy'},output_schema:object('value','boolean')},
    yes:{type:'transform',inputs:{text:{value:'yes'}},output_schema:object('text')},no:{type:'transform',inputs:{text:{value:'no'}},output_schema:object('text')},
    merge:{type:'join',join:'selected',inputs:{text:{ref:'nodes.yes.output.text',optional:true,default:'no'}},output_schema:object('text')}
  },edges:[{source:'choose',target:'yes',when:true},{source:'choose',target:'no',when:false},{source:'yes',target:'merge'},{source:'no',target:'merge'}],output:{text:{ref:'nodes.merge.output.text'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.getByRole('button').filter({hasText:id}).click();
  const before=await(await request.get('/api/projects/'+id)).json();
  await page.getByRole('button',{name:'规格',exact:true}).click();await page.getByRole('button',{name:'画布',exact:true}).click();
  await page.getByRole('button',{name:'自动排列'}).click();await page.getByRole('button',{name:'保存',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('已保存');
  const after=await(await request.get('/api/projects/'+id)).json();expect(after.spec_hash).toBe(before.spec_hash);
  expect(after.spec.graph.edges.filter((edge:{when?:boolean})=>typeof edge.when==='boolean').map((edge:{when:boolean})=>edge.when).sort()).toEqual([false,true]);
  await page.getByLabel('运行输入',{exact:true}).fill('{"flag":false}');await page.getByRole('button',{name:'▷ 运行',exact:true}).click();
  await expect(page.locator('.results')).toContainText('"text": "no"');
});

test('human pause validates response, resumes and appears in history',async({page,request})=>{
  const id='approval-'+Date.now().toString(36);
  const spec={spec_version:'0.2',id,input_schema:object('question'),output_schema:object('text'),models:{},tools:{},resources:{},graph:{entry:'review',nodes:{review:{type:'human',inputs:{draft:{ref:'input.question'}},output_schema:object('text')}},edges:[],output:{text:{ref:'nodes.review.output.text'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.getByRole('button').filter({hasText:id}).click();await page.getByRole('button',{name:'▷ 运行',exact:true}).click();
  await expect(page.locator('.results')).toContainText('等待你的确认');
  await page.getByLabel('Response graph/review').fill('{"text":23}');await page.getByRole('button',{name:'提交并继续'}).click();
  await expect(page.getByRole('status')).toContainText('schema');
  await page.getByLabel('Response graph/review').fill('{"text":"approved in browser"}');await page.getByRole('button',{name:'提交并继续'}).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await page.getByRole('button',{name:'历史',exact:true}).click();await expect(page.locator('.panel')).toContainText('approved in browser');
});

test('resources, scoped documents, improvement, candidate diff and export',async({page,request})=>{
  await page.goto('/');const creation=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname==='/api/projects');await page.getByRole('button',{name:'＋ 新建项目'}).click();
  const id=(await(await creation).json()).id;await expect(page.locator('h1')).toHaveText(id);
  await page.getByRole('button',{name:'资源',exact:true}).click();await page.getByRole('button',{name:'将指令保存为资源'}).click();
  await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.getByRole('status')).toContainText('已保存');
  await page.getByRole('button',{name:'记忆与资料',exact:true}).click();
  await page.getByLabel('Memory content').fill('Use concise explanations.');await page.getByRole('button',{name:'保存记忆',exact:true}).click();
  await expect(page.locator('.record')).toContainText('Use concise explanations.');
  await page.getByLabel('Document title').fill('Checkpoint guide');await page.getByLabel('Document text').fill('Durable checkpoints preserve completed node results after a restart.');await page.getByRole('button',{name:'保存文档',exact:true}).click();
  await expect(page.locator('.record').filter({hasText:'Checkpoint guide'})).toBeVisible();
  await page.getByLabel('Document query').fill('checkpoints');await page.getByRole('button',{name:'检索',exact:true}).click();await expect(page.locator('blockquote')).toContainText('Durable checkpoints');
  await page.getByRole('button',{name:'改进',exact:true}).click();
  const sample=(id:string)=>({id,input:{question:id},expected:'Mock: '+JSON.stringify({question:id})});
  const suite={id:'browser-suite',metric:{kind:'exact',output_path:'answer'},search:[sample('search')],selection:[sample('selection')],release:[sample('release-a'),sample('release-b')],test:[sample('sealed')]};
  await page.getByText('导入 EvalSuite JSON',{exact:true}).click();await page.getByLabel('Evaluation suite JSON').fill(JSON.stringify(suite));await page.getByRole('button',{name:'保存任务集',exact:true}).click();
  await expect(page.getByLabel('Evaluation suite',{exact:true})).not.toHaveValue('');await page.getByRole('button',{name:'开始改进',exact:true}).click();
  await expect(page.locator('.history-list')).toContainText('completed',{timeout:30000});
  const studies=await(await request.get('/api/projects/'+id+'/studies')).json();expect(studies[0].result.candidates.length).toBe(1);expect(studies[0].result.gate.passed).toBe(true);
  await page.getByRole('button',{name:'版本',exact:true}).click();await page.getByRole('button',{name:'启用当前版本作为基线'}).click();
  await expect(page.locator('.panel')).toContainText('r1');await expect(page.getByRole('button',{name:'启用此版本',exact:true})).toBeDisabled();
  await page.getByText('instructions',{exact:true}).click();await expect(page.locator('.diff')).toContainText('Mock proposal');
  const downloading=page.waitForEvent('download');await page.getByRole('button',{name:'导出此快照',exact:true}).click();expect((await downloading).suggestedFilename()).toBe(id+'.zip');
  const evidence=process.env.EVOSPRIG_EVIDENCE_DIR;if(evidence)await page.screenshot({path:path.join(evidence,'studio-alpha-versions.png'),fullPage:true});
  const archive=await request.post('/api/projects/'+id+'/export?target=http');expect(archive.status()).toBe(200);
  await page.getByLabel('Import project ZIP').setInputFiles({name:'agent.zip',mimeType:'application/zip',buffer:await archive.body()});
  await expect(page.getByRole('heading',{name:'检查导入工程'})).toBeVisible();
  await page.getByRole('button',{name:'创建导入项目',exact:true}).click();await expect(page.locator('h1')).toHaveText(id+'-import');
  await page.getByLabel('Export target').selectOption('container');
  const containerDownload=page.waitForEvent('download');await page.getByRole('button',{name:'导出 container ↗',exact:true}).click();expect((await containerDownload).suggestedFilename()).toBe(id+'-import.zip');
});
