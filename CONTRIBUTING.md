# Contributing

Welcome! Useful contributions include bug fixes, application examples, model/tool integrations, memory backends and evaluation suites.

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

Describe the problem, resulting behavior and validation in your pull request. For public API changes, update the relevant schema, guide and contract tests. Runtime changes should preserve scope, budgets, idempotency and checkpoint recovery. Examples should include a runnable command, service dependencies and expected outputs.

English is the primary language for code and documentation. Keep `README.zh-CN.md` and Studio's Chinese interface aligned with user-facing changes.

For bug reports, include a minimal specification, expected behavior, version and sanitized error. Report security issues through the channel described in [SECURITY.md](SECURITY.md). Contributions are provided under Apache-2.0.

The optional Toolbox has its own execution checks:

```bash
npm --prefix apps/toolbox ci
cd apps/toolbox
npx playwright install chromium --only-shell
npm test
```
