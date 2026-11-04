# Self-evolving agents and controlled RSI

[English](evolution.md) · [简体中文](zh-CN/evolution.md) · [Documentation](README.md)

Automatically improve the prompts and skills your agent uses. Choose editable resources, bring your tasks and evaluator, set a budget, then inspect the resulting versions before release.

The self-improvement loop revises application resources, reruns the same tasks and uses feedback for further candidates. You control which resources can change, the budget and version adoption.

EvoSprig offers **23 training-free strategies across 21 method families**. They share the same application runtime, evaluator, candidate archive and release gate. GEPA uses its official library; the other strategies are native adaptations for resources and application harnesses with the mechanisms below.

## Choose a strategy

| Strategy | What changes | Feedback and data needed | Implementation |
| --- | --- | --- | --- |
| [OPRO](https://arxiv.org/abs/2309.03409) `opro` | Instructions | Task inputs and scalar scores | Score-history proposals |
| [GEPA](https://arxiv.org/abs/2507.19457) `gepa` | Selected prompt components | Scores, execution trajectories and textual feedback | Official `gepa==0.1.4` adapter; Pareto selection and round-robin components |
| [EvoPrompt GA](https://arxiv.org/abs/2309.08532) `evoprompt_ga` | Prompt population | Inputs and scalar fitness | Tournament parents, crossover, mutation and elitist survival |
| EvoPrompt DE `evoprompt_de` | Prompt population | Inputs and scalar fitness | Distinct donor triples, textual differences and target replacement |
| [Self-Refine](https://arxiv.org/abs/2303.17651) `self_refine` | Instruction resources | Execution feedback and a critic | Critique → revise → evaluate; adapts the paper's output-refinement idea to resources |
| [ACE](https://arxiv.org/abs/2510.04618) `ace` | Experience playbook | Trajectories, scores and failure feedback | Reflector/curator with stable entry IDs and validated add/update/remove deltas |
| [APE](https://arxiv.org/abs/2211.01910) `ape` | Instruction pool | Task examples and scores; references optional | Instruction induction, scored pool and neighborhood sampling |
| [ProTeGi](https://arxiv.org/abs/2305.03495) `protesgi` | Instruction beam | Failure minibatches, feedback and scores | Textual gradients and full-score beam search |
| [Bootstrap few-shot](https://arxiv.org/abs/2310.03714) `bootstrap_fewshot` | Demonstrations appended to resources | Successful search executions accepted by the evaluator | Harvests passing input/output pairs from the running application |
| Few-shot random search `fewshot_search` | Demonstration subsets and order | The same successful execution pool | Seeded subset/order search with held-out selection |
| [MIPRO resource search](https://arxiv.org/abs/2406.11695) `mipro` | Instructions and component demonstrations jointly | Tasks, scalar scores and successful component input/output traces | Grounded proposals, trace bootstrapping and categorical TPE over resource choices |
| [PromptBreeder](https://arxiv.org/abs/2309.16797) `promptbreeder` | Task and mutation instructions | Population fitness and feedback | Coevolves bounded task/mutator populations; a reduced operator set |
| [Reflexion](https://arxiv.org/abs/2303.11366) `reflexion` | Episodic reflections | Failure trajectories and environment/judge feedback | Appends bounded reflections while keeping the base instruction fixed |
| [ExpeL](https://arxiv.org/abs/2308.10144) `expel` | Reusable insight rules | Successful and failed experiences with feedback | Contrasts observations and updates rules citing actual search samples |

For **SkillOpt, Evo-Harness, AHE, Meta-Harness, RRSI, ADAS, DarwinX, ModularRSI and Arbor**, see [harness search and method policies](harness-search.md). These methods extend evolution to skills, structured settings, executable code and workflow graphs.

Explore [component coverage and upcoming algorithms](evolution-components.md), or [add your own optimizer](optimizer-plugins.md).

For the original papers, see [research references](references.md#training-free-evolution).

For upstream feedback assumptions and upcoming integration contracts, see the [method requirements guide](method-requirements.md).

## What should my evaluation set look like?

EvoSprig converts your application evaluations into scalar scores, written feedback and execution observations. All strategies can use [LLM-as-judge from task inputs](evaluation.md); objective environment checks remain useful whenever they exist.

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

In Studio, configure a task set, select resources and optional structured fields, and choose an algorithm. EvoSprig proposes edits and evaluates the running application automatically. The result view shows resource changes and paired outputs together. Review and enable the version in **Versions**.

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

Each candidate is a content-addressed snapshot of its resources and AgentSpec. The declared search space controls editable behavior. Deployment permissions, evaluator and task partitions remain fixed. `search` tasks guide proposals; `selection` supplies validation; `release` checks the selected version; optional `test` tasks stay sealed until reporting. Selection follows the chosen method’s policy.

## Joint instruction and demonstration search

```bash
evosprig improve my-agent/agent.yaml --suite tasks.yaml \
  --method mipro --resource instructions --rounds 3 \
  --instruction-candidates 3 --demo-candidates 3 --max-demos 2 \
  --demo-threshold 0.8 --max-candidates 16 --max-evaluations 100
```

MIPRO resource search proposes task-grounded instructions and harvests actual input/output pairs from passing **search-split component executions**. A categorical TPE sampler chooses joint instruction/demo combinations. Shared resources can collect demonstrations from each node that uses them. Demonstrations remain empty when no execution reaches the configured threshold.

This native adaptation uses independent categorical densities and full-split evaluation, with up to four joint trials per round. DSPy MIPROv2 provides a different program representation, richer bootstrapping and minibatch allocation. The candidate archive records selected component traces and instruction choices. Tune the pool sizes, threshold and budgets in the CLI or Studio.

## Budget, inspect and release

A study caps evaluations, candidates, model calls, tokens and elapsed time. Task, proposer and judge calls all count. Search initially receives 60% of the call/token/time cap; paired release/test evaluations are reserved. Validation may use the remaining balance. Calls with usage receipts are charged even when the provider truncates the response; calls without usage retain their reservations. Monetary cost is unknown without provider billing data.

Reports retain actual outputs, failure status, tool/environment observations and usage. Candidate archives retain rejected edits and lineage. After a study loses its lease, start a new study from an archived candidate. Ordinary agent runs have their own node-level recovery.

The release gate checks paired quality, task-group regressions, successful execution, sample count and inference usage. Review the diff and application outputs, then enable a version manually. Existing runs retain their original versions; rollback preserves current user memory.

See [evaluation setup](evaluation.md) for custom scorers, environments and comparison exports, and the [application gallery](../examples/README.md) for concrete results.
