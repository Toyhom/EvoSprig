# Security

Report vulnerabilities privately through [GitHub private vulnerability reporting](https://github.com/Toyhom/EvoSprig/security/advisories/new). Include the affected version, a minimal reproduction and the expected permission boundary. Do not include live credentials, private conversations or production data.

The current Alpha supports a local loopback control plane, explicit tool permissions, scoped storage and separately configured model credentials. Its supported deployment is a trusted host; it does not provide an operating-system sandbox for arbitrary user code. See [deployment](docs/deployment.md) and the [support matrix](docs/support-matrix.md).

Only the latest Alpha source is maintained. Fixes and relevant upgrade instructions are published in the changelog. Contributors should use synthetic data and mock model calls in reproductions and CI.
