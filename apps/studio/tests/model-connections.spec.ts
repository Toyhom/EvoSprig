import {test,expect} from '@playwright/test';

test('model connections bind individual agents and expose resident service preload',async({page,request})=>{
 const id='node-models-'+Date.now().toString(36);
 const spec={spec_version:'0.3',id,input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text']}},tools:{},resources:{},graph:{entry:'writer',nodes:{writer:{type:'model',model:'main',instructions:'Write a story.',inputs:{},output_schema:{}},reviewer:{type:'model',model:'main',instructions:'Review a frame.',inputs:{},output_schema:{}}},edges:[{source:'writer',target:'reviewer'}],output:{review:{ref:'nodes.reviewer.output'}}}};
 expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
 let connection:any=null,preloads=0;
 await page.route('**/api/models',async route=>{
  if(route.request().method()==='PUT'){
   const body=route.request().postDataJSON();connection={name:body.name,...body.connection};
   return route.fulfill({json:{saved:body.name}});
  }
  return route.fulfill({json:{editable:true,services:['vision-server'],models:connection?[connection]:[]}});
 });
 await page.route('**/api/services/vision-server/warmup',route=>{preloads++;return route.fulfill({json:{ready:true}});});
 await page.goto('/');await page.locator('.project[title="'+id+'"]').click();
 await page.getByText('Model connections',{exact:true}).click();
 await page.getByLabel('Provider preset').selectOption('Local / Custom');
 await page.getByLabel('Connection name',{exact:true}).fill('local-vision');
 await page.getByLabel('Connection model ID').fill('my-vision');
 await page.getByLabel('Model key environment').fill('VISION_API_KEY');
 await page.getByLabel('Connection supports vision').check();
 await page.getByLabel('Connection local service').selectOption('vision-server');
 await page.getByRole('button',{name:'Save connection',exact:true}).click();
 await expect(page.locator('.connection-settings [role="status"]')).toContainText('Connection saved');
 expect(connection.base_url).toBe('http://127.0.0.1:8000/v1');
 expect(connection.api_key_env).toBe('VISION_API_KEY');
 await page.locator('.react-flow__node[data-id="reviewer"]').click();
 await page.getByLabel('Model binding',{exact:true}).selectOption('connection:local-vision');
 await page.getByRole('button',{name:'Preload vision-server',exact:true}).click();
 await expect(page.locator('.agent-settings')).toContainText('Ready · retained across runs');
 expect(preloads).toBe(1);
 await page.getByRole('button',{name:'Save',exact:true}).click();
 await expect(page.locator('.save-state')).toHaveText('Saved');
 const saved=await(await request.get('/api/projects/'+id)).json();
 expect(saved.spec.graph.nodes.writer.model).toBe('main');
 expect(saved.spec.graph.nodes.reviewer.model).toBe('local-vision');
 expect(saved.spec.models['local-vision'].binding).toBe('local-vision');
 await page.reload();await page.locator('.project[title="'+id+'"]').click();
 await page.locator('.react-flow__node[data-id="reviewer"]').click();
 await expect(page.getByLabel('Model binding',{exact:true})).toHaveValue('local-vision');
});
