# What will you build?

Start with a working application pattern, connect your model and tools, then make it your own.

<table>
<tr>
<td width="50%" valign="top"><a href="video-studio/"><img src="video-studio/assets/gallery.png" alt="VideoClaw (EvoSprig)" width="100%" /></a><br><b><a href="video-studio/">VideoClaw (EvoSprig)</a></b><br>A story idea becomes a short film.<br><sub>Original: <a href="https://github.com/HITsz-TMG/VideoClaw">VideoClaw</a></sub></td>
<td width="50%" valign="top"><a href="cowork/"><img src="cowork/assets/workspace.png" alt="CoworkOS (EvoSprig)" width="100%" /></a><br><b><a href="cowork/">CoworkOS (EvoSprig)</a></b><br>A team that plans, writes and works with you.<br><sub>Original: <a href="https://github.com/RUC-NLPIR/CoworkOS">CoworkOS</a></sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="rai-manipulation/"><img src="rai-manipulation/assets/sorting.webp" alt="RAI manipulation (EvoSprig)" width="100%" /></a><br><b><a href="rai-manipulation/">RAI manipulation (EvoSprig)</a></b><br>See the scene. Move the objects. Check the result.<br><sub>Original: <a href="https://github.com/RobotecAI/rai">RAI</a></sub></td>
<td width="50%" valign="top"><a href="industry-environment-builder/"><img src="industry-environment-builder/assets/overview.svg" alt="Industry environment builder" width="100%" /></a><br><b><a href="industry-environment-builder/">Industry environment builder</a></b><br>Build a business world for your agent to learn in.<br><sub><a href="../docs/industry-environments.md">Environment guide</a></sub></td>
</tr>
</table>

## Build something useful

| I want an agent that… | Application | What you can customize |
| --- | --- | --- |
| Directs an animated story with dialogue | [Episode Studio](episode-studio/) | Cast, voices, shot continuity, render controls and automatic retakes |
| Repairs a repository and checks the patch | [Super-agent (EvoSprig)](repository-agent/) | Team roles, editable files, executable checks and review |
| Turns a story into a short film | [VideoClaw (EvoSprig)](video-studio/) | Characters, scenes, prompts and editing |
| Works with a team on shared documents | [CoworkOS (EvoSprig)](cowork/) | Specialist roles, project tools and follow-ups |
| Sees a scene and rearranges objects | [RAI manipulation (EvoSprig)](rai-manipulation/) | Visual controller, robot tools and physical goal checks |
| Builds a business sandbox for agent development | [Industry environment builder](industry-environment-builder/) | Scenario, schemas, procedures, tools, data and business checks |
| Tailors an application and helps me practice | [Career coach](career-coach/) | Resume facts, job requirements and interview skills |
| Writes a Xiaohongshu post from my notes | [Xiaohongshu Studio](xiaohongshu-studio/) | Reader, voice, example library, fact checks and revision limits |
| Produces editable office deliverables | [Office deliverables](office-deliverables/) | Source tables, report goals, number checks and file templates |
| Designs and simulates small circuits | [Circuit Lab](circuit-lab/) | Netlists, measurement targets and repair limits |
| Follows up with an overseas buyer | [Trade follow-up](trade-followup/) | Product facts, customer history, language and review |
| Draws a comic chapter | [Comic Studio](comic-studio/) | Story, cast references, panel direction, visual review and page layout |
| Adapts an announcement for several channels | [Content studio](content-studio/) | Source facts, channels, brand voice and editing skills |
| Teaches a topic and reviews my answers | [Study coach](study-coach/) | Course material, learning preferences and feedback |
| Turns an idea into a web app | [Software team](software-team/) | Product roles, acceptance checks, browser tools and design conventions |
| Analyzes files and draws charts | [Data Interpreter](data-interpreter/) | Data files, Python environment, analysis and review |
| Helps make a difficult decision | [Decision room](debate/) | Perspectives, rebuttals and decision criteria |
| Reads receipts and checks expenses | [Receipt assistant](receipt-assistant/) | OCR, arithmetic, expense rules and approval routing |
| Turns a question into a sourced brief | [Research team](research-team/) | Planning, parallel researchers, document collections and editorial review |
| Turns a meeting into clear next steps | [Meeting assistant](meeting-assistant/) | Decisions, owners, dates and review criteria |
| Writes a consistent multi-chapter guide | [Book studio](book-studio/) | Shared outline, parallel writers, style and editing |
| Builds a trip that fits the budget | [Travel planner](travel-planner/) | Traveler constraints, available activities and cost checks |
| Answers questions about business data | [SQL analyst](data-analyst/) | SQLite databases, CSV imports and business questions |
| Handles an industry business process | [Industry assistant](industry-assistant/) | SOPs, sandbox tools and business-state evaluation |
| Knows the team handbook | [Chat with your documents](document-chat/) | Handbooks, policies, product notes and citations |
| Helps customers with orders | [Customer support](customer-support/) | Order services, refund policies and human approval |
| Remembers preferences across sessions | [Personal assistant](personal-memory/) | Scoped facts, linked recall and source-aware summaries |

