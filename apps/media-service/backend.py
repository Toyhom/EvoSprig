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
                 video_steps=12, width=848, height=480, image_backend="flux-klein",
                 comfy_input=None, comfy_output=None, speech_model=None, voice_model=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.image_model = str(image_model)
        self.video_model = str(video_model) if video_model is not None else None
        self.base_url = base_url.rstrip("/")
        self.seed, self.image_steps, self.video_steps = seed, image_steps, video_steps
        self.width, self.height = width, height
        if image_backend not in {"flux-klein", "qwen-image-2.1"}:
            raise ValueError("unsupported image backend")
        self.image_backend = image_backend
        self.comfy_input = Path(comfy_input).resolve() if comfy_input else None
        self.comfy_output = Path(comfy_output).resolve() if comfy_output else None
        self.speech_model = str(Path(speech_model).resolve()) if speech_model else None
        self.transcriber = None
        self.voice_model = str(voice_model) if voice_model else None
        self.voice_generator = None
        self.pipeline = None
        self.loaded = None

    def asset(self, path):
        path = Path(path)
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".mp4": "video/mp4", ".wav": "audio/wav"}[path.suffix]
        return {"id": path.stem, "uri": self.base_url + "/files/" + path.name, "media_type": mime}

    def resolve(self, asset):
        uri = asset.get("uri", "") if isinstance(asset, dict) else asset
        prefix = self.base_url + "/files/"
        if not isinstance(uri, str) or not uri.startswith(prefix):
            raise ValueError("asset must belong to this media service; upload external images first")
        name = uri[len(prefix):]
        if not re.fullmatch(r"[a-f0-9]{32,64}(?:_[0-9]+)?\.(png|jpg|mp4|wav)", name):
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
        if not 1 <= len(assets) <= 8 or not 128 <= max_side <= 1024:
            raise ValueError("vision accepts 1–8 images and a 128–1024 pixel preview")
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
            if self.image_backend == "qwen-image-2.1":
                from diffusers import QwenImage21Pipeline
                pipeline_class = QwenImage21Pipeline
            else:
                from diffusers import Flux2KleinPipeline
                pipeline_class = Flux2KleinPipeline
            components = {}
            if self.image_backend == "qwen-image-2.1":
                strategy = os.environ.get("EVOSPRIG_IMAGE_LOAD_STRATEGY", "auto")
                if strategy not in {"auto", "eager"}:
                    raise ValueError("image loading strategy must be auto or eager")
                if strategy == "eager":
                    from diffusers import AutoencoderKLQwenImage21, QwenImage21Transformer2DModel
                    from transformers import Qwen3VLForConditionalGeneration

                    base = Path(self.image_model)
                    components["text_encoder"] = Qwen3VLForConditionalGeneration.from_pretrained(
                        base / "text_encoder", dtype=torch.bfloat16, disable_mmap=True, local_files_only=True)
                    for name, cls in (("transformer", QwenImage21Transformer2DModel), ("vae", AutoencoderKLQwenImage21)):
                        components[name] = cls.from_pretrained(base / name, torch_dtype=torch.bfloat16,
                                                              disable_mmap=True, local_files_only=True)
            pipeline = pipeline_class.from_pretrained(self.image_model, torch_dtype=torch.bfloat16,
                                                      local_files_only=True, **components)
        else:
            if self.video_model is None:
                raise ValueError("configure --video-model to use the local video generator")
            from diffusers import HunyuanVideo15ImageToVideoPipeline
            pipeline = HunyuanVideo15ImageToVideoPipeline.from_pretrained(self.video_model, torch_dtype=torch.bfloat16, local_files_only=True)
            pipeline.vae.enable_tiling()
        offload = os.environ.get("EVOSPRIG_IMAGE_OFFLOAD", "model") if kind == "image" else "model"
        if offload == "sequential":
            pipeline.enable_sequential_cpu_offload()
        elif offload == "model":
            pipeline.enable_model_cpu_offload()
        else:
            raise ValueError("EVOSPRIG_IMAGE_OFFLOAD must be model or sequential")
        if kind == "image" and hasattr(pipeline.vae, "enable_tiling"):
            pipeline.vae.enable_tiling()
        self.pipeline, self.loaded = pipeline, kind
        return pipeline

    def image(self, prompt, references, name, canceled, options=None):
        import torch
        options = options or {}
        if options.keys() - {"seed", "width", "height", "steps"}:
            raise ValueError("image options accept seed, width, height and steps")
        width, height = options.get("width", self.width), options.get("height", self.height)
        steps, seed = options.get("steps", self.image_steps), options.get("seed", self.seed)
        if any(type(v) is not int for v in (width, height, steps, seed)) or not (256 <= width <= 4096 and 256 <= height <= 4096 and 1 <= steps <= 80 and 0 <= seed < 2**63):
            raise ValueError("image dimensions, steps or seed are outside supported limits")
        limit = 10 if self.image_backend == "qwen-image-2.1" else 4
        if len(references) > limit:
            raise ValueError(f"image backend accepts at most {limit} references")
        if canceled():
            raise RuntimeError("job canceled")
        reference_images = []
        for ref in references:
            with Image.open(self.resolve(ref)) as reference:
                reference_images.append(reference.convert("RGB"))
        pipe = self.load("image")
        kwargs = {"prompt": prompt, "width": width, "height": height,
                  "num_inference_steps": steps,
                  "generator": torch.Generator(device="cpu").manual_seed(seed)}
        if self.image_backend == "flux-klein":
            kwargs["guidance_scale"] = 1.0
        if references:
            kwargs["image"] = reference_images
        image = pipe(**kwargs).images[0]
        if canceled():
            raise RuntimeError("job canceled")
        path = self.root / (name + ".png")
        image.save(path)
        self.record(name, {"kind": "image", "model": self.image_model, "prompt": prompt,
                           "references": references, "steps": steps, "seed": seed,
                           "width": width, "height": height, "backend": self.image_backend})
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

    def compose(self, clips, audio, subtitles, name, preserve_audio=False):
        if not 1 <= len(clips) <= 240:
            raise ValueError("composition accepts 1–240 clips")
        if audio:
            raise ValueError("use preserve_audio to keep the clips' soundtracks")
        paths = [self.resolve(clip) for clip in clips]
        if any(path.suffix != ".mp4" for path in paths):
            raise ValueError("composition requires video clips")
        ffmpeg = os.environ.get("MEDIA_FFMPEG") or shutil.which("ffmpeg")
        if not ffmpeg:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # A retake may use a different size or frame rate, and a quiet shot may
        # have no soundtrack. Normalize these inputs before concat demuxing.
        import av
        formats = []
        for path in paths:
            with av.open(str(path)) as container:
                if not container.streams.video:
                    raise ValueError("composition input has no video")
                video = container.streams.video[0]
                sound = container.streams.audio[0] if container.streams.audio else None
                duration = float(video.duration * video.time_base) if video.duration else (container.duration or 0) / av.time_base
                if not 0 < duration <= 1800:
                    raise ValueError("each composition input must be at most 30 minutes")
                formats.append((video.width, video.height, str(video.average_rate), str(video.time_base),
                                (sound.codec_context.sample_rate, sound.codec_context.layout.name, str(sound.time_base)) if sound else None,
                                duration))
        normalize = len({row[:5] if preserve_audio else row[:4] for row in formats}) > 1
        temporary = []
        try:
            if normalize:
                width, height = formats[0][:2]
                width, height = width + width % 2, height + height % 2
                for index, (path, info) in enumerate(zip(paths, formats)):
                    target = self.root / f"{name}_segment_{index}.mp4"
                    temporary.append(target)
                    command = [ffmpeg, "-y", "-v", "error", "-i", str(path)]
                    if preserve_audio and info[4] is None:
                        command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                    command += ["-map", "0:v:0", "-vf",
                                f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,setpts=PTS-STARTPTS"]
                    if preserve_audio:
                        command += ["-map", "0:a:0" if info[4] is not None else "1:a:0",
                                    "-af", "aresample=async=1:first_pts=0,apad", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
                    else:
                        command += ["-an"]
                    command += ["-t", str(info[5]), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)]
                    subprocess.run(command, check=True, capture_output=True, timeout=300)
                paths = temporary
            return self._compose_ready(paths, clips, subtitles, name, preserve_audio, ffmpeg)
        finally:
            for path in temporary:
                path.unlink(missing_ok=True)

    def _compose_ready(self, paths, clips, subtitles, name, preserve_audio, ffmpeg):
        manifest = self.root / (name + ".concat")
        manifest.write_text("".join(f"file '{path.name}'\n" for path in paths))
        output = self.root / (name + ".mp4")
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "1", "-i", manifest.name]
        if subtitles:
            if len(subtitles) > 100000:
                raise ValueError("subtitle text is too long")
            subtitle_path = self.root / (name + ".srt")
            subtitle_path.write_text(subtitles)
            cmd += ["-vf", "subtitles=" + subtitle_path.name]
        cmd += (["-map", "0:v:0", "-map", "0:a:0?", "-c:a", "aac", "-ar", "48000", "-af", "aresample=async=1:first_pts=0"]
                if preserve_audio else ["-an"])
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", output.name]
        subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, timeout=300)
        self.record(name, {"kind": "compose", "clips": clips, "preserve_audio": preserve_audio})
        return self.asset(output)

    def stage_reference(self, asset):
        if self.comfy_input is None:
            raise ValueError("configure the ComfyUI input directory")
        path = self.resolve(asset)
        self.comfy_input.mkdir(parents=True, exist_ok=True)
        target = (self.comfy_input / path.name).resolve()
        if target.parent != self.comfy_input:
            raise ValueError("reference path escapes the input directory")
        if path != target:
            shutil.copyfile(path, target)
        return {"filename": target.name, "asset": self.asset(path)}

    def ingest_comfy(self, outputs, name):
        if self.comfy_output is None:
            raise ValueError("configure the ComfyUI output directory")
        assets = []
        for node_id, output in outputs.items():
            for key in ("images", "gifs", "videos", "audio"):
                for item in output.get(key, []):
                    if not isinstance(item, dict) or item.get("type", "output") != "output":
                        continue
                    source = (self.comfy_output / item.get("subfolder", "") / item["filename"]).resolve()
                    if not source.is_relative_to(self.comfy_output) or not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".mp4", ".wav"}:
                        raise ValueError("ComfyUI output must be a media file in its configured directory")
                    target = self.root / (f"{name}_{len(assets)}" + source.suffix.lower())
                    shutil.copyfile(source, target)
                    assets.append({"node_id": node_id, "asset": self.asset(target)})
        if not assets:
            raise ValueError("ComfyUI returned no saved media")
        return {"assets": assets}

    def inspect_video(self, asset, name, tail_seconds=2, voice_seconds=4):
        import av
        import numpy as np

        if not 0.25 <= tail_seconds <= 5:
            raise ValueError("tail_seconds must be between 0.25 and 5")
        if not 1 <= voice_seconds <= 5:
            raise ValueError("voice_seconds must be between 1 and 5")
        path = self.resolve(asset)
        if path.suffix != ".mp4":
            raise ValueError("video inspection requires MP4")
        # Decode the actual endpoint: duration minus an arbitrary offset can
        # miss the final pose used to condition the next shot.
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise ValueError("video stream is missing")
            video = container.streams.video[0]
            width, height = video.width, video.height
            if width * height > 16777216:
                raise ValueError("video exceeds 16 megapixels")
            expected_duration = float(video.duration * video.time_base) if video.duration else (container.duration or 0) / av.time_base
            if not 0 < expected_duration <= 1800:
                raise ValueError("video inspection accepts up to 30 minutes")
            first = middle = last = None
            count, end_time = 0, 0.0
            start_time = float((video.start_time or 0) * video.time_base)
            fps = float(video.average_rate or 24)
            for frame in container.decode(video):
                count += 1
                if count > 108000:
                    raise ValueError("video has too many frames")
                timestamp = float(frame.time or 0) - start_time
                frame_duration = float(frame.duration * frame.time_base) if frame.duration else 1 / fps
                end_time = max(end_time, timestamp + frame_duration)
                if first is None:
                    first = frame.to_image()
                if middle is None and timestamp >= expected_duration / 2:
                    middle = frame.to_image()
                last = frame
            if last is None:
                raise ValueError("video frame could not be decoded")
            last_image = last.to_image()
            selected = [first, middle or last_image, last_image]
            duration = end_time
            has_audio = bool(container.streams.audio)
        frames = []
        for index, preview in enumerate(selected):
            target = self.root / f"{name}_{index}.png"
            preview.thumbnail((1024, 1024))
            preview.save(target)
            frames.append(self.asset(target))
        audio = {"duration_seconds": 0.0, "rms_dbfs": -120.0, "peak_dbfs": -120.0,
                 "audible_fraction": 0.0}
        speech_chunks = []
        if has_audio:
            from itertools import chain

            samples, power, peak, audible = 0, 0.0, 0.0, 0
            with av.open(str(path)) as container:
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
                for frame in chain(container.decode(audio=0), [None]):
                    for chunk in resampler.resample(frame):
                        values = chunk.to_ndarray().reshape(-1).astype(np.float64)
                        samples += values.size
                        if samples > 16000 * 1801:
                            raise ValueError("audio exceeds 30 minutes")
                        power += float(np.dot(values, values))
                        peak = max(peak, float(np.abs(values).max(initial=0)))
                        audible += int(np.count_nonzero(np.abs(values) > 0.001))
                        if self.speech_model:
                            speech_chunks.append(values.astype(np.float32))
            if samples:
                audio = {"duration_seconds": samples / 16000,
                         "rms_dbfs": float(10 * np.log10(max(power / samples, 1e-12))),
                         "peak_dbfs": float(20 * np.log10(max(peak, 1e-6))),
                         "audible_fraction": audible / samples}
        ffmpeg = os.environ.get("MEDIA_FFMPEG") or shutil.which("ffmpeg")
        if not ffmpeg:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        tail = self.root / f"{name}_3.mp4"
        subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", str(max(0, duration - tail_seconds)), "-i", str(path), "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-r", "24", str(tail)], check=True, capture_output=True, timeout=120)
        speech = self.transcribe(np.concatenate(speech_chunks)) if speech_chunks else None
        audio_asset, audio_excerpt = None, None
        if has_audio:
            track = self.root / f"{name}_4.wav"
            spoken = [segment for segment in (speech or {}).get("segments", [])
                      if segment["text"].strip() and segment["end"] > segment["start"]
                      and segment.get("no_speech_prob", 0) < 0.5]
            segment = max(spoken, key=lambda row: row["end"] - row["start"], default=None)
            offset = max(0, min(segment["start"] - 0.15, max(0, audio["duration_seconds"] - 0.05))) if segment else 0
            excerpt_duration = min(voice_seconds, max(0, audio["duration_seconds"] - offset))
            subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", str(offset), "-i", str(path), "-vn", "-t", str(voice_seconds),
                            "-ar", "32000", "-ac", "2", "-c:a", "pcm_s16le", str(track)],
                           check=True, capture_output=True, timeout=60)
            audio_asset = self.asset(track)
            audio_excerpt = {"start_seconds": offset, "duration_seconds": excerpt_duration}
        return {"clip": self.asset(path), "frames": frames, "last_frame": frames[-1],
                "tail": self.asset(tail), "duration_seconds": duration,
                "width": width, "height": height, "frame_count": count,
                "has_audio": has_audio, "audio": audio, "audio_asset": audio_asset,
                "audio_excerpt": audio_excerpt, "speech": speech}

    def transcribe(self, waveform):
        if self.transcriber is None:
            from faster_whisper import WhisperModel

            self.transcriber = WhisperModel(self.speech_model, device="cpu", compute_type="int8",
                                            local_files_only=True)
        # Supply the already-decoded 16 kHz mono audio. This avoids a second
        # decode and decouples Whisper's file reader from PyAV API versions.
        segments, info = self.transcriber.transcribe(waveform, beam_size=1, vad_filter=True,
                                                    condition_on_previous_text=False)
        rows = [{"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip(),
                 "avg_logprob": float(segment.avg_logprob), "no_speech_prob": float(segment.no_speech_prob)}
                for segment in segments]
        return {"text": " ".join(row["text"] for row in rows), "language": info.language,
                "language_probability": float(info.language_probability), "segments": rows}

    def execute(self, operation, payload, name, canceled):
        if operation == "warmup":
            family = payload.get("family")
            if family == "voice":
                if not self.voice_model:
                    raise ValueError("configure a Qwen Omni Instruct voice model")
                from voice import OmniVoice
                if self.voice_generator is None:
                    self.voice_generator = OmniVoice(self.voice_model)
                self.voice_generator.load()
                self.loaded = "voice"
            elif family in {"image", "video"}:
                pipeline = self.load(family)
                if family == "image" and payload.get("probe", False):
                    # CPU offload can leave mapped weights unread until the first
                    # forward pass. A small pass materializes them before readiness.
                    import torch
                    options = {"prompt": "A plain grey square.", "width": 256, "height": 256,
                               "num_inference_steps": 1,
                               "generator": torch.Generator(device="cpu").manual_seed(0)}
                    if self.image_backend == "qwen-image-2.1":
                        options["image"] = [Image.new("RGB", (256, 256), "grey")]
                    else:
                        options["guidance_scale"] = 1.0
                    pipeline(**options)
                    if canceled():
                        raise RuntimeError("job canceled")
            else:
                raise ValueError("choose image, video or voice for preloading")
            return {"loaded": family}
        if operation == "generate-voice":
            if not self.voice_model:
                raise ValueError("configure a Qwen Omni Instruct voice model")
            if self.voice_generator is None:
                from voice import OmniVoice
                self.voice_generator = OmniVoice(self.voice_model)
            path = self.root / (name + ".wav")
            metadata = self.voice_generator.generate(payload, path, canceled)
            self.record(name, metadata)
            self.loaded = "voice"
            return self.asset(path)
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
            return self.compose(payload["clips"], payload.get("audio", []), payload.get("subtitles", ""), name, payload.get("preserve_audio", False))
        if operation == "stage-reference":
            return self.stage_reference(payload["asset"])
        if operation == "ingest-comfy":
            return self.ingest_comfy(payload["outputs"], name)
        if operation == "inspect-video":
            return self.inspect_video(payload["asset"], name, payload.get("tail_seconds", 2), payload.get("voice_seconds", 4))
        if operation == "generate-image":
            return self.image(payload["prompt"], payload.get("references", []), name, canceled,
                              payload.get("options"))
        if operation == "generate-video":
            return self.video(payload["prompt"], payload["first_frame"], payload.get("duration", 5), name, canceled)
        raise ValueError("unknown media operation")
