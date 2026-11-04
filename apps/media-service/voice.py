"""Reusable Qwen Omni speech generation for character reference libraries."""

import os
import wave


class OmniVoice:
    speakers = ("Ethan", "Chelsie", "Aiden")

    def __init__(self, model_path):
        self.model_path = model_path
        self.model = self.processor = None

    def load(self):
        if self.model is None:
            from transformers import Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor

            self.processor = Qwen3OmniMoeProcessor.from_pretrained(self.model_path, local_files_only=True)
            strategy = os.environ.get("EVOSPRIG_VOICE_LOAD_STRATEGY", "auto")
            if strategy not in {"auto", "eager", "mmap"}:
                raise ValueError("voice loading strategy must be auto, eager or mmap")
            self.model = Qwen3OmniMoeForConditionalGeneration.from_pretrained(
                self.model_path, dtype="auto", device_map="auto", attn_implementation="sdpa",
                local_files_only=True, disable_mmap={"auto": None, "eager": True, "mmap": False}[strategy],
            ).eval()

    def generate(self, payload, path, canceled):
        import numpy as np
        import torch

        text = payload.get("text", "")
        speaker = payload.get("speaker", "Chelsie")
        direction = payload.get("direction", "Natural, clear speech")
        seconds = payload.get("max_seconds", 5)
        seed = payload.get("seed", 42)
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500:
            raise ValueError("voice text must contain 1–500 characters")
        if speaker not in self.speakers:
            raise ValueError("choose Ethan, Chelsie or Aiden")
        if not isinstance(direction, str) or len(direction) > 1000:
            raise ValueError("voice direction exceeds 1000 characters")
        if type(seconds) not in (int, float) or not 1 <= seconds <= 30:
            raise ValueError("voice duration must be between 1 and 30 seconds")
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise ValueError("voice seed must be a nonnegative 32-bit integer")
        if canceled():
            raise RuntimeError("job canceled")
        self.load()
        conversation = [{"role": "user", "content": [{"type": "text", "text": (
            "Read the following line aloud exactly, with no introduction or explanation. "
            f"Acting direction: {direction}.\nLine: {text}"
        )}]}]
        prompt = self.processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
        inputs = self.processor(text=prompt, return_tensors="pt", padding=True)
        inputs = inputs.to(self.model.device).to(self.model.dtype)
        # The isolated worker owns its random state and serves one request at a time.
        torch.manual_seed(seed)
        with torch.inference_mode():
            tokens, audio = self.model.generate(
                **inputs, speaker=speaker, return_audio=True, thinker_max_new_tokens=256,
                thinker_return_dict_in_generate=True,
            )
        if canceled():
            raise RuntimeError("job canceled")
        if audio is None:
            raise RuntimeError("the Omni checkpoint did not return speech")
        samples = audio.reshape(-1).detach().float().cpu().numpy()
        if not np.isfinite(samples).all() or len(samples) < 2400 or np.max(np.abs(samples)) < 1e-5:
            raise RuntimeError("the voice generator returned empty or silent audio")
        samples = samples[:int(seconds * 24000)]
        pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(pcm.tobytes())
        sequences = tokens.sequences if hasattr(tokens, "sequences") else tokens
        spoken = self.processor.batch_decode(sequences[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return {"speaker": speaker, "text": text, "generated_text": spoken,
                "direction": direction, "seed": seed, "sample_rate": 24000,
                "duration_seconds": len(samples) / 24000}
