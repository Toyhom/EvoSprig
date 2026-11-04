# Contribute an application

[English](example-guide.md) · [简体中文](zh-CN/example-guide.md) · [Documentation](README.md)

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
  assets/                    # Only images and short media used by the README
  deployment.example.yaml    # Optional model and tool connections
```

Start the README with its title and `![Workflow in EvoSprig Studio](canvas.png)`. Show a useful result on the same page: a result image with a short caption. Follow with how to run the application and what the reader can customize. A builder script is useful when it explains graph construction.

When evolution produces a useful change, show the original output, actual prompt or skill edit, and selected output in one image. Give the method and task context; accompany numeric comparisons with the task count and evaluator. Otherwise, show one final application result. Keep each application page self-contained and concise.

Cite the source of an application pattern and the papers behind named methods. Connect real tool contracts. Test shared capabilities in the framework's test suite.

## An application page must be runnable on its own

Include the required Python/Node versions, checkout and environment commands, dependency installation, exact model profile location, endpoint/model fields and credential environment variables. Provide a valid first input and an executable run command. Document required services, their install/start commands and ports, data loading, write permissions, human responses, output locations and how to resume or stop the application.

Include a canvas entry point and an import/export path for someone who already uses EvoSprig. Link to the framework's main setup for SDK development. Use `examples/quickstart.py` for standard applications: register the spec/profile/data in `quickstarts.json` and include a schema-valid sample input. Setup must preserve user edits. Test the command path and the export/import round trip; do not rely on a generic mock response for structured applications.
