# Ten minutes to a comic agent

[English](comic-studio.md) · [简体中文](../zh-CN/tutorials/comic-studio.md) · [Learning path](README.md)

[![Build Comic Studio from an empty canvas](assets/comic-01.jpg)](assets/comic-01.mp4)

**[Watch lesson 1](assets/comic-01.mp4)** · Chinese subtitles · [Classroom materials](assets/comic-materials.zip) · [Completed application](assets/comic-project.zip)

Build a comic application from an empty canvas, export it, then give the deployed application another story. The lesson creates each node and connection, adds character references and a visual review loop, and switches to Python before deployment.

| Time | In the video |
| --- | --- |
| 00:10 | Empty canvas, resource library and application input |
| 01:05 | Writer, character references, panel map and page layout |
| 02:30 | Panel subflow, drawing tools and visual review loop |
| 04:55 | Connect the nodes and save |
| 06:00 | Debug one node and inspect its result |
| 06:30 | Python view and HTTP export |
| 07:08 | Configure and start the independent application |
| 07:50 | Make the first comic |
| 08:38 | Submit another story to the same application |
| 09:20 | Finished comic pages |

## 1. Prepare the tools

You need Python 3.12+, Node.js 20+, Git, a text model, a vision model and an image-generation service. One multimodal API can serve both agent roles.

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[models,server,artifacts]'
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py comic-studio setup
```

Edit `.evosprig/examples/comic-studio/deployment.yaml`. Set `models.main` and `models.vision`: `base_url`, the provider's served `model` ID, and `api_key_env`. Set those key environment variables in the terminal that starts Studio. For DeepSeek Flash text calls, use `options: {thinking: {type: disabled}}`. The visual reviewer needs a connection with `vision` capability.

Start the [image service](../../apps/media-service/README.md) at `http://127.0.0.1:18880`, with `--preload image --idle-unload-seconds 0`. For Chinese lettering, set a CJK font, such as [Noto Sans CJK](https://github.com/notofonts/noto-cjk):

```bash
export EVOSPRIG_COMIC_FONT="/path/to/NotoSansCJKsc-Regular.otf"
export EVOSPRIG_IMAGE_ORIGIN="http://127.0.0.1:18880"
evosprig serve --workspace .evosprig/comic-classroom \
  --profile .evosprig/examples/comic-studio/deployment.yaml \
  --studio-dir apps/studio/dist --port 18766
```

Open `http://127.0.0.1:18766`. Unzip the classroom materials. `library.json` contains tools, prompts, skills and short data-processing functions. `SETTINGS.md` lists the input connections; `schemas/` contains the schemas to paste into the form.

## 2. Start with an empty canvas

Enter `comic-classroom` in **New project name**, create it, then select the starter node and press Delete. In **Resources → Import tool and resource library**, choose `library.json`.

Return to Canvas. Open **Workflow settings** and paste `schemas/application-input.json` into Application input. Set the output schema and execution budget from the corresponding files. The application takes one field, `story`. Choose the configured `main` connection as **Application default model**.

## 3. Create the four main nodes

Type a node name, choose its type, then click **Add node**. Use the inspector to choose its resource or tool and add input fields. A field can read an upstream result or hold a fixed value.

| Node | Type | Configure |
| --- | --- | --- |
| `adapt` | Agent | Prompt `adapter`, skill `continuity`, input `story ← input.story`; JSON output from the supplied schema |
| `cast` | Tool | Tool `assets`; characters and style from `adapt` |
| `panels` | Map | Items `nodes.adapt.output.panels`; shared catalog from `cast` and style from `adapt` |
| `pages` | Tool | Tool `layout`; title from `adapt`, panels from `nodes.panels.output.items` |

The writer defines the cast before planning the panels. Keep its output repair enabled with two attempts and a 3,200-token output limit. Its prompt assigns four panels a beginning, a problem, an action and an ending. The continuity skill keeps clothing, props and character IDs consistent across the plan.

## 4. Build one panel, then its review loop

Open the `panels` subflow and delete its starter node. Create:

| Node | Type | Job |
| --- | --- | --- |
| `context` | Code | Select `frame_context`; choose the current panel's character references |
| `takes` | Loop | Up to three attempts; stop when `input.accepted` is true |
| `letter` | Code | Select `panel`; return the image, caption and dialogue |

Open `takes` and create five nodes:

| Node | Type | Configure |
| --- | --- | --- |
| `direct` | Agent | Prompt `frame_director`; receives current context and prior feedback |
| `draw` | Tool | Tool `image`; receives the prompt, references and image options |
| `preview` | Tool | Tool `preview`; reads the generated asset |
| `review` | Agent | Prompt `frame_review`, model `vision`; mark `images` as an image input |
| `remember` | Code | Select `frame_carry`; carry the image and review into the next attempt |

Use `SETTINGS.md` for each field and the nested workflow outputs. Choose a JSON response for the agents, and paste their output schemas from `schemas/`. The reviewer returns `accepted` and specific `feedback`: for example, add the missing older man on the right and show the closed umbrella passing between their hands.

## 5. Connect, save and debug

Drag from the right handle of a node to the left handle of the next:

- Main workflow: **adapt → cast → panels → pages**.
- Each panel: **context → takes → letter**.
- Each attempt: **direct → draw → preview → review → remember**.

Set each subflow's outputs in **Workflow settings**. At the root, return `chapter`, `plan`, `catalog` and `panels` using the supplied field table. Arrange and save.

Select `adapt`, choose **Live model**, enter a short story and choose **Debug selection**. Inspect the cast and four-panel plan before running image generation. Later, **History → Debug with these inputs** lets you rerun one panel with its saved references and feedback.

## 6. Open Python and export

Save, then choose **Python**. The view contains the same nodes, resources and loops you just created. Choose **HTTP service** in the export selector and download the ZIP.

Extract it into a new directory. Copy your configured `deployment.yaml` into that directory and keep the image service running. Copy [comic_app.py](comic_app.py) alongside `serve.py`; it provides the simple story form used in the video. The completed classroom ZIP already includes it.

## 7. Run the independent application

From the extracted application directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps .
export EVOSPRIG_SERVICE_TOKEN="choose-a-local-service-token"
# Also set the model-key variables named in deployment.yaml.
export EVOSPRIG_COMIC_FONT="/path/to/NotoSansCJKsc-Regular.otf"
export EVOSPRIG_IMAGE_ORIGIN="http://127.0.0.1:18880"
python serve.py --profile deployment.yaml --workspace runtime \
  --port 18770 --allow-writes
```

In another terminal, activate the same environment and set the same service token:

```bash
export EVOSPRIG_SERVICE_TOKEN="choose-a-local-service-token"
python comic_app.py --workspace runtime --port 18771
```

Open **http://127.0.0.1:18771/**, enter a story and select **Make a comic**. The application follows image jobs in the background and shows the completed page, PDF and HTML. Use `/?lang=zh` for Chinese.

Submit another story in the same form. The deployed team, tools and model services are reused. Open Studio again when you want to change how the application works.

![A page made by the classroom application](assets/comic-result.jpg)

Give that same application a new story about a rabbit and a fox watering a sunflower:

![A second story made by the same deployed application](assets/comic-reuse.jpg)

**Next:** [change the application in Python](canvas-to-python.md) or [configure self-evolution](improve-an-agent.md). Reference: [canvas authoring](../studio.md), [model connections](../model-connections.md), [export and deployment](../deployment.md).
