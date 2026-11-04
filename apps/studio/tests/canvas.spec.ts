import {test,expect} from '@playwright/test';

test('nested graphs and nested visual groups survive edits, collapse and reload',async({page,request})=>{
  const id='nested-'+Date.now().toString(36);
  const transform=(text:string)=>({type:'transform',inputs:{text:{value:text}},output_schema:{type:'object'}});
  const body={entry:'draft',nodes:{draft:transform('before'),check:transform('review')},edges:[{source:'draft',target:'check'}],output:{text:{ref:'nodes.draft.output.text'}}};
  const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{},tools:{},resources:{},graph:{entry:'team',nodes:{team:{type:'loop',max_iterations:1,inputs:{},output_schema:{type:'object'},body},finish:transform('finish')},edges:[{source:'team',target:'finish'}],output:{text:{ref:'nodes.team.output.text'}}}};
  const canvas={groups:{graph:[{id:'group:inner',label:'Specialists',members:['team'],collapsed:true},{id:'group:outer',label:'Product team',members:['group:inner','finish'],collapsed:true}]}};
  expect((await request.post('/api/projects',{data:{spec,canvas}})).status()).toBe(201);
  await page.goto('/');await page.getByRole('button').filter({hasText:id}).click();
  await expect(page.locator('.react-flow__node-workflow')).toHaveCount(0);
  await page.getByRole('button',{name:'Expand Product team',exact:true}).click();
  await page.getByRole('button',{name:'Expand Specialists',exact:true}).click();
  await page.getByRole('button',{name:'Arrange',exact:true}).click();
  await page.locator('.subflow-links button').click();
  await expect(page.locator('.canvas-breadcrumb')).toContainText('team');
  await page.locator('.react-flow__node[data-id="draft"]').click();
  const draft=JSON.stringify({...transform('after')});
  await page.getByLabel('Full node (JSON)',{exact:true}).fill(draft);
  // Navigation must commit the pending nested-node draft.
  await page.locator('.canvas-breadcrumb').getByRole('button',{name:'Workflow',exact:true}).click();
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  const stored=await(await request.get('/api/projects/'+id)).json();
  expect(stored.spec.graph.nodes.team.body.nodes.draft.inputs.text.value).toBe('after');
  expect(stored.canvas.groups.graph).toHaveLength(2);
  expect(stored.layout['graph/team/body/draft']).toBeDefined();
  await page.reload();await page.getByRole('button').filter({hasText:id}).click();
  await page.getByRole('button',{name:'Collapse Product team',exact:true}).click();
  await expect(page.locator('.react-flow__node-workflow')).toHaveCount(0);
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.locator('.results')).toContainText('"text": "after"');
});

test('selected nodes form nested groups without changing the execution graph',async({page,request})=>{
  const id='grouping-'+Date.now().toString(36);
  const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{},tools:{},resources:{},graph:{entry:'a',nodes:{a:{type:'transform',inputs:{},output_schema:{}},b:{type:'transform',inputs:{},output_schema:{}}},edges:[{source:'a',target:'b'}],output:{}}};
  const created=await(await request.post('/api/projects',{data:{spec}})).json();
  await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
  await page.locator('.react-flow__node[data-id="a"]').click();
  await page.locator('.react-flow__node[data-id="b"]').click({modifiers:['Shift']});
  await page.getByRole('button',{name:'Group',exact:true}).click();
  await page.getByLabel('Group name',{exact:true}).fill('Specialists');
  await page.getByRole('button',{name:'Group',exact:true}).click();
  await page.getByLabel('Group name',{exact:true}).fill('Team');
  await page.getByRole('button',{name:'Collapse group',exact:true}).click();
  await expect(page.locator('.react-flow__node-workflow')).toHaveCount(0);
  await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
  const saved=await(await request.get('/api/projects/'+id)).json();
  expect(saved.spec_hash).toBe(created.spec_hash);
  expect(saved.canvas.groups.graph).toHaveLength(2);
  expect(saved.canvas.groups.graph.find((g:{label:string})=>g.label==='Specialists').members.sort()).toEqual(['a','b']);
});

test('focus and resize keep the arranged graph centered in the visible canvas',async({page,request})=>{
  const id='focus-'+Date.now().toString(36);
  const node={type:'transform',inputs:{},output_schema:{}};
  const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{},tools:{},resources:{},graph:{entry:'a',nodes:{a:node,b:node,c:node},edges:[{source:'a',target:'b'},{source:'b',target:'c'}],output:{}}};
  const canvas={groups:{graph:[{id:'group:team',label:'Task team',members:['a','b','c'],collapsed:false,direction:'DOWN'}]}};
  expect((await request.post('/api/projects',{data:{spec,canvas}})).status()).toBe(201);
  await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
  await page.getByRole('button',{name:'Arrange',exact:true}).click();
  await page.getByRole('button',{name:'Focus canvas',exact:true}).click();
  const centered=async()=>{
    await expect.poll(async()=>{
      const frame=await page.locator('.react-flow').boundingBox();
      const group=await page.locator('.react-flow__node[data-id="group:team"]').boundingBox();
      return frame&&group?Math.abs(group.x+group.width/2-frame.x-frame.width/2):10000;
    }).toBeLessThan(35);
  };
  await centered();
  await page.setViewportSize({width:1100,height:850});await centered();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button',{name:'Focus canvas',exact:true})).toBeVisible();
  await centered();
});

test('nested collapsed groups keep both connecting edges after save and reload',async({page,request})=>{
  const id='group-edges-'+Date.now().toString(36);
  const node={type:'transform',inputs:{},output_schema:{}};
  const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{},tools:{},resources:{},
    graph:{entry:'before',nodes:{before:node,inside:node,after:node},edges:[{source:'before',target:'inside'},{source:'inside',target:'after'}],output:{}}};
  const canvas={groups:{graph:[{id:'group:inner',label:'Inner team',members:['inside'],collapsed:true},
    {id:'group:outer',label:'Whole team',members:['before','group:inner','after'],collapsed:false,direction:'DOWN'}]}};
  await request.post('/api/projects',{data:{spec,canvas}});
  await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
  await page.getByRole('button',{name:'Arrange',exact:true}).click();
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  await expect(page.locator('.react-flow__node[data-id="group:inner"] .target')).toHaveClass(/react-flow__handle-top/);
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  await page.reload();await page.locator('.project[title="'+id+'"]').click();
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  await page.getByRole('button',{name:'Expand Inner team',exact:true}).click();
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
  await page.getByRole('button',{name:'Collapse Inner team',exact:true}).click();
  await expect(page.locator('.react-flow__edge')).toHaveCount(2);
});
