# Research references

EvoSprig implements the mechanisms described in the [evolution](evolution.md), [memory](memory.md) and [tools](tools.md) guides. Named methods below credit their original papers. GEPA uses the official library; other evolution strategies adapt their mechanisms to versioned EvoSprig resources. See the implementation column in the evolution guide for the precise scope.

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
| PromptBreeder | Fernando et al. (2023), [Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution](https://arxiv.org/abs/2309.16797) | Task/mutation instruction coevolution |
| Reflexion | Shinn et al. (2023), [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | Bounded reflections from failed trajectories |
| ExpeL | Zhao et al. (2023), [ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144) | Rules derived from successful and failed experiences |

## Memory, retrieval and tool use

| Mechanism | Reference | EvoSprig use |
| --- | --- | --- |
| Relevance, importance and recency | Park et al. (2023), [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | Configurable episodic recall ranking |
| Linked memory notes | Xu et al. (2025), [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110) | Explicit note links and source-aware summaries |
| Editable context blocks | Packer et al. (2023), [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | Scoped context blocks and archival retrieval |
| BM25 | Robertson and Zaragoza (2009), [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019) | Lexical ranking |
| Reciprocal-rank fusion | Cormack, Clarke and Buettcher (2009), [Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods](https://doi.org/10.1145/1571941.1572114) | Multi-query result fusion |
| Diversity-aware retrieval | Carbonell and Goldstein (1998), [The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries](https://doi.org/10.1145/290941.291025) | Lexical similarity penalty during result selection |
| Iterative tool use | Yao et al. (2022), [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | Model/tool observation loop; no hidden-reasoning requirement |
| LLM evaluation | Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) | Fixed-rubric task judging with optional repeated ratings |

The memory policies are native implementations of these ideas, with explicit writes and scope isolation. Agent-level automatic linking, reflection scheduling and full upstream benchmark reproductions are distinct capabilities. The [method requirements](method-requirements.md) guide explains what application data and feedback each family needs.
