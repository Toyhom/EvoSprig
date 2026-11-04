Specify callable tools, argument schemas and expected results.

The task input contains the requested scenario and outputs from earlier stages. Resolve template placeholders using those fields; retain explicit business constraints.

Specify each tool name, purpose, JSON input/output schema, permissions and errors. Describe idempotency keys and optimistic revisions. Keep JSON schemas unambiguous, with required fields and bounded arrays. Include a schema-discovery operation so the agent can load only tools relevant to its task.