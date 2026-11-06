const {app,BrowserWindow,Menu,dialog,shell,session,ipcMain,safeStorage}=require('electron');
const {join,resolve}=require('node:path');
const fs=require('node:fs');
const {startBackend,isLocalApi,externalLink}=require('./backend.cjs');

if(process.env.EVOSPRIG_DESKTOP_DATA)app.setPath('userData',resolve(process.env.EVOSPRIG_DESKTOP_DATA));
const data=app.getPath('userData');
const settingsFile=join(data,'desktop.json');
let settings={};try{settings=JSON.parse(fs.readFileSync(settingsFile,'utf8'));}catch{}
let workspace=process.env.EVOSPRIG_DESKTOP_WORKSPACE||settings.workspace||join(data,'workspace');
let window,keysWindow,backend,quitting=false,restarting=false,exiting=false,started=false;
let credentials={};
const credentialFile=join(data,'credentials.enc');
const root=resolve(__dirname,'..');
const logs=join(data,'logs');
function saveSettings(){fs.mkdirSync(data,{recursive:true});fs.writeFileSync(settingsFile,JSON.stringify({...settings,workspace}),{mode:0o600});}
function secureStorage(){return safeStorage.isEncryptionAvailable()&&(process.platform!=='linux'||safeStorage.getSelectedStorageBackend()!=='basic_text');}
function saveCredentials(){
  if(!secureStorage())return false;
  const tmp=credentialFile+'.tmp';fs.writeFileSync(tmp,safeStorage.encryptString(JSON.stringify(credentials)),{mode:0o600});fs.renameSync(tmp,credentialFile);return true;
}
function translated(en,zh){return app.getLocale().startsWith('zh')?zh:en;}
function allowedKeySender(event){if(!keysWindow||event.sender!==keysWindow.webContents||event.senderFrame!==keysWindow.webContents.mainFrame)throw Error('Unknown settings window');}
function keysDialog(){
  if(keysWindow){keysWindow.focus();return;}
  keysWindow=new BrowserWindow({width:540,height:540,minWidth:440,minHeight:440,parent:window,modal:true,title:translated('API keys','API 密钥'),autoHideMenuBar:true,
    webPreferences:{preload:join(__dirname,'credentials-preload.cjs'),sandbox:true,contextIsolation:true,nodeIntegration:false}});
  keysWindow.webContents.setWindowOpenHandler(()=>({action:'deny'}));keysWindow.webContents.on('will-navigate',e=>e.preventDefault());
  keysWindow.loadFile(join(__dirname,'credentials.html'));keysWindow.on('closed',()=>{keysWindow=null;});
}
function menu(){
  const t=translated;
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform==='darwin'?[{role:'appMenu'}]:[]),
    {label:t('File','文件'),submenu:[
      {label:t('Open workspace…','打开工作区…'),click:async()=>{const result=await dialog.showOpenDialog(window,{properties:['openDirectory','createDirectory']});if(!result.canceled)await restart(result.filePaths[0]);}},
      {label:t('Show workspace folder','打开工作区文件夹'),click:()=>shell.openPath(workspace)},
      {type:'separator'},{label:t('API keys…','API 密钥…'),click:keysDialog},
      {label:t('Open deployment settings','打开部署配置'),click:()=>shell.openPath(join(workspace,'deployment.yaml'))},
      {label:t('Restart local backend','重启本地后端'),click:()=>restart()},
      {type:'separator'},{role:process.platform==='darwin'?'close':'quit'},
    ]},
    {role:'editMenu'},
    {role:'viewMenu'},
    {role:'windowMenu'},
    {role:'help',submenu:[
      {label:t('Tutorials','教程'),click:()=>shell.openExternal('https://github.com/Toyhom/EvoSprig/tree/main/docs/tutorials')},
      {label:t('Open logs','打开日志'),click:()=>shell.openPath(logs)},
      {label:t('Desktop downloads','客户端下载'),click:()=>shell.openExternal('https://github.com/Toyhom/EvoSprig/actions/workflows/desktop.yml')},
    ]},
  ]));
}
function closeWindow(current){
  if(!current||current.isDestroyed())return Promise.resolve(true);
  return new Promise(resolve=>{
    const cleanup=()=>{current.removeListener('closed',closed);current.removeListener('evosprig-close-cancelled',cancelled);};
    const closed=()=>{cleanup();resolve(true);};const cancelled=()=>{cleanup();resolve(false);};
    current.once('closed',closed);current.once('evosprig-close-cancelled',cancelled);current.close();
  });
}
async function restart(nextWorkspace=workspace){
  if(restarting)return;
  restarting=true;
  try{
    if(!await closeWindow(window))return;
    await backend?.stop();workspace=nextWorkspace;saveSettings();await launch();
  }finally{restarting=false;}
}
async function launch(){
  started=false;fs.mkdirSync(logs,{recursive:true});saveSettings();
  const logFile=join(logs,'backend.log');
  if(fs.existsSync(logFile)&&fs.statSync(logFile).size>2_000_000)fs.renameSync(logFile,logFile+'.previous');
  const log=fs.createWriteStream(logFile,{flags:'a',mode:0o600});
  backend=startBackend({workspace,credentials,packaged:app.isPackaged,resources:process.resourcesPath,root,python:process.env.EVOSPRIG_PYTHON,
    studio:app.isPackaged?join(process.resourcesPath,'studio'):resolve(root,'../studio/dist'),onLog:line=>log.write(line)});
  const owned=backend;
  owned.child.on('exit',()=>{log.end();if(started&&!quitting&&!restarting&&owned===backend){dialog.showErrorBox(translated('Local backend stopped','本地后端已停止'),translated('Open File → Restart local backend to reconnect. Your workspace is saved on disk.','可从“文件 → 重启本地后端”重新连接。工作区保存在本地。'));}});
  const studioSession=session.fromPartition('persist:evosprig-studio');
  studioSession.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  studioSession.setPermissionCheckHandler(()=>false);
  window=new BrowserWindow({width:settings.width||1440,height:settings.height||960,minWidth:900,minHeight:600,title:'EvoSprig Studio',icon:join(root,'assets/icon.png'),backgroundColor:'#f7f7f8',show:false,autoHideMenuBar:false,
    webPreferences:{session:studioSession,sandbox:true,contextIsolation:true,nodeIntegration:false,spellcheck:false}});
  const current=window;
  current.webContents.setWindowOpenHandler(({url})=>{if(externalLink(url))void shell.openExternal(url);return {action:'deny'};});
  current.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==owned.origin){event.preventDefault();if(externalLink(url))void shell.openExternal(url);}});
  current.webContents.on('will-prevent-unload',event=>{
    const choice=dialog.showMessageBoxSync(current,{type:'question',buttons:[translated('Keep editing','继续编辑'),translated('Discard changes','放弃修改')],defaultId:0,cancelId:0,message:translated('This project has unsaved changes.','这个项目有未保存的修改。')});
    if(choice===1)event.preventDefault();else current.emit('evosprig-close-cancelled');
  });
  current.on('close',()=>{if(!current.isMaximized()){const [width,height]=current.getSize();settings={...settings,width,height};saveSettings();}});
  current.on('closed',()=>{if(window===current)window=null;});
  menu();
  await current.loadFile(join(__dirname,'loading.html'));current.show();
  try{
    const origin=await owned.ready;
    // The auth token stays in the main process, scoped to this backend's API.
    studioSession.webRequest.onBeforeSendHeaders({urls:[origin+'/*']},(details,callback)=>{
      const headers={...details.requestHeaders};if(isLocalApi(details.url,origin))headers.Authorization='Bearer '+owned.token;
      callback({requestHeaders:headers});
    });
    if(!current.isDestroyed()){await current.loadURL(origin);started=true;}
  }catch(error){
    if(!quitting){dialog.showErrorBox(translated('Could not start EvoSprig','无法启动 EvoSprig'),error.message+'\n'+logFile);}
    await owned.stop();
  }
}
if(!app.requestSingleInstanceLock()){app.quit();}else{
  app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.show();window.focus();}});
  app.whenReady().then(async()=>{
    if(secureStorage()&&fs.existsSync(credentialFile)){
      try{credentials=JSON.parse(safeStorage.decryptString(fs.readFileSync(credentialFile)));}
      catch{dialog.showErrorBox(translated('API keys could not be unlocked','无法解锁 API 密钥'),translated('Re-enter your keys in File → API keys.','请在“文件 → API 密钥”中重新输入。'));}
    }
    ipcMain.handle('keys:list',event=>{allowedKeySender(event);return {names:Object.keys(credentials),persistent:secureStorage(),zh:app.getLocale().startsWith('zh')};});
    ipcMain.handle('keys:save',(event,{name,value,remove=false})=>{
      allowedKeySender(event);
      if(typeof name!=='string'||! /^[A-Z][A-Z0-9_]{0,90}_(?:KEY|TOKEN)$/.test(name)||name.startsWith('EVOSPRIG_'))throw Error('Use a provider variable such as MODEL_API_KEY.');
      if(!remove&&(typeof value!=='string'||!value.trim()||value.length>16384))throw Error('Enter an API key.');
      if(remove)delete credentials[name];else credentials[name]=value.trim();
      return {names:Object.keys(credentials),persistent:saveCredentials()};
    });
    await launch();
    app.on('activate',()=>{if(!window&&!restarting)void restart();});
  }).catch(error=>{dialog.showErrorBox('EvoSprig Studio',error.message);app.quit();});
  app.on('window-all-closed',()=>{if(process.platform!=='darwin'&&!restarting&&!exiting&&!quitting)app.quit();});
  app.on('before-quit',event=>{
    if(quitting)return;
    event.preventDefault();if(exiting)return;exiting=true;
    void (async()=>{
      if(!await closeWindow(window)){exiting=false;return;}
      quitting=true;await backend?.stop();app.quit();
    })();
  });
}
