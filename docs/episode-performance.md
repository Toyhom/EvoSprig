# Episode Studio runtime and resource use

[English](episode-performance.md) · [简体中文](zh-CN/episode-performance.md) · [Documentation](README.md)

Episode Studio separates the director, image generation, video rendering and CPU media work into services. A production session loads its models once and reuses them across shots and films. An API director removes the local language-model allocation.

## Measured rendering

Observed on H100 80 GB hardware with the included 1.5 MP, 12-step render configuration:

| Render | Wall time |
| --- | ---: |
| 12-second request, 12.25-second output at 1664 × 928, including initial model loading | 480.02 s |
| 6-second request, two warm renders | 154.48–157.57 s |
| 5-second request, two warm renders | 111.58–111.76 s |

These are ComfyUI execution times. A shot also needs a first frame, direction and review; retakes repeat the relevant generation stage. Longer clips and different settings should be measured separately.

## Framework overhead

A 133-second sample of an active production measured the EvoSprig worker at **179–295 MiB RSS**, using **0.10 CPU core on average**. Model serving is separate: the video process used 70–74 GiB of host memory and 48–54 GiB of GPU memory in that window. The local director reserved about 74.7 GiB on each of four GPUs; this reservation includes its serving cache. These are observations from that deployment, useful when sizing a similar session.

Multimodal checkpoints store large strings once per run. In an isolated comparison using a production checkpoint and five successive state changes:

| Per-run storage | Full JSON | Deduplicated strings |
| --- | ---: | ---: |
| Checkpoint rewritten per save | 24.08 MB | 2.89 MB |
| Median save time | 240 ms | 91 ms |
| SQLite database after five saves | 24.13 MB | 6.91 MB |

Values use decimal MB. Both paths restored the same state. The complete database contains the referenced strings and remains the backup unit.

## What determines episode time?

For sequential shots, production time is approximately:

`startup + planning + reference library + Σ(first-frame attempts + video attempts + review + orchestration) + assembly`

A deterministic timing node balances shot durations against the target and speech length. On a 24-shot generated draft, it adjusted 130 seconds to 180 seconds in 0.51 seconds through the native runtime, with no model call and no changes to dialogue or story events.

Startup is paid once per session. Reusing a `series` skips existing cast and location references. The default team allows two attempts per frame and video, then continues with remaining review comments in `notes`; use `build()` to change these limits. Shots with a preceding-frame dependency run in order. Separate productions can overlap director, image and video work; one image worker and one ComfyUI instance each run one generation at a time.

For a fixed clip size, model configuration and attempt limit, generation work grows roughly with the number of shots. The runtime retains node results and events as the episode grows. For `V` expanded nodes, `E` dependencies and `P` scheduling passes, the current scheduler scans up to `O(P × (V + E))`. Large strings are stored in `O(U)` space for unique content plus state references; each save still traverses the checkpoint to find and hash them. Video-model attention and activation memory depend on latent frame count, resolution and the selected attention backend.

Use [deployment settings](../apps/episode-studio/#deployment-settings) to choose API/local direction, concurrency and model lifetime. Use the canvas's node timings to distinguish an expensive generation from a slow tool connection or repeated review.
