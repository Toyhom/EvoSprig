import {test,expect} from '@playwright/test';

test('configure a node prompt, proposer, goal and budget across screen sizes',async({page,request},info)=>{
 const id='scoped-support-'+Date.now().toString(36);
 const node={type:'agent',model:'main',instructions:{resource:'shared'},inputs:{question:{ref:'input.question'}},output_schema:{},harness:{max_tool_rounds:4}};
 const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text']},optimizer:{binding:'main',requires:['text']}},tools:{},resources:{shared:{path:'prompts/shared.md',role:'prompt'}},graph:{entry:'reply',nodes:{reply:node,review:{...node}},edges:[{source:'reply',target:'review'}],output:{answer:{ref:'nodes.reply.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec,resources:{shared:'Answer customer questions using the supplied policy.'}}})).status()).toBe(201);
 expect((await request.post(`/api/projects/${id}/suites/from-inputs`,{data:{name:'support-requests',inputs:[{question:'refund'},{question:'delivery'},{question:'warranty'},{question:'invoice'},{question:'exchange'},{question:'account'}]}})).status()).toBe(201);
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
 await page.getByRole('button',{name:'Improve',exact:true}).click();
 await page.getByLabel('Evolution target node').selectOption('/graph/nodes/reply');
 await page.getByLabel('Evolution target module').selectOption('prompt');
 await expect(page.locator('.resource-choices')).toContainText('shared');
 await page.getByLabel('Evolution proposer').selectOption('optimizer');
 await page.getByLabel('Search rounds',{exact:true}).fill('8');
 await page.getByLabel('Evolution target score').fill('0.5');
 await page.getByLabel('Evolution patience').fill('3');
 await page.getByText('Budget and adoption criteria',{exact:true}).click();
 await page.getByLabel('Time limit (seconds)').fill('900');
 await page.getByLabel('Minimum validation samples').fill('1');
 await page.screenshot({path:info.outputPath('evolution-desktop.png'),fullPage:true});
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:1000});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth)).toBeLessThanOrEqual(1);
  await expect(page.getByLabel('Evolution target node')).toBeVisible();
 }
 const started=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith(`/projects/${id}/studies`));
 await page.getByRole('button',{name:'Start improvement',exact:true}).click();
 const body=(await started).postDataJSON();
 expect(body.config.target).toEqual({node:'/graph/nodes/reply',modules:['prompt']});
 expect(body.proposer_binding).toBe('optimizer');
 expect(body.config.goal).toEqual({score:0.5,patience:3});
 expect(body.config.budget.max_seconds).toBe(900);
 await expect(page.locator('.history-list')).toContainText('completed',{timeout:30000});
 await expect(page.getByText('Target score reached',{exact:true})).toBeVisible();
 // Guided harness search requires no JSON editing and stays inside this node.
 await page.getByLabel('Evolution target module').selectOption('harness');
 await page.getByLabel('Evolution parameter minimum').fill('2');
 await page.getByLabel('Evolution parameter maximum').fill('6');
 const harness=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith(`/projects/${id}/studies`));
 await page.getByRole('button',{name:'Start improvement',exact:true}).click();
 expect((await harness).postDataJSON().config.search_space.fields).toEqual({'/graph/nodes/reply/harness/max_tool_rounds':{kind:'integer',minimum:2,maximum:6}});
 await expect(page.locator('.history-list')).toContainText('completed',{timeout:30000});
});

test('node settings keep sections separate and context policy survives save',async({page,request},info)=>{
 const id='context-policy-'+Date.now().toString(36);
 const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text']}},tools:{},resources:{},graph:{entry:'assistant',nodes:{assistant:{type:'agent',model:'main',instructions:'Answer the request.',output_schema:{}}},edges:[],output:{answer:{ref:'nodes.assistant.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
 await page.locator('.react-flow__node[data-id="assistant"]').click();
 await expect(page.getByLabel('Instructions',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Tool rounds',{exact:true})).toBeHidden();
 await page.getByRole('button',{name:'Runtime',exact:true}).click();
 await page.getByLabel('Structured harness',{exact:true}).check();
 await page.getByLabel('Prune tool history').check();
 await page.getByLabel('Tool history budget').fill('12000');
 await page.getByLabel('Keep recent tool rounds').fill('1');
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
 const doc=await(await request.get(`/api/projects/${id}`)).json();
 expect(Object.values(doc.spec.graph.nodes).find((n:any)=>n.type==='agent')).toMatchObject({harness:{tool_history:{max_chars:12000,keep_recent_rounds:1}}});
 await page.screenshot({path:info.outputPath('inspector-runtime.png'),fullPage:true});
 await page.getByRole('button',{name:'Design',exact:true}).click();
 await expect(page.getByLabel('Instructions',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Tool history budget')).toBeHidden();
});
