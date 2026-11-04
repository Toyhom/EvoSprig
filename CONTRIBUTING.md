# Contributing

Welcome! Useful contributions include bug fixes, application examples, model/tool integrations, memory backends and evaluation suites.

Application authors can follow [Build an application](docs/build-applications.md). Algorithm and integration authors can start with [Extend EvoSprig](docs/extend-framework.md) and [Optimizer plugins](docs/optimizer-plugins.md).

## Design and learning experience

**What would PyTorch do?** Start with a useful default and a small runnable example. Let developers add control as their application grows.

- Tutorials lead through a complete task, show the expected result and offer one next change.
- Reference documentation covers public fields, defaults, precedence, lifecycle and extension contracts.
- Keep English and Chinese learning paths aligned. Put configuration details in reference pages and link to them from tutorials.
- A shared application model should work with one setting; per-node and deployment overrides add flexibility when needed.

## Development setup

Use Python 3.12+ and Node.js 20+:

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
npm --prefix apps/studio ci
ruff check src tests examples scripts
pytest -q
npm --prefix apps/studio run build
npm --prefix apps/studio test
```

The test suite uses deterministic fixtures and does not require paid model APIs. Install Playwright Chromium with `npx playwright install chromium --only-shell` from `apps/studio` before browser testing.

## Changes

Describe the problem, resulting behavior and validation in your pull request. For public API changes, update the relevant schema, guide and contract tests. Runtime changes should preserve scope, budgets, idempotency and checkpoint recovery. Examples follow the [application conventions](docs/example-guide.md): start the README with the actual Studio canvas, include a runnable command and service dependencies, and show useful outputs.

English is the primary language for code and documentation. Keep `README.zh-CN.md`, `docs/zh-CN/` and Studio's Chinese interface aligned with user-facing changes.

For bug reports, include a minimal specification, expected behavior, version and sanitized error. Report security issues through the channel described in [SECURITY.md](SECURITY.md). Contributions are provided under Apache-2.0.

The optional Toolbox has its own execution checks:

```bash
npm --prefix apps/toolbox ci
cd apps/toolbox
npx playwright install chromium --only-shell
npm test
```
