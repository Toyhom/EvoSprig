import {test,expect, type Page} from '@playwright/test';

async function ready(page:Page){await page.goto('/');await page.locator('.project[title="hello"]').click();await expect(page.locator('.editor')).toHaveAttribute('aria-busy','false');}

test('workspace dividers support dragging, keyboard sizing, persistence and reset',async({page})=>{
 await ready(page);
 const sidebar=page.getByRole('separator',{name:'Resize project sidebar'});
 const original=Number(await sidebar.getAttribute('aria-valuenow'));
 const box=(await sidebar.boundingBox())!;
 await page.mouse.move(box.x+box.width/2,box.y+180);await page.mouse.down();await page.mouse.move(box.x+box.width/2+60,box.y+180,{steps:8});await page.mouse.up();
 await expect(sidebar).toHaveAttribute('aria-valuenow',String(original+60));
 const inspector=page.getByRole('separator',{name:'Resize node inspector'});await inspector.focus();await page.keyboard.press('ArrowLeft');await expect(inspector).toHaveAttribute('aria-valuenow','380');
 const bottom=page.getByRole('separator',{name:'Resize run panel'});await bottom.focus();await page.keyboard.press('ArrowUp');await expect(bottom).toHaveAttribute('aria-valuenow','250');
 await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('evosprig.workspace-layout.v1')||'{}').results)).toBe(250);
 await page.reload();await expect(bottom).toHaveAttribute('aria-valuenow','250');await expect(inspector).toHaveAttribute('aria-valuenow','380');await expect(sidebar).toHaveAttribute('aria-valuenow',String(original+60));
 await sidebar.dblclick();await expect(sidebar).toHaveAttribute('aria-valuenow','240');
 await page.getByLabel('Workspace layout',{exact:true}).click();await page.getByLabel('Node inspector',{exact:true}).uncheck();await page.keyboard.press('Escape');await expect(page.locator('.inspector')).toBeHidden();
 await page.locator('.react-flow__node[data-id="assistant"]').click();await expect(page.locator('.inspector')).toBeVisible();
 await page.getByRole('button',{name:'Results and events',exact:true}).click();await expect(page.getByLabel('Run input',{exact:true})).toBeHidden();await expect(bottom).toBeHidden();
 await page.getByRole('button',{name:'Results and events',exact:true}).click();await expect(page.getByLabel('Run input',{exact:true})).toBeVisible();
 await page.getByLabel('Workspace layout',{exact:true}).click();await page.getByRole('button',{name:'Reset layout',exact:true}).click();await expect(inspector).toHaveAttribute('aria-valuenow','370');await expect(bottom).toHaveAttribute('aria-valuenow','240');
});

test('sidebar actions visibly respond and all main views stay within the viewport',async({page})=>{
 await ready(page);
 const action=page.locator('summary').filter({hasText:'Model connections'});
 const normal=await action.evaluate(el=>getComputedStyle(el).backgroundColor);await action.hover();await expect.poll(()=>action.evaluate(el=>getComputedStyle(el).backgroundColor)).not.toBe(normal);
 await action.click();await expect(page.getByText('Start Studio with --profile deployment.yaml to edit connections.',{exact:true})).toBeVisible();await action.click();
 for(const view of ['Canvas','Spec','Python','Resources','History','Knowledge','Memory','Improve','Versions']){
   await page.locator('.tabs').getByRole('button',{name:view,exact:true}).click();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight)).toBeTruthy();
 }
 await page.setViewportSize({width:1000,height:720});await page.locator('.tabs').getByRole('button',{name:'Canvas',exact:true}).click();
 expect((await page.locator('.workspace').boundingBox())!.width).toBeGreaterThan(280);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await expect(page.getByRole('separator',{name:'Resize project sidebar'})).toBeHidden();
});

test('memory and knowledge have independent navigation, data and node controls',async({page,request})=>{
 const id='memory-separation-'+Date.now();
 const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text']}},tools:{},resources:{},graph:{entry:'assistant',nodes:{assistant:{type:'agent',model:'main',instructions:'Help.',inputs:{query:{value:'preferences'}},output_schema:{type:'object'},tools:[]}},edges:[],output:{text:{ref:'nodes.assistant.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();await page.locator('.tabs').getByRole('button',{name:'Memory',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Agent memory',exact:true})).toBeVisible();await expect(page.getByLabel('Upload knowledge files')).toHaveCount(0);
 await page.getByLabel('Memory content').fill('Prefer diagrams.');await page.getByRole('button',{name:'Save memory',exact:true}).click();await expect(page.locator('.record')).toContainText('Prefer diagrams.');
 await page.locator('.tabs').getByRole('button',{name:'Knowledge',exact:true}).click();await expect(page.getByLabel('Memory content')).toHaveCount(0);await expect(page.getByRole('heading',{name:'Knowledge library',exact:true})).toBeVisible();
 await page.locator('.tabs').getByRole('button',{name:'Canvas',exact:true}).click();await page.locator('.react-flow__node[data-id="assistant"]').click();
 await page.locator('.settings-sections').getByRole('button',{name:'Memory',exact:true}).click();await page.getByRole('button',{name:'+ Facts',exact:true}).click();await page.getByRole('button',{name:'Configure context policy',exact:true}).click();await page.getByLabel('Prune tool history').check();await page.getByLabel('Harness memory tool').selectOption('memory_search');
 await page.locator('.settings-sections').getByRole('button',{name:'Tools & knowledge',exact:true}).click();await expect(page.getByLabel('Tool memory_search')).toBeHidden();await page.getByRole('button',{name:'+ Search',exact:true}).click();
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
 const saved=await(await request.get('/api/projects/'+id)).json();expect(saved.spec.graph.nodes.assistant.tools).toEqual(['memory_search','documents_search']);expect(saved.spec.graph.nodes.assistant.harness.memory.tool).toBe('memory_search');expect(saved.spec.graph.nodes.assistant.harness.tool_history.max_chars).toBe(16000);
});

test('workflow import remains scrollable and keyboard accessible on small screens',async({page})=>{
 await ready(page);await page.setViewportSize({width:900,height:600});
 const launch=page.getByRole('button',{name:'ComfyUI · Import workflow',exact:true});await launch.click();
 const dialog=page.getByRole('dialog',{name:'Import workflow',exact:true});await expect(dialog).toBeVisible();
 await page.getByText('Use saved node schemas',{exact:true}).click();await page.getByLabel('ComfyUI node schemas').scrollIntoViewIfNeeded();await expect(page.getByLabel('ComfyUI node schemas')).toBeInViewport();
 expect((await dialog.boundingBox())!.height).toBeLessThanOrEqual(552);
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await expect(launch).toBeFocused();
});
