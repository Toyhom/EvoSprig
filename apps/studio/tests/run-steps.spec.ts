import {test,expect} from '@playwright/test';

test('inspect a failed map item and debug it with its saved inputs',async({page,request})=>{
  const id='step-inspection-'+Date.now();
  const body={entry:'check',nodes:{check:{type:'transform',inputs:{text:{ref:'input.item'}},output_schema:{type:'object',properties:{text:{const:'accepted'}}}}},edges:[],output:{text:{ref:'nodes.check.output.text'}}};
  const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:{type:'object'},models:{},tools:{},resources:{},graph:{entry:'shots',nodes:{shots:{type:'map',items:{value:['accepted','needs fixing']},carry:{value:{}},body,inputs:{},output_schema:{type:'object'}}},edges:[],output:{shots:{ref:'nodes.shots.output'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
  await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('failed');
  const step=page.locator('.run-step[title="graph/shots/item-1/check"]');
  await expect(step).toContainText('Failed');await step.click();
  const detail=page.getByRole('article',{name:'Step details'});
  await expect(detail).toContainText('transform · Failed');
  await detail.getByText('Input',{exact:true}).click();await expect(detail).toContainText('needs fixing');
  await detail.getByRole('button',{name:'Debug with these inputs',exact:true}).click();
  const panel=page.getByRole('region',{name:'Node debug'});
  await expect(panel.getByLabel('Saved execution',{exact:true})).toHaveValue('graph/shots/item-1');
  await expect(panel.getByLabel('item',{exact:true})).toHaveValue('"needs fixing"');
  await panel.getByLabel('item',{exact:true}).fill('"accepted"');
  const started=page.waitForResponse(r=>r.url().endsWith('/debug/runs')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Run selected nodes',exact:true}).click();
  const result=await(await started).json();
  await expect(page.getByRole('status')).toContainText('succeeded');
  const record=await(await request.get('/api/runs/'+result.run_id)).json();
  expect(record.output.check.text).toBe('accepted');
  expect(record.events.some((event:{node_id:string})=>event.node_id==='graph/shots')).toBe(false);
});

test('history step inspection switches back to the right canvas node',async({page,request})=>{
  const id='history-step-'+Date.now();
  const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:{type:'object'},models:{},tools:{},resources:{},graph:{entry:'task',nodes:{task:{type:'transform',inputs:{text:{value:'A saved result'}},output_schema:{type:'object'}}},edges:[],output:{text:{ref:'nodes.task.output.text'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await page.getByRole('button',{name:'History',exact:true}).click();
  await page.locator('.run-step[title="graph/task"]').click();
  await page.getByRole('button',{name:'Debug with these inputs',exact:true}).click();
  await expect(page.getByRole('region',{name:'Node debug'})).toBeVisible();
  await expect(page.locator('.react-flow__node[data-id="task"]')).toBeVisible();
});
