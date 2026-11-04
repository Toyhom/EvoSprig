import {test, expect} from '@playwright/test';

test('render controls keep drafts, save typed values and export the full graph', async ({page, request}) => {
  const id = 'recipe-' + Date.now();
  const spec = {spec_version:'0.3', id, input_schema:{}, output_schema:{}, models:{}, resources:{},
    tools:{recipe:{plugin:'film.recipe',version:'1'}},
    graph:{entry:'prepare',nodes:{prepare:{type:'tool',tool:'recipe',inputs:{},output_schema:{}}},edges:[],output:{}}};
  let document = await (await request.post('/api/projects', {data:{spec}})).json();
  let steps = 12;
  const recipe = () => ({name:'film.recipe', revision:document.revision, workflow_hash:'graph-'+steps,
    workflow:{nodes:[{id:1,type:'Sampler',widgets_values:[steps]},{id:2,type:'Note',widgets_values:['Keep me']}],links:[[1,1,0,2,0,'*']]},
    nodes:[{id:'1',class_type:'Sampler',title:'Shot sampling',mode:0,position:[0,0],inputs:{steps,scheduler:'simple'},
      input_schemas:{steps:{type:'integer',minimum:1,maximum:50},scheduler:{enum:['simple','beta']}}},
      {id:'2',class_type:'Note',title:'Production notes',mode:0,position:[360,0],inputs:{}}]});
  await page.route('**/api/projects/'+id+'/recipes', route=>route.fulfill({json:[{name:'film.recipe',node_count:2}]}));
  await page.route('**/api/projects/'+id+'/recipes/film.recipe', async route=>{
    if(route.request().method()==='POST'){
      const change = route.request().postDataJSON();
      expect(change.changes).toEqual({'1':{inputs:{steps:14}}});
      steps=14;document={...document,revision:document.revision+1};
      await route.fulfill({json:{project:document,workflow_hash:'graph-14'}});
    }else await route.fulfill({json:recipe()});
  });
  await page.goto('/');
  await page.locator('.project[title="'+id+'"]').click();
  await page.getByRole('button',{name:'Open render workflow',exact:true}).click();
  const graph=page.getByRole('region',{name:'Render graph'});
  await graph.locator('.compute-node-list').getByRole('button').filter({hasText:'Shot sampling'}).click();
  await graph.getByLabel('steps',{exact:true}).fill('14');
  await expect(graph.locator('.react-flow__edge')).toHaveCount(1);
  await graph.getByLabel('Search compute nodes').fill('Sampler');
  await expect(graph.locator('.react-flow__edge')).toHaveCount(1);
  await expect(graph.getByRole('button',{name:'Export ComfyUI',exact:true})).toBeDisabled();
  page.once('dialog', dialog=>dialog.dismiss());
  await graph.getByRole('button',{name:'Back to team',exact:true}).click();
  await expect(graph.getByLabel('steps',{exact:true})).toHaveValue('14');
  await graph.getByRole('button',{name:'Save parameters',exact:true}).click();
  await expect(graph.getByRole('button',{name:'Save parameters',exact:true})).toBeDisabled();
  const download=page.waitForEvent('download');
  await graph.getByRole('button',{name:'Export ComfyUI',exact:true}).click();
  const stream=await (await download).createReadStream();
  const chunks=[];for await(const chunk of stream!)chunks.push(chunk);
  const exported=JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.nodes[0].widgets_values).toEqual([14]);
  expect(exported.nodes[1].widgets_values).toEqual(['Keep me']);
  await graph.getByRole('button',{name:'Back to team',exact:true}).click();
  await expect(graph).toHaveCount(0);
});
