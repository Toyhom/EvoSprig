const $=id=>document.getElementById(id);
let lang=localStorage.getItem('episode-language')||'en',runId=null,timer=null,after=0,starting=false,hasRun=false,activeStatus=null,steps=new Map();
const say=(en,zh)=>lang==='zh'?zh:en;
const statusNames={queued:['In queue','等待制作'],running:['Making your film','制作中'],waiting_external:['Making your film','制作中'],waiting_input:['Needs your review','等待审核'],succeeded:['Film ready','制作完成'],failed:['Production stopped','制作中断'],canceled:['Canceled','已取消']};
const statusLabel=status=>statusNames[status]?.[lang==='zh'?1:0]||status;
function translate(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-en]').forEach(el=>el.textContent=el.dataset[lang]);$('language').textContent=lang==='zh'?'English':'中文';$('story').placeholder=say('A lighthouse keeper discovers that the stars have been sending letters to the sea…','灯塔守夜人发现，星星一直在给大海写信……');if(activeStatus)$('state').textContent=statusLabel(activeStatus);}
$('language').onclick=()=>{lang=lang==='en'?'zh':'en';localStorage.setItem('episode-language',lang);translate();progress([]);refreshHistory();};translate();
document.querySelectorAll('[data-idea]').forEach(button=>button.onclick=()=>{$('story').value=button.dataset.idea;$('story').focus();});
async function api(path,init={}){const response=await fetch('/api'+path,{...init,headers:{'Content-Type':'application/json',...($('token').value?{Authorization:'Bearer '+$('token').value}:{})}});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;}
const previews=new ProductionPreview(api,()=>$('token').value,say);
let reviewKey='';
async function showReviews(run,current){
  const waiting=run.status==='waiting_input'?(run.waiting||[]).filter(item=>item.input?.frame||item.input?.take):[];
  const key=JSON.stringify([current,lang,waiting]);
  if(key===reviewKey)return;
  reviewKey=key;$('review-items').replaceChildren();
  for(const item of waiting){
    const take=item.input.take,asset=take?.clip||item.input.frame;
    if(!asset?.uri)continue;
    const card=document.createElement('div'),caption=document.createElement('p'),button=document.createElement('button');
    caption.textContent=item.input.feedback||say('Review this result before continuing.','确认这个结果后继续制作。');
    const media=document.createElement(take?'video':'img');
    media.style.width='100%';
    if(take){media.controls=true;media.playsInline=true;media.preload='metadata';}
    else media.alt=say('Reference to review','待审核的参考图');
    button.textContent=say('Use this result and continue','采用这个结果，继续制作');
    button.onclick=async()=>{
      if(runId!==current)return;button.disabled=true;
      try{await api('/runs/'+current+'/input',{method:'POST',body:JSON.stringify({path:item.path,response:take?{take}:{frame:asset}})});
        if(runId===current){card.remove();reviewKey='';}
      }catch(error){if(runId===current){$('error').textContent=error.message;button.disabled=false;}}
    };
    card.append(media,caption,button);$('review-items').append(card);
    try{const url=await previews.media(asset,previews.generation);if(runId===current&&key===reviewKey&&url)media.src=url;}
    catch{if(runId===current)caption.textContent+=say(' Preview unavailable; open the canvas to inspect it.',' 暂时无法预览，可打开画布查看。');}
  }
}
const roles={creative_director:['Creative direction','创意导演'],source_reader:['Reading the story','解读原文'],producer:['Writing the screenplay','编写剧本'],script_editor:['Editing the script','审校剧本'],art_director:['Designing the cast','角色设计'],voice_director:['Casting the voices','配音选角'],voice_library:['Recording voice references','生成音色参考'],reference_library:['Drawing character references','绘制角色参考'],shot_director:['Directing the shot','镜头导演'],generate:['Drawing the first frame','绘制首帧'],render:['Rendering the shot','生成视频'],continuity_review:['Reviewing the take','检查镜头衔接'],assemble:['Editing the film','合成影片']};
function progress(events){for(const e of events){const path=e.node_id||e.data?.path;if(!path||!e.type.startsWith('node.'))continue;const key=path.split('/').at(-1);if(!roles[key])continue;steps.set(path,{role:key,done:e.type==='node.completed'||e.type==='node.succeeded',failed:e.type==='node.failed'});}const fragment=document.createDocumentFragment();for(const item of [...steps.values()].slice(-12)){const line=document.createElement('div');line.className='step';const mark=document.createElement('span');mark.textContent=item.failed?'!':item.done?'✓':'◌';line.append(mark,document.createTextNode(roles[item.role][lang==='zh'?1:0]));fragment.append(line);}$('progress').replaceChildren(fragment);}
async function poll(){
  if(!runId)return;
  const current=runId;
  $('history').disabled=true;
  try{
    const run=await api('/runs/'+current+'?after='+after);
    if(runId!==current)return;
    for(const event of run.events)after=Math.max(after,event.sequence||0);
    progress(run.events);
    await previews.update(current,run.events,run.output?.plan||run.input?.upstream?.script_editor);
    if(runId!==current)return;
    activeStatus=run.status;$('state').textContent=statusLabel(run.status);
    $('review').hidden=run.status!=='waiting_input';
    await showReviews(run,current);
    if(runId!==current)return;
    if(['queued','running','waiting_external','waiting_input'].includes(run.status)){
      timer=setTimeout(poll,1200);return;
    }
    $('cancel').hidden=true;
    const film=run.output?.film||run.output?.assemble;
    if(film?.uri){
      const url=await previews.media(film,previews.generation);
      if(runId!==current||!url)return;
      $('film').src=url;$('film').hidden=false;$('empty').hidden=true;
    }
    if(run.error)$('error').textContent=run.error.message||JSON.stringify(run.error);
    sessionStorage.removeItem('episode-run');runId=null;$('create').disabled=false;$('history').disabled=false;refreshHistory();
  }catch(e){
    if(runId===current){$('error').textContent=e.message;timer=setTimeout(poll,4000);}
  }
}
$('create').onclick=async()=>{if(starting||runId||!$('story').value.trim())return;starting=true;$('create').disabled=true;$('error').textContent='';try{const project=await api('/projects/episode-studio');const input={source_text:$('story').value.trim()};if($('style').value.trim())input.style=$('style').value.trim();if($('spoken').value.trim())input.language=$('spoken').value.trim();if($('seconds').value)input.target_seconds=Number($('seconds').value);const run=await api('/projects/episode-studio/runs',{method:'POST',body:JSON.stringify({revision:project.revision,input,mock:false,allow_writes:true})});runId=run.run_id;hasRun=true;sessionStorage.setItem('episode-run',runId);after=0;steps.clear();previews.reset();$('cancel').hidden=false;$('film').hidden=true;$('sample-label').hidden=true;$('empty').hidden=false;$('empty').querySelector('p').textContent=say('The team is working on your story.','制作团队正在处理你的故事。');await poll();}catch(e){$('error').textContent=e.message;$('create').disabled=false;}finally{starting=false;}};
$('cancel').onclick=async()=>{if(!runId)return;try{await api('/runs/'+runId+'/cancel',{method:'POST'});}catch(e){$('error').textContent=e.message;}};
if(sessionStorage.getItem('episode-run')){runId=sessionStorage.getItem('episode-run');hasRun=true;$('create').disabled=true;$('cancel').hidden=false;poll();}
window.addEventListener('beforeunload',()=>clearTimeout(timer));

