# What can evolve?

EvoSprig searches versioned application resources and developer-selected behavior fields. Configure the task set and search space, then choose one of **23 strategies across 21 method families**.

| Component | Search target |
| --- | --- |
| Prompts, procedures and examples | Attached text resources; shared or per-agent |
| Skill libraries | Task-stream discovery, topic/general procedures and bounded skill updates |
| Structured agent harness | Tool rounds, tool selection, parallel reads, output recovery and token limits |
| Model routing | Choices among declared model aliases; sampling parameters |
| Memory and retrieval | Retrieval tool, record count, query input and context budget |
| Workflow topology | Nodes, edges, branches, bounded loops and nested graphs |
| Executable code | Versioned Python resources executed by a declared code tool |

[Configure a harness search](harness-search.md) in Python, CLI or Studio. Candidate versions include both resource and graph diffs, and export with their selected behavior.

## Coverage of the FlashRSI method list

The catalog now includes **SkillOpt, Evo-Harness, AHE, Meta-Harness, RRSI, ADAS, DarwinX, ModularRSI and Arbor**, alongside OPRO, GEPA, EvoPrompt and ACE. The [method policies](harness-search.md#method-policies) describe each native implementation and link its original work.

## Other algorithm integrations

| Method | Evolution target | Integration work |
| --- | --- | --- |
| [TextGrad](https://github.com/zou-group/textgrad) | Multiple textual variables | Computation-graph feedback and variable-level credit assignment |
| [DSPy COPRO](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/copro_optimizer.py) | Per-component instructions | Coordinate search across agent resources |
| [DSPy SIMBA](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/simba.py) | Rules and demonstrations | Stochastic minibatches, trajectory analysis and candidate selection |
| [DSPy MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) | Programs, instructions and demonstrations | Full upstream program adapter and teacher/minibatch controls; native resource search is available |
| [AFlow](https://github.com/geekan/MetaGPT/tree/main/examples/aflow) | Workflow operators and topology | Operator search, valid graph construction and execution budgets |
| [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) | Agent implementation and tools | Isolated code edits, functional tasks and variant archive |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Executable programs | Program search with a verifiable objective |
| [Voyager](https://github.com/MineDojo/Voyager) | Executable skills and curriculum | Skill library, environment interaction and reuse checks |
| [SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | Reusable browser procedures | Browser skill synthesis, verification and retrieval |

These integrations can use the structured candidate space, execution tools and evaluation machinery. [Method requirements](method-requirements.md) maps each direction to its input and environment needs.

## Design a new search space

Beyond instructions, useful targets include model routing, tool descriptions and discovery, memory extraction and forgetting, retrieval queries and ranking, context compaction, decomposition, role assignment, retry policy and executable skills. Measure task quality together with latency, model/tool cost and failure rate. Keep evaluation criteria and deployment permissions under developer control.

To add an optimizer for resources or structured candidates, use the [plugin interface](optimizer-plugins.md).
