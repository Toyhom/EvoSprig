"""Optional browser client for the lesson's exported writing service.

Start the exported serve.py first. Both processes use EVOSPRIG_SERVICE_TOKEN.
The exported runtime performs all writing, checking and revision.
"""

import argparse
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Xiaohongshu Studio</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f8fa;color:#252a32;font:16px/1.6 system-ui,sans-serif}main{max-width:1220px;margin:35px auto;padding:0 28px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}h1{font-size:27px;margin:0}h2{font-size:19px;margin:0 0 16px}small,.hint{color:#687484}a{color:inherit}section{background:white;border:1px solid #e1e5e9;border-radius:12px;padding:24px;min-width:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:14px;margin:12px 0 4px}textarea,input,select{width:100%;border:1px solid #ccd3dc;border-radius:6px;padding:9px;font:inherit;background:white;color:inherit}textarea{resize:vertical;min-height:80px}#source{min-height:170px}button{border:1px solid #cbd3dd;border-radius:7px;background:white;padding:9px 18px;font:inherit;cursor:pointer}button.primary{background:#283f56;color:white;border-color:#283f56;margin-top:18px}button:disabled{opacity:.5;cursor:wait}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.85 system-ui,"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;margin:0;max-height:650px;overflow:auto}#status{min-height:28px;margin:14px 0;color:#52647a}details{margin-top:16px}summary{cursor:pointer;font-size:14px}#feedback{color:#805b31}#copy{float:right}#output:empty:before{content:attr(data-placeholder);color:#8993a0}footer{font-size:13px;color:#768190;margin:20px 0}@media(max-width:760px){.grid{grid-template-columns:1fr}main{padding:0 14px}section{padding:18px}header{align-items:start;gap:20px}.row{grid-template-columns:1fr}}
</style><main><header><div><h1>Xiaohongshu Studio</h1><small id="subtitle"></small></div><a id="language"></a></header><div class="grid"><section><h2 id="requestTitle"></h2><form id="form"><label for="source" id="sourceLabel"></label><textarea id="source" required maxlength="12000"></textarea><label for="audience" id="audienceLabel"></label><input id="audience" maxlength="500"><label for="goal" id="goalLabel"></label><textarea id="goal" maxlength="500"></textarea><div class="row"><div><label for="voice" id="voiceLabel"></label><select id="voice"><option value="observer">Observer / 第三方</option><option value="brand">Brand / 品牌</option><option value="personal">Personal / 个人</option></select></div><div><label for="emoji" id="emojiLabel"></label><select id="emoji"><option value="light">Light / 少量</option><option value="lively">Lively / 活泼</option><option value="none">None / 无</option></select></div></div><details id="advanced"><summary id="advancedLabel"></summary><label for="terms" id="termsLabel"></label><input id="terms"><label for="links" id="linksLabel"></label><textarea id="links"></textarea><label for="reference" id="referenceLabel"></label><textarea id="reference" maxlength="2000"></textarea><div class="row"><div><label for="titleLimit" id="titleLimitLabel"></label><input id="titleLimit" type="number" min="10" max="60" value="38"></div><div><label for="bodyLimit" id="bodyLimitLabel"></label><input id="bodyLimit" type="number" min="100" max="1500" value="1100"></div></div></details><button class="primary" id="submit"></button></form></section><section><button id="copy" disabled></button><h2 id="resultTitle"></h2><p id="status" role="status"></p><pre id="output"></pre><p id="feedback"></p></section></div><footer id="footer"></footer></main>
<script>
const zh=new URLSearchParams(location.search).get('lang')==='zh';const $=id=>document.getElementById(id);
const t=zh?{subtitle:'素材 → 写作简报 → 撰稿与审核 → 完整文案',requestTitle:'这次想写什么？',sourceLabel:'原始素材',audienceLabel:'写给谁看',goalLabel:'这篇重点讲什么',voiceLabel:'叙述视角',emojiLabel:'表情风格',advancedLabel:'链接、必含词与参考文风',termsLabel:'必含词（每个用逗号分隔）',linksLabel:'链接（每行一个）',referenceLabel:'参考文风',titleLimitLabel:'标题字数上限',bodyLimitLabel:'正文字数上限',submit:'生成文案',copy:'复制文案',resultTitle:'完成稿',footer:'使用 EvoSprig 导出的独立应用 · 更换素材可再次使用',waiting:'正在整理素材、撰稿与审核…',empty:'完成的标题、正文、链接和标签会显示在这里。',failed:'运行未完成：',done:'完成',review:'已达到修改轮数，请检查反馈',rounds:'轮审核',copied:'已复制'}:{subtitle:'Source → Brief → Draft and review → Finished post',requestTitle:'What are you writing?',sourceLabel:'Source material',audienceLabel:'Audience',goalLabel:'Angle and goal',voiceLabel:'Voice',emojiLabel:'Emoji',advancedLabel:'Links, required terms and reference style',termsLabel:'Required terms (comma separated)',linksLabel:'Links (one per line)',referenceLabel:'Reference style',titleLimitLabel:'Title character limit',bodyLimitLabel:'Body character limit',submit:'Write a post',copy:'Copy post',resultTitle:'Finished post',footer:'An independent application exported from EvoSprig · Reuse it with new material',waiting:'Preparing the brief, drafting and reviewing…',empty:'Your title, body, links and tags appear here.',failed:'Run did not finish: ',done:'Completed',review:'Revision limit reached; check feedback',rounds:'review rounds',copied:'Copied'};
for(const id of ['subtitle','requestTitle','sourceLabel','audienceLabel','goalLabel','voiceLabel','emojiLabel','advancedLabel','termsLabel','linksLabel','referenceLabel','titleLimitLabel','bodyLimitLabel','submit','copy','resultTitle','footer'])$(id).textContent=t[id];document.documentElement.lang=zh?'zh-CN':'en';$('language').textContent=zh?'English':'简体中文';$('language').href=zh?'/':'/?lang=zh';$('output').dataset.placeholder=t.empty;
let postText='';
function show(out){postText=out.text;$('output').replaceChildren();for(const part of postText.split(/(\*\*[^*\n]+\*\*)/g)){if(part.startsWith('**')&&part.endsWith('**')){const b=document.createElement('strong');b.textContent=part.slice(2,-2);$('output').append(b);}else $('output').append(document.createTextNode(part));}$('status').textContent=(out.ready?t.done:t.review)+' · '+out.rounds+' '+t.rounds;$('feedback').textContent=out.ready?'':(out.feedback||[]).join('；');$('copy').disabled=false;}
async function api(path,body){const r=await fetch('/api'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw Error(data.detail||r.status);return data;}
$('form').onsubmit=async e=>{e.preventDefault();$('submit').disabled=true;$('copy').disabled=true;$('copy').textContent=t.copy;$('output').textContent='';$('feedback').textContent='';$('status').textContent=t.waiting;try{const input={source:$('source').value,audience:$('audience').value,goal:$('goal').value,voice:$('voice').value,emoji:$('emoji').value,required_terms:$('terms').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean),links:$('links').value.split('\n').map(x=>x.trim()).filter(Boolean),references:$('reference').value?[$('reference').value]:[],max_title_chars:Number($('titleLimit').value),max_body_chars:Number($('bodyLimit').value)};const receipt=await api('/runs',{input});window.lastRunId=receipt.run_id;let run;do{await new Promise(r=>setTimeout(r,1000));run=await api('/runs/'+receipt.run_id);}while(['running','pending','queued','suspended'].includes(run.status));if(run.status!=='succeeded')throw Error(run.error||run.status);show(run.output);}catch(error){$('status').textContent=t.failed+error.message;}finally{$('submit').disabled=false;}};
$('copy').onclick=async()=>{await navigator.clipboard.writeText(postText);$('copy').textContent=t.copied;};
const saved=new URLSearchParams(location.search).get('run');if(saved&&/^[a-f0-9]{32}$/.test(saved))api('/runs/'+saved).then(r=>{if(r.status==='succeeded')show(r.output);else $('status').textContent=r.status;}).catch(e=>$('status').textContent=e.message);
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:18773')
    parser.add_argument('--port', type=int, default=18774)
    args = parser.parse_args()
    token = os.environ.get('EVOSPRIG_SERVICE_TOKEN')
    if not token:
        parser.error('Set EVOSPRIG_SERVICE_TOKEN to the exported service token')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        with opener.open(urllib.request.Request(args.api.rstrip('/') + path, data=body, headers=headers), timeout=30) as response:
            return json.load(response)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data, content_type='application/json'):
            body = json.dumps(data, ensure_ascii=False).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/':
                return self.send(200, PAGE.encode(), 'text/html; charset=utf-8')
            if not re.fullmatch(r'/api/runs/[a-f0-9]{32}', path):
                return self.send(404, {'detail': 'Not found'})
            try:
                run = request(path[4:])
                self.send(200, {'run_id': run['run_id'], 'status': run['status'], 'output': run.get('output'), 'error': (run.get('error') or {}).get('message')})
            except (OSError, ValueError, KeyError):
                self.send(502, {'detail': 'Could not read the exported application'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{args.port}':
                return self.send(403, {'detail': 'Use the local application page'})
            if self.path != '/api/runs':
                return self.send(404, {'detail': 'Not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 100_000:
                    return self.send(413, {'detail': 'Request is too large'})
                data = json.loads(self.rfile.read(length))
                self.send(202, request('/runs', data))
            except (OSError, ValueError):
                self.send(400, {'detail': 'Check the input and exported service connection'})

    print(f'Xiaohongshu Studio: http://127.0.0.1:{args.port}/ (中文: /?lang=zh)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
