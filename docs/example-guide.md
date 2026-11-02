# Contribute an application example

An example should help someone build their own application. Implement orchestration with EvoSprig's Builder, AgentSpec and runtime; reuse its tools, memory, approvals and evaluation interfaces. Add a shared framework capability when the application exposes a missing one.

Use this folder structure:

```text
examples/my-application/
  README.md                  # Canvas image, purpose, setup, run, customization
  studio.json                # Optional saved layout and visual groups
  canvas.png                 # Screenshot of this application's actual Studio graph
  agent.yaml                 # Executable workflow
  build_agent.py             # Optional SDK construction
  prompts/                   # Editable instructions and skills
  sample.json                # A useful task
  deployment.example.yaml    # Optional services; credentials by environment name
  results/                   # Selected application outputs and useful screenshots
```

Begin the README with the title, then `![Workflow in EvoSprig Studio](canvas.png)`. Follow with a short description, a run command and concrete customization points. For large applications, show the grouped overview first and include subflow screenshots below it.

Use real tool contracts and actual output artifacts. Describe provider requirements clearly. Cite the upstream application pattern and papers behind any named method. Keep testing instructions in the contributor guide and tests in the test suite.

An evolution comparison includes the same task inputs, actual original/evolved outputs, reusable prompt snapshots, method, model, evaluator and sample count. Distinguish measured outcomes from general claims about a method.
