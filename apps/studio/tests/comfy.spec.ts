import {test,expect} from '@playwright/test';

test('import, run, edit and export a ComfyUI graph from the canvas',async({page,request})=>{
  const id='comfy-'+Date.now();
  const workflow={version:0.4,extra:{display:'preserved'},nodes:[
    {id:1,type:'Number',pos:[0,0],widgets_values:[12],outputs:[{type:'INT',links:[1]}]},
    {id:2,type:'Save',pos:[340,0],widgets_values:['shot'],inputs:[{name:'number',type:'INT',link:1}],outputs:[]},
    {id:3,type:'Note',widgets_values:['A production note'],pos:[0,200]},
  ],links:[[1,1,0,2,0,'INT']]};
  const schemas={Number:{input:{required:{value:['INT',{min:1,max:50}]}},output:['INT']},
    Save:{input:{required:{number:['INT',{forceInput:true}],prefix:['STRING']}},output:[],output_node:true}};
  await page.goto('/');
  await page.getByRole('button',{name:'ComfyUI · Import workflow',exact:true}).click();
  const panel=page.getByRole('region',{name:'ComfyUI import'});
  await panel.getByLabel('ComfyUI workflow JSON').setInputFiles({name:'workflow.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(workflow))});
  await panel.getByLabel('ComfyUI server').fill('');
  await panel.getByLabel('ComfyUI project ID').fill(id);
  await panel.getByText('Use saved node schemas',{exact:true}).click();
  await panel.getByLabel('ComfyUI node schemas').setInputFiles({name:'schemas.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(schemas))});
  await panel.getByRole('button',{name:'Check nodes and parameters',exact:true}).click();
  await expect(panel).toContainText('2 tool nodes ready');
  await panel.getByRole('button',{name:'Open on canvas',exact:true}).click();
  await expect(page.locator('.project.active')).toContainText(id);
  const document=await(await request.get('/api/projects/'+id)).json();
  const original=document.spec.graph.nodes.comfy_1;
  await page.locator('.react-flow__node[data-id="comfy_1"]').click();
  await page.locator('.advanced-node > summary').click();
  await page.getByLabel('Full node (JSON)',{exact:true}).fill(JSON.stringify({...original,inputs:{value:{value:14}}}));
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('succeeded');
  await page.getByLabel('Export target').selectOption('comfy');
  const download=page.waitForEvent('download');
  await page.locator('button.export-button').click();
  const stream=await(await download).createReadStream();
  const chunks=[];for await(const chunk of stream!)chunks.push(chunk);
  const exported=JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.nodes.find((n:{id:number})=>n.id===1).widgets_values).toEqual([14]);
  expect(exported.nodes.find((n:{id:number})=>n.id===3).widgets_values).toEqual(['A production note']);
  expect(exported.extra).toEqual(workflow.extra);
});
