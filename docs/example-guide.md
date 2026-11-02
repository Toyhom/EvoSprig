# Contribute an application

Show readers something they can build and use. Coordinate agents through EvoSprig's SDK, AgentSpec and runtime. Add a reusable framework capability when the application needs one.

```text
examples/my-application/
  README.md                  # Canvas, useful result, run command, customization
  canvas.png                 # The application's actual Studio canvas
  studio.json                # Saved layout and visual groups
  agent.yaml                 # Executable workflow
  prompts/                   # Role instructions
  skills/                    # Reusable procedures, when needed
  sample.json                # A task to try
  assets/                    # Only images used by the README
  deployment.example.yaml    # Optional model and tool connections
```

Start the README with its title and `![Workflow in EvoSprig Studio](canvas.png)`. Show a useful result on the same page: a screenshot, short excerpt or compact table. Follow with how to run the application and what the reader can customize. A builder script is useful when it explains graph construction.

When evolution produces a useful change, show the actual prompt or skill edit alongside selected output excerpts. Give the method and task context; accompany numeric comparisons with the task count and evaluator. Otherwise, show one final application result. Keep each application page self-contained and concise.

Cite the source of an application pattern and the papers behind named methods. Connect real tool contracts. Test shared capabilities in the framework's test suite.