The catalog includes the five application categories highlighted by [MetaGPT](https://github.com/FoundationAgents/MetaGPT), writing/planning patterns from [CrewAI](https://github.com/crewAIInc/crewAI-examples), retrieval and stateful assistant patterns used with [LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents), [VideoClaw](https://github.com/HITsz-TMG/VideoClaw) production, and [CoworkOS](https://github.com/RUC-NLPIR/CoworkOS) collaboration.

## Self-evolution in action

<img src="study-coach/assets/evolution.png" alt="Study coach: original output, actual skill edits and selected feedback" width="100%" />

**Study coach:** one Self-Refine round updates two shared skills so exercises and feedback stay tied to the supplied problem. [View the edits and answers](study-coach/).

<img src="book-studio/assets/comparison.png" alt="Book studio: original and evolved chapters on the same task" width="100%" />

**Book studio:** APE search improved the average score from **0.740 to 0.895** on two held-out writing tasks. Read the [prompt changes and output excerpts](book-studio/README.md): the original community-event guide changes budget amounts across chapters; the selected outline emphasizes the constraints and distinct chapter responsibilities.

**Document chat:** textual-gradient search improves the placement of citations and separates rules from different handbook sections. [Read the selected answer](document-chat/).

The comparisons use DeepSeek Flash as task model and judge. Each application page gives its task context and shows the result directly.

Bring your own representative tasks to [LLM-as-judge or a custom evaluator](../docs/evaluation.md), then choose one of the [23 training-free strategies](../docs/evolution.md). The same evaluator checks the original and candidate; you decide whether to adopt the result.

## Start running

Every application page includes its installation, model/API configuration, tool services, a first input, and instructions for opening it in Studio. Start with the page of the application you want to use.

Most examples share a small launcher. After the installation shown on their page:

```bash
python examples/quickstart.py book-studio setup
export DEEPSEEK_API_KEY="your-api-key"
python examples/quickstart.py book-studio run
```

`setup` creates an editable profile and input under `.evosprig/examples/<name>` and loads the example's data. `run` and `studio` call EvoSprig's native CLI. `pack --out application.zip` exports the same application for standalone use or import into another Studio. To configure another model at setup, add `--base-url https://your-provider.example/v1 --model your-model --key-env MODEL_API_KEY`; otherwise edit the generated deployment file. Use `--workspace` on every command to select another state directory.

[Episode Studio](episode-studio/) has its own model installer. [Industry assistant](industry-assistant/) runs inside business evaluation sessions. [Hello](hello/) is a small first workflow; [Motion graphics](motion-graphics/) uses a CPU renderer.

Adding an application? Follow the [example conventions](../docs/example-guide.md).
