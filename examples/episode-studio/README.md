# Episode Studio

![Episode Studio canvas](assets/canvas.png)

Turn a story into an animated episode. A source reader identifies the cast and dialogue; a producer and script editor adapt the story. The art director, shot director, render engineer and continuity editor carry the cast from one shot to the next.

- **One cast across the episode.** Character and location references are generated once and reused.
- **Automatic retakes.** The first frame is reviewed before rendering. The visual editor then checks each clip and sends specific changes back to the team.
- **Longer stories.** Shots share final frames, ending motion and saved character voices, then assemble into a film with audio.
- **Editable decisions.** Agents read the render recipe's switches, parameter limits and saved defaults. Prompts, skills, LoRA strengths, sampling and upscaling settings can change together.

## Run

Connect a vision-capable model server, the [media service](../../apps/media-service/) and a [ComfyUI render recipe](../../docs/comfyui.md). The recipe exposes `prompt`, `action`, `steps`, `scheduler`, `shift_video`, `shift_audio`, `duration` and `seed`, with six image slots, three audio slots and a video slot.

```bash
python examples/episode-studio/configure.py --recipe film-recipe.json --out deployment.yaml
evosprig serve --project examples/episode-studio/agent.yaml \
  --profile deployment.yaml --workspace .evosprig/episode-studio \
  --studio-dir apps/studio/dist
```

Enter your story as `source_text`, choose `style` and `language`, and set `target_seconds`. Enable write tools to generate and save media.

## Make it yours

![Render controls and continuity review](assets/render-team.png)

Edit the role instructions in `prompts/` and the shared continuity/cinematography rules in `skills/`. Expose extra controls in the recipe to make them available to the render engineer; omitted values keep their saved defaults. `build_agent.py` sets the number of takes and concurrency. A shot that still needs work after its retake budget pauses for review; completed shots remain available when the run continues.

Use **Debug selection** to try a prompt, reference-image stage or rendering group before running the episode. Use **Improve** with your own scene tasks and rubric to compare prompt, skill and harness candidates.

The supplied [search space](search-space.yaml) divides changes between story, visual direction, first-frame review and motion continuity. Select the eight prompts and two skills in **Improve** to search those modules together with their output and retake limits. [Configure an evaluation suite](../../docs/evaluation.md) · [Harness search](../../docs/harness-search.md).
