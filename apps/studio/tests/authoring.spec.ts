import {test,expect} from '@playwright/test';

test('build from an empty canvas with a tool library and input fields, then export',async({page,request})=>{
 await page.goto('/');
 const creation=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/projects');
 await page.getByRole('button',{name:'＋ New project'}).click();const id=(await(await creation).json()).id;
 await page.locator('.react-flow__node[data-id="assistant"]').click();await page.keyboard.press('Delete');
 await expect(page.locator('.react-flow__node')).toHaveCount(0);
 await page.getByRole('button',{name:'Resources',exact:true}).click();
 await page.getByLabel('Import resource library').setInputFiles({name:'library.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'evosprig.library.v1',resources:{calculate:{path:'code/calculate.py',role:'code',content:'def run(inputs):\n    return {"answer": inputs["number"] * 2}\n'}},tools:{python:{plugin:'code.python',version:'1'}}}))});
 await expect(page.getByLabel('Resource calculate')).toContainText('number');
 await page.getByRole('button',{name:'Canvas',exact:true}).click();
 await page.getByLabel('New node name').fill('double');await page.getByLabel('New node type').selectOption('code');await page.getByRole('button',{name:'Add node',exact:true}).click();
 await expect(page.locator('.react-flow__node[data-id="double"]')).toBeVisible();
 await page.getByLabel('Node code resource').selectOption('calculate');
 await page.getByLabel('Node input name',{exact:true}).fill('number');await page.locator('.node-inputs').getByRole('button',{name:'Add field',exact:true}).click();
 await page.getByLabel('Node input number source',{exact:true}).selectOption('value');await page.getByLabel('Node input number value',{exact:true}).fill('21');
 await page.getByLabel('Workflow settings',{exact:true}).click();
 await page.locator('.workflow-fields details').filter({hasText:'Application output and budget'}).locator('summary').click();
 await page.getByLabel('Application output JSON',{exact:true}).fill('{"type":"object"}');
 await page.getByLabel('Workflow output answer reference',{exact:true}).fill('nodes.double.output.answer');
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
 const doc=await(await request.get('/api/projects/'+id)).json();expect(doc.spec.graph.entry).toBe('double');expect(doc.spec.graph.nodes.double.code).toBe('calculate');
 await page.getByRole('button',{name:'▷ Run',exact:true}).click();await expect(page.getByRole('status')).toContainText('succeeded');await expect(page.locator('.results .json-block').first()).toContainText('42');
 const download=page.waitForEvent('download');await page.getByLabel('Export target').selectOption('http');await page.getByRole('button',{name:'Export http ↗',exact:true}).click();expect((await download).suggestedFilename()).toBe(id+'.zip');
});

test('authoring toolbar keeps whole labels at laptop widths',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'＋ New project'}).click();
 for(const width of [1600,1280,1024]){
  await page.setViewportSize({width,height:900});await page.locator('.react-flow__node').first().click();
  expect(await page.locator('.canvas-tools').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();
  expect(await page.locator('.inspector').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();
  const overlaps=await page.locator('.canvas-actions button').evaluateAll(buttons=>buttons.some((b,i)=>buttons.slice(i+1).some(other=>{const a=b.getBoundingClientRect(),c=other.getBoundingClientRect();return Math.min(a.right,c.right)-Math.max(a.left,c.left)>1&&Math.min(a.bottom,c.bottom)-Math.max(a.top,c.top)>1;})));
  expect(overlaps).toBeFalsy();
 }
});

test('invalid field editing does not leak into another node',async({page})=>{
 await page.goto('/');
 const creation=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/projects');
 await page.getByRole('button',{name:'＋ New project'}).click();const id=(await(await creation).json()).id;
 await expect(page.locator('h1')).toHaveText(id);
 await expect(page.locator('.editor')).toHaveAttribute('aria-busy','false');
 await page.getByLabel('New node name').fill('second');await page.getByRole('button',{name:'Add model node',exact:true}).click();
 await expect(page.locator('.react-flow__node[data-id="second"]')).toBeVisible();
 await page.locator('.react-flow__node[data-id="assistant"]').click();
 await page.locator('.node-fields details > summary').filter({hasText:'Output schema'}).click();
 await page.getByLabel('Output schema JSON',{exact:true}).fill('{');
 await expect(page.locator('.node-fields [role="alert"]')).toBeVisible();
 await page.locator('.react-flow__node[data-id="second"]').click();
 await page.locator('.node-fields details > summary').filter({hasText:'Output schema'}).click();
 expect(await page.getByLabel('Output schema JSON',{exact:true}).evaluate((e:HTMLTextAreaElement)=>e.checkValidity())).toBeTruthy();
 await expect(page.locator('.node-fields [role="alert"]')).toHaveCount(0);
});
