import {test,expect} from '@playwright/test';

test('accept the displayed take without copying its JSON',async({page,request})=>{
  const id='review-take-'+Date.now();
  const take={title:'The cottage window',duration:12};
  const schema={type:'object',properties:{take:{type:'object'}},required:['take'],additionalProperties:false};
  const spec={id,spec_version:'0.3',input_schema:{type:'object'},output_schema:schema,models:{},tools:{},resources:{},graph:{entry:'review',nodes:{review:{type:'human',inputs:{take:{value:take},feedback:{value:'Check the character at the window.'}},output_schema:schema}},edges:[],output:{take:{ref:'nodes.review.output.take'}}}};
  expect((await request.post('/api/projects',{data:{spec}})).status()).toBe(201);
  await page.goto('/');await page.locator(`.project[title="${id}"]`).click();
  await page.getByRole('button',{name:'▷ Run',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('waiting_input');
  const response=page.waitForResponse(r=>r.url().endsWith('/input')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Use shown result and continue',exact:true}).click();
  const reply=await response;
  expect(reply.request().postDataJSON().response).toEqual({take});
  await expect(page.getByRole('status')).toContainText('succeeded');
});
