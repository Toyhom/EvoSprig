const {test}=require('node:test');
const assert=require('node:assert/strict');
const {mkdtemp,rm}=require('node:fs/promises');
const {join,resolve}=require('node:path');
const {tmpdir}=require('node:os');
const {backendCommand,startBackend,isLocalApi,externalLink}=require('../src/backend.cjs');

test('packaged backend uses native executables without a shell',()=>{
 assert.equal(backendCommand({packaged:true,resources:'/app',platform:'win32'})[0],join('/app','backend','evosprig-backend.exe'));
 assert.equal(backendCommand({packaged:true,resources:'/app',platform:'darwin'})[0],join('/app','backend','evosprig-backend'));
 assert.deepEqual(backendCommand({packaged:false,root:'/checkout',python:'/custom/python'})[1],['-u',join('/checkout','backend.py')]);
});
test('credentials and external links stay within their intended destinations',()=>{
 const origin='http://127.0.0.1:4321';
 assert.ok(isLocalApi(origin+'/api/models',origin));
 for(const url of ['http://127.0.0.1:4322/api/models','https://example.com/api/models',origin+'/assets/icon.svg',origin+'.example.com/api/a'])assert.ok(!isLocalApi(url,origin));
 assert.ok(externalLink('https://github.com/Toyhom/EvoSprig'));
 for(const url of ['file:///etc/passwd','javascript:alert(1)','http://localhost:8765','http://[::1]:42','evosprig://run'])assert.ok(!externalLink(url));
});
test('desktop backend binds an ephemeral port, authenticates, persists and stops with its parent',{timeout:45000},async()=>{
 const workspace=await mkdtemp(join(tmpdir(),'evosprig-desktop-'));
 const root=resolve(__dirname,'..');let backend;
 try{
  const options={root,workspace,studio:resolve(root,'../studio/dist'),python:process.env.EVOSPRIG_PYTHON,executable:process.env.EVOSPRIG_BACKEND_EXECUTABLE};
  backend=startBackend(options);const origin=await backend.ready;
  assert.notEqual(new URL(origin).port,'8765');
  assert.equal((await fetch(origin+'/api/health')).status,401);
  const headers={Authorization:'Bearer '+backend.token,'Content-Type':'application/json'};
  assert.equal((await fetch(origin+'/api/health',{headers})).status,200);
  assert.equal((await fetch(origin+'/api/models',{headers})).status,200);
  const spec={id:'desktop-test',spec_version:'0.3',input_schema:{type:'object'},output_schema:{},models:{},tools:{},resources:{},graph:{entry:'echo',nodes:{echo:{type:'transform',inputs:{message:{value:'desktop ready'}},output_schema:{type:'object'}}},edges:[],output:{result:{ref:'nodes.echo.output'}}}};
  const create=await fetch(origin+'/api/projects',{method:'POST',headers,body:JSON.stringify({spec})});assert.equal(create.status,201,await create.text());
  // Export requires Python module sources and lock files inside the frozen bundle.
  const exported=await fetch(origin+'/api/projects/desktop-test/export?target=http',{method:'POST',headers});assert.equal(exported.status,200,exported.status===200?'':await exported.text());assert.ok((await exported.arrayBuffer()).byteLength>1000);
  await backend.stop();assert.notEqual(backend.child.exitCode,null);
  backend=startBackend(options);const next=await backend.ready;
  const project=await fetch(next+'/api/projects/desktop-test',{headers:{Authorization:'Bearer '+backend.token}});assert.equal(project.status,200);
 }finally{await backend?.stop();await rm(workspace,{recursive:true,force:true});}
});