async function readiness(){if(runId||starting){setTimeout(readiness,5000);return;}try{const status=await api('/episode/services');if(runId||starting)return;$('create').disabled=!status.ready;if(!hasRun)$('state').textContent=status.ready?say('Ready when you are','等待开拍'):say('Preparing local services…','正在准备本地服务……');}catch(e){if(!runId&&!starting){$('create').disabled=true;if(!hasRun)$('state').textContent=say('Connect your local services','连接本地服务');}}finally{setTimeout(readiness,5000);}}readiness();

async function refreshHistory(){
  try{
    const records=await api('/projects/episode-studio/runs?summary=true');
    const selected=$('history').value;
    $('history').replaceChildren(new Option(say('Choose a production','选择一项制作'),''));
    for(const record of records){
      const date=new Date(record.created_at*1000).toLocaleDateString(lang==='zh'?'zh-CN':'en');
      $('history').append(new Option(`${record.title||date} · ${statusLabel(record.status)}`,record.run_id));
    }
    $('history').value=selected;
  }catch{/* A saved token can be entered in Connection before refreshing history. */}
}
$('token').addEventListener('change',refreshHistory);
$('history').onchange=()=>{
  if(runId||starting||!$('history').value)return;
  runId=$('history').value;hasRun=true;after=0;steps.clear();previews.reset();
  $('create').disabled=true;$('film').hidden=true;$('sample-label').hidden=true;$('empty').hidden=false;
  $('cancel').hidden=false;$('error').textContent='';sessionStorage.setItem('episode-run',runId);poll();
};
refreshHistory();
