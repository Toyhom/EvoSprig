"""Optional classroom client. The exported HTTP service owns retrieval and generation."""
import argparse
import os
import re
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response


def create_client(endpoint, token):
    app = FastAPI()

    @app.get('/')
    async def index():
        return HTMLResponse(Path(__file__).with_name('customer.html').read_text())

    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'DELETE'])
    async def proxy(path: str, request: Request):
        if request.headers.get('origin') not in {None, str(request.base_url).rstrip('/')}:
            return JSONResponse({'detail': 'same-origin request required'}, status_code=403)
        if not re.fullmatch(r'documents(?:/(?:upload|jobs(?:/[a-f0-9]{32})?|[a-f0-9]{32,64}))?|runs(?:/[a-f0-9]{32})?', path):
            return JSONResponse({'detail': 'unknown route'}, status_code=404)
        headers = {'Authorization': 'Bearer ' + token,
                   'Content-Type': request.headers.get('content-type', 'application/json')}
        try:
            async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
                result = await client.request(request.method, endpoint.rstrip('/')+'/'+path,
                    params=request.query_params, headers=headers, content=request.stream())
            return Response(result.content, status_code=result.status_code,
                            media_type=result.headers.get('content-type', 'application/json'))
        except httpx.HTTPError:
            return JSONResponse({'detail': 'service unavailable'}, status_code=502)
    return app


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--endpoint', default='http://127.0.0.1:18778')
    p.add_argument('--port', type=int, default=18779)
    a = p.parse_args()
    uvicorn.run(create_client(a.endpoint, os.environ['EVOSPRIG_SERVICE_TOKEN']), host='127.0.0.1', port=a.port)
