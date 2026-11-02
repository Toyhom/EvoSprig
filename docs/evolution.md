# Evaluate, improve and release

EvoSprig optimizes explicitly selected prompt or skill resources. The original
AgentSpec, tools, permissions, scorer and dataset partitions remain fixed. A candidate
is a new content-addressed resource snapshot with a diff. Running an optimization
never changes the active release.

`EvalSuite` defines four disjoint partitions: search examples for proposals,
selection examples for candidate ranking, release validation for the gate and
optional sealed test examples for reporting. IDs and input hashes must be unique.
The optimization context receives only search and selection. All examples use the
same configured models and tools, with a fresh memory identity per evaluation.
The Alpha harness accepts read-only tools; effectful environments need a separate
sandbox adapter. Installed Python plugins are trusted code, not an OS sandbox.

Scoring is deterministic: exact JSON/string match, text containment or required tool
receipts. Text normalization is explicit. Suites, versions and sample-level reports
are immutable by content. Reports include outputs, failure status, trace, scope,
tokens and tags. A failed execution scores zero. A report is not proof that a small
sample represents a broader task distribution.

## Methods

**OPRO** is an independent lightweight score-history baseline implementing the
history-conditioned proposal idea from [Yang et al.](https://arxiv.org/abs/2309.03409).
It sorts past candidates by search score, asks a model for complete revised resource
texts, evaluates search and selection splits, and retains the best selection score.
Invalid edits are rejected and recorded. This is not the authors' experimental harness.

**GEPA** uses the official [`gepa==0.1.4`](https://github.com/gepa-ai/gepa) library.
The adapter executes EvoSprig versions, returns scores and trajectories, and supplies
structured feedback to the library's reflection mechanism. The official driver
handles Pareto candidate selection, minibatch acceptance and validation. Alpha uses
round-robin component selection, seeded sampling, no merge, and reflection even for
perfect samples so a bounded integration run can exercise the mechanism. The driver
archive retains candidate lineage and per-example fronts. No FlashRSI code is used.

Install optional GEPA with `pip install 'evosprig[evolution]'`. Base execution and
exported applications do not need an optimization library.

## Budgets and recovery

A study has explicit caps for sample evaluations, candidate count, model calls,
tokens and elapsed time. Search initially receives 60% of the call/token/time cap;
evaluation slots are reserved for paired release/test runs. Validation can use the
unused balance. Reflection and task calls both count. Failed calls without a usage
receipt keep their reservations. Currency cost stays unknown unless billing evidence
is available.

Study workers persist usage reservations, candidate creation, sample reports and
method checkpoints. A lost study lease marks the job `interrupted`, retains evidence,
and does not silently replay a potentially paid search. Start a new study from an
archived candidate when appropriate. GEPA's JSON result is stored; untrusted pickle
checkpoints are never loaded. Ordinary agent runs retain their separate durable
node-level resume semantics.

## Manual release

Compare the candidate diff, paired scores, regressions by task tag and inference
usage. The release gate checks minimum gain, sample count, maximum regression,
mean token use and successful executions. The API's manual publish action uses
both the expected release revision and baseline version. Two competing releases
cannot overwrite each other. Existing runs retain their original frozen versions.
Rollback only targets a compatible previously released version; current user memory
is preserved. Application export can select any archived compatible version.

The [research assistant](../examples/research-assistant/README.md) includes reproducible
CLI commands, two real method runs and a manual baseline, including its no-gain test
result. Studio's Improve and Versions pages expose the same service operations.
