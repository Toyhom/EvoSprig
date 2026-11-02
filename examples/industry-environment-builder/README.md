# Industry environment builder

![Workflow in EvoSprig Studio](canvas.png)

Turn a business scenario into a reviewable environment design: context, schemas, SOPs, tools, data and implementation drafts. A human review closes the workflow before you integrate and validate the environment.

## Try it

Use your IndustryBench synthesis template directory:

```bash
evosprig industry synthesis --templates /path/to/industry-agent/synthesis \
  --scene government --out environment-builder
evosprig run environment-builder/agent.yaml \
  --input '{"brief":"Create a permit workflow with explicit eligibility and review rules"}'
```

Each stage runs as an EvoSprig model node. The command generates the project without calling a model; running the project uses the API you configure. See [environment setup](../../docs/industry-environments.md#draft-a-new-industry-environment) for review, validation and connection to an evolving agent.

## Make it yours

Edit the generated prompts, connect your own domain templates, or tune each node's output limit in Studio. Use the environment's reference and validation tools to freeze business checks after implementing the reviewed design.
