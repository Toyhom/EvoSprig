# Controlled evolution

Improve the prompts and skills your agent uses, without training model weights. Choose editable resources, bring your tasks and evaluator, set a budget, then inspect the resulting versions before release.

EvoSprig offers **13 training-free strategies across 11 method families**. They share the same application runtime, evaluator, candidate archive and release gate. GEPA uses its official library; the other strategies are native resource-level adaptations with the mechanisms below.

## Choose a strategy

| Strategy | What changes | Feedback and data needed | Implementation |
| --- | --- | --- | --- |
| [OPRO](https://arxiv.org/abs/2309.03409) `opro` | Instructions | Task inputs and scalar scores | Score-history proposals |
| [GEPA](https://arxiv.org/abs/2507.19457) `gepa` | Selected prompt components | Scores, execution trajectories and textual feedback | Official `gepa==0.1.4` adapter; Pareto selection, round-robin components, no merge |
| [EvoPrompt GA](https://arxiv.org/abs/2309.08532) `evoprompt_ga` | Prompt population | Inputs and scalar fitness | Tournament parents, crossover, mutation and elitist survival |
| EvoPrompt DE `evoprompt_de` | Prompt population | Inputs and scalar fitness | Distinct donor triples, textual differences and target replacement |
| [Self-Refine](https://arxiv.org/abs/2303.17651) `self_refine` | Instruction resources | Execution feedback and a critic | Critique → revise → evaluate; adapts the paper's output-refinement idea to resources |
| [ACE](https://arxiv.org/abs/2510.04618) `ace` | Experience playbook | Trajectories, scores and failure feedback | Reflector/curator with stable entry IDs and validated add/update/remove deltas |
| [APE](https://arxiv.org/abs/2211.01910) `ape` | Instruction pool | Task examples and scores; references optional | Instruction induction, scored pool and neighborhood sampling |
| [ProTeGi](https://arxiv.org/abs/2305.03495) `protesgi` | Instruction beam | Failure minibatches, feedback and scores | Textual gradients and full-score beam search; does not implement the paper's UCB allocation |
| [Bootstrap few-shot](https://arxiv.org/abs/2310.03714) `bootstrap_fewshot` | Demonstrations appended to resources | Successful search executions accepted by the evaluator | Harvests actual passing input/output pairs; no teacher-model or module-level DSPy optimization |
| Few-shot random search `fewshot_search` | Demonstration subsets and order | The same successful execution pool | Seeded subset/order search with held-out selection |
| [PromptBreeder](https://arxiv.org/abs/2309.16797) `promptbreeder` | Task and mutation instructions | Population fitness and feedback | Coevolves bounded task/mutator populations; a reduced operator set |
| [Reflexion](https://arxiv.org/abs/2303.11366) `reflexion` | Episodic reflections | Failure trajectories and environment/judge feedback | Appends bounded reflections while keeping the base instruction fixed |
| [ExpeL](https://arxiv.org/abs/2308.10144) `expel` | Reusable insight rules | Successful and failed experiences with feedback | Contrasts observations and updates rules citing actual search samples |

GA/DE are one paper family; the two demonstration strategies are another. Native adaptations run on EvoSprig resources rather than reproducing upstream benchmark harnesses. TextGrad/MIPRO-style program optimization and workflow/skill synthesis are separate future integrations, described in the [roadmap](roadmap.md).

For the original papers, see [research references](references.md#training-free-evolution).

For upstream feedback assumptions and upcoming integration contracts, see the [method requirements guide](method-requirements.md).

## What should my evaluation set look like?

The optimizer does not need a special benchmark format for each method. EvoSprig converts your application evaluations into scalar scores, written feedback and execution observations. All strategies can use [LLM-as-judge from task inputs](evaluation.md); objective environment checks remain useful whenever they exist.

| Application | Useful input/reference data | Useful feedback granularity |
| --- | --- | --- |
| Document assistant | Questions, source documents, optional cited reference answers | Answer grounding, citation checks, retrieval records |
| Software team | Feature requests, acceptance criteria, a disposable execution/browser environment | Build/test results, individual tool errors, final application behavior |
| Data Interpreter | Questions and tables/files, optional known aggregates | Numeric checks, executed code, chart artifacts |
| Support or operations | Customer requests, policies, sandbox state, explicit approval decisions | Policy compliance, tool arguments and final environment state |
| Writing or planning | Briefs, audience, constraints and optional examples | Rubric-based completeness, consistency and usability |
| Personal assistant | Task inputs and scoped seed facts; optional multi-step sandbox sessions | Memory updates, preference use and final outcomes |

Demonstration methods need at least one successful search execution. A judge can validate that success when no reference answer exists. Reflection and insight methods become more informative when the environment supplies failure reasons. Population methods need a larger evaluation budget than a short refinement loop.

## From agent to improved version

In Studio, configure a task set, select prompt or skill resources, and choose an algorithm. EvoSprig proposes edits and evaluates the running application automatically. The result view shows resource changes and paired outputs together. Review and enable the version in **Versions**.

Attach reusable skills with `Builder.skill(...)` and `node(..., skills=[...])`. See [agent configuration](agent-resources.md) for the full setup.

## Run an improvement

```bash
evosprig improve my-agent/agent.yaml \
  --suite my-agent/tasks.yaml \
  --method protesgi --resource instructions \
  --rounds 2 --max-candidates 16 \
  --max-evaluations 100 --max-model-calls 200 \
  --profile my-agent/deployment.yaml
```

Install `pip install 'evosprig[evolution]'` for GEPA. Native strategies need no extra optimization dependency. Studio lists the same methods from the backend registry and can create input-only suites, inspect paired application outputs and compare resource diffs.

Each candidate is a content-addressed snapshot. The AgentSpec, tools, permissions, evaluator and partition assignment remain fixed. `search` inputs guide proposals; `selection` ranks candidates; `release` validates the selected version; optional `test` inputs stay sealed until reporting. The baseline remains selected if no candidate improves its selection score.

## Budget, inspect and release

A study caps evaluations, candidates, model calls, tokens and elapsed time. Task, proposer and judge calls all count. Search initially receives 60% of the call/token/time cap; paired release/test evaluations are reserved. Validation may use the remaining balance. Failed calls without usage receipts retain their reservations. Monetary cost is unknown without provider billing data.

Reports retain actual outputs, failure status, tool/environment observations and usage. Candidate archives retain rejected edits and lineage. A study interrupted by a lost lease is not silently replayed; start a new study from an archived candidate. Ordinary agent runs have their own node-level recovery.

The release gate checks paired quality, task-group regressions, successful execution, sample count and inference usage. Review the diff and application outputs, then enable a version manually. Existing runs retain their original versions; rollback preserves current user memory. No search automatically changes the production release.

See [evaluation setup](evaluation.md) for custom scorers, environments and comparison exports, and the [application gallery](../examples/README.md) for concrete results.
