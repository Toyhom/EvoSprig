# Roadmap

## Agent capabilities and applications

- Expand application coverage with repository maintenance, web navigation, sales operations and long-running personal assistants.
- Add TextGrad-style component feedback, MIPRO-style joint instruction/demonstration search, and ADAS/AFlow-style workflow synthesis behind explicit execution environments.
- Grow verified procedural skill libraries, following the reusable-skill direction of Voyager and SkillWeaver, without model-weight training.
- Add memory-provider bindings, automatic note linking, consolidation scheduling and conflict-resolution policies.
- Extend video production with provider integrations, asset continuity and interactive shot editing.
- Add richer artifact previews, evaluation forms, collaborative canvas editing and reusable subflow templates.

## Server deployment and portability

- Separate API and worker processes, with queue backpressure, connection pools and PostgreSQL storage.
- Measure mixed workloads: simultaneous interactive runs, tool jobs, evaluations and improvement studies; tune concurrency against measured bottlenecks.
- Add per-provider admission control, fair scheduling and observability so a self-hosted deployment can use server resources efficiently.
- Support multi-node workers and recovery without coupling an application to Studio.
- Add native TypeScript execution, cross-language contracts and verified container deployment recipes.

Implemented interfaces are listed in the [support matrix](support-matrix.md). These directions extend the application/runtime foundation; no model training is required for the planned inference-time search and memory policies.
