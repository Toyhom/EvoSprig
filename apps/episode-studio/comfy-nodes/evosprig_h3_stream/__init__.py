"""Optional SolarX H3 streaming decode using the VAE already loaded by ComfyUI."""

import time
from types import SimpleNamespace

import torch
import torch.nn.functional as F


class FeedForward:
    def __init__(self, original):
        self.w1, self.w2 = original.w1, original.w2
        self.use_gated, self.act_fn = True, torch.nn.SiLU()

    def __call__(self, x):
        gate, up = self.w1(x).chunk(2, dim=-1)
        return self.w2(F.silu(gate) * up)


def compatible_vae(model):
    """Expose official decoder attributes without copying or replacing model weights."""
    decoder = model.decoder
    if getattr(model, 'noncausal', False) or getattr(model, 'still_frame', None) is not None:
        raise ValueError('Streaming decode needs the standard H3 video VAE, not a distilled/still-image decoder')

    def position(ids):
        table = decoder.pos_embed(ids)
        # Comfy uses 2x2 rotation matrices; SolarX expects split-half cos/sin.
        cos, sin = table[..., 0, 0], table[..., 1, 0]
        return torch.cat([cos, cos], dim=-1), torch.cat([sin, sin], dim=-1)

    blocks = [SimpleNamespace(norm1=b.norm1, norm2=b.norm2, attn=b.attn,
                              scale1=b.scale1, scale2=b.scale2, ff=FeedForward(b.ff), use_scale=True)
              for b in decoder.transformer_blocks]
    compatible = SimpleNamespace(x_embedder=decoder.x_embedder, register_tokens=decoder.register_tokens,
                                 transformer_blocks=blocks, norm_out=decoder.norm_out, proj_out=decoder.proj_out,
                                 pos_embed=position, config=SimpleNamespace(patch_size=decoder.patch_size, patch_size_t=decoder.patch_size_t))
    return SimpleNamespace(decoder=compatible, post_quant_conv=model.post_quant_conv,
                           tokens_chunk_size=model.tokens_chunk_size, token_overlap=model.token_overlap,
                           vae_ratio_t=model.vae_ratio_t, frame_pre_padding=model.frame_pre_padding,
                           vae_ratio=model.vae_ratio, split_tiles=lambda length, decoding=True: model.split_tiles(length),
                           blend=model.blend)


def decode_chunks(model, samples, *, compensate=True, token_budget=4096):
    from h3_vae import StreamingDecoder

    if samples.ndim != 5 or samples.shape[0] != 1 or samples.shape[1] != 24:
        raise ValueError('H3 streaming decode expects one [1,24,T,H,W] video latent')
    wrapped = compatible_vae(model)
    decoder = StreamingDecoder(wrapped, compile=False, compensate=compensate, token_budget=token_budget)
    # Comfy H3 latents are normalized. Convert exactly once before post_quant_conv.
    mean = model.latents_mean.view(1, -1, 1, 1, 1)
    std = model.latents_std.view(1, -1, 1, 1, 1)
    device, dtype = model.decoder.x_embedder.weight.device, model.decoder.x_embedder.weight.dtype
    with torch.inference_mode():
        for index in range(samples.shape[2]):
            z = samples[:, :, index:index + 1].to(device=device, dtype=dtype)
            z = z * std.to(z) + mean.to(z)
            output = decoder.push(z)
            # Same ImageNet pixel transform as the standard Comfy H3 decoder.
            yield model._finalize_pixels(output).squeeze(0).permute(1, 2, 3, 0).cpu()


class EvoSprigH3StreamingDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'samples': ('LATENT',), 'vae': ('VAE',),
                             'compensate': ('BOOLEAN', {'default': True}),
                             'token_budget': ('INT', {'default': 4096, 'min': 256, 'max': 65536})}}

    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'decode'
    CATEGORY = 'EvoSprig/video'
    DESCRIPTION = 'Decode H3 latents one at a time with the SolarX streaming VAE. Keeps the existing sampler and audio path.'

    def decode(self, samples, vae, compensate=True, token_budget=4096):
        import comfy.model_management as mm
        from comfy.utils import ProgressBar

        try:
            import h3_vae  # noqa: F401
        except ImportError:
            raise RuntimeError('Install the optional H3 streaming decoder in the ComfyUI Python environment; see Episode Studio streaming-decoder.md') from None
        z = samples['samples']
        if z.is_nested:
            z = z.unbind()[0]
        model = vae.first_stage_model
        if not hasattr(model, 'latents_mean') or not hasattr(model, 'tokens_chunk_size'):
            raise ValueError('Select a MiniMax H3 video VAE')
        # The upstream decoder keeps KV for all spatial tiles. Reserve it explicitly.
        wrapped = compatible_vae(model)
        y, _, _ = model.split_tiles(z.shape[-2] * model.vae_ratio)
        x, _, _ = model.split_tiles(z.shape[-1] * model.vae_ratio)
        tile_h = min(model.tile_size, z.shape[-2] * model.vae_ratio) // model.vae_ratio
        tile_w = min(model.tile_size, z.shape[-1] * model.vae_ratio) // model.vae_ratio
        attn = wrapped.decoder.transformer_blocks[0].attn
        cache_bytes = len(y) * len(x) * len(wrapped.decoder.transformer_blocks) * (5 + (model.tokens_chunk_size + model.token_overlap) * tile_h * tile_w) * attn.heads * attn.dim_head * 2 * torch.tensor([], dtype=vae.vae_dtype).element_size()
        mm.load_models_gpu([vae.patcher], memory_required=cache_bytes + 1024**3, force_full_load=True)
        progress = ProgressBar(z.shape[2])
        began, first, chunks = time.perf_counter(), None, []
        for index, frames in enumerate(decode_chunks(model, z, compensate=compensate, token_budget=token_budget)):
            if first is None:
                first = time.perf_counter() - began
            chunks.append(frames)
            progress.update_absolute(index + 1, z.shape[2])
        print(f'[EvoSprig H3 stream] first chunk {first:.3f}s; total {time.perf_counter()-began:.3f}s; KV estimate {cache_bytes/1024**3:.2f} GiB')
        return (torch.cat(chunks, dim=0),)


NODE_CLASS_MAPPINGS = {'EvoSprigH3StreamingDecode': EvoSprigH3StreamingDecode}
NODE_DISPLAY_NAME_MAPPINGS = {'EvoSprigH3StreamingDecode': 'H3 streaming decode · EvoSprig'}
