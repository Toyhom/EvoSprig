import {test,expect} from '@playwright/test';
import path from 'node:path';

test('configure a memory bank, attach automatic recall, run and reimport its settings',async({page,request})=>{
 const id='bank-agent-'+Date.now();
 const spec={id,spec_version:'0.3',input_schema:{type:'object',properties:{query:{type:'string'}},required:['query']},output_schema:{type:'object'},models:{main:{binding:'main',requires:['text','tool_calling']}},tools:{},resources:{},graph:{entry:'assistant',nodes:{assistant:{type:'agent',model:'main',instructions:'Use relevant user preferences.',inputs:{query:{ref:'input.query'}},output_schema:{type:'object'},tools:[]}},edges:[],output:{answer:{ref:'nodes.assistant.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();await expect(page.locator('.editor')).toHaveAttribute('aria-busy','false');
 await page.locator('.tabs').getByRole('button',{name:'Memory',exact:true}).click();
 await page.getByText('New memory bank',{exact:true}).click();await page.getByLabel('New memory bank name').fill('writer');await page.getByRole('button',{name:'Create memory bank',exact:true}).click();
 await expect(page.getByLabel('Memory bank',{exact:true})).toHaveValue('writer');
 await page.getByLabel('Allow agent memory writes').uncheck();await page.getByRole('button',{name:'Save memory bank settings',exact:true}).click();
 await expect(page.locator('.knowledge-notice')).toHaveText('Memory bank settings saved');
 await page.getByRole('button',{name:'Records',exact:true}).click();await page.getByLabel('Memory content').fill('Prefer concise replies with a diagram.');await page.getByRole('button',{name:'Save memory',exact:true}).click();await expect(page.locator('.record')).toContainText('concise replies');
 await page.getByRole('button',{name:'Retrieval test',exact:true}).click();await page.getByLabel('Memory query').fill('concise');await page.getByRole('button',{name:'Search memories',exact:true}).click();await expect(page.locator('.record')).toContainText('a diagram');
 await page.getByLabel('Memory bank',{exact:true}).selectOption('default');await page.getByRole('button',{name:'Records',exact:true}).click();await expect(page.locator('.record')).toHaveCount(0);
 await page.locator('.tabs').getByRole('button',{name:'Canvas',exact:true}).click();await page.locator('.react-flow__node[data-id="assistant"]').click();await page.locator('.settings-sections').getByRole('button',{name:'Memory',exact:true}).click();
 await page.getByLabel('Agent memory bank').selectOption('writer');await expect(page.getByLabel('Attach memory write tool')).toBeDisabled();await page.getByLabel('Automatically recall selected bank').check();await page.getByRole('button',{name:'Connect memory bank',exact:true}).click();
 await expect(page.getByLabel('Harness memory tool')).toHaveValue('memory_writer_search');
 const screenshots=process.env.EVOSPRIG_SCREENSHOT_DIR;if(screenshots)await page.screenshot({path:path.join(screenshots,'node-memory-bank.png')});
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.locator('.save-state')).toContainText('Saved');
 await page.reload();await page.locator(`.project[title="${id}"]`).click();await page.locator('.react-flow__node[data-id="assistant"]').click();await page.locator('.settings-sections').getByRole('button',{name:'Memory',exact:true}).click();
 await expect(page.getByLabel('Agent memory bank')).toHaveValue('writer');await expect(page.getByLabel('Automatically recall selected bank')).toBeChecked();
 await page.getByLabel('Automatically recall selected bank').uncheck();await page.getByRole('button',{name:'Connect memory bank',exact:true}).click();await expect(page.getByLabel('Harness memory tool')).toHaveValue('');
 await page.getByLabel('Automatically recall selected bank').check();await page.getByRole('button',{name:'Connect memory bank',exact:true}).click();await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.locator('.save-state')).toContainText('Saved');
 await page.getByLabel('Run input',{exact:true}).fill('{"query":"concise"}');await page.getByRole('button',{name:'▷ Run',exact:true}).click();await expect(page.locator('footer[role=status]')).toContainText('succeeded');await expect(page.locator('.run-output')).toContainText('Prefer concise replies with a diagram.');
 const archive=await request.post('/api/projects/'+id+'/export?target=http');expect(archive.status()).toBe(200);
 await page.getByLabel('Import project ZIP').setInputFiles({name:'memory.zip',mimeType:'application/zip',buffer:await archive.body()});await page.getByRole('button',{name:'Create imported project',exact:true}).click();await expect(page.locator('h1')).toHaveText(id+'-import');
 const restored=await(await request.get('/api/projects/'+id+'-import/memory/banks')).json();expect(restored.banks.writer.agent_writes).toBe(false);
 expect((await(await request.get('/api/projects/'+id+'-import/memory?bank=writer')).json())).toEqual([]);
});

test('vector memory configuration survives reload and is independent of knowledge retrieval',async({page,request})=>{
 const id='vector-memory-'+Date.now();const source=await(await request.get('/api/projects/hello')).json();expect((await request.post('/api/projects',{data:{spec:{...source.spec,id},resources:source.resources}})).status()).toBe(201);
 let release!:()=>void;const loaded=new Promise<void>(resolve=>{release=resolve;});
 await page.route('**/memory/banks',async route=>{await loaded;await route.continue();});
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();await page.locator('.tabs').getByRole('button',{name:'Memory',exact:true}).click();
 await page.getByRole('button',{name:'Retrieval & writes',exact:true}).click();await expect(page.getByLabel('Memory retrieval mode')).toHaveCount(0);release();await page.getByLabel('Memory retrieval mode').selectOption('hybrid');
 await page.getByLabel('Memory embedding base_url').fill('http://127.0.0.1:8011/v1');await page.getByLabel('Memory embedding model').fill('bge-m3');await page.getByLabel('Memory embedding api_key_env').fill('MEMORY_EMBEDDING_API_KEY');await page.getByLabel('Memory minimum similarity').fill('0.35');
 await page.getByRole('button',{name:'Save memory bank settings',exact:true}).click();await expect(page.locator('.knowledge-notice')).toHaveText('Memory bank settings saved');
 await page.reload();await page.locator(`.project[title="${id}"]`).click();await page.locator('.tabs').getByRole('button',{name:'Memory',exact:true}).click();await page.getByRole('button',{name:'Retrieval & writes',exact:true}).click();await expect(page.getByLabel('Memory embedding model')).toHaveValue('bge-m3');await expect(page.getByLabel('Memory retrieval mode')).toHaveValue('hybrid');
 const screenshots=process.env.EVOSPRIG_SCREENSHOT_DIR;if(screenshots)await page.screenshot({path:path.join(screenshots,'memory-retrieval-settings.png')});
 const knowledge=await(await request.get('/api/projects/'+id+'/documents/settings')).json();expect(knowledge.retrieval).toBe('lexical');
});

test('disconnecting the last memory write tool permits a read-only run',async({page,request})=>{
 const id='readonly-memory-'+Date.now();
 const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:{type:'object'},models:{main:{binding:'main',requires:['text','tool_calling']}},tools:{write:{plugin:'memory.write',version:'1'}},resources:{},graph:{entry:'assistant',nodes:{assistant:{type:'agent',model:'main',instructions:'Help.',inputs:{query:{value:'preferences'}},output_schema:{type:'object'},tools:['write']}},edges:[],output:{answer:{ref:'nodes.assistant.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();await page.locator('.react-flow__node[data-id="assistant"]').click();await page.locator('.settings-sections').getByRole('button',{name:'Memory',exact:true}).click();
 await expect(page.getByLabel('Attach memory write tool')).toBeChecked();await page.getByLabel('Attach memory write tool').uncheck();await page.getByRole('button',{name:'Connect memory bank',exact:true}).click();
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.locator('.save-state')).toContainText('Saved');
 const saved=await(await request.get('/api/projects/'+id)).json();expect(saved.spec.tools.write).toBeUndefined();expect(saved.spec.graph.nodes.assistant.tools).toEqual(['memory_search']);
 await page.getByRole('button',{name:'▷ Run',exact:true}).click();await expect(page.locator('footer[role=status]')).toContainText('succeeded');
});
