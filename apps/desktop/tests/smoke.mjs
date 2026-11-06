import {_electron as electron,expect} from 'playwright/test';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
const data=await mkdtemp(join(tmpdir(),'evosprig-desktop-ui-'));
let app;
try{
 const env={...process.env,EVOSPRIG_DESKTOP_DATA:data};delete env.ELECTRON_RUN_AS_NODE;
 app=await electron.launch({...(process.env.EVOSPRIG_DESKTOP_EXECUTABLE?{executablePath:process.env.EVOSPRIG_DESKTOP_EXECUTABLE}:{}),args:['--disable-gpu',...(process.env.EVOSPRIG_DESKTOP_EXECUTABLE?[]:[resolve('.')]),...(process.env.EVOSPRIG_ELECTRON_NO_SANDBOX==='1'?['--no-sandbox']:[])],env,timeout:60000});
 const page=await app.firstWindow();await page.waitForURL('http://127.0.0.1:**',{timeout:90000});
 await expect(page.getByRole('button',{name:'＋ New project'})).toBeVisible();
 await page.getByLabel('New project name').fill('desktop-smoke');await page.getByRole('button',{name:'＋ New project'}).click();
 await expect(page.locator('h1')).toHaveText('desktop-smoke');
 await page.getByRole('button',{name:'▷ Run',exact:true}).click();await expect(page.locator('.results-heading .status-succeeded')).toBeVisible({timeout:30000});
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export Python ↗'}).click();const file=await download;expect(file.suggestedFilename()).toBe('desktop-smoke.zip');await file.saveAs(join(data,'project.zip'));
 // Native key settings are isolated from the main renderer.
 const keyWindow=app.waitForEvent('window');
 await app.evaluate(({Menu})=>Menu.getApplicationMenu().items.find(item=>item.label==='File').submenu.items.find(item=>item.label==='API keys…').click());
 const keyPage=await keyWindow;await expect(keyPage.locator('#name')).toBeVisible();
 await keyPage.locator('#name').fill('MODEL_API_KEY');await keyPage.locator('#value').fill('desktop-test-placeholder');await keyPage.locator('#save').click();await expect(keyPage.locator('#message')).toContainText('Saved');
 await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('credentials.html')).close());
 const newWindow=app.waitForEvent('window');
 await app.evaluate(({Menu})=>Menu.getApplicationMenu().items.find(item=>item.label==='File').submenu.items.find(item=>item.label==='Restart local backend').click());
 const reopened=await newWindow;await reopened.waitForURL('http://127.0.0.1:**',{timeout:90000});
 await expect(reopened.locator('h1')).toHaveText('desktop-smoke');
 if(process.env.EVOSPRIG_DESKTOP_SCREENSHOT)await reopened.screenshot({path:process.env.EVOSPRIG_DESKTOP_SCREENSHOT});
 await app.close();app=null;
 console.log('Desktop create → run → export and API-key dialog passed.');
}finally{if(app)await app.close();await rm(data,{recursive:true,force:true});}
