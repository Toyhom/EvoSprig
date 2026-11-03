# What can evolve?

EvoSprig currently searches **versioned text resources attached to model/agent nodes**. A study proposes changes, executes the application and selects a candidate using your evaluation tasks.

| Component | Current support | Useful evaluation |
| --- | --- | --- |
| System/task prompts | Automatic search | Output quality and task completion |
| Textual skills and procedures | Automatic search; shared across nodes | Multi-step task outcomes and constraints |
| Few-shot examples | Bootstrap, subset/order search and joint instruction/demo search | Passing executions and generalization tasks |
| Experience playbooks and reflection notes | ACE, Reflexion and ExpeL resource updates | Trajectories, failure reasons and success signals |
| Tool-use, retrieval and collaboration instructions | Automatic search when stored as attached resources | Tool receipts, retrieved sources and team outputs |
| Model, sampling settings and context limits | Developer configuration | Quality, latency and cost |
| Tool allowlists, schemas and implementations | Developer configuration | Action correctness and service outcomes |
| Memory store and retrieval parameters | Developer configuration; runtime memory writes and summaries | Recall, freshness and cross-session success |
| Graph topology, routing, loops and agent roles | Developer configuration | Whole-workflow correctness and resource use |
| Executable skills and application code | Developer implementation | Sandbox execution and functional tests |

**Harness** includes orchestration, tools, state, context construction, budgets and recovery. Today its instruction resources can evolve; structural harness search is a development direction. Runtime memory accumulation and autonomous prompt evolution are separate operations.

## Coverage of the FlashRSI method list

EvoSprig includes OPRO, GEPA, EvoPrompt GA/DE and ACE from the [FlashRSI catalog](https://github.com/RUC-NLPIR/FlashRSI/blob/main/docs/integrations/algorithms.md). The following nine methods are pending integration:

| Method | Target and search mechanism | Required extension |
| --- | --- | --- |
| [SkillOpt](https://arxiv.org/abs/2605.23904) | Skills with fast/slow updates | Separate update schedules, skill snapshots and validation-based adoption |
| [Evo-Harness](https://arxiv.org/abs/2608.15071) | Skills accumulated over a task stream | Native skill discovery and persistent task-stream feedback |
| [AHE](https://arxiv.org/abs/2604.25850) | Successive harness edits | Diagnosed file edits, executable candidates and edit validation |
| [Meta-Harness](https://arxiv.org/abs/2603.28052) | Harness search using historical code, scores and traces | File-based candidate history and editable harness checkouts |
| [RRSI](https://arxiv.org/abs/2609.24972) | History-guided harness revisions | Score/cost admission and implementation-level candidate execution |
| [ADAS](https://arxiv.org/abs/2408.08435) | Agent designs selected from an archive | Executable graph/code candidates and environment tests |
| [DarwinX](https://arxiv.org/abs/2608.07545) | Branch evolution and recombination | Branch archive, merges and repeated outcome checks |
| [ModularRSI](https://arxiv.org/abs/2609.14857) | Module-specific branches and integration | Explicit module ownership, branch integration and joint evaluation |
| [Arbor](https://github.com/RUC-NLPIR/Arbor) | Hypothesis trees and upward insight synthesis | Hypothesis coordinator, candidate executor and tree-linked experiment history |

Text resource optimizers can use the [plugin interface](optimizer-plugins.md) today. Harness/code methods additionally need versioned executable candidates and an isolated execution environment.

## Other algorithm integrations

| Method | Evolution target | Integration work |
| --- | --- | --- |
| [TextGrad](https://github.com/zou-group/textgrad) | Multiple textual variables | Computation-graph feedback and variable-level credit assignment |
| [DSPy COPRO](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/copro_optimizer.py) | Per-component instructions | Coordinate search across agent resources |
| [DSPy SIMBA](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/simba.py) | Rules and demonstrations | Stochastic minibatches, trajectory analysis and candidate selection |
| [DSPy MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) | Programs, instructions and demonstrations | Full upstream program adapter and teacher/minibatch controls; native resource search is available |
| [ADAS](https://github.com/ShengranHu/ADAS) | Agent architectures | Executable candidate graphs/code and environment evaluation |
| [AFlow](https://github.com/geekan/MetaGPT/tree/main/examples/aflow) | Workflow operators and topology | Operator search, valid graph construction and execution budgets |
| [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) | Agent implementation and tools | Isolated code edits, functional tasks and variant archive |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Executable programs | Program search with a verifiable objective |
| [Voyager](https://github.com/MineDojo/Voyager) | Executable skills and curriculum | Skill library, environment interaction and reuse checks |
| [SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | Reusable browser procedures | Browser skill synthesis, verification and retrieval |

These integrations build on the current evaluator and version machinery. Structural/code candidates additionally need a versioned configuration space, isolated execution and validation of tool authority. [Method requirements](method-requirements.md) maps each direction to its input and environment needs.

## Design a new search space

Beyond instructions, useful targets include model routing, tool descriptions and discovery, memory extraction and forgetting, retrieval queries and ranking, context compaction, decomposition, role assignment, retry policy and executable skills. Measure task quality together with latency, model/tool cost and failure rate. Keep evaluation criteria and deployment permissions under developer control.

To contribute a resource optimizer today, use the [plugin interface](optimizer-plugins.md).
