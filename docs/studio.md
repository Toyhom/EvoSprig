# Build on the canvas

Open an AgentSpec in Studio, edit its nodes, then save and run the same application you use from Python. Studio starts in English and includes Chinese translations.

## Choose the right node

| Node | Use it for | Appearance |
| --- | --- | --- |
| Agent | A model chooses tools and iterates toward a task | Agent card with its tool set |
| Model | One model step, such as drafting or classification | Compact inference card |
| Tool | An operation that must run: OCR, SQL, Python, HTTP | Task card with a capability icon |
| Transform / join | Mapping values and bringing branches together | Small utility node |
| Condition | A deterministic predicate | Branch card with true/false ports |
| Human | Reviewing or supplying an explicit response | Approval card |
| Loop / map / parallel | Repeated work, batches or multiple teams | Subflow card with entry buttons |

The same typed tool can be used in a deterministic tool node or offered to an agent. Keep business operations in tools and orchestration in graph nodes. See [custom tools](tools.md) for Python, HTTP and MCP contracts.

## Organize a large application

**Shift-select nodes → Group** creates a visual group. Rename it in the inspector, collapse it to a summary, or expand it to inspect individual nodes. Select groups at the same level to create another enclosing group. Ungrouping preserves the nodes and connections. Collapsed connections summarize links across group boundaries; expand the group to edit individual connections.

Visual groups do not add execution steps or change the behavior version. They are saved with the project's canvas metadata. Example projects can include a `studio.json` sidecar; `evosprig serve --project` loads it when first creating the project. Existing workspace edits are preserved. **Arrange** uses a layered layout with nested group boundaries. Expanded groups default to vertical layout; choose horizontal or vertical in the group inspector, then arrange. Drag a collapsed group to move its contents together.

Loop, map and parallel cards open real executable subgraphs. Use the breadcrumbs to return to an outer graph. Edits, pending node JSON and positions are preserved when navigating and saving. These subgraphs share the application's declared models, tools and prompt resources.

## Tune model behavior

The inspector's **Execution settings** controls a node's output-token limit and structured-output repair policy. An empty token limit inherits the application default. Choose feedback repair for a model that occasionally produces invalid JSON, and set a maximum retry count. Every retry still consumes the shared execution budget.

Studio grouping uses the [React Flow](https://reactflow.dev/learn/layouting/sub-flows) view model and [ELK](https://github.com/kieler/elkjs) layout engine. Execution follows explicit workflow/agent and subgraph distinctions also used in [LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents); deterministic operations use typed tools, comparable to [Dify code nodes](https://docs.dify.ai/en/use-dify/nodes/code).
