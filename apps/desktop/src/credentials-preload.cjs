const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('keys',{
  list:()=>ipcRenderer.invoke('keys:list'),
  save:(name,value,remove=false)=>ipcRenderer.invoke('keys:save',{name,value,remove}),
});
