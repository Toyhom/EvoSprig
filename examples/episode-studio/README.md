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

```bash
python apps/episode-studio/launch.py setup --model-dir /path/to/models --env-root /path/to/environments
python apps/episode-studio/launch.py start
```

Open **http://127.0.0.1:18767/episode/**. Paste your story and choose **Make this film**. Follow the script, cast and shots as they appear. Completed films stay in **Your productions**.

Use **Open canvas** to change an agent, **Debug selection** to try a node or group, and **Open render workflow** to edit the render graph and export it to ComfyUI.

**[Installation, API models and domestic mirrors](../../apps/episode-studio/)** · **[ComfyUI import/export](../../docs/comfyui.md)**

### Edit the team and continue a series

Change the [role instructions](prompts/), [production skills](skills/) and [render recipe](../../apps/episode-studio/render-recipe.json). The render agent keeps the tuned defaults and changes only what the shot needs. Its video-prompt skill follows [MiniMax H3’s official examples](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing).

Pass a completed run’s `series` into the next story to carry its cast bible, reference images and voices forward. Models stay loaded between productions. [Series input and deployment settings](../../apps/episode-studio/#continue-a-series).

Want the team to improve? Open **Improve**, choose the prompts, skills or harness settings, and supply scene tasks with your judging criteria. The included [search space](search-space.yaml) covers story, visual direction, frame review and continuity. [Set up evaluation](../../docs/evaluation.md).
