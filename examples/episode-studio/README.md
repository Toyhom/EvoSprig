# Episode Studio

![The Episode Studio production team in EvoSprig](assets/canvas.png)

[English](README.md) · [简体中文](README.zh-CN.md)

**A novel. A sentence. Your next animated film.**

Give Episode Studio a story. Its agents develop the script, cast and locations, create the reference images, direct each shot and assemble the film with dialogue and sound. The entire production team is editable in EvoSprig.

[**Showcase ↓**](#showcase) · [**Features ↓**](#features) · [**Make a film ↓**](#implementation)

## Showcase

### Vera’s Melancholy · opening scene

[![Play the animated opening](assets/hillside.webp)](assets/hillside.mp4)

**Two friends. A quiet town. A world beyond the hills.**

25 seconds · Chinese dialogue and narration · **[Watch with sound](assets/hillside.mp4)**

From [Vera’s Melancholy, Volume I](https://wiki.biligame.com/ys/少女薇拉的忧郁), an in-game book in *Genshin Impact*.

## Features

| You bring | The team takes care of |
| --- | --- |
| A novel or a short idea | Style, screenplay, character designs, locations and shot prompts |
| A recurring cast | Shared reference images, costumes and character voices across episodes |
| A scene that needs another take | Visual checks, specific corrections and bounded retakes |
| A longer story | Ordered shots, ending-frame continuity and the final cut with audio |

### Automatic visual review and retakes

![Automatic visual review corrects the foreground character](assets/retake.jpg)

The visual editor checks generated frames against the cast and shot plan. When it finds a mismatch, it sends specific corrections to the shot director and requests another take. Here it restored Vera’s short hair, blue dress and position beside Sachi.

## Implementation

### Run the application

![Episode Studio: story input and production progress](assets/application.png)

Use **Linux, Python 3.12, Node.js 20+, Git and an NVIDIA CUDA driver**. The API-director profile uses two GPUs for local image/video generation; the default local-director profile uses six 80 GB GPUs. Start with the API option:

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
mkdir -p .evosprig/episode
cp apps/episode-studio/model-api.example.json .evosprig/episode/model-api.json
export EPISODE_MODEL_API_KEY="your-api-key"
python3.12 apps/episode-studio/launch.py setup --director api \
  --model-config .evosprig/episode/model-api.json \
  --model-dir "$PWD/models" --env-root "$PWD/.venvs"
python3.12 apps/episode-studio/launch.py start
```

The installer creates the application/model environments, downloads the pinned weights and builds the canvas editor. Set `--model-dir` to your large model disk and `--env-root` to your environment directory. Append `--mirror https://hf-mirror.com` to setup for domestic downloads. Rerun the same setup command to resume an interrupted installation.

Before setup, edit `.evosprig/episode/model-api.json` to select your provider. The supplied connection uses `https://api.moonshot.cn/v1`, model `kimi-k3.1-pro`, and credential variable `EPISODE_MODEL_API_KEY`. It serves both the director and visual reviewer. For separate models, add a `vision` connection alongside `main`; the reviewer must accept image inputs. Export every credential variable before `start` in each new terminal. `.env` files are not loaded automatically.

For a fully local director, run setup with `--director local` and omit `--model-config`. Change GPU assignments and ports in `.evosprig/episode/services.json` after installation. The image and video model sources are listed in [models.json](../../apps/episode-studio/models.json).

Open **http://127.0.0.1:18767/episode/**. Paste your story and choose **Make this film**. Follow the script, cast and shots as they appear. Completed films stay in **Your productions**.

Use **Open canvas** to change an agent, **Debug selection** to try a node or group, and **Open render workflow** to edit the render graph and export it to ComfyUI.

**[Installation, API models and domestic mirrors](../../apps/episode-studio/)** · **[ComfyUI import/export](../../docs/comfyui.md)**

### Stop or reopen the application

```bash
python3.12 apps/episode-studio/launch.py status
python3.12 apps/episode-studio/launch.py stop
```

Models stay loaded between films; `stop` releases this session's services. Use the same state directory when restarting to retain productions. If port **18767** is occupied, change `ports.app` in `services.json` before starting.

### Import into an existing EvoSprig installation

After the first start, the configured tool/model profile is `.evosprig/episode/deployment.yaml`. Open the application directly:

```bash
evosprig serve --project examples/episode-studio/agent.yaml \
  --profile .evosprig/episode/deployment.yaml \
  --workspace .evosprig/episode-editor --studio-dir apps/studio/dist --port 18768
```

Keep the image and ComfyUI services running. Open **http://127.0.0.1:18768**, edit the team and debug individual nodes. Use **Export** to create a Python/HTTP application ZIP, or **Import project** in another Studio to continue editing it. Reconnect its deployment profile and media services on the destination. [Framework installation and SDK development](../../README.md#get-started).

### Edit the team and continue a series

Change the [role instructions](prompts/), [production skills](skills/) and [render recipe](../../apps/episode-studio/render-recipe.json). The render agent keeps the tuned defaults and changes only what the shot needs. Its video-prompt skill follows [MiniMax H3’s official examples](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing).

Pass a completed run’s `series` into the next story to carry its cast bible, reference images and voices forward. Models stay loaded between productions. [Series input and deployment settings](../../apps/episode-studio/#continue-a-series).

Want the team to improve? Open **Improve**, choose the prompts, skills or harness settings, and supply scene tasks with your judging criteria. The included [search space](search-space.yaml) covers story, visual direction, frame review and continuity. [Set up evaluation](../../docs/evaluation.md).
