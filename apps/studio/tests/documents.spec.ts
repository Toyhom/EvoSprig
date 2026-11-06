import {test,expect} from '@playwright/test';
test('knowledge library accepts customer uploads and carries developer configuration in exports',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('evosprig.language','zh'));
 await page.goto('/');await page.getByLabel('New project name').fill('knowledge-'+Date.now());await page.getByRole('button',{name:'＋ 新建项目'}).click();await expect(page.locator('.editor')).toHaveAttribute('aria-busy','false');
 await page.getByRole('button',{name:'知识库',exact:true}).click();await page.getByRole('button',{name:'导入与部署设置',exact:true}).click();
 await page.getByLabel('Chunk size',{exact:true}).fill('800');await page.getByLabel('Chunk overlap',{exact:true}).fill('100');await page.getByLabel('max_file_bytes').fill('');await page.getByLabel('Enable customer uploads').check();await page.getByRole('button',{name:'保存知识库设置'}).click();await expect(page.getByText('知识库配置已保存',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'资料',exact:true}).click();await page.getByLabel('Upload knowledge files').setInputFiles({name:'warranty.txt',mimeType:'text/plain',buffer:Buffer.from('Warranty lasts one year.')});await expect(page.locator('.knowledge-sources article')).toContainText('warranty');
 await page.getByLabel('Upload knowledge files').setInputFiles({name:'warranty.txt',mimeType:'text/plain',buffer:Buffer.from('Warranty lasts three years.')});await page.getByRole('button',{name:'检索测试',exact:true}).click();await page.getByLabel('Document query').fill('three');await expect.poll(async()=>{await page.getByRole('button',{name:'检索',exact:true}).click();return page.locator('blockquote').allTextContents();}).toEqual([expect.stringContaining('three years')]);
 await page.getByRole('button',{name:'导入与部署设置',exact:true}).click();await expect(page.getByLabel('Enable customer uploads')).toBeChecked();await expect(page.getByLabel('max_file_bytes')).toHaveValue('');
 await page.setViewportSize({width:900,height:900});await page.getByRole('button',{name:'保存知识库设置'}).scrollIntoViewIfNeeded();await expect(page.getByRole('button',{name:'保存知识库设置'})).toBeInViewport();
});

test('citation validation on a model upgrades older graph specs when saved',async({page,request})=>{
 const id='rag-check-'+Date.now();
 const spec={id,spec_version:'0.2',input_schema:{type:'object'},output_schema:{},models:{main:{binding:'main',requires:['text']}},tools:{},resources:{check:{path:'code/check.py',role:'code'}},graph:{entry:'answer',nodes:{answer:{type:'model',model:'main',instructions:'Answer with citations.',output_schema:{}}},edges:[],output:{answer:{ref:'nodes.answer.output.text'}}}};
 expect((await request.post('/api/projects',{data:{spec,resources:{check:'def run(inputs):\n    return {"valid": True, "feedback": ""}\n'}}})).status()).toBe(201);
 await page.goto('/');await page.locator('.project[title="'+id+'"]').click();await expect(page.locator('.editor')).toHaveAttribute('aria-busy','false');await page.locator('.react-flow__node[data-id="answer"]').click();await page.getByRole('button',{name:'Runtime',exact:true}).click();await page.getByLabel('Output validator',{exact:true}).selectOption('check');await page.getByLabel('Output error policy').selectOption('feedback');await page.getByLabel('Output repair attempts').fill('2');await page.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved');
 const result=await(await request.get('/api/projects/'+id)).json();expect(result.spec.spec_version).toBe('0.3');expect(result.spec.graph.nodes.answer.output_validator).toBe('check');expect(result.spec.graph.nodes.answer.max_output_retries).toBe(2);
});
