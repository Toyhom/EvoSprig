# Build on the canvas

[English](studio.md) · [简体中文](zh-CN/studio.md) · [Documentation](README.md)

Open an AgentSpec in Studio, edit its nodes, then save and run the same application you use from Python. Studio starts in English and includes Chinese translations.

## Create and configure nodes

Give a new project a name, then add nodes by name and type. The first node on an empty canvas becomes the entry point. **Workflow settings** defines application input, output fields and the execution budget. Drag between node handles to connect execution order.

The inspector separates node design from execution settings. Input fields accept an upstream reference, such as `nodes.writer.output.title`, or a fixed JSON value. Tool and code nodes select from the project's declared tools and code resources. Map nodes select a list and item limit; loop nodes set an attempt limit and an acceptance reference. Expand **Output schema** to define the result format. **Advanced node JSON** exposes the complete configuration.

In **Resources**, import a tool and resource library with format `evosprig.library.v1`. Each resource supplies `path`, `role` and `content`; each tool supplies `plugin` and `version`. Use libraries to reuse prompts, skills and functions while building a new graph. The [comic lesson](tutorials/comic-studio.md) includes a library and a complete walkthrough.

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

Choose **Focus canvas** for more room to inspect a large graph. **Exit focus** or Escape restores the project list and inspector. Opening node debugging also brings the inspector back.

## Try a node or a group

Select a node, several nodes or a collapsed group, then choose **Debug selection**. Fill the input fields or choose **Use outputs from the last run**. Required fields start with their displayed defaults; add optional fields only when you need them. The selected nodes execute with their current prompts and settings, and the panel supplies saved outputs for the surrounding graph.

Inside a map or loop, choose a saved item or take. Studio restores that execution's inputs, including the previous shot's state. You can also select separated nodes: live outputs flow between the selected nodes while intermediate outputs come from the saved run. Repeating a debug run retains the inputs you last used.

Start with a planning node, then try an asset group and a single rendering step. **History** shows each result and any service error. Once those sections work, run the complete application.

**Steps** shows completed work, tool waits and failures, including each map item and loop take. Select a step to see its saved inputs, output and media. **Debug with these inputs** opens that node on the canvas with the same item or take selected. Edit the inputs or prompt, then run the node on its own.

## Tune model behavior

The inspector's **Execution settings** controls a node's output-token limit and structured-output repair policy. An empty token limit inherits the application default. Choose feedback repair for a model that occasionally produces invalid JSON, and set a maximum retry count. Every retry still consumes the shared execution budget.

Studio grouping uses the [React Flow](https://reactflow.dev/learn/layouting/sub-flows) view model and [ELK](https://github.com/kieler/elkjs) layout engine. Execution follows explicit workflow/agent and subgraph distinctions also used in [LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents); deterministic operations use typed tools, comparable to [Dify code nodes](https://docs.dify.ai/en/use-dify/nodes/code).

## Agent configuration

Select an agent to edit its main prompt, attach reusable skills, choose tools and memory access, and set model parameters. **Make prompt evolvable** turns an inline instruction into a resource. The Improve page can optimize either prompts or attached skills and show their changes beside the application outputs. See [agent configuration](agent-resources.md).
