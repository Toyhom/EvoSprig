# Chat with your documents

![Workflow in EvoSprig Studio](canvas.png)

**Turn your team's knowledge into an assistant people can ask.**

“How much can I spend on a course?” Add a handbook, meeting notes or product documentation. The assistant searches the collection and answers with source references.

## Try it

After installing EvoSprig and setting `DEEPSEEK_API_KEY`:

```bash
evosprig data add-documents examples/document-chat/documents \
  --project document-chat --workspace .evosprig/docs
evosprig run examples/document-chat/agent.yaml \
  --workspace .evosprig/docs \
  --input '{"question":"Can I use my learning budget for a $250 course?"}'
```

Replace the sample folder with your own `.md` or `.txt` files. Use the same workspace and project ID when loading documents and running the assistant. Local CLI runs share a local identity; an authenticated Studio deployment scopes documents to its users.

## Make it yours

Open `agent.yaml` in Studio and edit `prompts/assistant.md` for your audience. Studio's Memory page can also add documents. Connect another search service through an HTTP or MCP tool when your knowledge lives elsewhere.

```bash
evosprig serve --project examples/document-chat/agent.yaml \
  --workspace .evosprig/docs --studio-dir apps/studio/dist
```

## Take it with you

Export the application with `evosprig export examples/document-chat/agent.yaml --out exported-docs`.
After installing the exported project, load documents using `python app.py --documents ./notes`,
then ask a question with `python app.py --input '{"question":"What is our learning budget?"}'`.
The application uses its own workspace; export does not copy your original document collection.

## Before and after

[Compare outputs and reusable versions](results/README.md) on the same application tasks.
