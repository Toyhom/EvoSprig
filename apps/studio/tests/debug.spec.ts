import {test,expect} from '@playwright/test';

test('debug inputs submit visible defaults and keep optional fields absent',async({page,request})=>{
  const id='debug-defaults-'+Date.now();
  const settings={type:'object',properties:{mode:{type:'string',enum:['draft','final']},steps:{type:'integer',default:12,minimum:1},audio:{type:'boolean'},notes:{type:'string',minLength:1}},required:['mode','steps','audio'],additionalProperties:false};
  const spec={id,spec_version:'0.3',input_schema:{type:'object',properties:{settings},required:['settings']},output_schema:{},models:{},tools:{},resources:{},graph:{entry:'render',nodes:{render:{type:'transform',inputs:{settings:{ref:'input.settings'}},output_schema:{}}},edges:[],output:{settings:{ref:'nodes.render.output.settings'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
  await page.locator('.react-flow__node[data-id="render"]').click();
  await page.getByRole('button',{name:'Debug selection',exact:true}).click();
  const panel=page.getByRole('region',{name:'Node debug'});
  await expect(panel.getByLabel('mode',{exact:true})).toHaveValue('"draft"');
  await expect(panel.getByLabel('steps',{exact:true})).toHaveValue('12');
  await panel.getByRole('button',{name:'Add optional notes',exact:true}).click();
  await panel.getByLabel('notes',{exact:true}).fill('One test frame');
  await panel.getByRole('button',{name:'Remove optional notes',exact:true}).click();
  const started=page.waitForResponse(r=>r.url().endsWith('/debug/runs')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Run selected nodes',exact:true}).click();
  const response=await started;expect(response.status()).toBe(202);
  const run=await response.json();
  await expect(page.getByRole('status')).toContainText('succeeded');
  const result=await(await request.get('/api/runs/'+run.run_id)).json();
  expect(result.output.render.settings).toEqual({mode:'draft',steps:12,audio:false});
});

test('debug a node with guided upstream input and leave its source idle',async({page,request})=>{
  const id='debug-'+Date.now();
  const output_schema={type:'object',properties:{text:{type:'string'}},required:['text']};
  const spec={id,spec_version:'0.3',input_schema:{type:'object',properties:{text:{type:'string'}},required:['text']},output_schema,models:{},tools:{},resources:{},graph:{entry:'source',nodes:{source:{type:'transform',inputs:{text:{ref:'input.text'}},output_schema},target:{type:'transform',inputs:{text:{ref:'nodes.source.output.text'}},output_schema}},edges:[{source:'source',target:'target'}],output:{text:{ref:'nodes.target.output.text'}}}};
  expect((await request.post('/api/projects',{data:{spec,resources:{}}})).status()).toBe(201);
  await page.goto('/');
  await page.locator(`.project[title="${id}"]`).click();
  await page.locator('.react-flow__node[data-id="target"]').click();
  await page.getByRole('button',{name:'Debug selection',exact:true}).click();
  const panel=page.getByRole('region',{name:'Node debug'});
  await expect(panel.getByRole('group',{name:'source',exact:true})).toBeVisible();
  await panel.getByRole('group',{name:'source',exact:true}).getByLabel('text',{exact:true}).fill('A saved character reference');
  const started=page.waitForResponse(r=>r.url().endsWith('/debug/runs')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Run selected nodes',exact:true}).click();
  const run=await(await started).json();
  await expect(page.getByRole('status')).toContainText('succeeded');
  const result=await(await request.get('/api/runs/'+run.run_id)).json();
  expect(result.output.target.text).toBe('A saved character reference');
  expect(result.events.some((event:{node_id:string})=>event.node_id==='graph/source')).toBe(false);
});

test('debug a collapsed group without running its predecessor',async({page,request})=>{
  const id='debug-group-'+Date.now();
  const output_schema={type:'object',properties:{text:{type:'string'}},required:['text']};
  const node=(ref:string)=>({type:'transform',inputs:{text:{ref}},output_schema});
  const spec={id,spec_version:'0.3',input_schema:{type:'object',properties:{text:{type:'string'}},required:['text']},output_schema,models:{},tools:{},resources:{},graph:{entry:'source',nodes:{source:node('input.text'),first:node('nodes.source.output.text'),second:node('nodes.first.output.text')},edges:[{source:'source',target:'first'},{source:'first',target:'second'}],output:{text:{ref:'nodes.second.output.text'}}}};
  const canvas={groups:{graph:[{id:'group:shots',label:'Shot team',members:['first','second'],collapsed:true}]}};
  expect((await request.post('/api/projects',{data:{spec,canvas}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
  await page.locator('.react-flow__node[data-id="group:shots"]').click();
  await page.getByRole('button',{name:'Debug selection',exact:true}).click();
  const panel=page.getByRole('region',{name:'Node debug'});
  await panel.getByRole('group',{name:'source',exact:true}).getByLabel('text',{exact:true}).fill('Continue from this pose');
  const response=page.waitForResponse(r=>r.url().endsWith('/debug/runs')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Run selected nodes',exact:true}).click();
  const run=await(await response).json();
  await expect(page.getByRole('status')).toContainText('succeeded');
  const result=await(await request.get('/api/runs/'+run.run_id)).json();
  expect(Object.keys(result.output).sort()).toEqual(['first','second']);
  expect(result.output.second.text).toBe('Continue from this pose');
  expect(result.events.some((event:{node_id:string})=>event.node_id==='graph/source')).toBe(false);
});

test('debug a saved map item with its own upstream values',async({page,request})=>{
  const id='debug-item-'+Date.now();
  const output_schema={type:'object',properties:{text:{type:'string'}},required:['text']};
  const body={entry:'source',nodes:{
    source:{type:'transform',inputs:{text:{ref:'input.item'}},output_schema},
    target:{type:'transform',inputs:{text:{ref:'nodes.source.output.text'}},output_schema}},
    edges:[{source:'source',target:'target'}],output:{text:{ref:'nodes.target.output.text'}}};
  const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:{type:'object'},models:{},tools:{},resources:{},
    graph:{entry:'shots',nodes:{shots:{type:'map',items:{value:['First frame','Second frame']},body,inputs:{},output_schema:{type:'object'}}},
    edges:[],output:{shots:{ref:'nodes.shots.output'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
  await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await page.locator('.subflow-links button').click();
  await page.locator('.react-flow__node[data-id="target"]').click();
  await page.getByRole('button',{name:'Debug selection',exact:true}).click();
  const panel=page.getByRole('region',{name:'Node debug'});
  await panel.getByRole('button',{name:'Use outputs from the last run',exact:true}).click();
  await expect(panel.getByLabel('Saved execution',{exact:true})).toHaveValue('graph/shots/item-1');
  await expect(panel.getByRole('group',{name:'source',exact:true}).getByLabel('text',{exact:true})).toHaveValue('Second frame');
  await panel.getByLabel('Saved execution',{exact:true}).selectOption('graph/shots/item-0');
  await expect(panel.getByRole('group',{name:'source',exact:true}).getByLabel('text',{exact:true})).toHaveValue('First frame');
  const started=page.waitForResponse(r=>r.url().endsWith('/debug/runs')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Run selected nodes',exact:true}).click();
  const run=await(await started).json();
  await expect(page.getByRole('status')).toContainText('succeeded');
  const result=await(await request.get('/api/runs/'+run.run_id)).json();
  expect(result.output.target.text).toBe('First frame');
  expect(result.events.some((event:{node_id:string})=>event.node_id==='graph/source')).toBe(false);
});
