# Build your next agent

Start with an application, connect your model and tools, then make it your own.

| I want to… | Start here | Make it yours |
| --- | --- | --- |
| Ask questions about business data | [Data analyst](data-analyst/) | Connect a SQLite database or import your own CSV |
| Find answers in team documents | [Chat with your documents](document-chat/) | Add handbooks, notes or product documentation |
| Turn a big question into a useful brief | [Research team](research-team/) | Let a planner delegate research and review the final draft |
| Make videos from an idea | [Video studio](video-studio/) | Connect your image and video tools, approve shots and retake a scene |
| Help customers with orders | [Customer support](customer-support/) | Connect order lookup and refund services |
| Remember preferences across sessions | [Personal assistant](personal-memory/) | Save what matters and use it in the next conversation |

All six applications run on EvoSprig's AgentSpec and runtime. Open the same workflow in Studio, edit prompts and tools, or export it as a standalone application.

## Start running

Install `python -m pip install -e '.[server]'` and configure a compatible model API. The examples use `DEEPSEEK_API_KEY` by default; [deployment profiles](../docs/deployment.md) let you choose another provider. Each example has its own data or tool setup instructions.

For a first run without a model connection, try [Hello](hello/):

```bash
evosprig run examples/hello/agent.yaml --mock --input '{"question":"Hello"}'
```

Want a local renderer? [Motion graphics](motion-graphics/) creates a short animation with Pillow and FFmpeg.
