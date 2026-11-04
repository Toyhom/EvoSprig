Connect business operations with their dependencies and preconditions.

The task input contains the requested scenario and outputs from earlier stages. Resolve template placeholders using those fields; retain explicit business constraints.

Map each operating step to a tool. Show read/write dependencies, approvals, retry paths and terminal outcomes. Make mandatory deterministic operations explicit. Define idempotency and version-conflict behavior for writes. Keep tool names and record fields consistent with the earlier stages.