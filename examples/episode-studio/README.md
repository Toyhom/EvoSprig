# Episode Studio

![Episode Studio canvas](assets/canvas.png)

[English](README.md) · [简体中文](README.zh-CN.md)

**Paste a novel. Or start with one sentence. Let the production team make the film.**

Episode Studio turns stories into animated episodes. Its director chooses a visual style and develops a brief; writers, artists, voice and shot directors take it through to the final cut. Open the same application in EvoSprig's canvas to change the team.

- **An idea is enough.** Agents expand the story, choose the style, write dialogue and prepare every generation prompt. Style, language and length are optional directions.
- **One cast across the episode.** Character, location and voice references are generated once and reused.
- **Automatic retakes.** Reference images and first frames are reviewed before rendering. The visual editor then checks each clip and sends specific changes back to the team.
- **Longer stories.** Shots share final frames, ending motion and saved character voices, then assemble into a film with audio.
- **Editable decisions.** Agents read the render recipe's switches, parameter limits and saved defaults. Prompts, skills, LoRA strengths, sampling and upscaling settings can change together.

## On the hillside

[![Watch the opening scene](assets/hillside.webp)](assets/hillside.mp4)

Two friends, a quiet town, and a world beyond the hills. **25 seconds · Chinese dialogue and narration · [Watch with sound](assets/hillside.mp4)**.

Adapted from [Vera's Melancholy, Volume I](https://wiki.biligame.com/ys/少女薇拉的忧郁), an in-game book in *Genshin Impact*.

## The team checks its work

![A mismatched character corrected after automatic visual review](assets/retake.jpg)

The visual editor catches the wrong character in the foreground and sends a correction to the shot director. The next frame restores Vera’s short hair, blue dress and position beside Sachi.

## Make a film

![Episode Studio application](assets/application.png)

```bash
python apps/episode-studio/launch.py setup --model-dir /path/to/models --env-root /path/to/environments
python apps/episode-studio/launch.py start
```

Open **http://127.0.0.1:18767/episode/**, paste your story and choose **Make this film**. Watch the script, cast and shots appear as the team works, then play the finished film. Return to earlier films from **Your productions**. Use the language switch for the Chinese interface.

[Installation and hardware settings](../../apps/episode-studio/) · [Domestic mirrors](../../apps/episode-studio/#install) · [Connect existing services](../../apps/episode-studio/#deployment-settings)

## Make it yours

![Render controls and continuity review](assets/render-team.png)

Edit the role instructions in `prompts/` and the shared continuity/cinematography rules in `skills/`. Expose extra controls in the recipe to make them available to the render engineer; omitted values keep their saved defaults. `build_agent.py` sets the number of takes and concurrency. If a reference or shot reaches its retake limit, preview it in the application and choose a result to continue. Completed work stays available.

**Open render workflow** reveals the model loaders, references, adapters, samplers and output nodes. Search for a node, edit its parameters, switch an adapter on or off, and export the graph to ComfyUI. The [included recipe](../../apps/episode-studio/render-recipe.json) carries the attention, chunking and upscaling controls alongside the creative settings.

Use **Debug selection** to try a prompt, reference-image stage or rendering group before running the episode. Use **Improve** with your own scene tasks and rubric to compare prompt, skill and harness candidates.

The supplied [search space](search-space.yaml) divides changes between story, visual direction, voice casting, first-frame review and motion continuity. Select the team's prompts and skills in **Improve** to search those modules together with their output and retake limits. [Configure an evaluation suite](../../docs/evaluation.md) · [Harness search](../../docs/harness-search.md).
