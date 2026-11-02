# Research team

A research-and-writing team follows the role-based collaboration pattern popularized by [CrewAI](https://github.com/crewAIInc/crewAI). It retrieves a shared evidence set, runs analyst and critic branches in parallel, synthesizes a cited report and pauses for editorial review.

```bash
python examples/research-team/run_demo.py --workspace .evosprig/team
# Set DEEPSEEK_API_KEY to use a live model.
python examples/research-team/run_demo.py --workspace .evosprig/team-live --live
```

The default demo uses deterministic role responses and the original documents in `documents/`. `--live` uses the configured model for all three roles. Both modes run the same graph, document tool and human checkpoint; the script accepts the draft automatically for the demo.

Replace the document collection, edit the role prompts, or add a search service through HTTP/MCP. Open `agent.yaml` in Studio to review the report interactively. The critic receives the same citations as the analyst and flags unsupported conclusions before the writer produces the final draft.
