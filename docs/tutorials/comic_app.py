"""Small browser client for the exported comic HTTP application.

Run serve.py from the export first, then launch this file on the same machine.
Both processes read EVOSPRIG_SERVICE_TOKEN. Models and execution stay in the export.
"""

import argparse
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Comic Studio</title><style>
*{box-sizing:border-box}body{margin:0;background:#f7f7f6;color:#242628;font:16px/1.65 system-ui,sans-serif}main{max-width:1100px;margin:45px auto;padding:0 28px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ddd;padding-bottom:20px}h1{font-size:26px;margin:0}small{color:#707378}button{border:1px solid #ccc;border-radius:8px;background:white;padding:10px 18px;font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:wait}button.primary{background:#242628;color:white;border-color:#242628}section{display:grid;grid-template-columns:360px 1fr;gap:28px;margin-top:30px}article{background:white;border:1px solid #e0e2e4;border-radius:12px;padding:24px}label{font-weight:600;display:block;margin-bottom:12px}textarea{width:100%;min-height:220px;border:1px solid #d1d5da;border-radius:8px;padding:14px;font:15px/1.8 inherit;resize:vertical}#status{white-space:pre-wrap;color:#5b6670;margin:20px 0}#result img{width:100%;margin:12px 0}#result a{margin-right:14px;color:#314c68}#result{min-height:430px}h2{font-size:18px;margin:0 0 12px}#form button{margin-top:16px}@media(max-width:800px){section{grid-template-columns:1fr}}
</style><main><header><div><h1>Comic Studio</h1><small id="subtitle"></small></div><button id="lang">中文 / EN</button></header><section><article><form id="form"><label for="story" id="label"></label><textarea id="story" required maxlength="6000"></textarea><button class="primary" id="create"></button></form><p id="status"></p><small id="reuse"></small></article><article id="result"><h2 id="heading"></h2><p id="empty"></p><div id="media"></div></article></section></main><script>
let zh=new URLSearchParams(location.search).get('lang')==='zh',busy=false;let active;
const $=s=>document.querySelector(s),strings={en:['A story in, a comic page out.','Your story','Make a comic','Your comic','Add a story to begin.','Use the same application again with another story.','Creating your comic…','Comic complete','The run stopped. Check the application log.'],zh:['输入故事，制作一页漫画。','写下你的故事','开始制作','漫画成品','从左侧输入一个故事开始。','换一个故事，继续使用这个应用。','正在制作漫画……','漫画制作完成','任务已停止，请查看应用日志。']};
function language(){const t=strings[zh?'zh':'en'];['subtitle','label','create','heading','empty','reuse'].forEach((id,i)=>$('#'+id).textContent=t[i]);document.documentElement.lang=zh?'zh-CN':'en';}
$('#lang').onclick=()=>{zh=!zh;language();};language();
async function call(path,options){const r=await fetch(path,options);const data=await r.json();if(!r.ok)throw Error(data.detail||'Request failed');return data;}
async function poll(id){const r=await call('/api/runs/'+id);if(id!==active)return;const t=strings[zh?'zh':'en'];$('#status').textContent=r.status==='succeeded'?t[7]:t[6]+'\n'+r.status+' · '+r.completed+' '+(zh?'个步骤已完成':'steps complete');
 if(r.status==='succeeded'){$('#media').replaceChildren();$('#empty').hidden=true;for(const item of r.files){const a=document.createElement('a');a.href=item.url;a.textContent=item.name;a.target='_blank';$('#media').append(a);if(/\.jpe?g$|\.png$/i.test(item.name)){const img=document.createElement('img');img.src=item.url;img.alt=r.title||'Comic page';$('#media').append(img);}}}
 if(['succeeded','failed','canceled'].includes(r.status)){busy=false;$('#create').disabled=false;if(r.status!=='succeeded')$('#status').textContent=t[8]+'\n'+(r.error||'');return;}setTimeout(()=>poll(id).catch(failed),2000);}
function failed(e){busy=false;$('#create').disabled=false;$('#status').textContent=e.message;}
$('#form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;$('#create').disabled=true;$('#status').textContent=strings[zh?'zh':'en'][6];$('#media').replaceChildren();$('#empty').hidden=true;try{const r=await call('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:{story:$('#story').value}})});active=r.run_id;localStorage.setItem('comic.run',active);localStorage.setItem('comic.story',$('#story').value);await poll(active);}catch(e){failed(e);}};
const previous=new URLSearchParams(location.search).get('run')||localStorage.getItem('comic.run');$('#story').value=localStorage.getItem('comic.story')||'';if(previous&&/^[a-f0-9]+$/.test(previous)){active=previous;busy=true;$('#create').disabled=true;poll(active).catch(failed);}
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:18770')
    parser.add_argument('--port', type=int, default=18771)
    parser.add_argument('--workspace', type=Path, default=Path('runtime'))
    args = parser.parse_args()
    token = os.environ.get('EVOSPRIG_SERVICE_TOKEN')
    if not token:
        parser.error('Set EVOSPRIG_SERVICE_TOKEN for the exported HTTP service')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    artifacts = (args.workspace / 'artifacts').resolve()

    def request(path, data=None):
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        raw = None if data is None else json.dumps(data).encode()
        with opener.open(urllib.request.Request(args.api.rstrip('/') + path, data=raw, headers=headers), timeout=30) as response:
            return json.load(response)

    def files(output):
        found = []
        if isinstance(output, dict):
            if isinstance(output.get('directory'), str) and isinstance(output.get('files'), list):
                directory = Path(output['directory']).resolve()
                for name in output['files']:
                    if not isinstance(name, str):
                        continue
                    file = (directory / name).resolve()
                    if file.is_relative_to(artifacts) and file.is_file():
                        relative = file.relative_to(artifacts).as_posix()
                        found.append({'name': file.name, 'url': '/files/' + quote(relative)})
            for value in output.values():
                found.extend(files(value))
        return found

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data, content_type='application/json'):
            payload = json.dumps(data, ensure_ascii=False).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlparse(self.path)
            try:
                if path.path == '/':
                    return self.send(200, PAGE.encode(), 'text/html; charset=utf-8')
                if path.path.startswith('/files/'):
                    relative = unquote(path.path[len('/files/'):])
                    file = (artifacts / relative).resolve()
                    if not file.is_relative_to(artifacts) or file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.pdf', '.html'} or not file.is_file():
                        return self.send(404, {'detail': 'File not found'})
                    return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                if re.fullmatch(r'/api/runs/[a-f0-9]+', path.path):
                    run = request(path.path[4:])
                    count = sum(e.get('kind', e.get('type', '')) in {'node.succeeded', 'node.completed'} for e in run.get('events', []))
                    return self.send(200, {'run_id': run['run_id'], 'status': run['status'], 'completed': count, 'files': files(run.get('output')), 'error': (run.get('error') or {}).get('message')})
                self.send(404, {'detail': 'Not found'})
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
                if length < 1 or length > 50_000:
                    return self.send(413, {'detail': 'Story request is too large'})
                data = json.loads(self.rfile.read(length))
                self.send(202, request('/runs', data))
            except (OSError, ValueError):
                self.send(400, {'detail': 'Check the story and exported service connection'})

    print(f'Comic Studio: http://127.0.0.1:{args.port}/ (中文: /?lang=zh)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
