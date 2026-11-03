# EvoSprig Toolbox

Run Python, preview web apps and read receipts through ordinary HTTP tools. The [Data Interpreter](../../examples/data-interpreter/), [Software team](../../examples/software-team/) and [Receipt assistant](../../examples/receipt-assistant/) use these same endpoints.

```bash
npm ci --prefix apps/toolbox
cd apps/toolbox
npx playwright install chromium --only-shell
npm start
```

The service listens on `127.0.0.1:18769`. Use `EVOSPRIG_TOOLBOX_PORT` to change it and update your deployment bindings. `EVOSPRIG_TOOLBOX_TOKEN` enables bearer authentication; set the tool binding's `auth_env` to the variable holding that token. `EVOSPRIG_ARTIFACT_DIR` chooses artifact storage. Artifact downloads require the same authentication and expire after one hour.

| POST endpoint | Input | Result |
| --- | --- | --- |
| `/python` | `code`, `files`: filename → text | `ok`, stdout, stderr, generated artifact URLs |
| `/preview` | `html`, `actions`: click/fill/text checks | Page text, errors, per-check results, screenshot URL |
| `/ocr` | `image_base64` | Recognized English text and confidence |

Python runs in Pyodide with the standard library. `from evosprig_plot import bar` provides a small SVG chart helper. Each request starts a fresh virtual filesystem; files must be supplied explicitly. Failed Python execution returns `ok: false` with stderr so an agent can repair its code. Browser checks return failed observations for missing elements or incorrect text. OCR uses Tesseract.js and bundled English language data.

Generated code receives no host filesystem, process environment or network access. Browser routes serve only bundled runtime assets; other requests and WebSockets are blocked. Jobs have time, input, output and concurrency limits. A browser context does not enforce an OS memory quota: deploy this optional service in a resource-limited container/process under an unprivileged account when accepting untrusted workloads. Keep it behind your application or an authenticated proxy rather than exposing it as a public code runner.

You can also bind your own code sandbox, browser automation or OCR backend.

The browser action schema is published in [contracts.json](contracts.json) and reused by the SDK catalog builder. Actions require `kind` and `selector`; `fill` adds `value`, and `text` adds `contains`. Use this schema in your own HTTP binding so invalid requests can be corrected before execution.
