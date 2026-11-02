# Contributing

维护范围：EvoSprig contributors。Alpha 当前由项目维护者管理运行协议、导出边界、回归测试和发行候选。

使用 Python 3.12+、Node.js 20+；在隔离环境安装 `requirements-dev.lock` 与本包。运行 `ruff check src tests examples scripts`、`pytest -q`，修改 Studio 时增加 `npm --prefix apps/studio run build` 和浏览器测试。

修改公共行为时同步规格、支持矩阵和相关契约测试。运行器需要保留预算、作用域、操作幂等性、租约与恢复语义。不要把凭据、私人对话、业务数据库、模型权重或未授权素材提交到产品树。真实模型测试需要显式配置自己的凭据，离线 CI 使用 mock。

问题报告应附最小规格、期望行为、版本和脱敏错误；安全问题避免在公开记录中附凭据或私人运行数据。依赖升级记录固定版本、许可证和验证范围。贡献按 Apache-2.0 提供。
