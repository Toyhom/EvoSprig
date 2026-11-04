# Research references

[English](references.md) · [简体中文](zh-CN/references.md) · [Documentation](README.md)

Original research behind EvoSprig’s [evolution methods](evolution.md), [memory](memory.md) and [tool use](tools.md).

## Training-free evolution

| Method | Original paper | EvoSprig use |
| --- | --- | --- |
| OPRO | Yang et al. (2023), [Large Language Models as Optimizers](https://arxiv.org/abs/2309.03409) | Score-history prompt proposals |
| GEPA | Agrawal et al. (2025), [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457) | Official reflective optimizer adapter |
| EvoPrompt | Guo et al. (2023), [EvoPrompt: Connecting LLMs with Evolutionary Algorithms Yields Powerful Prompt Optimizers](https://arxiv.org/abs/2309.08532) | Genetic and differential prompt search |
| Self-Refine | Madaan et al. (2023), [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) | Critique/revision of instruction resources |
| ACE | Zhang et al. (2025), [Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618) | Reflector/curator playbook updates |
| APE | Zhou et al. (2022), [Large Language Models Are Human-Level Prompt Engineers](https://arxiv.org/abs/2211.01910) | Instruction induction and neighborhood search |
| ProTeGi | Pryzant et al. (2023), [Automatic Prompt Optimization with “Gradient Descent” and Beam Search](https://arxiv.org/abs/2305.03495) | Textual gradients and beam search |
| Bootstrap demonstrations | Khattab et al. (2023), [DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714) | Passing input/output demonstrations and subset search |
| MIPRO | Opsahl-Ong et al. (2024), [Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs](https://arxiv.org/abs/2406.11695) | Native joint instruction/demo search with passing component traces and categorical TPE |
| PromptBreeder | Fernando et al. (2023), [Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution](https://arxiv.org/abs/2309.16797) | Task/mutation instruction coevolution |
| Reflexion | Shinn et al. (2023), [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | Bounded reflections from failed trajectories |
| ExpeL | Zhao et al. (2023), [ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144) | Rules derived from successful and failed experiences |

| SkillOpt | [SkillOpt](https://arxiv.org/abs/2605.23904) | Bounded anchored edits, strict skill validation and slow guidance |
| Evo-Harness | [Evo-Harness: Context-to-Harness Skill Compilation for Self-Evolving Agents](https://arxiv.org/abs/2608.15071) | Failure-memory compilation and topic/general skill discovery |
| AHE | [Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses](https://arxiv.org/abs/2604.25850) | Diagnosis, edit manifests, measured attribution and rollback |
| Meta-Harness | [Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052) | Implementation/trace archive and score/token frontier |
| RRSI | [RRSI: Regularized Recursive Self-Improvement of Agent Harnesses](https://arxiv.org/abs/2609.24972) | Repeated score/cost admission and regularized revision history |
| ADAS | [Automated Design of Agentic Systems](https://arxiv.org/abs/2408.08435) | Design archive, self-critique and executable candidates |
| DarwinX | [DarwinX: Evolving Agent Harnesses Through Natural Selection](https://arxiv.org/abs/2608.07545) | Branch recombination and repeated preserve-and-extend checks |
| ModularRSI | [ModularRSI: Modular and Generalizable Recursive Harness Self-Improvement](https://arxiv.org/abs/2609.14857) | Independent target-owned branches, contrastive diagnosis and integration |
| Arbor | [RUC-NLPIR/Arbor](https://github.com/RUC-NLPIR/Arbor), hypothesis-tree coordinator and executor | Tree expansion, pruning, trunk experiments and upward insight synthesis |

Implementation policies and settings: [Harness search](harness-search.md#method-policies).

## Memory, retrieval and tool use

| Mechanism | Reference | EvoSprig use |
| --- | --- | --- |
| Relevance, importance and recency | Park et al. (2023), [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | Configurable episodic recall ranking |
| Linked memory notes | Xu et al. (2025), [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110) | Explicit note links and source-aware summaries |
| Editable context blocks | Packer et al. (2023), [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | Scoped context blocks and archival retrieval |
| BM25 | Robertson and Zaragoza (2009), [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019) | Lexical ranking |
| Reciprocal-rank fusion | Cormack, Clarke and Buettcher (2009), [Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods](https://doi.org/10.1145/1571941.1572114) | Multi-query result fusion |
| Diversity-aware retrieval | Carbonell and Goldstein (1998), [The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries](https://doi.org/10.1145/290941.291025) | Lexical similarity penalty during result selection |
| Iterative tool use | Yao et al. (2022), [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | Model/tool observation loop |
| LLM evaluation | Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) | Fixed-rubric task judging with optional repeated ratings |

See [method requirements](method-requirements.md) for application data and feedback contracts.

## Embodied applications

- **RAI** — Rachwał et al., *RAI: Flexible Agent Framework for Embodied AI* (2025). [Paper](https://arxiv.org/abs/2505.07532) · [Code](https://github.com/RobotecAI/rai). The [manipulation application](../examples/rai-manipulation/) recreates the camera–reasoning–tool–feedback loop in EvoSprig.

### Agent runtime design

- [PenguinHarness](https://github.com/Prism-Shadow/penguin-harness): compact tool sets, context management, background sessions and agent workbenches informed the local service and tool-observation work.
