# Roadmap

## Agent capabilities and applications

- Expand application coverage with repository maintenance, web navigation, sales operations and long-running personal assistants.
- Integrate SkillOpt and Evo-Harness skill updates; extend candidate execution for AHE, Meta-Harness, RRSI, DarwinX, ModularRSI and Arbor. See the [method coverage](evolution-components.md#coverage-of-the-flashrsi-method-list).
- Add TextGrad component feedback, full DSPy MIPROv2 program integration, and ADAS/AFlow workflow synthesis behind explicit execution environments.
- Add DGM-style agent-code evolution and AlphaEvolve-style program search with isolated execution, correctness checks and version archives.
- Grow verified procedural skill libraries, following the reusable-skill direction of Voyager and SkillWeaver, without model-weight training.
- Add memory-provider bindings, automatic note linking, consolidation scheduling and conflict-resolution policies.
- Extend video production with temporal visual review, automatic shot revision and more media providers.
- Add richer artifact previews, evaluation forms, collaborative canvas editing and reusable subflow templates.

## Server deployment and portability

- Separate API and worker processes, with queue backpressure and PostgreSQL storage; extend the existing per-provider HTTP pools with deployment-wide admission limits.
- Measure mixed workloads: simultaneous interactive runs, tool jobs, evaluations and improvement studies; tune concurrency against measured bottlenecks.
- Add per-provider admission control, fair scheduling and observability so a self-hosted deployment can use server resources efficiently.
- Support multi-node workers and recovery without coupling an application to Studio.
- Add native TypeScript execution, cross-language contracts and verified container deployment recipes.

Implemented interfaces are listed in the [support matrix](support-matrix.md). The planned search and memory methods operate without model-weight training.
