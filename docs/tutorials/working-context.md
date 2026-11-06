# Carry working context between turns

[English](working-context.md) · [简体中文](../zh-CN/tutorials/working-context.md)

Build a conversation workflow that keeps important details from earlier turns without sending the entire history to the answering model. It uses two ordinary **Model** nodes: `summarize → answer`. No knowledge library is required.

## 1. Create the workflow

From a checkout with EvoSprig installed:

```bash
python docs/tutorials/working_context.py
```

The [complete code](working_context.py) writes `.evosprig/working-context/agent.yaml`. The application accepts `previous_summary`, `older_messages`, `recent_messages` and `question`. The summarizer returns structured JSON; the answering node receives the summary and unchanged recent messages. The output includes both the answer and the summary for the next request.

## 2. Connect models and open Studio

Create `.evosprig/working-context/deployment.yaml`:

```yaml
models:
  main:
    base_url: https://api.openai.com/v1
    model: your-answer-model
    api_key_env: MODEL_API_KEY
    capabilities: [text, structured_output]
  summary:
    base_url: https://api.openai.com/v1
    model: your-summary-model
    api_key_env: MODEL_API_KEY
    capabilities: [text, structured_output]
```

Replace the URLs and model IDs with your provider or local service. Both bindings may use the same model.

```bash
export MODEL_API_KEY='your-key'
evosprig serve --project .evosprig/working-context/agent.yaml \
  --workspace .evosprig/working-context/workspace \
  --profile .evosprig/working-context/deployment.yaml \
  --studio-dir apps/studio/dist --port 8000
```

On the canvas, open `summarize`. **Design** edits its prompt; **Model binding** selects its model. **Input mappings** connect the older messages and earlier summary. `answer` references `nodes.summarize.output.summary` and the original recent messages. You can build the same graph by adding two ordinary Model nodes and connecting them.

## 3. Run a conversation turn

Paste this into **Run input**, select **Live model**, and run:

```json
{
  "previous_summary": "The user is planning a small team workshop.",
  "older_messages": [
    "User: Keep the total cost below 800 yuan.",
    "Assistant: We could reserve a room on Friday.",
    "User: Change it to Saturday. There are six people."
  ],
  "recent_messages": ["User: One participant needs step-free access."],
  "question": "Which requirements should I give the venue?"
}
```

Inspect `summarize` and `answer` in the run details. The answer should retain Saturday, six people, the budget and the access requirement. Change a constraint and run again to check that your summarizer preserves corrections.

## 4. Reuse after deployment

Export **HTTP service** from Studio. Your application stores `output.summary` in its conversation session, retains recent turns separately and supplies them on the next request. Keep each user's session separate. The exported backend executes the same graph; Studio is not needed for subsequent conversations. See [deployment](../deployment.md) for the service commands and API.

This two-node workflow runs compression each time. In a longer application, use an ordinary **Condition** node to invoke compression only when your configured context threshold is reached, and a **Transform** node to pass through the existing summary otherwise. Keep a recent-turn allowance and reserve space for the answer. Split oversized histories into successive windows before summarizing; the summarizer also has a model context limit.

For agent tool loops, **Node settings → Memory → Configure context policy → Limit tool history** bounds older tool observations without a second model call. It preserves recent rounds and full run records; it is truncation, not semantic summarization. [Agent memory](../memory.md) describes persistent facts, experiences and context blocks.
