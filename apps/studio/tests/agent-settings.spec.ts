import {test,expect} from '@playwright/test';

test('node resources, skills, shared memory and sampling survive save and run',async({page,request})=>{
 const id='configured-agent-'+Date.now().toString(36);
 const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text','tool_calling']}},tools:{count:{plugin:'builtin.text_stats',version:'1'}},resources:{},graph:{entry:'assistant',nodes:{assistant:{type:'agent',model:'main',instructions:'Help with the task.',inputs:{},output_schema:{type:'object'},tools:['count']}},edges:[],output:{text:{ref:'nodes.assistant.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
 await page.locator('.react-flow__node[data-id="assistant"]').click();
 await page.getByRole('button',{name:'Make prompt evolvable'}).click();
 await page.getByLabel('Instructions',{exact:true}).fill('Answer with concrete steps.');
 await page.getByLabel('New skill name').fill('review');await page.locator('.agent-settings').getByRole('button',{name:'Add',exact:true}).click();
 await page.getByLabel('Skill content review').fill('Check the requested dates before answering.');
 await page.getByRole('button',{name:'+ Facts',exact:true}).click();
 await page.getByLabel('Temperature',{exact:true}).fill('0.4');await page.getByLabel('Top P',{exact:true}).fill('0.85');
 await page.getByLabel('Tool selection',{exact:true}).selectOption('relevant');
 await page.getByLabel('Parallel read tools').check();await page.getByLabel('Tool rounds',{exact:true}).fill('3');
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
 const saved=await(await request.get('/api/projects/'+id)).json();
 expect(saved.spec.graph.nodes.assistant.skills).toEqual(['review']);
 expect(saved.spec.graph.nodes.assistant.tools).toEqual(['count','memory_search']);
 expect(saved.resources.review).toContain('requested dates');
 expect(saved.resources.assistant_prompt).toBe('Answer with concrete steps.');
 expect(saved.spec.graph.nodes.assistant.temperature).toBe(0.4);
 expect(saved.spec.graph.nodes.assistant.top_p).toBe(0.85);
 await page.reload();await page.locator('.project[title="'+id+'"]').click();await page.locator('.react-flow__node[data-id="assistant"]').click();
 await expect(page.getByLabel('Skill review',{exact:true})).toBeChecked();
 await page.getByRole('button',{name:'Improve',exact:true}).click();
 await expect(page.getByLabel('Task inputs JSON')).toBeVisible();
 await expect(page.locator('.check').filter({hasText:'review'})).toContainText('skill');
 await page.getByRole('button',{name:'Canvas',exact:true}).click();await page.getByRole('button',{name:'▷ Run',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('succeeded');
});

test('vision inputs are selectable and persist in the saved workflow',async({page,request})=>{
 const id='vision-review-'+Date.now().toString(36);
 const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{vision:{binding:'vision',requires:['text','vision']}},tools:{},resources:{},graph:{entry:'review',nodes:{review:{type:'model',model:'vision',instructions:'Review the frame.',inputs:{frame:{ref:'input.frame'},brief:{ref:'input.brief'}},output_schema:{}}},edges:[],output:{review:{ref:'nodes.review.output'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
 await page.locator('.react-flow__node[data-id="review"]').click();
 await page.getByLabel('Image input frame',{exact:true}).check();
 await expect(page.getByLabel('Image input brief',{exact:true})).not.toBeChecked();
 await page.getByRole('button',{name:'Save',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Saved');
 const saved=await(await request.get('/api/projects/'+id)).json();
 expect(saved.spec.graph.nodes.review.image_inputs).toEqual(['frame']);
 await page.reload();await page.locator('.project[title="'+id+'"]').click();
 await page.locator('.react-flow__node[data-id="review"]').click();
 await expect(page.getByLabel('Image input frame',{exact:true})).toBeChecked();
});
