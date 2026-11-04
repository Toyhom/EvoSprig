import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

test('episode input stays minimal and a reviewed run continues in the same page', async ({page}) => {
  const web=resolve('../episode-studio/web');
  await page.route('**/episode/**', route=>{
    const name=new URL(route.request().url()).pathname.split('/').pop()||'index.html';
    return route.fulfill({body:readFileSync(resolve(web,name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
  });
  let state='waiting_input',polls=0,posts=0,reviews=0;
  const reference = 'a'.repeat(32)+'.png', clip = 'b'.repeat(32)+'.mp4';
  await page.route('**/api/runs/episode-test/nodes/**', route=>{
    const path=new URL(route.request().url()).pathname;
    const asset={uri:'http://localhost:18880/files/'+reference,media_type:'image/png'};
    const output=path.endsWith('/script_editor')?{title:'The last seed',logline:'A robot grows a flower.',shots:[{id:'one',duration_seconds:12,action:'The robot waters a seed.'}]}:
      path.endsWith('/selected_take')?{clip:{uri:'http://localhost:18880/files/'+clip,media_type:'video/mp4'},frame:asset,shot:{action:'The flower opens.'}}:asset;
    return route.fulfill({json:{status:'succeeded',output}});
  });
  await page.route('**/api/episode/services',route=>route.fulfill({json:{ready:true,services:[]}}));
  await page.route('**/api/projects/episode-studio',route=>route.fulfill({json:{revision:1}}));
  await page.route('**/api/projects/episode-studio/runs?summary=true',route=>route.fulfill({json:[
    {run_id:'episode-test',title:'The last seed',status:state,created_at:1793754000},
  ]}));
  await page.route('**/api/projects/episode-studio/runs',async route=>{
    expect(route.request().postDataJSON().input).toEqual({source_text:'A robot grows a flower.'});
    posts++;await route.fulfill({json:{run_id:'episode-test'}});
  });
  await page.route('**/api/runs/episode-test/input',async route=>{
    expect(route.request().postDataJSON()).toEqual({path:'graph/reference_library/item-0/needs_review',response:{
      frame:{uri:'http://localhost:18880/files/'+reference,media_type:'image/png'},
    }});
    reviews++;state='succeeded';await route.fulfill({json:{run_id:'episode-test',status:'queued'}});
  });
  await page.route('**/api/runs/episode-test?*', route=>{
    polls++;return route.fulfill({json:{status:state,events:[
      {sequence:1,type:'node.completed',node_id:'graph/script_editor'},
      {sequence:2,type:'node.completed',node_id:'graph/reference_library/item-0/selected_reference'},
      {sequence:3,type:'node.completed',node_id:'graph/shots/item-0/selected_take'},
    ],waiting:state==='waiting_input'?[{path:'graph/reference_library/item-0/needs_review',input:{
      frame:{uri:'http://localhost:18880/files/'+reference,media_type:'image/png'},feedback:'Check the empty room.'}}]:[],
    input:{upstream:{script_editor:{title:'The last seed',logline:'A robot grows a flower.',shots:[]}}},
    output:state==='succeeded'?{assemble:{uri:'http://localhost:18880/files/'+clip,media_type:'video/mp4'}}:null,error:null}});
  });
  await page.goto('/episode/');
  await page.getByLabel('The starting point',{exact:true}).fill('A robot grows a flower.');
  await expect(page.getByRole('button',{name:'Make this film ↗',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Make this film ↗',exact:true}).click();
  await expect(page.locator('#review')).toBeVisible();
  await expect(page.locator('#storyboard summary')).toHaveText('The last seed');
  await expect(page.locator('#cast-assets img')).toHaveAttribute('src','/episode-media/'+reference);
  await expect(page.locator('#shot-assets video')).toHaveAttribute('src','/episode-media/'+clip);
  await expect(page.locator('#shot-assets figcaption')).toHaveText('1 · The flower opens.');
  await expect(page.getByRole('button',{name:'Make this film ↗',exact:true})).toBeDisabled();
  expect(await page.evaluate(()=>sessionStorage.getItem('episode-run'))).toBe('episode-test');
  await expect(page.locator('#review-items')).toContainText('Check the empty room.');
  await page.getByRole('button',{name:'Use this result and continue',exact:true}).click();
  await expect(page.locator('#state')).toHaveText('Film ready');
  await expect(page.locator('#review')).toBeHidden();
  await expect(page.locator('#film')).toHaveAttribute('src','/episode-media/'+clip);
  expect(await page.evaluate(()=>sessionStorage.getItem('episode-run'))).toBe(null);
  expect(posts).toBe(1);
  expect(reviews).toBe(1);
  expect(polls).toBeGreaterThan(1);
  await expect(page.locator('#cast-assets figure')).toHaveCount(1);
  await page.getByLabel('Your productions').selectOption('episode-test');
  await expect(page.locator('#history')).toBeEnabled();
  await expect(page.locator('#shot-assets video')).toHaveCount(1);
  expect(posts).toBe(1);
  await page.getByRole('button',{name:'中文',exact:true}).click();
  await expect(page.getByRole('heading',{name:'今天，想讲一个什么故事？',exact:true})).toBeVisible();
  await expect(page.locator('#state')).toHaveText('制作完成');
});
