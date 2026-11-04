# Episode Studio

A story-to-film application built with EvoSprig. Start from a novel, a scene or one sentence. The production team develops the characters, locations and screenplay, creates references, directs the shots and edits the film.

## Install

Use Linux, Python 3.12, Node.js 20+, Git and an NVIDIA CUDA driver, then run:

For an API director, copy [model-api.example.json](model-api.example.json) to `model-api.json` and set your endpoint, model ID and credential environment variable. Use a vision-capable model for both roles, or add a separate `vision` connection alongside `main`.

```bash
python apps/episode-studio/launch.py setup --director api --model-config model-api.json \
  --model-dir /path/to/models --env-root /path/to/environments
```

This installs local image/video tools and skips the director weights and vLLM environment. OpenAI-compatible providers, including Kimi and MiniMax, use the same connection format. Select a vision-capable endpoint for visual review; a text-only model can serve the writing team alongside a separate vision model. Set the credential environment variable before starting; credentials are not written into the deployment profile.

For a fully local director:

```bash
python apps/episode-studio/launch.py setup \
  --model-dir /path/to/models --env-root /path/to/environments
```

The installer includes a render recipe and creates separate environments for the framework, director, media tools and ComfyUI. It downloads pinned model versions directly from their upstream repositories, checks render-weight checksums and resumes interrupted transfers. To use a domestic Hugging Face mirror, append `--mirror https://hf-mirror.com`, or use your preferred compatible endpoint. Add `--recipe your-recipe.json` to use a [custom ComfyUI recipe](../../docs/comfyui.md).

Model sources, pinned versions and runtime extensions are listed in [models.json](models.json). [Model terms](../../docs/model-sources.md).

## Start a production session

```bash
python apps/episode-studio/launch.py start
```

Open **http://127.0.0.1:18767/episode/**. Paste your text and choose **Make this film**. The director fills in style, language and length; open the optional settings to give your own direction. Switch between English and Chinese in the header.

The page shows the screenplay, character references, voices and selected shots as they become ready. Open **Your productions** to return to an earlier film. **Open canvas** takes you to the agents, prompts, skills, run steps and node debugging. **Open render workflow** displays the complete compute graph, including bypassed nodes and routing. Select a node in the searchable list to jump to its parameters. Save edits or export the workflow to ComfyUI.

Models are shared across agents, shots and productions for the lifetime of the session. Startup preloads the image model with a small inference pass; local deployments also load the director. ComfyUI caches render models after their first execution. Completing or pausing a film keeps the services running. To stop the session and release its GPUs:

```bash
python apps/episode-studio/launch.py stop
python apps/episode-studio/launch.py status
```

On a shared server, run the production session inside your GPU scheduler allocation. The launcher maps its service partitions onto `CUDA_VISIBLE_DEVICES`.

## Deployment settings

Edit `.evosprig/episode/services.json` after setup. API mode uses one GPU for images and one for video. The local Flash FP8 profile adds four GPUs for the director; this profile targets six 80 GB GPUs. Set `director_gpus`, `media_gpu`, `comfy_gpu`, context length and service ports for your hardware. `idle_unload_seconds: 0` retains media weights until shutdown; set a positive timeout to unload them when idle. `model_timeout_seconds` allows up to 20 minutes per local director response. The director uses CUDA Graphs, prefix caching and GPU-resident n-gram embeddings. Set `enforce_eager: true` to disable graph compilation when diagnosing a backend issue. `safetensors_load_strategy` selects weight loading (`eager` by default, or `prefetch` for advance reads).

The director supports concurrent requests (`max_concurrent_requests`, default 4). Director, image and video services run independently. Media inspection, reference staging and composition have their own CPU queue, so an image generation does not block them. Each image worker and each ComfyUI instance executes one generation at a time. Shots that need the preceding ending frame run in order; independent productions can overlap work across the services.

A timing tool balances the screenplay’s shot durations, so the writers do not regenerate a script to correct duration arithmetic. The renderer keeps the tuned recipe defaults. Its agent returns the audiovisual prompt, the approved action switch and only necessary parameter changes. Duration and seeds come from the timeline. The screenplay and render roles have separate worked examples in their [skills](../../examples/episode-studio/skills/).

## Continue a series

The completed production returns `series`: character and location settings, style, reference images and voices. Supply it with the next story:

```python
next_input = {"source_text": "The next chapter…", "series": previous_result.output["series"]}
next_result = await runtime.run(version, next_input)
```

The source reader retains recurring character IDs. Writers keep their established appearance and voice, and the reference library generates only newly needed assets. Keep the media service and referenced files available. Remove a reference from `series.references` when you want it redrawn. Explicit `voices` inputs override matching series voices.

## Voices across an episode

The video model creates the initial voice from the character's written voice description. The first accepted single-speaker take supplies an audio excerpt, reused for that character in later shots. Mixed conversations are not assigned to one character. The completed run returns a `voices` array; pass it as the next production's `voices` input to reuse the same cast across episodes. Keep character IDs stable and retain the media files.

Omni remains an optional tool: add `--with-voice` during setup and build the team with `build(enable_voice=True)` to generate its preset voices before images. The default team uses voices from its rendered shots.

Production continues after its bounded retakes and returns any unresolved review comments in `notes`. Set `build(review_policy="pause")` to stop at these cases for approval. Each take retains its original review result.

You can also use existing model and media servers:

```bash
python examples/episode-studio/configure.py --recipe film-recipe.json \
  --model-config model-api.json --out deployment.yaml
python apps/episode-studio/app.py --profile deployment.yaml \
  --workspace .evosprig/episode-studio --media-root /path/to/media/outputs
```

Setup builds the canvas editor and installs the local dialogue transcriber. Application generation uses the same saved AgentSpec and runtime as the editor. Role instructions and skills live in [examples/episode-studio](../../examples/episode-studio/).

[Runtime and resource measurements](../../docs/episode-performance.md).
