# VideoClaw, built with EvoSprig

![Production workflow in EvoSprig Studio](canvas.png)

An EvoSprig reproduction of [VideoClaw](https://github.com/HITsz-TMG/VideoClaw). Turn a story idea into a short film: plan the scenes, create the characters, generate the shots and assemble the cut.

## Moon Garden

A tiny robot tends luminous flowers in a greenhouse on the moon.

[![Watch Moon Garden](assets/moon-garden.webp)](assets/moon-garden.mp4)

## The Last Library

A librarian discovers a book that fills the night with light.

[![Watch The Last Library](assets/last-library.webp)](assets/last-library.mp4)

## Cloud Bakery

An orange cat opens a little bakery above the clouds.

[![Watch Cloud Bakery](assets/cloud-bakery.webp)](assets/cloud-bakery.mp4)

## Make your own film

Start the [media worker](../../apps/media-service/), set `MOONSHOT_API_KEY`, then open the workflow:

```bash
evosprig serve --project examples/video-studio/local-agent.yaml \
  --profile examples/video-studio/deployment.local.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/video
```

Open **http://127.0.0.1:18766** and submit a brief such as `{"brief":"A librarian discovers a living book. Three silent shots."}`. Enable writes for media jobs. Review the script, frames and timeline in **History**, then assemble the film.

The director plans the story; shared character references connect the shots. A vision model checks each first frame. You can replace a frame or shot and keep the rest of the production. Select the director, storyboard or review prompts in **Improve** to evolve them against your own tasks.

| Project | Purpose |
| --- | --- |
| `local-agent.yaml` | Full production workflow |
| `frame-agent.yaml` | Create a replacement first frame |
| `local-shot-agent.yaml` | Generate one shot |
| `compose-agent.yaml` | Assemble clips and subtitles |
| `script-agent.yaml` | Develop stories before rendering |

The included profile uses Kimi K3.1 Pro, FLUX.2-klein-4B and HunyuanVideo-1.5. These shorts contain three five-second silent shots. To connect other providers, edit the [tool bindings](deployment.example.yaml); the [Python builder](build_agent.py) defines the workflows.

## One brief, two workflows

**Laid Off** — a programmer receives an envelope, closes his laptop and leaves with a box.

[![EvoSprig and VideoClaw, side by side](assets/preview.webp)](assets/evosprig.mp4)

[EvoSprig film](assets/evosprig.mp4) · [VideoClaw film](assets/videoclaw.mp4)

Both productions use the [same brief](brief.json) and model setup. The VideoClaw film runs its [original workflow](https://github.com/HITsz-TMG/VideoClaw/tree/16c1ce0b553e30eff90ff1274e8a8a63c1d548a3) through the [provider adapter](../../apps/media-service/videoclaw.py).
