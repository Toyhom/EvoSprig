"""Local image/video inference behind the same jobs used by any EvoSprig agent."""

import base64
import gc
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image


class MediaBackend:
    def __init__(self, root, image_model, video_model, base_url, seed=42, image_steps=4,
                 video_steps=12, width=848, height=480):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.image_model, self.video_model = str(image_model), str(video_model)
        self.base_url = base_url.rstrip("/")
        self.seed, self.image_steps, self.video_steps = seed, image_steps, video_steps
        self.width, self.height = width, height
        self.pipeline = None
        self.loaded = None

    def asset(self, path):
        path = Path(path)
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".mp4": "video/mp4"}[path.suffix]
        return {"id": path.stem, "uri": self.base_url + "/files/" + path.name, "media_type": mime}

    def resolve(self, asset):
        uri = asset.get("uri", "") if isinstance(asset, dict) else asset
        prefix = self.base_url + "/files/"
        if not isinstance(uri, str) or not uri.startswith(prefix):
            raise ValueError("asset must belong to this media service; upload external images first")
        name = uri[len(prefix):]
        if not re.fullmatch(r"[a-f0-9]{32,64}(?:_[0-9]+)?\.(png|jpg|mp4)", name):
            raise ValueError("invalid asset name")
        path = (self.root / name).resolve()
        if path.parent != self.root or not path.is_file():
            raise ValueError("asset is missing")
        return path

    def upload(self, data_uri):
        if not isinstance(data_uri, str) or len(data_uri) > 16 * 1024 * 1024:
            raise ValueError("image upload exceeds 16 MiB")
        header, data = data_uri.split(",", 1)
        if header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"}:
            raise ValueError("unsupported image format")
        raw = base64.b64decode(data, validate=True)
        path = self.root / (hashlib.sha256(raw).hexdigest() + ".png")
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 16000000:
                raise ValueError("image exceeds 16 megapixels")
            image.convert("RGB").save(path)
        return self.asset(path)

    def vision(self, assets, max_side=768):
        if not 1 <= len(assets) <= 6 or not 128 <= max_side <= 1024:
            raise ValueError("vision accepts 1–6 images and a 128–1024 pixel preview")
        images = []
        for asset in assets:
            with Image.open(self.resolve(asset)) as image:
                image = image.convert("RGB")
                image.thumbnail((max_side, max_side))
                stream = io.BytesIO()
                image.save(stream, format="JPEG", quality=82)
            images.append("data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode())
        return {"images": images}

    def load(self, kind):
        if self.loaded == kind:
            return self.pipeline
        import torch
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            self.loaded = None
            gc.collect()
            torch.cuda.empty_cache()
        if kind == "image":
            from diffusers import Flux2KleinPipeline
            pipeline = Flux2KleinPipeline.from_pretrained(self.image_model, torch_dtype=torch.bfloat16, local_files_only=True)
        else:
            from diffusers import HunyuanVideo15ImageToVideoPipeline
            pipeline = HunyuanVideo15ImageToVideoPipeline.from_pretrained(self.video_model, torch_dtype=torch.bfloat16, local_files_only=True)
            pipeline.vae.enable_tiling()
        pipeline.enable_model_cpu_offload()
        self.pipeline, self.loaded = pipeline, kind
        return pipeline

    def image(self, prompt, references, name, canceled):
        import torch
        if canceled():
            raise RuntimeError("job canceled")
        pipe = self.load("image")
        kwargs = {"prompt": prompt, "width": self.width, "height": self.height,
                  "num_inference_steps": self.image_steps, "guidance_scale": 1.0,
                  "generator": torch.Generator(device="cpu").manual_seed(self.seed)}
        if references:
            kwargs["image"] = [Image.open(self.resolve(ref)).convert("RGB") for ref in references[:4]]
        image = pipe(**kwargs).images[0]
        if canceled():
            raise RuntimeError("job canceled")
        path = self.root / (name + ".png")
        image.save(path)
        self.record(name, {"kind": "image", "model": self.image_model, "prompt": prompt,
                           "references": references, "steps": self.image_steps})
        return self.asset(path)

    def video(self, prompt, first_frame, duration, name, canceled):
        import torch
        from diffusers.utils import export_to_video
        if not 1 <= duration <= 15:
            raise ValueError("local video duration must be between 1 and 15 seconds")
        if canceled():
            raise RuntimeError("job canceled")
        pipe = self.load("video")
        def check_cancellation(module, inputs):
            if canceled():
                raise RuntimeError("job canceled")
        # Hunyuan 1.5 chooses a resolution bucket from the first frame. Its
        # Diffusers API has no width/height or callback_on_step_end arguments.
        # A scoped model hook checks cancellation between denoising steps.
        hook = pipe.transformer.register_forward_pre_hook(check_cancellation)
        try:
            result = pipe(prompt=prompt, image=Image.open(self.resolve(first_frame)).convert("RGB"),
                          num_frames=int(duration * 24) + 1,
                          num_inference_steps=self.video_steps,
                          generator=torch.Generator(device="cpu").manual_seed(self.seed)).frames[0]
        finally:
            hook.remove()
        if canceled():
            raise RuntimeError("job canceled")
        path = self.root / (name + ".mp4")
        export_to_video(result, str(path), fps=24)
        self.record(name, {"kind": "video", "model": self.video_model, "prompt": prompt,
                           "first_frame": first_frame, "steps": self.video_steps,
                           "frames": len(result), "fps": 24,
                           "height": int(result[0].shape[0]), "width": int(result[0].shape[1])})
        return self.asset(path)

    def record(self, name, metadata):
        for key, value in {"seed": self.seed, "width": self.width, "height": self.height}.items():
            metadata.setdefault(key, value)
        (self.root / (name + ".json")).write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    def compose(self, clips, audio, subtitles, name):
        if not 1 <= len(clips) <= 20:
            raise ValueError("composition accepts 1–20 clips")
        if audio:
            raise ValueError("the local backend currently composes silent clips")
        paths = [self.resolve(clip) for clip in clips]
        if any(path.suffix != ".mp4" for path in paths):
            raise ValueError("composition requires video clips")
        manifest = self.root / (name + ".concat")
        manifest.write_text("".join(f"file '{path.name}'\n" for path in paths))
        ffmpeg = os.environ.get("MEDIA_FFMPEG") or shutil.which("ffmpeg")
        if not ffmpeg:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        output = self.root / (name + ".mp4")
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "1", "-i", manifest.name]
        if subtitles:
            if len(subtitles) > 100000:
                raise ValueError("subtitle text is too long")
            subtitle_path = self.root / (name + ".srt")
            subtitle_path.write_text(subtitles)
            cmd += ["-vf", "subtitles=" + subtitle_path.name]
        cmd += ["-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", output.name]
        subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, timeout=300)
        self.record(name, {"kind": "compose", "clips": clips})
        return self.asset(output)

    def execute(self, operation, payload, name, canceled):
        if operation == "assets":
            characters = payload["characters"]
            if not 1 <= len(characters) <= 8:
                raise ValueError("a catalog requires 1–8 characters")
            assets = []
            for index, character in enumerate(characters):
                prompt = f"Character reference portrait. {character['description']}. Visual style: {payload['style']}. No labels or text."
                assets.append({"character_id": character["id"], "asset": self.image(prompt, [], f"{name}_{index}", canceled)})
            return {"assets": assets}
        if operation == "image":
            shot = payload["shot"]
            refs = [entry["asset"] for entry in payload["catalog"]["assets"] if entry["character_id"] in shot["characters"]]
            prompt = payload.get("prompt") or f"{shot['description']}. Camera: {shot['camera']}. Visual style: {payload['style']}. Preserve the identity and clothing of the reference characters. No text overlays."
            return self.image(prompt, refs, name, canceled)
        if operation == "video":
            shot = payload["shot"]
            prompt = f"{shot['description']}. Camera: {shot['camera']}. Preserve the characters and scene in the first frame. Continuous natural motion, no cuts, no text overlays."
            return self.video(prompt, payload["first_frame"], shot["duration_seconds"], name, canceled)
        if operation == "compose":
            return self.compose(payload["clips"], payload.get("audio", []), payload.get("subtitles", ""), name)
        if operation == "generate-image":
            return self.image(payload["prompt"], payload.get("references", []), name, canceled)
        if operation == "generate-video":
            return self.video(payload["prompt"], payload["first_frame"], payload.get("duration", 5), name, canceled)
        raise ValueError("unknown media operation")
