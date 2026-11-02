"""Bind an unmodified VideoClaw backend to the same local media tools.

Call install() after adding VideoClaw's backend directory to sys.path. Only
provider entry points are adapted; its agents, prompts and workflow stay intact.
"""

import base64
import io
import json
import os
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image


class LocalProviders:
    def __init__(self, media_url="http://127.0.0.1:18880", model_url="https://api.moonshot.cn/v1",
                 key_env="MOONSHOT_API_KEY", model="kimi-k3.1-pro", max_images=16, max_videos=6):
        self.media_url, self.model_url = media_url.rstrip("/"), model_url.rstrip("/")
        self.key_env, self.model = key_env, model
        self.max_images, self.max_videos = max_images, max_videos
        self.images = self.videos = 0
        self.model_slot = threading.BoundedSemaphore(1)
        self.counter_lock = threading.Lock()
        self.local_open = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

    def request(self, method, path, payload=None, key=None):
        headers = {"Content-Type": "application/json"}
        if os.environ.get("EVOSPRIG_MEDIA_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["EVOSPRIG_MEDIA_TOKEN"]
        if key:
            headers["Idempotency-Key"] = key
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.media_url + path, data, headers, method=method)
        with self.local_open(request, timeout=30) as response:
            return json.load(response)

    def job(self, operation, payload):
        identifier = self.request("POST", "/" + operation, payload, uuid.uuid4().hex)["job_id"]
        deadline = time.monotonic() + 3600
        while time.monotonic() < deadline:
            result = self.request("GET", "/" + operation + "/" + identifier)
            if result["status"] == "succeeded":
                return result["output"]
            if result["status"] in {"failed", "canceled"}:
                raise RuntimeError("local media job " + result["status"])
            time.sleep(2)
        raise TimeoutError("local media job remains pending; inspect its job receipt")

    def upload(self, path):
        if str(path).startswith(self.media_url + "/files/"):
            return {"uri": str(path)}
        with Image.open(path) as image:
            stream = io.BytesIO()
            image.convert("RGB").save(stream, format="PNG")
        uri = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()
        return self.request("POST", "/upload", {"image": uri})

    def download(self, asset, path):
        uri = asset["uri"]
        if not uri.startswith(self.media_url + "/files/"):
            raise ValueError("media service returned an unexpected asset location")
        headers = {}
        if os.environ.get("EVOSPRIG_MEDIA_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["EVOSPRIG_MEDIA_TOKEN"]
        with self.local_open(urllib.request.Request(uri, headers=headers), timeout=120) as response:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        return str(target.resolve())

    def chat(self, prompt, images=None):
        # Upstream stages may fan out even when media concurrency is disabled.
        # Serialize paid model requests independently of the GPU job queue.
        with self.model_slot:
            return self._chat(prompt, images)

    def _chat(self, prompt, images=None):
        content = [{"type": "text", "text": prompt}]
        for path in images or []:
            if str(path).startswith("data:"):
                uri = path
            else:
                with Image.open(path) as image:
                    image = image.convert("RGB")
                    image.thumbnail((768, 768))
                    stream = io.BytesIO()
                    image.save(stream, format="JPEG", quality=82)
                uri = "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode()
            content.append({"type": "image_url", "image_url": {"url": uri}})
        payload = {"model": self.model, "messages": [{"role": "user", "content": content}],
                   "reasoning_effort": "low", "max_completion_tokens": 6000}
        request = urllib.request.Request(self.model_url + "/chat/completions", json.dumps(payload).encode(),
                                         {"Authorization": "Bearer " + os.environ[self.key_env],
                                          "Content-Type": "application/json"})
        with (self.local_open if self.model_url.startswith("http://127.0.0.1:") else urllib.request.urlopen)(request, timeout=300) as response:
            body = json.load(response)
        if body["choices"][0].get("finish_reason") == "length":
            raise RuntimeError("Kimi response reached the configured output budget")
        return body["choices"][0]["message"]["content"]

    def install(self):
        from models.image_client import ImageClient
        from models.llm_client import LLM
        from models.video_client import VideoClient
        from models.vlm_client import VLM

        adapter = self
        def llm_query(instance, prompt, image_urls=None, model="", safe_content=True, task_id=None, web_search=False):
            if web_search:
                raise ValueError("web search is disabled in the local comparison")
            return adapter.chat(prompt, image_urls)

        def vlm_query(instance, prompt, image_paths=None, model="", session_id=None):
            return adapter.chat(prompt, image_paths)

        def image_generate(instance, prompt, image_paths=None, model="", save_dir=None, session_id=None, **kwargs):
            with adapter.counter_lock:
                if adapter.images >= adapter.max_images:
                    raise RuntimeError("local image-generation budget exhausted")
                adapter.images += 1
            asset = adapter.job("generate-image", {"prompt": prompt,
                                "references": [adapter.upload(path) for path in image_paths or []]})
            target = Path(save_dir or "code/result/local-images") / (asset["id"] + ".png")
            return [adapter.download(asset, target)]

        def video_generate(instance, prompt, image_path, save_path, model="", duration=5, **kwargs):
            with adapter.counter_lock:
                if adapter.videos >= adapter.max_videos:
                    raise RuntimeError("local video-generation budget exhausted")
                adapter.videos += 1
            if kwargs.get("last_image_path") or kwargs.get("reference_video_paths"):
                raise ValueError("this local adapter supports first-frame generation")
            asset = adapter.job("generate-video", {"prompt": prompt,
                                "first_frame": adapter.upload(image_path), "duration": duration})
            adapter.download(asset, save_path)
            return asset["uri"]

        LLM.query, VLM.query = llm_query, vlm_query
        ImageClient.generate_image, VideoClient.generate_video = image_generate, video_generate
        return self
