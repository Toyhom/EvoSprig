# What will you build?

Start with a working application pattern, connect your model and tools, then make it your own. Each application uses EvoSprig's SDK, AgentSpec and runtime for its coordination, tool calls, memory and approvals.

<img src="../docs/assets/applications.png" alt="Generated web app, Python chart, receipt input and a written guide" width="100%" />

## Build something useful

| I want an agent that… | Application | What you can customize |
| --- | --- | --- |
| Tailors an application and helps me practice | [Career coach](career-coach/) | Resume facts, job requirements and interview skills |
| Adapts an announcement for several channels | [Content studio](content-studio/) | Source facts, channels, brand voice and editing skills |
| Teaches a topic and reviews my answers | [Study coach](study-coach/) | Course material, learning preferences and feedback |
| Turns an idea into a web app | [Software team](software-team/) | Product roles, acceptance checks, browser tools and design conventions |
| Analyzes files and draws charts | [Data Interpreter](data-interpreter/) | Data files, Python environment, analysis and review |
| Helps make a difficult decision | [Decision room](debate/) | Perspectives, rebuttals and decision criteria |
| Reads receipts and checks expenses | [Receipt assistant](receipt-assistant/) | OCR, arithmetic, expense rules and approval routing |
| Turns a question into a sourced brief | [Research team](research-team/) | Planning, parallel researchers, document collections and editorial review |
| Makes a video from a brief | [Video studio](video-studio/) | Characters, storyboards, image/video providers, shot approval and retakes |
| Turns a meeting into clear next steps | [Meeting assistant](meeting-assistant/) | Decisions, owners, dates and review criteria |
| Writes a consistent multi-chapter guide | [Book studio](book-studio/) | Shared outline, parallel writers, style and editing |
| Builds a trip that fits the budget | [Travel planner](travel-planner/) | Traveler constraints, available activities and cost checks |
| Answers questions about business data | [SQL analyst](data-analyst/) | SQLite databases, CSV imports and business questions |
| Handles an industry business process | [Industry assistant](industry-assistant/) | SOPs, sandbox tools and business-state evaluation |
| Drafts a new evaluation environment | [Environment builder](industry-environment-builder/) | Scenario, schemas, procedures, datasets and reviewed implementation drafts |
| Knows the team handbook | [Chat with your documents](document-chat/) | Handbooks, policies, product notes and citations |
| Helps customers with orders | [Customer support](customer-support/) | Order services, refund policies and human approval |
| Remembers preferences across sessions | [Personal assistant](personal-memory/) | Scoped facts, linked recall and source-aware summaries |

The catalog includes the five application categories highlighted by [MetaGPT](https://github.com/FoundationAgents/MetaGPT), writing/planning patterns from [CrewAI](https://github.com/crewAIInc/crewAI-examples), retrieval and stateful assistant patterns used with [LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents), and [VideoClaw](https://github.com/HITsz-TMG/VideoClaw)-style production. These are EvoSprig implementations of the application patterns. Their guides describe the connected tools and scope.

## Self-evolution in action

<img src="study-coach/assets/evolution.png" alt="Study coach: original output, actual skill edits and selected feedback" width="100%" />

**Study coach:** one Self-Refine round updates two shared skills so exercises and feedback stay tied to the supplied problem. [View the edits and answers](study-coach/).

<img src="book-studio/assets/comparison.png" alt="Book studio: original and evolved chapters on the same task" width="100%" />

**Book studio:** APE search improved the average score from **0.740 to 0.895** on two held-out writing tasks. Read the [prompt changes and output excerpts](book-studio/README.md): the original community-event guide changes budget amounts across chapters; the selected outline emphasizes the constraints and distinct chapter responsibilities.

**Document chat:** textual-gradient search improves the placement of citations and separates rules from different handbook sections. [Read the selected answer](document-chat/).

The comparisons use DeepSeek Flash as task model and judge. Each application page gives its task context and shows the result directly.

Bring your own representative tasks to [LLM-as-judge or a custom evaluator](../docs/evaluation.md), then choose one of the [14 training-free strategies](../docs/evolution.md). The same evaluator checks the original and candidate; you decide whether to adopt the result.

## Start running

Install `python -m pip install -e '.[server]'` and configure a compatible model API. The applications use `DEEPSEEK_API_KEY` by default; [deployment profiles](../docs/deployment.md) let you choose another provider. Software, Python and receipt applications can use the optional [Toolbox](../apps/toolbox/README.md). Video generation uses the media services you connect.

Each application guide includes its run command. For example:

```bash
evosprig run examples/book-studio/agent.yaml \
  --input-file examples/book-studio/sample.json
```

Open the same AgentSpec in Studio to edit it, inspect runs and compare versions. The [catalog builder](build_catalog.py) creates seven of the workflows with the Python SDK.

For a first run without a model connection, try [Hello](hello/). For a local animation renderer, [Motion graphics](motion-graphics/) uses Pillow and FFmpeg.

Adding an application? Follow the [example conventions](../docs/example-guide.md).
