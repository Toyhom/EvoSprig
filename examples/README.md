# Example gallery

Build a complete application, inspect its workflow and replace the model or tools with your own services.

| Example | Pattern | Run |
| --- | --- | --- |
| [Video studio](video-studio/) | VideoClaw-style staged production, parallel shots, approvals and retakes | `python examples/video-studio/run_demo.py --workspace .evosprig/video` |
| [Research team](research-team/) | Researcher, critic and writer collaboration | `python examples/research-team/run_demo.py --workspace .evosprig/team` |
| [Customer support](customer-support/) | Tool lookup, routing, approval and transactional action | `python examples/customer-support/run_demo.py --workspace .evosprig/support --scenario approved` |
| [Personal memory](personal-memory/) | Persistent profile, facts and temporal relationships | `python examples/personal-memory/run_demo.py --workspace .evosprig/memory` |
| [Research assistant](research-assistant/) | Tool-backed answers and instruction optimization | [Evaluation and improvement commands](research-assistant/README.md) |
| [Motion graphics](motion-graphics/) | Storyboard approval and an external CPU render job | [Render an MP4](motion-graphics/README.md) |
| [Hello](hello/) | First Builder/AgentSpec workflow | `evosprig run examples/hello/agent.yaml --mock --input '{"question":"Hello"}'` |

Install `python -m pip install -e '.[server,evolution,mcp]'` first. Demo commands use deterministic model/tool fixtures by default; the research, support and memory demos accept `--live` for the configured model. Video production includes a replaceable media job contract and an offline orchestration simulator. Motion graphics generates an actual MP4 using the optional `media` dependencies.

Every application uses the same runtime as Studio. Open a workflow with:

```bash
evosprig serve --project examples/video-studio/agent.yaml \
  --profile examples/video-studio/deployment.example.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/studio
```

Connect the media service before running the video project in Studio. The offline demo drives the same specification directly with a simulator. Original application code is included here; linked upstream projects identify the workflow patterns being adapted.
