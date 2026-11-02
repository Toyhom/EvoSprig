# Match evaluation data to an improvement method

The same application task can support several optimization methods. What differs is the feedback each method consumes. EvoSprig's [evaluation contract](evaluation.md) supplies scores, written feedback, node outputs, tool receipts and environment observations without requiring a fixed benchmark collection.

## Implemented strategies

| Family / strategies | Typical upstream data and feedback | Supply to EvoSprig |
| --- | --- | --- |
| OPRO | Examples and a scalar objective, often answer accuracy | Task inputs plus references, a scorer or LLM judge |
| GEPA | Training/validation instances; scalar scores and reflection traces | Disjoint tasks, metric and actual runtime observations; optional reference answers |
| EvoPrompt GA / DE | Labeled task examples and population fitness | `expected` values with rules, or an equivalent task-specific scorer |
| Self-Refine | A task, an initial output and natural-language self-critique; labels are not essential | Inputs and a fixed evaluator for the resource-level adaptation |
| ACE | Agent trajectories, execution outcomes and feedback for playbook updates | Environment/judge feedback with tool observations and failure reasons |
| APE | Input/output demonstrations for instruction induction; likelihood or task accuracy for selection | Paired references when available; input-only induction plus judge scoring is the native adaptation |
| ProTeGi | Minibatches of examples, predictions and reference/error feedback | References or concrete judge/environment feedback; textual gradients retain their source tasks |
| Bootstrap few-shot / random search | Training examples, optional teacher traces and a metric that accepts demonstrations | Search tasks with at least one scored successful execution; native variants use input/output demonstrations |
| PromptBreeder | Task examples and fitness for task/mutation-prompt populations | Inputs plus stable scalar scoring, enough budget for population evaluation |
| Reflexion | Interactive task attempts, observations and success/failure signals | Failure trajectories and environment or judge feedback; bounded reflections become versioned resources |
| ExpeL | Successful and failed experiences, often multiple attempts per task | Runtime experiences with a score and reason; rules reference actual search sample IDs |

Replacing a paper's labels or environment reward with an LLM judge changes the evaluation objective. The native strategy remains useful for an application, but its scores are not directly comparable to published benchmark numbers. Final comparisons use the same fixed criterion for both versions.

## Other training-free directions

These are integration targets, not additional implemented algorithms:

| Direction | Required inputs/environment | Why a generic answer-only dataset is insufficient |
| --- | --- | --- |
| [TextGrad](https://github.com/zou-group/textgrad) | Task inputs, a textual loss/evaluator and a graph of editable variables | Feedback must reach the responsible component, not merely a final prompt |
| [MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) | Train/validation tasks, a callable metric, instruction and demonstration candidates | Joint program optimization needs component traces and search allocation |
| [ADAS](https://github.com/ShengranHu/ADAS) | Task data, an execution environment for generated agent code, a task fitness function | Generated architectures require bounded execution and behavioral checks |
| AFlow-style workflow search | Executable workflow operators, task inputs and an evaluation environment | Search changes orchestration, so topology and resource costs must be validated |
| [Voyager](https://github.com/MineDojo/Voyager) | An interactive world, observations, task/curriculum feedback and reusable skills | Skill success depends on environment state and action effects |
| [SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | Browser tasks, page observations, executable skills and verification | A reusable browser procedure needs more than a plausible text response |

Memory policies have a different contract. [Generative Agents](https://github.com/joonspk-research/generative_agents) uses relevance, importance and recency; [A-Mem](https://github.com/agiresearch/A-mem) organizes and links notes; [Mem0](https://github.com/mem0ai/mem0) and [Graphiti](https://github.com/getzep/graphiti) provide memory extraction/update or temporal knowledge mechanisms. Their write paths need events, source metadata and scope; a labeled benchmark is optional for use, but application-specific recall and outcome checks are needed to measure benefit. EvoSprig's native memory policies and their boundaries are listed in the [memory guide](memory.md).

Methods whose essential step updates model weights—such as Toolformer-style tool-use training or policy fine-tuning—are outside this training-free strategy count. A pretrained external model may still be connected as a model, embedder or evaluator.

## Choose the smallest useful contract

- **Writing and decisions:** input, optional context, a rubric and an LLM judge.
- **Retrieval:** questions, a document collection, source-aware observations and grounding checks.
- **Code and data:** task inputs, supplied files, a disposable execution environment and actual assertions.
- **Operations:** initial sandbox state, explicit approval responses, allowed actions and final-state checks.
- **Persistent assistants:** seed memory, session identities and expected state changes; use an SDK environment for multi-turn sessions.

Use `Sample.context` for information available only to the evaluator, `Sample.expected` for references, `responses` for explicit human-node inputs, and deployment bindings for services. The optimizer cannot replace these with its own grading rules.
