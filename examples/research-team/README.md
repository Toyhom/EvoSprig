# Research team

![Workflow in EvoSprig Studio](canvas.png)

**Give your agent a question that needs more than one search.**

“What should we address before launching Review Desk?” A planner divides the question into focused tasks. Researchers explore your documents, a writer combines their findings, and you review the final brief.

## A launch question becomes a sourced brief

**“Should we launch the Team plan at $19 per seat?”**

The team reads the launch plan, pricing proposal and customer interviews. Its recommendation:

> Do not launch $19 as a committed public price yet. Run it as a live pricing test inside the June 15 beta, then decide.

The brief connects the decision to the proposed three-seat minimum, the 14-day trial and the need to test willingness to pay. An editor reviews the assembled brief before handoff.

## Try it

After installing EvoSprig and setting `DEEPSEEK_API_KEY`, load the included fictional launch notes:

```bash
evosprig data add-documents examples/research-team/documents \
  --project research-team --workspace .evosprig/research
evosprig serve --project examples/research-team/agent.yaml \
  --workspace .evosprig/research --studio-dir apps/studio/dist
```

Open Studio, run with `{"question":"What should we address before launching Review Desk?"}`, then open History to read and approve the draft. The final review accepts `{"text":"Your approved brief"}`.

You can also start from the CLI with `evosprig run` and complete the review with [`evosprig resume`](../../docs/durable-runtime.md).

## Make it yours

Load your own documents. Edit the planner, researcher and writer prompts. Add a web search HTTP/MCP tool to the researcher's tool list to investigate external sources. The included template researches the document collection you supply.

The framework's `map` node handles the variable task list, bounded parallel work and checkpoints. No separate team scheduler is needed. [Open Deep Research](https://github.com/langchain-ai/open_deep_research) is a useful reference for the broader research-agent application pattern.
