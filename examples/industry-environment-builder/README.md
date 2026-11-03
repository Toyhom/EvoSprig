# Industry environment builder

![The environment construction workflow in EvoSprig Studio](canvas.png)

Build the world your industry agent works in: business records, operating procedures, tools and rules for checking the result. Start from a scenario in finance, government services or manufacturing, then connect the reviewed environment to agent evaluation and self-evolution.

![From a business scenario to an environment and an improving agent](assets/overview.svg)

## From a business brief to a sandbox

> Build a benefits-application workflow. Check the applicant's records, determine eligibility, route exceptions for review and record the final decision.

Seven connected stages develop the environment:

| Stage | What it produces |
| --- | --- |
| Context | Participants, business goals and constraints |
| Schema | Records, fields, relationships and state |
| Procedures | Decision rules, required steps and approval paths |
| Tool graph | Operations and their dependencies |
| Data | Records for exercising the workflow |
| APIs | Tool descriptions, inputs and outputs |
| Implementation | Code drafts for the environment's operations |

Review the package, integrate its implementations and validate the reference cases. The resulting sandbox gives an agent somewhere to act and a concrete way to check its work.

## Build an environment

Point the builder at your IndustryBench synthesis templates:

```bash
evosprig industry synthesis --templates /path/to/industry-agent/synthesis \
  --scene government --out environment-builder
```

Open the generated project in Studio:

```bash
evosprig serve --project environment-builder/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/industry-builder
```

Submit a business brief, inspect each stage and review the complete design. Every stage has an editable prompt; earlier outputs feed the later stages. Available templates cover `loan`, `account`, `credit_cards`, `deposit`, `invest`, `government` and `manufacturing`.

## Put your agent to work

Once the environment's operations and reference cases are validated, prepare an [industry agent](../industry-assistant/):

```bash
export INDUSTRYBENCH_ROOT=/path/to/industry-agent
evosprig industry prepare --industry government --limit 12 --out benefits-agent
```

The agent reads the procedure, discovers relevant tools and acts on business records. Each evaluation starts from a fresh state and checks the recorded outcome. Use those same tasks to improve the agent's instructions with **Improve** or the CLI.

[Build, evaluate and evolve an industry agent](../../docs/industry-environments.md) · [Industry assistant](../industry-assistant/)
