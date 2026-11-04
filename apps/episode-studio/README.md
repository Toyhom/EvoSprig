# Episode Studio

A story-to-film application built with EvoSprig. Start from a novel, a scene or one sentence. The production team chooses the visual direction, develops the screenplay, creates character and voice references, directs the shots and edits the film.

## Install

Use Linux, Python 3.12, Node.js 20+, Git and an NVIDIA CUDA driver, then run:

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

Models are shared across agents and shots for the lifetime of the session. Startup checks the director's CUDA compiler before loading its weights and preloads the voice generator. The media worker records the voice library first, then switches to image generation. ComfyUI retains its render models between shots. To stop the session and release its GPUs:

```bash
python apps/episode-studio/launch.py stop
python apps/episode-studio/launch.py status
```

On a shared server, run the production session inside your GPU scheduler allocation. The launcher maps its service partitions onto `CUDA_VISIBLE_DEVICES`.

## Deployment settings

Edit `.evosprig/episode/services.json` after setup. The default Flash FP8 deployment uses four GPUs for the director, one for images/voices and one for video. The default profile targets six 80 GB GPUs. Set `director_gpus`, `media_gpu`, `comfy_gpu`, context length, concurrent requests, idle timeout and service ports for your hardware. `model_timeout_seconds` allows up to 20 minutes per director response by default, covering long screenplays on slower local servers. The director uses CUDA Graphs, prefix caching and GPU-resident n-gram embeddings; models are loaded once per session. Set `enforce_eager: true` to disable graph compilation when diagnosing a backend issue. `safetensors_load_strategy` selects weight loading (`eager` by default, or `prefetch` for advance reads).

You can also use existing model and media servers:

```bash
python examples/episode-studio/configure.py --recipe film-recipe.json --out deployment.yaml
python apps/episode-studio/app.py --profile deployment.yaml \
  --workspace .evosprig/episode-studio --media-root /path/to/media/outputs
```

Setup builds the canvas editor and installs the local dialogue transcriber. Application generation uses the same saved AgentSpec and runtime as the editor. Role instructions and skills live in [examples/episode-studio](../../examples/episode-studio/).
